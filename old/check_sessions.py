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
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.types import InputPeerUser
from telethon.tl.functions.users import GetFullUserRequest

CONFIG_FILE = "config.json"
SESSION_FOLDER = "sessions"
BAD_SESSIONS_FOLDER = "нерабочие_сессии"
PROXY_FOLDER = "proxies"
SPAMBOT_USERNAME = "spambot"

folders_created = False

def create_folders_once():
    global folders_created
    if folders_created:
        return
    
    folders = [SESSION_FOLDER, BAD_SESSIONS_FOLDER, PROXY_FOLDER]
    
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
    
    error_subfolders = [
        "не_авторизован",
        "сессия_недействительна",
        "номер_забанен", 
        "требуется_2fa",
        "flood_wait",
        "спамблок",
        "другие_ошибки"
    ]
    
    for subfolder in error_subfolders:
        subfolder_path = os.path.join(BAD_SESSIONS_FOLDER, subfolder)
        os.makedirs(subfolder_path, exist_ok=True)
    
    folders_created = True

def load_config():
    create_folders_once()
    
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "api_id": "",
            "api_hash": "",
            "proxy_type": "socks5",
            "check_interval": 3600,
            "tg_phone": "42777"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_proxies():
    create_folders_once()
    
    if not os.path.exists(PROXY_FOLDER):
        return []
    
    proxies = []
    proxy_files = [f for f in os.listdir(PROXY_FOLDER) if os.path.isfile(os.path.join(PROXY_FOLDER, f))]
    
    for fname in proxy_files:
        path = os.path.join(PROXY_FOLDER, fname)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith('#'):
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
                        
                        try:
                            host, port = host_port.split(":")
                            port = int(port)
                            proxies.append((proxy_type, host, port, user, pwd))
                        except ValueError:
                            continue
                    else:
                        parts = s.split(":")
                        if len(parts) >= 2:
                            try:
                                host = parts[0]
                                port = int(parts[1])
                                user = parts[2] if len(parts) > 2 else None
                                pwd = parts[3] if len(parts) > 3 else None
                                proxies.append(("socks5", host, port, user, pwd))
                            except (ValueError, IndexError):
                                continue
        except Exception:
            continue
    
    return proxies

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

async def check_telegram_premium(client):
    try:
        me = await client.get_me()
        
        if hasattr(me, 'premium') and me.premium:
            return True, "✅ Telegram Premium активен"
            
        if hasattr(me, 'premium_animation'):
            return True, "✅ Telegram Premium (по анимации)"
            
        try:
            full_user = await client(GetFullUserRequest(me))
            if hasattr(full_user, 'premium') and full_user.premium:
                return True, "✅ Telegram Premium (полная проверка)"
        except Exception:
            pass
            
        return False, "❌ Telegram Premium отсутствует"
        
    except Exception as e:
        return False, f"❌ Ошибка проверки Premium: {str(e)}"

async def check_spambot_ban(client):
    try:
        spam_bot = await client.get_entity(SPAMBOT_USERNAME)
        
        await client.send_message(spam_bot, "/start")
        await asyncio.sleep(2)
        
        messages = await client.get_messages(spam_bot, limit=5)
        
        for message in messages:
            if message.text and any(keyword in message.text.lower() for keyword in 
                                  ['ban', 'block', 'ограничен', 'заблокирован', 'spam', 'ограничение']):
                return True, message.text[:100] + "..." if len(message.text) > 100 else message.text
                
        return False, "Нет сообщений о блокировке"
        
    except Exception as e:
        return False, f"Ошибка проверки: {str(e)}"

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
            return False
        else:
            entity = await client.get_entity(phone_number)
            messages = await client.get_messages(entity, limit=10)
            for message in messages:
                if message.sender_id == entity.id:
                    await message.delete()
                    return True
            return False
        
    except Exception as e:
        return False

async def try_remove_spamblock(client):
    failure_reasons = []
    
    try:
        spam_bot = await client.get_entity(SPAMBOT_USERNAME)
        
        try:
            await client.send_message(spam_bot, "/start")
            await asyncio.sleep(random.uniform(3.251, 5.861))
            
            messages = await client.get_messages(spam_bot, limit=10)
            found_unblock_option = False
            
            for message in messages:
                if message.text and ('unblock' in message.text.lower() or 'разблок' in message.text.lower()):
                    found_unblock_option = True
                    if message.buttons:
                        for button_row in message.buttons:
                            for button in button_row:
                                if 'unblock' in button.text.lower() or 'разблок' in button.text.lower():
                                    try:
                                        await button.click()
                                        await asyncio.sleep(random.uniform(3.251, 5.861))
                                        return True, "Спамблок снят через кнопку"
                                    except Exception as e:
                                        failure_reasons.append(f"Ошибка клика по кнопке: {str(e)}")
            
            if not found_unblock_option:
                failure_reasons.append("Не найдено опций разблокировки в сообщениях SpamBot")
                
        except Exception as e:
            failure_reasons.append(f"Ошибка отправки /start: {str(e)}")
        
        try:
            await client(DeleteHistoryRequest(
                peer=spam_bot,
                max_id=0,
                just_clear=True
            ))
            await asyncio.sleep(random.uniform(3.251, 5.861))
        except Exception as e:
            failure_reasons.append(f"Ошибка очистки истории: {str(e)}")
        
        try:
            input_user = InputPeerUser(spam_bot.id, spam_bot.access_hash)
            await client(BlockRequest(id=input_user))
            await asyncio.sleep(random.uniform(3.251, 5.861))
            await client(UnblockRequest(id=input_user))
            await asyncio.sleep(random.uniform(3.251, 5.861))
        except Exception as e:
            failure_reasons.append(f"Ошибка блок/разблока: {str(e)}")
        
        await asyncio.sleep(random.uniform(3.251, 5.861))
        is_still_blocked, block_info = await check_spambot_ban(client)
        
        if not is_still_blocked:
            return True, "Спамблок снят после комплексной очистки"
        else:
            failure_reasons.append(f"Спамблок подтвержден после всех попыток: {block_info}")
            
        return False, "; ".join(failure_reasons)
        
    except Exception as e:
        return False, f"Критическая ошибка: {str(e)}"

async def delete_all_spambot_messages(client):
    try:
        spam_bot = await client.get_entity(SPAMBOT_USERNAME)
        # Удаляем всю историю переписки с SpamBot
        await client(DeleteHistoryRequest(
            peer=spam_bot,
            max_id=0,
            just_clear=True
        ))
        return True
    except Exception as e:
        return False
        
async def check_and_clean_session(session_path, api_id, api_hash, proxy_info=None, proxy_type="socks5"):
    session_name = os.path.splitext(os.path.basename(session_path))[0]
    client = None
    status = {
        'session_name': session_name,
        'working': False,
        'spam_blocked': False,
        'spam_removed': False,
        'spam_remove_reason': None,
        'deleted_tg_messages': 0,
        'deleted_spambot_messages': False,
        'is_premium': False,
        'premium_status': '',
        'error': None,
        'phone': None,
        'error_type': None,
        'need_move': False,
        'move_folder': None,
        'move_reason': None
    }
    
    try:
        if proxy_info:
            proxy_tuple = create_proxy_tuple(proxy_info, proxy_type)
            client = TelegramClient(session_path, int(api_id), api_hash, proxy=proxy_tuple)
        else:
            client = TelegramClient(session_path, int(api_id), api_hash)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            status['error'] = "Не авторизован"
            status['error_type'] = "не_авторизован"
            status['need_move'] = True
            status['move_folder'] = "не_авторизован"
            return status
        
        me = await client.get_me()
        status['phone'] = me.phone
        
        is_premium, premium_status = await check_telegram_premium(client)
        status['is_premium'] = is_premium
        status['premium_status'] = premium_status
        
        # Удаляем все сообщения от SpamBot
        spambot_deleted = await delete_all_spambot_messages(client)
        if spambot_deleted:
            status['deleted_spambot_messages'] = True
        
        cfg = load_config()
        target_phone = cfg.get("tg_phone", "42777")
        
        success = await delete_last_message_by_phone(client, target_phone)
        if success:
            status['deleted_tg_messages'] = 1
        
        status['spam_blocked'], block_info = await check_spambot_ban(client)
        
        if status['spam_blocked']:
            status['spam_removed'], status['spam_remove_reason'] = await try_remove_spamblock(client)
            
            if status['spam_removed']:
                status['spam_blocked'] = False
            else:
                status['need_move'] = True
                status['move_folder'] = "спамблок"
                status['move_reason'] = status['spam_remove_reason']
                status['working'] = False
                return status
        
        status['working'] = True
        
    except (AuthKeyError, AuthKeyUnregisteredError, UserDeactivatedError):
        status['error'] = "Сессия недействительна"
        status['error_type'] = "сессия_недействительна"
        status['need_move'] = True
        status['move_folder'] = "сессия_недействительна"
    except PhoneNumberBannedError:
        status['error'] = "Номер забанен"
        status['error_type'] = "номер_забанен"
        status['need_move'] = True
        status['move_folder'] = "номер_забанен"
    except FloodWaitError as e:
        status['error'] = f"Flood wait: {e.seconds} секунд"
        status['error_type'] = "flood_wait"
        status['need_move'] = True
        status['move_folder'] = "flood_wait"
    except SessionPasswordNeededError:
        status['error'] = "Требуется 2FA"
        status['error_type'] = "требуется_2fa"
        status['need_move'] = True
        status['move_folder'] = "требуется_2fa"
    except Exception as e:
        status['error'] = f"Ошибка: {str(e)}"
        status['error_type'] = "другие_ошибки"
        status['need_move'] = True
        status['move_folder'] = "другие_ошибки"
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
    
    return status

def move_bad_session(session_file, error_type, is_spam_blocked=False, spam_reason=None):
    create_folders_once()
    
    if is_spam_blocked:
        reason_folder = os.path.join(BAD_SESSIONS_FOLDER, "спамблок")
    elif error_type in ["не_авторизован", "сессия_недействительна", "номер_забанен", 
                       "требуется_2fa", "flood_wait"]:
        reason_folder = os.path.join(BAD_SESSIONS_FOLDER, error_type)
    else:
        reason_folder = os.path.join(BAD_SESSIONS_FOLDER, "другие_ошибки")
    
    try:
        os.makedirs(reason_folder, exist_ok=True)
        dest_path = os.path.join(reason_folder, os.path.basename(session_file))
        
        if os.path.exists(session_file):
            import time
            time.sleep(0.2)
            shutil.move(session_file, dest_path)
            
            if is_spam_blocked and spam_reason:
                reason_file = os.path.join(reason_folder, f"{os.path.basename(session_file)}.reason.txt")
                with open(reason_file, "w", encoding="utf-8") as f:
                    f.write(f"Причина спамблока: {spam_reason}")
            
            base_name = os.path.splitext(session_file)[0]
            for ext in ['.session', '.session-journal']:
                related_file = base_name + ext
                if os.path.exists(related_file):
                    time.sleep(0.1)
                    dest_related = os.path.join(reason_folder, os.path.basename(related_file))
                    try:
                        shutil.move(related_file, dest_related)
                    except Exception:
                        pass
            return True
        else:
            return False
            
    except Exception:
        return False
        
async def main():
    create_folders_once()
    cfg = load_config()
    proxies = load_proxies()
    
    if not cfg.get("api_id") or not cfg.get("api_hash"):
        print("[❌] Ошибка: Не настроены API ID и API Hash")
        return
    
    session_files = [os.path.join(SESSION_FOLDER, f) for f in os.listdir(SESSION_FOLDER) if f.endswith('.session')]
    
    if not session_files:
        print("[!] Нет файлов сессий для проверки")
        return
    
    print(f"[+] Найдено {len(session_files)} сессий для проверки")
    
    proxy_assignment = []
    if proxies:
        print(f"[🌐] Используется {len(proxies)} прокси")
        for i, session_file in enumerate(session_files):
            proxy_idx = i % len(proxies)
            proxy_assignment.append(proxies[proxy_idx])
    else:
        proxy_assignment = [None] * len(session_files)
        print("[ℹ️] Работа без прокси")
    
    results = []
    for i, (session_file, proxy_info) in enumerate(zip(session_files, proxy_assignment)):
        session_name = os.path.basename(session_file)
        print(f"\n[{i+1}/{len(session_files)}] Проверяю {session_name}...")
        
        result = await check_and_clean_session(
            session_file, 
            cfg["api_id"], 
            cfg["api_hash"], 
            proxy_info,
            cfg.get("proxy_type", "socks5")
        )
        
        if result.get('need_move', False):
            move_bad_session(
                session_file, 
                result['move_folder'], 
                result['move_folder'] == "спамблок",
                result.get('move_reason')
            )
        
        results.append(result)
        
        if result['working']:
            premium_icon = "💎" if result['is_premium'] else "🔹"
            if result['spam_blocked']:
                print(f"   {premium_icon} РАБОЧАЯ, НО СПАМБЛОК - {result['phone']}")
            else:
                if result['spam_removed']:
                    print(f"   {premium_icon} РАБОЧАЯ (спамблок снят) - {result['phone']}")
                else:
                    print(f"   {premium_icon} РАБОЧАЯ - {result['phone']}")
        else:
            print(f"   ❌ НЕРАБОЧАЯ - {result['error']}")
        
        if i < len(session_files) - 1:
            await asyncio.sleep(random.uniform(2, 4))
    
    working_sessions = [r for r in results if r['working']]
    working_without_spam = [r for r in working_sessions if not r['spam_blocked']]
    working_with_spam = [r for r in working_sessions if r['spam_blocked']]
    spam_removed_sessions = [r for r in working_sessions if r['spam_removed']]
    non_working_sessions = [r for r in results if not r['working']]
    premium_sessions = [r for r in working_sessions if r['is_premium']]
    
    print("\n" + "="*70)
    print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ И ОЧИСТКИ СЕССИЙ")
    print("="*70)
    print(f"✅ Рабочих сессий: {len(working_sessions)}")
    print(f"   ├── Без спамблока: {len(working_without_spam)}")
    print(f"   ├── Со спамблоком: {len(working_with_spam)}")
    print(f"   ├── Спамблоков снято: {len(spam_removed_sessions)}")
    print(f"   └── 💎 Telegram Premium: {len(premium_sessions)}")
    print(f"❌ Нерабочих сессий: {len(non_working_sessions)}")
    print("="*70)

async def periodic_check():
    cfg = load_config()
    check_interval = cfg.get("check_interval", 3600)
    
    while True:
        await main()
        await asyncio.sleep(check_interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Проверка и очистка сессий Telegram")
    parser.add_argument("--once", action="store_true", help="Выполнить проверку один раз")
    parser.add_argument("--daemon", action="store_true", help="Запустить в режиме службы")
    
    args = parser.parse_args()
    
    create_folders_once()
    
    if args.daemon:
        asyncio.run(periodic_check())
    else:
        asyncio.run(main())
