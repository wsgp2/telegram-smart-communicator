#!/usr/bin/env python3
"""
📡 ОТДЕЛЬНАЯ КОНСОЛЬ ДЛЯ ПРОСЛУШКИ
Запускается в отдельном окне и показывает все ответы
"""
import asyncio
import os
import sys
from datetime import datetime

# Добавляем путь для импортов
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telethon import events
from notification_bot import init_notification_bot, notification_bot


class ListenerConsole:
    def __init__(self):
        self.sessions = []
        self.is_listening = False

    async def setup_listeners(self, sessions):
        """Настройка обработчиков для всех сессий"""
        self.sessions = sessions
        self.is_listening = True

        print("🎧 НАСТРОЙКА ПРОСЛУШКИ")
        print("=" * 60)

        for client in sessions:
            try:
                me = await client.get_me()
                client.sent_users = set()  # Очищаем старые данные

                # Загружаем обработанных пользователей
                from user_manager import UserManager
                user_manager = UserManager()
                users_data = await user_manager.load_all_users()
                processed_users = users_data["processed"]

                # Добавляем обработанных пользователей
                for user in processed_users:
                    try:
                        entity = await client.get_entity(user)
                        client.sent_users.add(entity.id)
                    except Exception as e:
                        print(f"⚠️ Не удалось добавить {user}: {e}")

                # Создаем обработчик
                self._create_message_handler(client)
                print(f"✅ {me.first_name}: готов к прослушке")

            except Exception as e:
                print(f"❌ Ошибка настройки {client}: {e}")

        print(f"\n🎯 Прослушиваем {len(processed_users)} пользователей")
        print("💬 Все ответы будут здесь и в Telegram-боте")
        print("=" * 60)

    def _create_message_handler(self, client):
        """Создает обработчик сообщений с выводом в консоль и бота"""

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            try:
                sender = await event.get_sender()
                text = event.raw_text

                if not sender:
                    return

                # Получаем информацию о нашем аккаунте
                me = await event.client.get_me()

                # 🔥 ВЫВОД В КОНСОЛЬ (это окно)
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{timestamp}] 📩 {sender.first_name} -> {me.first_name}:")
                print(f"   💬 {text}")
                print("   " + "─" * 50)

                # 🔥 ОТПРАВКА В БОТА
                if notification_bot:
                    account_info = {
                        'phone': me.phone or 'Unknown',
                        'name': me.first_name or 'Unknown'
                    }
                    sender_info = {
                        'name': sender.first_name or 'Unknown',
                        'username': sender.username or 'No username'
                    }

                    await notification_bot.send_notification(account_info, sender_info, text)

                # 🗑️ Удаляем сообщение у себя
                try:
                    await event.message.delete(revoke=False)
                except:
                    pass

            except Exception as e:
                print(f"❌ Ошибка обработки: {e}")

    async def start_listening(self):
        """Запуск прослушивания"""
        if not self.sessions:
            print("❌ Нет сессий для прослушивания!")
            return

        print("\n🚀 ЗАПУСК ПРОСЛУШКИ...")
        print("Нажмите Ctrl+C для остановки")
        print("=" * 60)

        try:
            await asyncio.gather(*[client.run_until_disconnected() for client in self.sessions])
        except KeyboardInterrupt:
            print("\n🛑 Прослушивание остановлено")
        except Exception as e:
            print(f"❌ Ошибка прослушивания: {e}")


async def main():
    """Главная функция"""
    print("📡 ЗАГРУЗКА КОНСОЛИ ПРОСЛУШКИ")
    print("=" * 60)

    # Инициализируем бота
    init_notification_bot()

    # Загружаем сессии
    from session_manager import SessionManager
    session_manager = SessionManager()
    sessions = await session_manager.load_sessions()

    if not sessions:
        print("❌ Нет доступных сессий!")
        return

    # Настраиваем и запускаем прослушку
    listener = ListenerConsole()
    await listener.setup_listeners(sessions)
    await listener.start_listening()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Завершение работы консоли прослушки")
