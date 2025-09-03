import os
import json
import asyncio
import shutil
import random
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, AuthKeyError,
    FloodWaitError, PhoneNumberBannedError,
    UserDeactivatedError, AuthKeyUnregisteredError
)
from telethon.tl.functions.messages import ReportSpamRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.types import InputPeerUser

# Конфигурационные параметры
CONFIG_FILE = "config.json"
SESSION_FOLDER = "sessions"
BAD_SESSIONS_FOLDER = "нерабочие_сессии"
PROXY_FOLDER = "proxies"
SPAMBOT_USERNAME = "spambot"


# Загрузка конфигурации
def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "api_id": "",
            "api_hash": "",
            "proxy_type": "socks5",
            "check_interval": 3600  # Интервал проверки в секундах
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# Загрузка прокси (аналогично вашему скрипту рассылки)
def load_proxies():
    if not os.path.exists(PROXY_FOLDER):
        return []

    proxies = []
    for fname in os.listdir(PROXY_FOLDER):
        path = os.path.join(PROXY_FOLDER, fname)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue

                if "://" in s:
                    proxy_parts = s.split("://")
                    proxy_type = proxy_parts[0].lower()
                    auth_host = proxy_parts[1]

                    if "@" in auth_host:
                        auth, host_port = auth_host.split("@")
                        user, pwd = auth.split(":") if ":" in auth else (auth, "")
                    else:
                        host_port = auth_host
                        user, pwd = None, None

                    host, port = host_port.split(":")
                    port = int(port)
                    proxies.append((proxy_type, host, port, user, pwd))
                else:
                    parts = s.split(":")
                    try:
                        if len(parts) >= 2:
                            host = parts[0]
                            port = int(parts[1])
                            user = parts[2] if len(parts) > 2 else None
                            pwd = parts[3] if len(parts) > 3 else None
                            proxies.append(("socks5", host, port, user, pwd))
                    except Exception as e:
                        print(f"[!] Неверный формат прокси: {s} - {e}")
    return proxies


# Создание прокси-кортежа
def create_proxy_tuple(proxy_info, proxy_type):
    proxy_type, host, port, user, pwd = proxy_info
    telethon_proxy_type = {
        "socks5": "socks5",
        "socks4": "socks4",
        "http": "http",
        "https": "http",
        "mtproto": "mtproto"
    }.get(proxy_type.lower(), "socks5")

    if user and pwd:
        return (telethon_proxy_type, host, port, True, user, pwd)
    else:
        return (telethon_proxy_type, host, port, True)


# Проверка наличия спамблока через @SpamBot
async def check_spambot_ban(client):
    try:
        # Пытаемся получить информацию о SpamBot
        spam_bot = await client.get_entity(SPAMBOT_USERNAME)

        # Отправляем сообщение для проверки блокировки
        await client.send_message(spam_bot, "/start")

        # Ждем ответа
        await asyncio.sleep(2)

        # Получаем последние сообщения от SpamBot
        messages = await client.get_messages(spam_bot, limit=5)

        for message in messages:
            if message.text and any(keyword in message.text.lower() for keyword in
                                    ['ban', 'block', 'ограничен', 'заблокирован', 'spam']):
                return True

        return False

    except Exception as e:
        print(f"[!] Ошибка проверки SpamBot: {e}")
        return False


# Удаление последнего сообщения от Telegram (аналогично вашему скрипту)
async def delete_last_message_by_phone(client, phone_number):
    try:
        if phone_number in ['42777', '777000']:
            dialogs = await client.get_dialogs()

            for dialog in dialogs:
                try:
                    entity = dialog.entity
                    if (hasattr(entity, 'id') and
                            ((entity.id == 777000) or (hasattr(entity, 'phone') and str(entity.phone) == '42777'))):
                        messages = await client.get_messages(entity, limit=10)
                        for message in messages:
                            if message.sender_id == entity.id:
                                await message.delete()
                                return True
                except Exception:
                    continue
        else:
            entity = await client.get_entity(phone_number)
            messages = await client.get_messages(entity, limit=10)

            for message in messages:
                if message.sender_id == entity.id:
                    await message.delete()
                    return True

        return False

    except Exception as e:
        print(f"❌ Ошибка удаления сообщения: {e}")
        return False


# Удаление переписки со спамблоком
async def cleanup_spambot_chat(client):
    try:
        spam_bot = await client.get_entity(SPAMBOT_USERNAME)

        # Пытаемся удалить историю
        try:
            await client(DeleteHistoryRequest(
                peer=spam_bot,
                max_id=0,
                just_clear=True
            ))
        except Exception:
            # Если не получается очистить историю, просто удаляем сообщения
            messages = await client.get_messages(spam_bot, limit=50)
            for message in messages:
                try:
                    await message.delete()
                except Exception:
                    continue

        # Пытаемся заблокировать и разблокировать для сброса
        try:
            await client(BlockRequest(id=InputPeerUser(spam_bot.id, spam_bot.access_hash)))
            await asyncio.sleep(1)
            await client(UnblockRequest(id=InputPeerUser(spam_bot.id, spam_bot.access_hash)))
        except Exception:
            pass

        return True

    except Exception as e:
        print(f"[!] Ошибка очистки SpamBot: {e}")
        return False


# Основная функция проверки сессии
async def check_session(session_path, api_id, api_hash, proxy_info=None, proxy_type="socks5"):
    session_name = os.path.splitext(os.path.basename(session_path))[0]
    client = None
    status = {
        'session_name': session_name,
        'working': False,
        'spam_blocked': False,
        'error': None,
        'phone': None
    }

    try:
        # Создаем клиент с прокси или без
        if proxy_info:
            proxy_tuple = create_proxy_tuple(proxy_info, proxy_type)
            client = TelegramClient(session_path, int(api_id), api_hash, proxy=proxy_tuple)
        else:
            client = TelegramClient(session_path, int(api_id), api_hash)

        await client.connect()

        # Проверяем авторизацию
        if not await client.is_user_authorized():
            status['error'] = "Не авторизован"
            return status

        # Получаем информацию об аккаунте
        me = await client.get_me()
        status['phone'] = me.phone

        # Проверяем спамблок
        status['spam_blocked'] = await check_spambot_ban(client)

        # Если есть спамблок, пытаемся очистить переписку
        if status['spam_blocked']:
            await cleanup_spambot_chat(client)

        # Удаляем последнее сообщение от Telegram (если настроено)
        cfg = load_config()
        target_phone = cfg.get("tg_phone", "").strip()
        if target_phone:
            await delete_last_message_by_phone(client, target_phone)

        status['working'] = True

    except (AuthKeyError, AuthKeyUnregisteredError, UserDeactivatedError):
        status['error'] = "Сессия недействительна (пользователь восстановил аккаунт)"
    except PhoneNumberBannedError:
        status['error'] = "Номер забанен"
    except FloodWaitError as e:
        status['error'] = f"Flood wait: {e.seconds} секунд"
    except SessionPasswordNeededError:
        status['error'] = "Требуется двухфакторная аутентификация"
    except Exception as e:
        status['error'] = f"Ошибка: {str(e)}"
    finally:
        if client:
            await client.disconnect()

    return status


# Перемещение нерабочих сессий
def move_bad_session(session_file, reason):
    if not os.path.exists(BAD_SESSIONS_FOLDER):
        os.makedirs(BAD_SESSIONS_FOLDER)

    try:
        # Создаем подпапку по причине
        reason_folder = os.path.join(BAD_SESSIONS_FOLDER, reason.replace(" ", "_"))
        if not os.path.exists(reason_folder):
            os.makedirs(reason_folder)

        # Перемещаем файл сессии
        dest_path = os.path.join(reason_folder, os.path.basename(session_file))
        shutil.move(session_file, dest_path)

        # Также перемещаем связанные файлы (если есть)
        base_name = os.path.splitext(session_file)[0]
        for ext in ['.session', '.session-journal']:
            related_file = base_name + ext
            if os.path.exists(related_file):
                dest_related = os.path.join(reason_folder, os.path.basename(related_file))
                shutil.move(related_file, dest_related)

        return True
    except Exception as e:
        print(f"[!] Ошибка перемещения сессии {session_file}: {e}")
        return False


# Основная функция
async def main():
    cfg = load_config()
    proxies = load_proxies()

    # Создаем папки если их нет
    if not os.path.exists(SESSION_FOLDER):
        os.makedirs(SESSION_FOLDER)
        print(f"[!] Папка {SESSION_FOLDER} создана, но сессий нет")
        return

    # Получаем список сессий
    session_files = []
    for f in os.listdir(SESSION_FOLDER):
        if f.endswith('.session'):
            session_files.append(os.path.join(SESSION_FOLDER, f))

    if not session_files:
        print("[!] Нет файлов сессий для проверки")
        return

    print(f"[+] Найдено {len(session_files)} сессий для проверки")

    # Распределяем прокси по сессиям
    proxy_assignment = []
    if proxies:
        for i, session_file in enumerate(session_files):
            proxy_idx = i % len(proxies)
            proxy_assignment.append(proxies[proxy_idx])
    else:
        proxy_assignment = [None] * len(session_files)

    # Проверяем каждую сессию
    results = []
    for i, (session_file, proxy_info) in enumerate(zip(session_files, proxy_assignment)):
        print(f"\n[{i + 1}/{len(session_files)}] Проверяю {os.path.basename(session_file)}...")

        result = await check_session(
            session_file,
            cfg["api_id"],
            cfg["api_hash"],
            proxy_info,
            cfg.get("proxy_type", "socks5")
        )

        results.append(result)

        # Выводим результат
        if result['working']:
            status_msg = "✅ РАБОЧАЯ"
            if result['spam_blocked']:
                status_msg += " (⚠️ СПАМБЛОК)"
            print(f"   {status_msg} - {result['phone']}")
        else:
            print(f"   ❌ НЕРАБОЧАЯ - {result['error']}")

        # Небольшая задержка между проверками
        if i < len(session_files) - 1:
            await asyncio.sleep(random.uniform(1, 3))

    # Анализируем результаты
    working_sessions = [r for r in results if r['working']]
    non_working_sessions = [r for r in results if not r['working']]
    spam_blocked_sessions = [r for r in results if r['spam_blocked']]

    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ СЕССИЙ")
    print("=" * 60)
    print(f"✅ Рабочих сессий: {len(working_sessions)}")
    print(f"❌ Нерабочих сессий: {len(non_working_sessions)}")
    print(f"⚠️  С спамблоком: {len(spam_blocked_sessions)}")
    print("=" * 60)

    # Перемещаем нерабочие сессии
    moved_count = 0
    for result in non_working_sessions:
        session_file = os.path.join(SESSION_FOLDER, result['session_name'] + '.session')
        if os.path.exists(session_file):
            if move_bad_session(session_file, result['error'] or "unknown_error"):
                moved_count += 1

    print(f"\n📦 Перемещено нерабочих сессий: {moved_count}/{len(non_working_sessions)}")

    # Сохраняем детальный отчет
    report_file = "session_check_report.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("ОТЧЕТ ПРОВЕРКИ СЕССИЙ\n")
        f.write("=" * 50 + "\n\n")

        f.write("РАБОЧИЕ СЕССИИ:\n")
        for result in working_sessions:
            status = " (СПАМБЛОК)" if result['spam_blocked'] else ""
            f.write(f"- {result['session_name']} ({result['phone']}){status}\n")

        f.write("\nНЕРАБОЧИЕ СЕССИИ:\n")
        for result in non_working_sessions:
            f.write(f"- {result['session_name']}: {result['error']}\n")

    print(f"📝 Детальный отчет сохранен в {report_file}")


# Функция для периодической проверки
async def periodic_check():
    cfg = load_config()
    check_interval = cfg.get("check_interval", 3600)

    while True:
        print(f"\n⏰ Запускаю периодическую проверку сессий...")
        await main()
        print(f"\n💤 Следующая проверка через {check_interval // 3600} часов")
        await asyncio.sleep(check_interval)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Проверка сессий Telegram на работоспособность")
    parser.add_argument("--once", action="store_true", help="Выполнить проверку один раз")
    parser.add_argument("--daemon", action="store_true", help="Запустить в режиме демона с периодической проверкой")

    args = parser.parse_args()

    if args.daemon:
        print("🚀 Запуск в режиме демона с периодической проверкой")
        asyncio.run(periodic_check())
    else:
        print("🔍 Запуск единоразовой проверки сессий")
        asyncio.run(main())