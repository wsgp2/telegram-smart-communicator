import os
import asyncio
import aiofiles
from datetime import datetime
from config import load_config, update_config_timestamp
from session_manager import SessionManager


class UserManager:
    def __init__(self):
        self.config = load_config()
    async def check_for_new_users(self):
        new_users = await self.load_users_async(self.config["new_users_file"])
        return len(new_users) > 0

    async def load_all_users(self):
        target_users = await self.load_users_async(self.config["target_users_file"])
        processed_users = await self.load_users_async(self.config["processed_users_file"])
        new_users = await self.load_users_async(self.config["new_users_file"])
        pending_users = await self.load_users_async(self.config["pending_users_file"])
        phone_numbers = await self.load_users_async(self.config["phone_numbers_file"])

        return {
            "target": target_users,
            "processed": processed_users,
            "new": new_users,
            "pending": pending_users,
            "phones": phone_numbers,
            "available": list(set(target_users) - set(processed_users))
        }

        users_data = {}
        for key, path in files.items():
            users_data[key] = await self.load_users_async(path)

        users_data["available"] = list(set(users_data["target"]) - set(users_data["processed"]))
        return users_data

    async def load_users_async(self, users_file):
        """Асинхронная загрузка списка пользователей из файла"""
        if not os.path.exists(users_file):
            return []

        try:
            async with aiofiles.open(users_file, "r", encoding="utf-8") as f:
                lines = await f.readlines()
                return [line.strip() for line in lines if line.strip()]
        except Exception as e:
            print(f"❌ Ошибка загрузки {users_file}: {e}")
            return []

    async def save_users_async(self, users_file, users):
        """Асинхронное сохранение списка пользователей в файл"""
        try:
            async with aiofiles.open(users_file, "w", encoding="utf-8") as f:
                for user in users:
                    await f.write(f"{user}\n")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения {users_file}: {e}")
            return False

    async def mark_as_processed(self, users):
        """Помечает пользователей как обработанных"""
        if not users:
            return
        processed = await self.load_users_async(self.config["processed_users_file"])
        processed.extend(users)
        await self.save_users_async(self.config["processed_users_file"], list(set(processed)))
        print(f"✅ Помечено как обработанные: {len(users)} пользователей")

    async def add_new_users(self, new_users):
        """Добавляет новых пользователей в файл new_users"""
        if not new_users:
            return False
        current_new = await self.load_users_async(self.config["new_users_file"])
        current_new.extend(new_users)
        await self.save_users_async(self.config["new_users_file"], list(set(current_new)))
        return True

    async def move_new_to_target(self):
        """Переносит новых пользователей в основной список target"""
        new_users = await self.load_users_async(self.config["new_users_file"])
        if not new_users:
            return 0

        target_users = await self.load_users_async(self.config["target_users_file"])
        target_users.extend(new_users)
        await self.save_users_async(self.config["target_users_file"], list(set(target_users)))
        await self.save_users_async(self.config["new_users_file"], [])
        return len(new_users)

    async def get_available_users_count(self):
        """Возвращает количество доступных для обработки пользователей"""
        target = await self.load_users_async(self.config["target_users_file"])
        processed = await self.load_users_async(self.config["processed_users_file"])
        return len(set(target) - set(processed))

    async def calculate_distribution(self, sessions_count: int, messages_per_account: int, max_per_account: int = None):
        available_count = await self.get_available_users_count()

        if max_per_account is None:
            max_per_account = self.config.get("max_messages_per_account", 10)

        max_capacity = sessions_count * max_per_account
        required_capacity = available_count

        if required_capacity <= max_capacity:
            actual_per_account = min(max_per_account, (required_capacity + sessions_count - 1) // sessions_count)
            needed_sessions = 0
        else:
            actual_per_account = max_per_account
            needed_sessions = (required_capacity - max_capacity + max_per_account - 1) // max_per_account

        return {
            "available_users": available_count,
            "current_sessions": sessions_count,
            "max_per_account": max_per_account,
            "required_capacity": required_capacity,
            "max_capacity": max_capacity,
            "actual_per_account": actual_per_account,
            "needed_sessions": needed_sessions,
            "can_send": required_capacity <= max_capacity
        }

    async def convert_phones_to_usernames(self):
        """Конвертирует номера телефонов в username'ы через первую доступную сессию"""
        phones = await self.load_users_async(self.config["phone_numbers_file"])
        if not phones:
            print("❌ Нет номеров для конвертации!")
            return 0

        session_manager = SessionManager()
        sessions = await session_manager.load_sessions()
        if not sessions:
            print("❌ Нет доступных сессий!")
            return 0

        client = sessions[0]
        converted, failed_numbers = [], []

        for phone in phones:
            try:
                formatted_phone = self._format_phone_number(phone)
                entity = await self._find_entity_by_phone(client, formatted_phone)
                if entity:
                    username = self._get_username_from_entity(entity)
                    converted.append(username)
                    print(f"✅ {formatted_phone} -> {username}")
                else:
                    failed_numbers.append(phone)
                    print(f"❌ Не найден: {formatted_phone}")
                await asyncio.sleep(2)
            except Exception as e:
                failed_numbers.append(phone)
                print(f"❌ Ошибка конвертации {phone}: {e}")
                await asyncio.sleep(5)

        if converted:
            await self.add_new_users(converted)
            print(f"✅ Успешно сконвертировано: {len(converted)} номеров")
        if failed_numbers:
            await self.save_users_async("data/failed_numbers.txt", failed_numbers)
            print(f"⚠️ Не удалось конвертировать: {len(failed_numbers)} номеров")

        await self.save_users_async(self.config["phone_numbers_file"], [])
        return len(converted)

    def _format_phone_number(self, phone):
        clean = ''.join(filter(str.isdigit, str(phone)))
        if clean.startswith('7') and len(clean) == 11:
            return '+' + clean
        elif clean.startswith('8') and len(clean) == 11:
            return '+7' + clean[1:]
        elif len(clean) == 10:
            return '+7' + clean
        else:
            return '+' + clean

    async def _find_entity_by_phone(self, client, phone):
        """Поиск entity по телефону разными способами"""
        try:
            try:
                return await client.get_entity(phone)
            except:
                pass

            from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
            from telethon.tl.types import InputPhoneContact

            contact = InputPhoneContact(client_id=0, phone=phone, first_name="Temp", last_name="User")
            result = await client(ImportContactsRequest([contact]))
            if result.users:
                entity = result.users[0]
                if result.imported:
                    await client(DeleteContactsRequest([entity]))
                return entity

            # Поиск через контакты
            from telethon.tl.functions.contacts import SearchRequest
            search_result = await client(SearchRequest(q=phone, limit=10))
            for user in search_result.users:
                if hasattr(user, 'phone') and user.phone == phone.replace('+', ''):
                    return user
            return None
        except Exception as e:
            print(f"❌ Ошибка поиска {phone}: {e}")
            return None

    def _get_username_from_entity(self, entity):
        if hasattr(entity, 'username') and entity.username:
            return f"@{entity.username}"
        elif hasattr(entity, 'id'):
            return str(entity.id)
        return f"user_{hash(entity)}"
