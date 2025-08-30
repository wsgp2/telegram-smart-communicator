import os
import json
import asyncio
import random
from telethon import TelegramClient
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.errors import FloodWaitError, PeerFloodError
import telethon


CONFIG_FILE = "config.json"
SESSION_FOLDER = "sessions"
USERS_FILE = "target_users.txt"
PROXY_FOLDER = "proxies"


# ---------- Загрузка/сохранение конфига ----------

def load_config():
    if not os.path.exists(CONFIG_FILE):
        # Создаем конфиг по умолчанию
        default_config = {
            "api_id": "",
            "api_hash": "",
            "accounts_per_proxy": 1,
            "proxy_mode": "auto",
            "target_users_file": USERS_FILE,
            "message": "Привет!",
            "delay_ms": 1000,
            "messages_per_account": 1,
            "proxy_type": "socks5"  # Новое поле: тип прокси
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Устанавливаем значения по умолчанию для отсутствующих полей
    defaults = {
        "accounts_per_proxy": 1,
        "proxy_mode": "auto",
        "target_users_file": USERS_FILE,
        "message": "Привет!",
        "delay_ms": 1000,
        "messages_per_account": 1,
        "proxy_type": "socks5"
    }

    for key, value in defaults.items():
        if key not in cfg:
            cfg[key] = value

    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


# ---------- Загрузка списка пользователей ----------
def load_users(users_file):
    if not os.path.exists(users_file):
        print(f"[!] Файл {users_file} не найден. Создан пустой.")
        open(users_file, "w", encoding="utf-8").close()
        return []
    with open(users_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ---------- Загрузка прокси ----------
def load_proxies():
    if not os.path.exists(PROXY_FOLDER):
        os.makedirs(PROXY_FOLDER)
        print(f"[!] Папка {PROXY_FOLDER} создана, но прокси не найдены.")
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

                # Поддержка различных форматов прокси
                if "://" in s:
                    # Формат: тип://user:pass@host:port
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
                    # Старый формат: host:port:user:pwd
                    parts = s.split(":")
                    try:
                        if len(parts) >= 2:
                            host = parts[0]
                            port = int(parts[1])
                            user = parts[2] if len(parts) > 2 else None
                            pwd = parts[3] if len(parts) > 3 else None
                            # По умолчанию используем socks5 для старого формата
                            proxies.append(("socks5", host, port, user, pwd))
                    except Exception as e:
                        print(f"[!] Неверный формат прокси: {s} - {e}")
    return proxies


# ---------- Создание прокси-кортежа для Telethon ----------
def create_proxy_tuple(proxy_info, proxy_type):
    proxy_type, host, port, user, pwd = proxy_info

    # Преобразуем тип прокси в формат, понятный Telethon
    telethon_proxy_type = {
        "socks5": "socks5",
        "socks4": "socks4",
        "http": "http",
        "https": "http",  # Telethon использует "http" для HTTPS прокси
        "mtproto": "mtproto"
    }.get(proxy_type.lower(), "socks5")

    if user and pwd:
        return (telethon_proxy_type, host, port, True, user, pwd)
    else:
        return (telethon_proxy_type, host, port, True)


# ---------- Загрузка сессий с прокси ----------
async def load_sessions(api_id, api_hash, proxies, accounts_per_proxy, proxy_type):
    if not os.path.exists(SESSION_FOLDER):
        os.makedirs(SESSION_FOLDER)
        print(f"[!] Папка {SESSION_FOLDER} создана, но пустая.")
        return []

    files = [f for f in os.listdir(SESSION_FOLDER) if f.endswith(".session")]
    if not files:
        print("[!] Нет файлов сессий в папке.")
        return []

    # Правильное распределение аккаунтов по прокси
    assigned = []
    if proxies:
        if len(proxies) == 1:
            # Если один прокси - используем его для всех аккаунтов
            assigned = [proxies[0]] * len(files)
        else:
            # Если несколько прокси - равномерно распределяем аккаунты
            accounts_per_proxy = max(1, len(files) // len(proxies))
            for i, proxy in enumerate(proxies):
                start_idx = i * accounts_per_proxy
                end_idx = min((i + 1) * accounts_per_proxy, len(files))
                for j in range(start_idx, end_idx):
                    if j < len(files):
                        assigned.append(proxy)

            # Если остались аккаунты без прокси, распределяем их по существующим прокси
            remaining = len(files) - len(assigned)
            if remaining > 0:
                for i in range(remaining):
                    proxy_idx = i % len(proxies)
                    assigned.append(proxies[proxy_idx])
    else:
        assigned = [None] * len(files)

    sessions = []
    for idx, fname in enumerate(files):
        name = os.path.splitext(fname)[0]
        session_path = os.path.join(SESSION_FOLDER, name)
        proxy_info = assigned[idx] if idx < len(assigned) else None

        try:
            if proxy_info:
                proxy_tuple = create_proxy_tuple(proxy_info, proxy_type)
                client = TelegramClient(session_path, int(api_id), api_hash, proxy=proxy_tuple)
            else:
                client = TelegramClient(session_path, int(api_id), api_hash)

            await client.connect()

            if not await client.is_user_authorized():
                print(f"[X] {name} не авторизован.")
                await client.disconnect()
                continue

            me = await client.get_me()
            if proxy_info:
                proxy_type, host, port, user, pwd = proxy_info
                print(f"[+] Загружен {me.first_name} ({me.phone}) -> {proxy_type}://{host}:{port}")
            else:
                print(f"[+] Загружен {me.first_name} ({me.phone}) -> без прокси")
            sessions.append(client)

        except Exception as e:
            print(f"\n🔴 [X] Ошибка загрузки {fname}:")
            print(f"   Тип ошибки: {type(e).__name__}")
            print(f"   Полный текст: {str(e)}")
            if hasattr(e, '__dict__'):
                for attr, value in e.__dict__.items():
                    if attr not in ['args']:
                        print(f"   {attr}: {value}")
            print()

    return sessions


# ---------- Отправка сообщений ----------
async def send_messages(sessions, users, message, delay_ms, msgs_per_acc):
    if not users:
        print("[!] Нет пользователей для отправки сообщений")
        return

    # Статистика отправки
    total_sent = 0
    total_errors = 0
    error_types = {}

    # перемешиваем пользователей случайным образом
    random.shuffle(users)

    for client in sessions:
        me = await client.get_me()
        print(f"\n=== Работаем через аккаунт: {me.first_name} ===")

        try:
            # берем случайные пользователи для этой сессии
            targets = []
            if users:
                for _ in range(min(msgs_per_acc, len(users))):
                    if users:
                        target = users.pop(random.randrange(len(users)))
                        targets.append(target)

            for target in targets:
                try:
                    # Создаем уникальные сообщения
                    unique_messages = [
                        "Привет, я от Сергея, тестирую связь 👋",
                        "Здравствуйте! Сергей просил проверить связь",
                        "Добрый день, это тест от Сергея",
                        "Привет! Сергей передает привет и тестирует связь",
                        "Здравствуйте, проверяю связь по поручению Сергея",
                        "Привет, тестовое сообщение от Сергея ✌️",
                        "Добрый день! Сергей попросил протестировать связь"
                    ]
                    
                    # Выбираем случайное сообщение
                    random_message = random.choice(unique_messages)
                    await client.send_message(target, random_message)
                    print(f"✅ [{me.first_name}] -> {target}: {random_message}")
                    total_sent += 1
                except Exception as e:
                    # Детальное логирование ошибок Telegram
                    print(f"\n🔴 [{me.first_name}] Ошибка при отправке {target}:")
                    print(f"   Тип ошибки: {type(e).__name__}")
                    print(f"   Полный текст: {str(e)}")
                    
                    # Специальная обработка ошибок лимитов
                    if isinstance(e, FloodWaitError):
                        wait_time = e.seconds
                        hours = wait_time // 3600
                        minutes = (wait_time % 3600) // 60
                        secs = wait_time % 60
                        print(f"   ⏰ ТОЧНОЕ время ожидания: {hours}ч {minutes}м {secs}с (всего {wait_time} сек)")
                        
                    elif isinstance(e, PeerFloodError):
                        print(f"   🚫 PeerFloodError: Этот аккаунт отправил слишком много сообщений получателям")
                        print(f"   ⏰ Рекомендуется ждать: 12-24 часа")
                        print(f"   💡 Решение: Использовать другие аккаунты или новых получателей")
                    
                        
                    elif "FloodWaitError" in str(type(e)) or "Too many requests" in str(e):
                        if hasattr(e, 'seconds'):
                            wait_time = e.seconds
                            hours = wait_time // 3600
                            minutes = (wait_time % 3600) // 60
                            seconds = wait_time % 60
                            print(f"   ⏰ Нужно ждать: {hours}ч {minutes}м {seconds}с (всего {wait_time} сек)")
                        else:
                            # Попробуем извлечь время из текста ошибки
                            import re
                            time_match = re.search(r'(\d+)', str(e))
                            if time_match:
                                wait_seconds = int(time_match.group(1))
                                hours = wait_seconds // 3600
                                minutes = (wait_seconds % 3600) // 60
                                print(f"   ⏰ Примерное время ожидания: {hours}ч {minutes}м ({wait_seconds} сек)")
                            else:
                                print(f"   ⏰ Время ожидания не определено, рекомендуется подождать 1-24 часа")
                    
                    # Учитываем статистику ошибок  
                    total_errors += 1
                    error_type = type(e).__name__
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                    
                    # Показать дополнительные атрибуты ошибки
                    if hasattr(e, '__dict__'):
                        for attr, value in e.__dict__.items():
                            if attr not in ['args']:
                                print(f"   {attr}: {value}")
                    print()

                base_delay = delay_ms / 1000.0
                jitter = random.uniform(-0.355, 0.355)
                await asyncio.sleep(max(0.1, base_delay + jitter))

        except Exception as e:
            print(f"\n🔴 [{me.first_name}] Критическая ошибка при работе аккаунта:")
            print(f"   Тип ошибки: {type(e).__name__}")
            print(f"   Полный текст: {str(e)}")
            if hasattr(e, '__dict__'):
                for attr, value in e.__dict__.items():
                    if attr not in ['args']:
                        print(f"   {attr}: {value}")
            print()
        finally:
            await client.disconnect()
            print(f"[{me.first_name}] Сессия завершена")
    
    # Показать итоговую статистику
    print("\n" + "="*50)
    print("📊 ИТОГОВАЯ СТАТИСТИКА РАССЫЛКИ")
    print("="*50)
    print(f"✅ Успешно отправлено: {total_sent}")
    print(f"❌ Ошибок: {total_errors}")
    if error_types:
        print("\n🔍 Типы ошибок:")
        for error_type, count in error_types.items():
            print(f"   {error_type}: {count}")
    print("="*50)


# ---------- Редактирование настроек ----------
def edit_settings(cfg):
    print("\n=== Редактирование настроек ===")

    # Доступные типы прокси
    proxy_types = ["socks5", "socks4", "http", "https", "mtproto"]

    for key in cfg:
        if key == "proxy_type":
            print(f"Доступные типы прокси: {', '.join(proxy_types)}")
            new = input(f"{key} [{cfg[key]}]: ").strip()
            if new and new.lower() in proxy_types:
                cfg[key] = new.lower()
            elif new:
                print(f"Неверный тип прокси. Используется значение по умолчанию: {cfg[key]}")
        else:
            old = cfg[key]
            new = input(f"{key} [{old}]: ").strip()
            if new:
                if key in ["delay_ms", "messages_per_account", "accounts_per_proxy", "api_id"]:
                    try:
                        cfg[key] = int(new)
                    except ValueError:
                        print(f"Неверное числовое значение для {key}. Используется старое значение: {old}")
                else:
                    cfg[key] = new

    save_config(cfg)
    print("[+] Настройки сохранены\n")


# ---------- Показать информацию о прокси ----------
def show_proxy_info(proxies):
    if not proxies:
        print("[!] Прокси не найдены")
        return

    print("\n=== Информация о прокси ===")
    for i, proxy in enumerate(proxies, 1):
        proxy_type, host, port, user, pwd = proxy
        auth_info = f" (auth: {user}:{pwd})" if user and pwd else " (без авторизации)"
        print(f"{i}. {proxy_type}://{host}:{port}{auth_info}")


# ---------- MAIN ----------
async def main():
    cfg = load_config()

    while True:
        print("\n=== Telegram Mass Sender (Console) ===")
        print("1 - Редактировать настройки")
        print("2 - Показать информацию о прокси")
        print("3 - Запустить рассылку")
        print("0 - Выход")

        choice = input("Выберите действие: ").strip()

        if choice == "1":
            edit_settings(cfg)

        elif choice == "2":
            proxies = load_proxies()
            show_proxy_info(proxies)

        elif choice == "3":
            users = load_users(cfg["target_users_file"])
            if users:
                print(f"[+] Загружено {len(users)} пользователей из {cfg['target_users_file']}")
            else:
                print("[!] Файл пуст, будут использоваться контакты аккаунтов")

            proxies = load_proxies()
            if proxies:
                print(f"[+] Загружено {len(proxies)} прокси")
                show_proxy_info(proxies)
            else:
                print("[!] Прокси не найдены, аккаунты будут работать напрямую")

            sessions = await load_sessions(
                cfg["api_id"],
                cfg["api_hash"],
                proxies,
                cfg["accounts_per_proxy"],
                cfg["proxy_type"]
            )

            if not sessions:
                print("[!] Нет рабочих аккаунтов.")
                continue

            print(f"[+] Используется {len(sessions)} сессий")

            await send_messages(
                sessions,
                users,
                cfg["message"],
                cfg["delay_ms"],
                cfg["messages_per_account"]
            )

        elif choice == "0":
            print("Выход.")
            break
        else:
            print("Неверный выбор.")


if __name__ == "__main__":
    asyncio.run(main())
