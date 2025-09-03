import os
import asyncio
import aiofiles
from datetime import datetime
from config import load_config, update_config_timestamp


class UserManager:
    def __init__(self):
        self.config = load_config()

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

    async def load_users_async(self, users_file):
        if not os.path.exists(users_file):
            return []

        try:
            async with aiofiles.open(users_file, "r", encoding="utf-8") as f:
                content = await f.read()
                return [line.strip() for line in content.splitlines() if line.strip()]
        except Exception as e:
            print(f"Error loading users from {users_file}: {e}")
            return []

    async def save_users_async(self, users_file, users):
        try:
            async with aiofiles.open(users_file, "w", encoding="utf-8") as f:
                for user in users:
                    await f.write(f"{user}\n")
            return True
        except Exception as e:
            print(f"Error saving users to {users_file}: {e}")
            return False

    async def mark_as_processed(self, users):
        processed = await self.load_users_async(self.config["processed_users_file"])
        processed.extend(users)
        await self.save_users_async(self.config["processed_users_file"], list(set(processed)))

    async def add_new_users(self, new_users):
        if not new_users:
            return False

        current_new = await self.load_users_async(self.config["new_users_file"])
        current_new.extend(new_users)
        await self.save_users_async(self.config["new_users_file"], list(set(current_new)))
        return True

    async def move_new_to_target(self):
        new_users = await self.load_users_async(self.config["new_users_file"])
        if not new_users:
            return 0

        target_users = await self.load_users_async(self.config["target_users_file"])
        target_users.extend(new_users)
        await self.save_users_async(self.config["target_users_file"], list(set(target_users)))

        await self.save_users_async(self.config["new_users_file"], [])

        return len(new_users)

    async def check_for_new_users(self):
        new_users = await self.load_users_async(self.config["new_users_file"])
        return len(new_users) > 0

    async def check_for_new_phones(self):
        phones = await self.load_users_async(self.config["phone_numbers_file"])
        return len(phones) > 0

    async def get_available_users_count(self):
        target_users = await self.load_users_async(self.config["target_users_file"])
        processed_users = await self.load_users_async(self.config["processed_users_file"])
        return len(set(target_users) - set(processed_users))

    async def calculate_distribution(self, sessions_count, messages_per_account, max_per_account=None):
        available_count = await self.get_available_users_count()

        if max_per_account is None:
            max_per_account = self.config.get("max_messages_per_account", 10)

        max_capacity = sessions_count * max_per_account
        required_capacity = available_count

        if required_capacity <= max_capacity:
            actual_per_account = min(max_per_account,
                                     (required_capacity + sessions_count - 1) // sessions_count)
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
        phones = await self.load_users_async(self.config["phone_numbers_file"])
        if not phones:
            print("❌ No phone numbers found")
            return 0

        from session_manager import SessionManager
        session_manager = SessionManager()
        sessions = await session_manager.load_sessions()

        if not sessions:
            print("❌ No sessions available for conversion")
            return 0

        converted = []
        client = sessions[0]

        for phone in phones:
            try:
                entity = await client.get_entity(phone)
                username = f"@{entity.username}" if entity.username else str(entity.id)
                converted.append(username)
                print(f"✅ Converted {phone} -> {username}")
            except Exception as e:
                print(f"❌ Failed to convert {phone}: {e}")

        if converted:
            await self.add_new_users(converted)
            await self.save_users_async(self.config["phone_numbers_file"], [])

        print(f"✅ Converted {len(converted)} numbers")
        return len(converted)
