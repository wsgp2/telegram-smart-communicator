import os
import asyncio
import aiohttp
from datetime import datetime
from telethon import TelegramClient
from config import load_config, update_config_timestamp
from proxy_manager import ProxyManager


class SessionManager:
    def __init__(self, session_folder="sessions"):
        self.session_folder = session_folder
        self.sessions = []
        self.last_loaded_count = 0
        self.config = load_config()
        self.proxy_manager = ProxyManager()

    async def load_sessions(self, force_reload=False):
        """Загружает сессии, проверяя изменения"""
        current_files = self._get_session_files()

        if not force_reload and len(current_files) == self.last_loaded_count:
            return self.sessions

        print("🔄 Loading sessions...")
        self.sessions = await self._load_all_sessions(current_files)
        self.last_loaded_count = len(self.sessions)

        update_config_timestamp("last_session_check")
        return self.sessions

    async def reload_sessions_if_needed(self):
        """Перезагружает сессии если нужно"""
        if not self.config.get("auto_check_new_sessions", True):
            return self.sessions

        last_check = self.config.get("last_session_check")
        if last_check:
            try:
                last_check_dt = datetime.fromisoformat(last_check)
                check_interval = self.config.get("check_interval_minutes", 5)
                if (datetime.now() - last_check_dt).total_seconds() < check_interval * 60:
                    return self.sessions
            except:
                pass

        return await self.load_sessions()

    def _get_session_files(self):
        if not os.path.exists(self.session_folder):
            os.makedirs(self.session_folder)
            return []

        return [f for f in os.listdir(self.session_folder) if f.endswith(".session")]

    async def _load_all_sessions(self, session_files):
        proxies = self.proxy_manager.load_india_proxies()
        assigned_proxies = self.proxy_manager.assign_proxies_to_sessions(
            session_files, proxies, self.config["accounts_per_proxy"]
        )

        sessions = []
        tasks = []

        for idx, fname in enumerate(session_files):
            proxy_info = assigned_proxies[idx] if idx < len(assigned_proxies) else None
            task = self._create_session_task(fname, proxy_info)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, TelegramClient):
                sessions.append(result)

        print(f"✅ Loaded {len(sessions)} sessions")
        return sessions

    async def _create_session_task(self, fname, proxy_info):
        name = os.path.splitext(fname)[0]
        session_path = os.path.join(self.session_folder, name)

        try:
            if proxy_info:
                proxy_tuple = self.proxy_manager.create_proxy_tuple(proxy_info)
                client = TelegramClient(
                    session_path,
                    int(self.config["api_id"]),
                    self.config["api_hash"],
                    proxy=proxy_tuple
                )
            else:
                client = TelegramClient(
                    session_path,
                    int(self.config["api_id"]),
                    self.config["api_hash"]
                )

            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                return None

            me = await client.get_me()
            client.sent_users = set()

            if self.config.get('auto_hide_chats', False):
                from chat_manager import ChatManager
                client.chat_manager = ChatManager(client)
                client.chat_manager.auto_delete_delay = self.config.get('auto_delete_delay', 4)

            if proxy_info:
                proxy_type, host, port, user, pwd = proxy_info
                print(f"✅ {me.first_name} ({me.phone}) -> {proxy_type}://{host}:{port}")
            else:
                print(f"✅ {me.first_name} ({me.phone}) -> no proxy")

            return client

        except Exception as e:
            print(f"❌ Error loading {fname}: {e}")
            return None

    async def get_session_stats(self):
        stats = {
            "total": len(self.sessions),
            "active": 0,
            "with_chat_manager": 0
        }

        for client in self.sessions:
            try:
                if await client.is_user_authorized():
                    stats["active"] += 1
                if hasattr(client, 'chat_manager'):
                    stats["with_chat_manager"] += 1
            except:
                pass

        return stats

    async def create_new_session(self, phone_number):
        session_name = f"{phone_number[1:].replace('+', '')}"
        session_path = os.path.join(self.session_folder, session_name)

        client = TelegramClient(
            session_path,
            int(self.config["api_id"]),
            self.config["api_hash"]
        )

        try:
            await client.connect()
            await client.send_code_request(phone_number)

            code = input(f"Enter code for {phone_number}: ").strip()
            await client.sign_in(phone_number, code)

            me = await client.get_me()
            print(f"✅ Session created for {me.first_name} ({me.phone})")

            await client.disconnect()
            return True

        except Exception as e:
            if "Two steps verification" in str(e) or "password" in str(e).lower():
                password = input("Enter 2FA password: ").strip()
                await client.sign_in(password=password)
                await client.disconnect()
                return True
            print(f"❌ Error creating session: {e}")
            await client.disconnect()
            return False