#!/usr/bin/env python3
"""
📡 ListenerConsole - прослушка входящих сообщений с автоответчиком
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telethon import events
from config import load_config
from notification_bot import init_notification_bot, notification_bot
from auto_responder import init_auto_responder, get_auto_responder


class ListenerConsole:
    def __init__(self):
        self.sessions = []
        self.is_listening = False
        self.session_manager = None  # Добавляем ссылку на менеджер сессий

    async def setup_listeners(self, sessions, session_manager=None):
        """Настройка обработчиков для всех сессий"""
        self.sessions = sessions
        self.session_manager = session_manager
        self.is_listening = True
        print("🎧 Настройка прослушки...")
        print("=" * 60)

        async def setup_client(client):
            try:
                me = await client.get_me()
                client.sent_users = set()

                # Загружаем обработанных пользователей
                from user_manager import UserManager
                user_manager = UserManager()
                users_data = await user_manager.load_all_users()
                processed_users = users_data.get("processed", [])

                # Добавляем их в кэш
                for user in processed_users:
                    try:
                        entity = await client.get_entity(user)
                        client.sent_users.add(entity.id)
                    except:
                        continue

                # Создаем обработчик
                self._create_message_handler(client)
                print(f"✅ {me.first_name}: готов к прослушке")
                return len(processed_users)
            except Exception as e:
                print(f"❌ Ошибка настройки клиента: {e}")
                return 0

        counts = await asyncio.gather(*[setup_client(c) for c in sessions])
        total_users = sum(counts)

        print(f"\n🎯 Прослушиваем {total_users} пользователей")
        print("💬 Все ответы будут здесь и в Telegram-боте")
        print("=" * 60)

    def _create_message_handler(self, client):
        """Создает обработчик сообщений с выводом в консоль и ботом"""
        auto_responder = get_auto_responder()

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            try:
                sender = await event.get_sender()
                if not sender:
                    return

                if sender.id not in client.sent_users:
                    return

                text = event.raw_text
                me = await client.get_me()
                timestamp = datetime.now().strftime("%H:%M:%S")

                # Вывод в консоль
                print(f"\n[{timestamp}] 📩 {sender.first_name} -> {me.first_name}: {text}")
                print("─" * 60)

                # Отправка уведомления в бот
                if notification_bot:
                    account_info = {'phone': me.phone or 'Unknown', 'name': me.first_name or 'Unknown'}
                    sender_info = {'name': sender.first_name or 'Unknown', 'username': sender.username or 'No username'}
                    asyncio.create_task(notification_bot.send_notification(account_info, sender_info, text))

                # Автоответчик - используем текущего клиента для ответа
                if auto_responder:
                    asyncio.create_task(self._handle_auto_response(client, sender, text))

                # Удаляем сообщение у себя
                try:
                    await event.message.delete(revoke=False)
                except:
                    pass

            except Exception as e:
                print(f"❌ Ошибка обработки сообщения: {e}")

    async def _handle_auto_response(self, client, sender, text):
        """Асинхронная обработка автоответа через AutoResponder"""
        auto_responder = get_auto_responder()
        if not auto_responder:
            return

        try:
            response = await auto_responder.handle_message(str(sender.id), text)
            if response:
                # Используем текущего клиента для отправки ответа
                await client.send_message(sender.id, response)
                print(f"🤖 Автоответ отправлен {sender.first_name}: {response}")

                # Также уведомляем в бота
                if notification_bot:
                    me = await client.get_me()
                    account_info = {'phone': me.phone or 'Unknown', 'name': me.first_name or 'Unknown'}
                    sender_info = {'name': sender.first_name or 'Unknown', 'username': sender.username or 'No username'}
                    asyncio.create_task(notification_bot.send_notification(
                        account_info, sender_info, f"🤖 Автоответ: {response}", is_auto_response=True
                    ))
        except Exception as e:
            print(f"❌ Ошибка автоответчика: {e}")

    async def start_listening(self):
        """Запуск прослушивания всех сессий"""
        if not self.sessions:
            print("❌ Нет сессий для прослушивания!")
            return

        print("\n🚀 Запуск прослушки... Нажмите Ctrl+C для остановки")
        print("=" * 60)

        try:
            await asyncio.gather(*[client.run_until_disconnected() for client in self.sessions])
        except KeyboardInterrupt:
            print("\n🛑 Прослушивание остановлено")
        except Exception as e:
            print(f"❌ Ошибка прослушивания: {e}")


async def main():
    print("📡 Загрузка консоли прослушки")
    print("=" * 60)
    init_notification_bot()
    config = load_config()
    from session_manager import SessionManager
    session_manager = SessionManager()
    sessions = await session_manager.load_sessions()
    if not sessions:
        print("❌ Нет доступных сессий!")
        return

    init_auto_responder(config, session_manager)

    ar = get_auto_responder()
    if ar :
        print(f"🤖 Автоответчик включен ")
    else:
        print("🤖 Автоответчик выключен")

    listener = ListenerConsole()
    await listener.setup_listeners(sessions, session_manager)
    await listener.start_listening()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Завершение работы консоли прослушки")
