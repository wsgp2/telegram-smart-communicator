#!/usr/bin/env python3
"""
📡 MASS SESSION CHECKER - асинхронная проверка Telegram сессий
- Массовая проверка сотен сессий
- Асинхронный пул для ускорения
- Совместимость с ChatManager и AutoResponder
- Проверка спамблока, очистка переписки
- Отчеты в JSON и TXT
"""

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
from telethon.tl.functions.messages import ReportSpamRequest, DeleteHistoryRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.types import InputPeerUser

# Конфигурация
CONFIG_FILE = "config.json"
SESSION_FOLDER = "sessions"
BAD_SESSIONS_FOLDER = "нерабочие_сессии"
PROXY_FOLDER = "proxies"
SPAMBOT_USERNAME = "spambot"
MAX_CONCURRENT = 20  # Максимум одновременно проверяемых сессий

# ------------------ Загрузка конфигурации ------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "api_id": "",
            "api_hash": "",
            "proxy_type": "socks5",
            "check_interval": 3600,
            "tg_phone": ""
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------ Загрузка прокси ------------------
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
                # SOCKS/HTTP/MTProto поддержка
                if "://" in s:
                    proxy_type, auth_host = s.split("://")
                    if "@" in auth_host:
                        auth, host_port = auth_host.split("@")
                        user, pwd = auth.split(":") if ":" in auth else (auth, "")
                    else:
                        host_port = auth_host
                        user, pwd = None, None
                    host, port = host_port.split(":")
                    port = int(port)
                    proxies.append((proxy_type.lower(), host, port, user, pwd))
                else:
                    parts = s.split(":")
                    if len(parts) >= 2:
                        host = parts[0]
                        port = int(parts[1])
                        user = parts[2] if len(parts) > 2 else None
                        pwd = parts[3] if len(parts) > 3 else None
                        proxies.append(("socks5", host, port, user, pwd))
    return proxies


def create_proxy_tuple(proxy_info):
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


# ------------------ SpamBot check ------------------
async def check_spambot_ban(client):
    try:
        spam_bot = await client.get_entity(SPAMBOT_USERNAME)
        await client.send_message(spam_bot, "/start")
        await asyncio.sleep(1)
        messages = await client.get_messages(spam_bot, limit=5)
        for msg in messages:
            if msg.text and any(k in msg.text.lower() for k in ['ban','block','ограничен','заблокирован','spam']):
                return True
        return False
    except:
        return False


async def cleanup_spambot_chat(client):
    try:
        spam_bot = await client.get_entity(SPAMBOT_USERNAME)
        try:
            await client(DeleteHistoryRequest(peer=spam_bot, max_id=0, just_clear=True))
        except:
            msgs = await client.get_messages(spam_bot, limit=50)
            for m in msgs:
                try: await m.delete()
                except: continue
        try:
            await client(BlockRequest(id=InputPeerUser(spam_bot.id, spam_bot.access_hash)))
            await asyncio.sleep(1)
            await client(UnblockRequest(id=InputPeerUser(spam_bot.id, spam_bot.access_hash)))
        except: pass
        return True
    except: return False


# ------------------ Проверка сессии ------------------
async def check_session(session_path, api_id, api_hash, proxy_info=None):
    session_name = os.path.splitext(os.path.basename(session_path))[0]
    client = None
    status = {'session_name': session_name, 'working': False, 'spam_blocked': False, 'error': None, 'phone': None}

    try:
        client = TelegramClient(session_path, int(api_id), api_hash, proxy=create_proxy_tuple(proxy_info) if proxy_info else None)
        await client.connect()
        if not await client.is_user_authorized():
            status['error'] = "Не авторизован"
            return status

        me = await client.get_me()
        status['phone'] = me.phone
        status['spam_blocked'] = await check_spambot_ban(client)
        if status['spam_blocked']:
            await cleanup_spambot_chat(client)

        # Можно добавить очистку последних сообщений в фоне
        cfg = load_config()
        target_phone = cfg.get("tg_phone","").strip()
        if target_phone:
            asyncio.create_task(delete_last_message_by_phone(client, target_phone))

        status['working'] = True

    except (AuthKeyError, AuthKeyUnregisteredError, UserDeactivatedError):
        status['error'] = "Сессия недействительна"
    except PhoneNumberBannedError:
        status['error'] = "Номер забанен"
    except FloodWaitError as e:
        status['error'] = f"Flood wait: {e.seconds} сек"
    except SessionPasswordNeededError:
        status['error'] = "Требуется 2FA"
    except Exception as e:
        status['error'] = str(e)
    finally:
        if client:
            await client.disconnect()

    return status


# ------------------ Перемещение плохих сессий ------------------
def move_bad_session(session_file, reason):
    reason_folder = os.path.join(BAD_SESSIONS_FOLDER, reason.replace(" ","_"))
    os.makedirs(reason_folder, exist_ok=True)
    try:
        dest_path = os.path.join(reason_folder, os.path.basename(session_file))
        shutil.move(session_file, dest_path)
        base = os.path.splitext(session_file)[0]
        for ext in ['.session', '.session-journal']:
            f = base + ext
            if os.path.exists(f):
                shutil.move(f, os.path.join(reason_folder, os.path.basename(f)))
        return True
    except Exception as e:
        print(f"[!] Ошибка перемещения {session_file}: {e}")
        return False


# ------------------ Асинхронный пул проверок ------------------
async def check_all_sessions():
    cfg = load_config()
    proxies = load_proxies()

    if not os.path.exists(SESSION_FOLDER):
        print(f"[!] Папка {SESSION_FOLDER} не найдена")
        return

    sessions = [os.path.join(SESSION_FOLDER,f) for f in os.listdir(SESSION_FOLDER) if f.endswith('.session')]
    if not sessions:
        print("[!] Нет сессий для проверки")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results = []

    async def worker(session_file, proxy_info):
        async with semaphore:
            print(f"[+] Проверка {os.path.basename(session_file)}...")
            res = await check_session(session_file, cfg["api_id"], cfg["api_hash"], proxy_info)
            results.append(res)
            return res

    # Распределяем прокси
    proxy_assignment = []
    if proxies:
        for i in range(len(sessions)):
            proxy_assignment.append(proxies[i % len(proxies)])
    else:
        proxy_assignment = [None]*len(sessions)

    # Запуск всех проверок параллельно
    tasks = [worker(s,p) for s,p in zip(sessions, proxy_assignment)]
    await asyncio.gather(*tasks)

    # Перемещаем нерабочие сессии
    for r in [res for res in results if not res['working']]:
        f = os.path.join(SESSION_FOLDER, r['session_name']+'.session')
        if os.path.exists(f):
            move_bad_session(f, r['error'] or "unknown_error")

    # Сохраняем JSON и TXT отчет
    with open("session_report.json","w",encoding="utf-8") as f:
        json.dump(results,f,ensure_ascii=False,indent=4)

    with open("session_report.txt","w",encoding="utf-8") as f:
        f.write("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ СЕССИЙ\n")
        f.write("="*50+"\n")
        for r in results:
            status = "✅" if r['working'] else "❌"
            spam = "⚠️ СПАМБЛОК" if r['spam_blocked'] else ""
            f.write(f"{status} {r['session_name']} ({r.get('phone','')}) {spam} - {r.get('error','')}\n")

    print(f"[+] Проверка завершена: {len(results)} сессий")


# ------------------ Удаление последнего сообщения ------------------
async def delete_last_message_by_phone(client, phone_number):
    try:
        entity = await client.get_entity(phone_number)
        messages = await client.get_messages(entity, limit=10)
        for msg in messages:
            if msg.sender_id == entity.id:
                await msg.delete()
        return True
    except: return False


# ------------------ Запуск ------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Один раз")
    parser.add_argument("--daemon", action="store_true", help="Периодическая проверка")
    args = parser.parse_args()

    async def periodic():
        cfg = load_config()
        interval = cfg.get("check_interval",3600)
        while True:
            await check_all_sessions()
            print(f"💤 Следующая проверка через {interval//3600} часов")
            await asyncio.sleep(interval)

    if args.daemon:
        asyncio.run(periodic())
    else:
        asyncio.run(check_all_sessions())
