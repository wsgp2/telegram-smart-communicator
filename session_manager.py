import os
import asyncio
import random
import time
import shutil
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from config import load_config, update_config_timestamp
from proxy_manager import ProxyManager
from chat_manager import ChatManager


class SessionManager:
    def __init__(self, session_folder="sessions"):
        self.session_folder = session_folder
        self.nonworking_folder = "nonworking_sessions"
        self.suspicious_folder = "suspicious_sessions"
        self.sessions = []
        self.last_loaded_count = 0
        self.config = load_config()
        self.proxy_manager = ProxyManager()
        self.last_action_time = {}
        self.problem_sessions = set()

        # Создаем папки, если их нет
        os.makedirs(self.session_folder, exist_ok=True)
        os.makedirs(self.nonworking_folder, exist_ok=True)
        os.makedirs(self.suspicious_folder, exist_ok=True)

    async def load_sessions(self, force_reload=False):
        """Загрузка всех сессий с проверкой на спамблок и авторизацию"""
        current_files = self._get_session_files()
        if not force_reload and len(current_files) == self.last_loaded_count:
            return self.sessions

        print("🔄 Загрузка сессий...")
        self.sessions = await self._load_all_sessions(current_files)
        self.last_loaded_count = len(current_files)
        update_config_timestamp("last_session_check")
        return self.sessions

    async def reload_sessions_if_needed(self):
        """Перезагрузка сессий при необходимости"""
        if not self.config.get("auto_check_new_sessions", True):
            return self.sessions

        last_check = self.config.get("last_session_check")
        interval_min = self.config.get("check_interval_minutes", 5)
        if last_check:
            try:
                last_dt = datetime.fromisoformat(last_check)
                if (datetime.now() - last_dt).total_seconds() < interval_min * 60:
                    return self.sessions
            except Exception:
                pass
        return await self.load_sessions()

    def _get_session_files(self):
        return [f for f in os.listdir(self.session_folder) if f.endswith(".session")]

    async def _load_all_sessions(self, session_files):
        """Создание клиентов Telegram с прокси и проверкой сессий"""
        proxies = self.proxy_manager.load_proxies()
        assigned_proxies = self.proxy_manager.assign_proxies_to_sessions(
            session_files, proxies, self.config.get("accounts_per_proxy", 1)
        )

        tasks = [self._create_session_task(fname, assigned_proxies[idx] if idx < len(assigned_proxies) else None)
                 for idx, fname in enumerate(session_files)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        sessions = [client for client in results if isinstance(client, TelegramClient)]
        print(f"✅ Рабочих сессий: {len(sessions)}/{len(session_files)}")
        return sessions

    async def _create_session_task(self, fname, proxy_info):
        """Создание и проверка одного клиента Telegram"""
        name = os.path.splitext(fname)[0]
        session_path = os.path.join(self.session_folder, name)
        client = None

        try:
            proxy_tuple = self.proxy_manager.create_proxy_tuple(proxy_info) if proxy_info else None
            client = TelegramClient(
                session_path,
                int(self.config["api_id"]),
                self.config["api_hash"],
                proxy=proxy_tuple
            )
            await client.connect()

            if not await client.is_user_authorized():
                await self._move_session(fname, self.nonworking_folder, "not_authorized")
                await client.disconnect()
                return None

            spam_status = await self.check_spam_status(client)
            if spam_status != "active":
                await self._move_session(fname, self.nonworking_folder, f"spam_{spam_status}")
                await client.disconnect()
                return None

            # Тестовая отправка себе сообщения
            me = await client.get_me()
            try:
                test_msg = await client.send_message(me, "test")
                await test_msg.delete()
            except Exception as e:
                await self._move_session(fname, self.nonworking_folder, f"not_working_{type(e).__name__}")
                await client.disconnect()
                return None

            # Настройка ChatManager при включенном auto_hide_chats
            if self.config.get('auto_hide_chats', False):
                client.chat_manager = ChatManager(client)
                client.chat_manager.auto_delete_delay = self.config.get('auto_delete_delay', 4)

            client.sent_users = set()
            proxy_info_str = f"{proxy_info[0]}://{proxy_info[1]}:{proxy_info[2]}" if proxy_info else "без прокси"
            print(f"✅ {me.first_name} ({me.phone}) -> {proxy_info_str}")
            return client

        except Exception as e:
            print(f"🚫 Ошибка загрузки сессии {fname}: {e}")
            if client:
                await client.disconnect()
            await self._move_session(fname, self.nonworking_folder, f"load_error_{type(e).__name__}")
            return None

    async def _move_session(self, session_file, target_folder, reason=""):
        """Перемещает файлы сессии в указанную папку с подпапкой по причине"""
        try:
            base_name = os.path.splitext(session_file)[0]
            reason_folder = os.path.join(target_folder, reason.replace(" ", "_"))
            os.makedirs(reason_folder, exist_ok=True)

            moved = 0
            for ext in ['.session', '.session-journal']:
                src = os.path.join(self.session_folder, base_name + ext)
                if os.path.exists(src):
                    shutil.move(src, os.path.join(reason_folder, base_name + ext))
                    moved += 1

            if moved > 0:
                print(f"📦 Сессия {session_file} перемещена -> {reason_folder}")
            else:
                print(f"⚠️ Файлы сессии {session_file} не найдены")
        except Exception as e:
            print(f"❌ Ошибка перемещения {session_file}: {e}")

    async def check_spam_status(self, client):
        """Проверка статуса сессии через тестовую отправку"""
        try:
            me = await client.get_me()
            try:
                test_msg = await client.send_message(me, "test")
                await test_msg.delete()
                return "active"
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ['ban', 'block', 'spam', 'deactivated']):
                    return "banned"
                elif 'flood' in err:
                    return "flood_wait"
                else:
                    return f"send_error_{type(e).__name__}"
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ['auth', 'session', 'invalid']):
                return "invalid_session"
            elif 'phone' in err:
                return "phone_banned"
            return f"unknown_error_{type(e).__name__}"

    async def safe_send_message(self, client, entity, message):
        """Отправка сессией с задержками и обработкой FloodWait"""
        session_id = client.session.filename
        if session_id in self.last_action_time:
            elapsed = time.time() - self.last_action_time[session_id]
            delay = random.uniform(3, 7)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

        try:
            await client.send_message(entity, message)
            self.last_action_time[session_id] = time.time()
            return True
        except FloodWaitError as e:
            print(f"⏳ Flood wait {e.seconds}s для {session_id}")
            await asyncio.sleep(e.seconds + 5)
            return False
        except Exception as e:
            print(f"❌ Ошибка отправки для {session_id}: {e}")
            return False

    async def get_session_stats(self):
        stats = {"total": len(self.sessions), "active": 0, "with_chat_manager": 0}
        for client in self.sessions:
            try:
                if await client.is_user_authorized():
                    stats["active"] += 1
                if hasattr(client, 'chat_manager'):
                    stats["with_chat_manager"] += 1
            except:
                pass
        return stats

    async def get_detailed_stats(self):
        stats = {
            'total_sessions': len(self.sessions),
            'active_sessions': 0,
            'nonworking_count': self._count_files(self.nonworking_folder),
            'suspicious_count': self._count_files(self.suspicious_folder),
            'problem_sessions': len(self.problem_sessions)
        }
        for client in self.sessions:
            if await client.is_user_authorized():
                stats['active_sessions'] += 1
        return stats

    def _count_files(self, folder):
        if not os.path.exists(folder):
            return 0
        return sum(1 for f in os.listdir(folder) if f.endswith(".session"))

    async def cleanup_sessions(self):
        """Повторная проверка и организация сессий"""
        print("🧹 Организация сессий...")
        session_files = self._get_session_files()
        for session_file in session_files:
            try:
                client = await self._create_session_task(session_file, None)
                if client:
                    await client.disconnect()
            except:
                pass
        print("✅ Организация сессий завершена")
