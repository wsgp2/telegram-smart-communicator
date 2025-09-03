#!/usr/bin/env python3
import asyncio
import random
import time
from telethon.errors import FloodWaitError
from utils import load_messages_from_file, log_error, log_info
from user_manager import UserManager


class MessageHandler:
    def __init__(self, config=None):
        self.user_manager = UserManager()
        self.config = config or self._load_config()
        self.messages = []
        self.max_retries = 3
        self.retry_delay = 30

    async def initialize(self):
        """Загрузка сообщений из файла"""
        try:
            messages_file = self.config.get("messages_file", "data/messages.txt")
            self.messages = await load_messages_from_file(messages_file)
            if not self.messages:
                log_error("Не удалось загрузить сообщения")
                return False
            log_info(f"Загружено {len(self.messages)} сообщений")
            return True
        except Exception as e:
            log_error(f"Ошибка инициализации MessageHandler: {e}")
            return False

    def _load_config(self):
        try:
            import json
            with open("config.json", "r") as f:
                return json.load(f)
        except Exception:
            return {}

    async def send_messages(self, sessions, users, message, delay_ms, msgs_per_acc):
        if not users or not sessions:
            log_info("Нет пользователей или сессий для отправки")
            return 0

        if not self.messages:
            success = await self.initialize()
            if not success:
                log_error("Не удалось загрузить сообщения для отправки")
                return 0

        total_sent = 0
        random.shuffle(users)

        tasks = [self._send_for_client(client, users, message, delay_ms, msgs_per_acc)
                 for client in sessions]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, int):
                total_sent += result
            elif isinstance(result, Exception):
                log_error(f"Ошибка при отправке: {result}")

        log_info(f"Всего отправлено сообщений: {total_sent}")
        return total_sent

    async def _send_for_client(self, client, users, message, delay_ms, msgs_per_acc):
        sent_count = 0

        try:
            me = await client.get_me()
            client_name = me.first_name if me else "Unknown"
        except Exception:
            print("❌ Не удалось получить информацию о клиенте, пропускаем сессию")
            return 0

        for _ in range(min(msgs_per_acc, len(users))):
            if not users:
                break

            target = users.pop()
            try:
                entity = await client.get_entity(target)
                random_message = random.choice(self.messages) if self.messages else message

                success = await self.send_with_retry(client, entity, random_message)
                if not success:
                    users.append(target)
                    break
                print(f"✅ {client_name} -> {target}")
                await self.user_manager.mark_as_processed([target])
                if hasattr(client, 'chat_manager'):
                    try:
                        await client.chat_manager.hide_chat(target)
                    except Exception as e:
                        print(f"⚠️ Ошибка скрытия чата {target}: {e}")

                sent_count += 1

                # Задержка с рандомизацией
                await asyncio.sleep(max(0.1, delay_ms / 1000.0 + random.uniform(-0.3, 0.3)))

            except Exception as e:
                print(f"❌ Ошибка обработки {target}: {e}")
                users.append(target)
                # При ошибке получения entity тоже прерываем сессию
                break

        return sent_count

    async def send_with_retry(self, client, entity, message):
        try:
            await client.send_message(entity, message)
            return True
        except FloodWaitError as e:
            print(f"⏳ Flood wait {e.seconds} сек, пропускаем сессию")
            return False
        except Exception as e:
            err_text = str(e).lower()
            if any(k in err_text for k in ['ban', 'block', 'spam', 'deactivated', 'unauthorized']):
                print(f"🚫 Критическая ошибка сессии: {e}")
            else:
                print(f"❌ Ошибка отправки: {e}")
            return False

    @staticmethod
    def is_telegram_service_message(event, sender):
        """Проверка на системные сообщения Telegram"""
        if not sender or not event or not getattr(event, 'message', None):
            return False

        text = getattr(event.message, 'text', '').lower()
        if getattr(sender, 'id', 0) in [777000, 42777]:
            return True
        if getattr(sender, 'phone', '') == '42777':
            return True
        if getattr(sender, 'username', '').lower() == 'telegram':
            return True

        service_patterns = [
            'код для входа в telegram', 'login code for telegram',
            'your telegram code', 'ваш код telegram',
            'new login to your telegram account', 'новый вход в ваш аккаунт telegram'
        ]
        return any(p in text for p in service_patterns)
