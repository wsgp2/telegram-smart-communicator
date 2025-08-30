import os
import json
import asyncio
import random
from telethon import TelegramClient, events
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.errors import FloodWaitError, PeerFloodError
import telethon

# 🤖 Импортируем бот для уведомлений
from notification_bot import init_notification_bot, notify_admin_via_bot, notification_bot

# 🗂️ Импортируем чат-менеджер
from chat_manager import ChatManager

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
            "messages_per_account": 2,
            "proxy_type": "socks5",
                    "admin_username": "",  # Изменено с admin_id на admin_username
        "auto_hide_chats": True,
        "auto_delete_delay": 4,
        "auto_ttl_messages": True
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
        "proxy_type": "socks5",
        "admin_username": "",
        "auto_hide_chats": True,
        "auto_delete_delay": 4,
        "auto_ttl_messages": True
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


# ---------- Создание прокси-кортежа ----------
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


# ---------- Отправка админу ----------
async def notify_admin(sender, text, client, admin_username):
    """УСТАРЕВШАЯ ФУНКЦИЯ - оставлена для совместимости"""
    if not admin_username:
        return
    try:
        await client.send_message(admin_username, f"📩 Сообщение от {sender.first_name}: {text}")
    except Exception as e:
        print(f"[!] Ошибка отправки админу: {e}")

# 🤖 НОВАЯ СИСТЕМА УВЕДОМЛЕНИЙ ЧЕРЕЗ БОТА

# 🔐 ОПРЕДЕЛЕНИЕ СЛУЖЕБНЫХ СООБЩЕНИЙ TELEGRAM (УЛУЧШЕННАЯ ВЕРСИЯ)
async def is_telegram_service_message(sender, text):
    """Определяет служебные сообщения от Telegram с подробным логированием"""
    
    # 📝 ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
    print(f"\n🔍 [DEBUG] Проверка сообщения:")
    print(f"   Отправитель ID: {getattr(sender, 'id', 'НЕТ')}")
    print(f"   Отправитель телефон: {getattr(sender, 'phone', 'НЕТ')}")
    print(f"   Отправитель username: {getattr(sender, 'username', 'НЕТ')}")
    print(f"   Отправитель имя: {getattr(sender, 'first_name', 'НЕТ')}")
    print(f"   Текст (первые 100 символов): {text[:100]}...")
    
    # ✅ РАСШИРЕННАЯ ПРОВЕРКА ID ОТПРАВИТЕЛЯ
    if hasattr(sender, 'id') and sender.id:
        service_ids = [
            777000,     # Telegram Service Notifications (основной)
            42777,      # Telegram Security  
            2000,       # Возможный служебный ID
            1,          # Возможный системный ID
        ]
        if sender.id in service_ids:
            print(f"✅ [DEBUG] Найден по ID: {sender.id}")
            return True
    
    # ✅ ПРОВЕРКА ТЕЛЕФОНА (более широкая)
    if hasattr(sender, 'phone') and sender.phone:
        service_phones = ['42777', '777000']
        if sender.phone in service_phones:
            print(f"✅ [DEBUG] Найден по телефону: {sender.phone}")
            return True
    
    # ✅ ПРОВЕРКА USERNAME
    if hasattr(sender, 'username') and sender.username:
        service_usernames = [
            'telegram', 'telegramnotifications', '42777',
            'telegramservice', 'telegram_notifications'
        ]
        if sender.username.lower() in service_usernames:
            print(f"✅ [DEBUG] Найден по username: {sender.username}")
            return True
    
    # ✅ ПРОВЕРКА ИМЕНИ ОТПРАВИТЕЛЯ  
    if hasattr(sender, 'first_name') and sender.first_name:
        service_names = ['telegram', 'service notifications']
        name_lower = sender.first_name.lower()
        if name_lower in service_names or 'telegram' in name_lower:
            print(f"✅ [DEBUG] Найден по имени: {sender.first_name}")
            return True
    
    # ✅ ПРОВЕРКА СОДЕРЖИМОГО СООБЩЕНИЯ (расширенная)
    security_keywords = [
        # Русские
        'код для входа', 'код входа', 'ваш код', 'проверочный код',
        'новый вход', 'новое устройство', 'код безопасности',
        'не давайте код', 'код подтверждения', 'авторизация',
        'вход в аккаунт', 'подтвердить вход',
        
        # Английские  
        'login code', 'verification code', 'your code', 'security code',
        'new login', 'new device', 'authenticate', 'authorization',
        "don't give the code", "don't share", 'confirmation code',
        'sign in', 'log in', 'access code',
        
        # Цифровые паттерны (коды обычно 4-6 цифр)
        'code:', 'код:', 'your telegram code', 'ваш код telegram'
    ]
    
    if text:
        text_lower = text.lower()
        for keyword in security_keywords:
            if keyword in text_lower:
                print(f"✅ [DEBUG] Найден по ключевому слову: '{keyword}'")
                return True
        
        # Дополнительная проверка на цифровые коды (например "65076" в сообщении)
        import re
        if re.search(r'\b\d{4,6}\b', text) and ('telegram' in text_lower or 'код' in text_lower or 'code' in text_lower):
            print(f"✅ [DEBUG] Найден цифровой код в тексте")
            return True
    
    print(f"❌ [DEBUG] НЕ определено как служебное сообщение")
    return False

# 🚨 УВЕДОМЛЕНИЯ О СЛУЖЕБНЫХ СООБЩЕНИЯХ
async def notify_telegram_service(sender, text, receiving_client):
    """Отправка критических уведомлений о безопасности"""
    if not notification_bot:
        return
        
    try:
        me = await receiving_client.get_me()
        
        # Определяем тип уведомления
        message_type = "🔐 СЛУЖЕБНОЕ УВЕДОМЛЕНИЕ"
        if 'код для входа' in text.lower() or 'login code' in text.lower():
            message_type = "🔑 КОД ВХОДА"
        elif 'new login' in text.lower() or 'новый вход' in text.lower():
            message_type = "🚨 НОВЫЙ ВХОД"
        elif 'security' in text.lower() or 'безопасность' in text.lower():
            message_type = "⚠️ БЕЗОПАСНОСТЬ"
        
        # Получаем информацию об аккаунте
        account_info = {
            'phone': me.phone,
            'name': me.first_name or 'Unknown'
        }
        
        # Информация об отправителе (Telegram Service)
        sender_name = "Telegram Service"
        if hasattr(sender, 'first_name') and sender.first_name:
            sender_name = sender.first_name
        elif hasattr(sender, 'username') and sender.username:
            sender_name = f"@{sender.username}"
        
        sender_info = {
            'name': sender_name,
            'username': getattr(sender, 'username', 'telegram_service')
        }
        
        # Отправляем КРИТИЧЕСКОЕ уведомление
        await notification_bot.send_security_notification(
            account_info, sender_info, text, message_type
        )
        
    except Exception as e:
        print(f"[!] Ошибка отправки служебного уведомления: {e}")


# ---------- Загрузка сессий ----------
async def load_sessions(api_id, api_hash, proxies, accounts_per_proxy, proxy_type, admin_username):
    if not os.path.exists(SESSION_FOLDER):
        os.makedirs(SESSION_FOLDER)
        print(f"[!] Папка {SESSION_FOLDER} создана, но пустая.")
        return []

    files = [f for f in os.listdir(SESSION_FOLDER) if f.endswith(".session")]
    if not files:
        print("[!] Нет файлов сессий в папке.")
        return []

    assigned = []
    if proxies:
        if len(proxies) == 1:
            assigned = [proxies[0]] * len(files)
        else:
            accounts_per_proxy = max(1, len(files) // len(proxies))
            for i, proxy in enumerate(proxies):
                start_idx = i * accounts_per_proxy
                end_idx = min((i + 1) * accounts_per_proxy, len(files))
                for j in range(start_idx, end_idx):
                    if j < len(files):
                        assigned.append(proxy)
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

            # Создаем словарь для хранения отправленных пользователей для этого клиента
            client.sent_users = set()
            
            # 🗂️ Добавляем ChatManager если включено в настройках
            cfg = load_config()
            if cfg.get('auto_hide_chats', False):
                client.chat_manager = ChatManager(client)
                client.chat_manager.auto_delete_delay = cfg.get('auto_delete_delay', 4)
                print(f"    🗂️ ChatManager подключен (авто-скрытие: ON)")

            sessions.append(client)

        except Exception as e:
            print(f"\n🔴 [X] Ошибка загрузки {fname}: {e}\n")

    return sessions


# ---------- Отправка сообщений ----------
async def send_messages(sessions, users, message, delay_ms, msgs_per_acc, admin_username):
    if not users:
        print("[!] Нет пользователей для отправки сообщений")
        return

    total_sent = 0
    total_errors = 0
    error_types = {}
    random.shuffle(users)

    # Создаем обработчики событий для каждого клиента
    for client in sessions:
        # 🔍 РАСШИРЕННЫЙ ОБРАБОТЧИК: Ответы пользователей + Служебные уведомления Telegram
        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            sender = await event.get_sender()
            text = event.raw_text
            
            # 🔐 СЛУЖЕБНЫЕ УВЕДОМЛЕНИЯ TELEGRAM (коды входа, безопасность)
            is_telegram_service = await is_telegram_service_message(sender, text)
            
            if is_telegram_service:
                print(f"\n🚨 [SECURITY] Служебное уведомление: {text[:50]}...")
                await notify_telegram_service(sender, text, event.client)
                return
            
            # 📱 ОТВЕТЫ ПОЛЬЗОВАТЕЛЕЙ (как раньше)
            if sender and hasattr(event.client, 'sent_users') and sender.id in event.client.sent_users:
                print(f"\n📩 [{sender.first_name}] -> {text}")
                await notify_admin_via_bot(sender, text, event.client)
                
                # 🗑️ Автоматически удаляем входящее сообщение только у нас
                if hasattr(event.client, 'chat_manager'):
                    asyncio.create_task(event.client.chat_manager.delete_incoming_message(event.message))

    for client in sessions:
        me = await client.get_me()
        print(f"\n=== Работаем через аккаунт: {me.first_name} ===")

        try:
            targets = []
            if users:
                for _ in range(min(msgs_per_acc, len(users))):
                    if users:
                        target = users.pop(random.randrange(len(users)))
                        targets.append(target)

            for target in targets:
                try:
                    unique_messages = [
                        "Привет, я от Сергея, тестирую связь 👋 Напишите что-нибудь в ответ!",
                        "Здравствуйте! Сергей просил проверить связь. Ответьте пожалуйста любым сообщением",
                        "Добрый день, это тест от Сергея. Напишите что-то в ответ для проверки",
                        "Привет! Сергей передает привет и тестирует связь. Ответьте когда получите!",
                        "Здравствуйте, проверяю связь по поручению Сергея. Пришлите любой ответ",
                        "Привет, тестовое сообщение от Сергея ✌️ Напишите хотя бы смайлик в ответ",
                        "Добрый день! Сергей попросил протестировать связь. Ответьте что получили сообщение"
                    ]
                    random_message = random.choice(unique_messages)

                    # Получаем информацию о пользователе, чтобы сохранить его ID
                    entity = await client.get_entity(target)
                    
                    # 🕐 СНАЧАЛА устанавливаем TTL если включено (до отправки сообщения)
                    cfg = load_config()
                    if cfg.get('auto_ttl_messages', False) and hasattr(client, 'chat_manager'):
                        await client.chat_manager.set_auto_delete_1_month(entity)
                    
                    # 📤 Отправляем сообщение и получаем объект сообщения
                    sent_message = await client.send_message(entity, random_message)
                    print(f"✅ [{me.first_name}] -> {target}: {random_message}")

                    # Сохраняем ID пользователя, которому отправили сообщение
                    client.sent_users.add(entity.id)
                    
                    # 🗂️ Автоматически управляем чатом если включено
                    if hasattr(client, 'chat_manager'):
                        # 🗑️ Удаляем наше сообщение через задержку (только у нас)
                        asyncio.create_task(client.chat_manager._delayed_delete(sent_message))
                        # 🔇📂 Скрываем чат (мьют + архив)
                        asyncio.create_task(client.chat_manager.hide_chat(target))
                    total_sent += 1

                except Exception as e:
                    print(f"\n🔴 [{me.first_name}] Ошибка при отправке {target}: {e}")
                    total_errors += 1
                    error_type = type(e).__name__
                    error_types[error_type] = error_types.get(error_type, 0) + 1

                base_delay = delay_ms / 1000.0
                jitter = random.uniform(-0.355, 0.355)
                await asyncio.sleep(max(0.1, base_delay + jitter))

        except Exception as e:
            print(f"\n🔴 [{me.first_name}] Критическая ошибка: {e}")

    print("\n" + "=" * 50)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 50)
    print(f"✅ Успешно отправлено: {total_sent}")
    print(f"❌ Ошибок: {total_errors}")
    if error_types:
        print("\n🔍 Типы ошибок:")
        for error_type, count in error_types.items():
            print(f"   {error_type}: {count}")
    print("=" * 50)


# ---------- MAIN ----------
async def main():
    cfg = load_config()
    
    # 🤖 Инициализируем бот для уведомлений
    init_notification_bot()
    
    # 🧪 Тестируем бот
    if notification_bot:
        await notification_bot.test_connection()

    while True:
        print("\n=== Telegram Mass Sender (Console) ===")
        print("1 - Редактировать настройки")
        print("2 - Показать информацию о прокси")
        print("3 - Запустить рассылку + приём сообщений")
        print("4 - Создать новую сессию")
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
                print(f"[+] Загружено {len(users)} пользователей")
            else:
                print("[!] Файл пуст, будут использоваться контакты аккаунтов")

            proxies = load_proxies()
            sessions = await load_sessions(
                cfg["api_id"],
                cfg["api_hash"],
                proxies,
                cfg["accounts_per_proxy"],
                cfg["proxy_type"],
                cfg["admin_username"]
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
                cfg["messages_per_account"],
                cfg["admin_username"]
            )

            print("\n[+] Все аккаунты теперь слушают входящие сообщения только от тех, кому отправляли...")
            await asyncio.gather(*[client.run_until_disconnected() for client in sessions])

        elif choice == "4":
            # Создание новой сессии
            if cfg["api_id"] and cfg["api_hash"]:
                await create_new_session(cfg["api_id"], cfg["api_hash"])
            else:
                print("❌ Сначала настройте API ID и API Hash в пункте 1")
            input("\n🔄 Нажмите Enter для продолжения...")

        elif choice == "0":
            print("Выход.")
            break
        else:
            print("Неверный выбор.")


# ---------- Доп. функции ----------
def edit_settings(cfg):
    print("\n=== Редактирование настроек ===")
    proxy_types = ["socks5", "socks4", "http", "https", "mtproto"]

    for key in cfg:
        if key == "proxy_type":
            print(f"Доступные типы прокси: {', '.join(proxy_types)}")
            new = input(f"{key} [{cfg[key]}]: ").strip()
            if new and new.lower() in proxy_types:
                cfg[key] = new.lower()
        elif key in ["delay_ms", "messages_per_account", "accounts_per_proxy", "api_id"]:
            old = cfg[key]
            new = input(f"{key} [{old}]: ").strip()
            if new:
                try:
                    cfg[key] = int(new)
                except ValueError:
                    print(f"Неверное число, оставляем {old}")
        elif key == "admin_username":
            old = cfg[key]
            new = input(f"{key} [{old}]: ").strip()
            if new:
                # Убедимся, что username начинается с @
                if not new.startswith('@'):
                    new = '@' + new
                cfg[key] = new
        else:
            old = cfg[key]
            new = input(f"{key} [{old}]: ").strip()
            if new:
                cfg[key] = new

    save_config(cfg)
    print("[+] Настройки сохранены\n")


async def create_new_session(api_id, api_hash):
    """🆕 Создание новой сессии по номеру телефона (принцип 20/80)"""
    print("\n🆕 === СОЗДАНИЕ НОВОЙ СЕССИИ ===")
    
    # Ввод номера телефона
    phone = input("📱 Введите номер телефона (например, +1234567890): ").strip()
    if not phone.startswith('+'):
        phone = '+' + phone
    
    # Создаем имя для сессии (используем телефон без +)
    session_name = f"sessions/{phone[1:]}_telethon"
    
    print(f"📂 Сессия будет сохранена как: {session_name}.session")
    
    # Создаем клиент и подключаемся
    client = TelegramClient(session_name, api_id, api_hash)
    
    try:
        await client.connect()
        
        # Отправляем код
        print(f"📤 Отправляем код на {phone}...")
        await client.send_code_request(phone)
        
        # Ввод кода
        code = input("🔐 Введите код из SMS: ").strip()
        
        # Авторизуемся
        await client.sign_in(phone, code)
        
        # Проверяем что получилось
        me = await client.get_me()
        print(f"✅ Успешно! Создана сессия для: {me.first_name} ({me.phone})")
        print(f"📁 Файл: {session_name}.session")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания сессии: {e}")
        
        # Если нужно 2FA
        if "Two steps verification" in str(e) or "password" in str(e).lower():
            try:
                password = input("🔑 Введите пароль двухфакторной аутентификации: ").strip()
                await client.sign_in(password=password)
                me = await client.get_me()
                print(f"✅ Успешно с 2FA! Создана сессия для: {me.first_name} ({me.phone})")
                await client.disconnect()
                return True
            except Exception as e2:
                print(f"❌ Ошибка с паролем 2FA: {e2}")
        
        await client.disconnect()
        return False


def show_proxy_info(proxies):
    if not proxies:
        print("[!] Прокси не найдены")
        return
    print("\n=== Информация о прокси ===")
    for i, proxy in enumerate(proxies, 1):
        proxy_type, host, port, user, pwd = proxy
        auth_info = f" (auth: {user}:{pwd})" if user and pwd else " (без авторизации)"
        print(f"{i}. {proxy_type}://{host}:{port}{auth_info}")


if __name__ == "__main__":
    asyncio.run(main())