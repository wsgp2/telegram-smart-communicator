#!/usr/bin/env python3
"""
MASS SENDER С УВЕДОМЛЕНИЯМИ И УПРАВЛЕНИЕМ ЧАТАМИ
Главный модуль системы с меню и автоматическим управлением
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from session_manager import SessionManager
from user_manager import UserManager
from message_handler import MessageHandler
from notification_bot import init_notification_bot, notification_bot
from config import load_config, save_config

class MassSender:
    def __init__(self):
        self.config = load_config()
        self.session_manager = SessionManager()
        self.user_manager = UserManager()
        self.message_handler = MessageHandler()
        self.active_sessions = []
        self.background_listener = None
        self.shutdown_called = False
        self.auto_responder = None

    async def initialize(self):
        """Инициализация системы"""
        print("🚀 Инициализация Mass Sender...")
        os.makedirs("sessions", exist_ok=True)
        os.makedirs("proxies", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        # Инициализация бота уведомлений
        init_notification_bot()


        print("✅ Система инициализирована")

    async def show_menu(self):
        """Главное меню системы"""
        menu_options = [
            "🎯 Запустить рассылку",
            "📊 Показать статус системы",
            "🔄 Перезагрузить сессии",
            "📱 Конвертировать номера телефонов",
            "⚙️  Настройки",
            "📥 Добавить пользователей вручную",
            "🔍 Проверить новые ресурсы",
            "🗂️ Управление чатами",
            "🧹 Очистка и организация сессий",
            "📊 Детальная статистика сессий",
            "❌ Выход"
        ]

        while True:
            print("\n" + "=" * 60)
            print("🤖 MASS SENDER")
            print("=" * 60)
            for i, option in enumerate(menu_options, 1):
                print(f"{i}. {option}")
            print("=" * 60)

            try:
                choice = input("Выберите опцию: ").strip()
                await self.handle_menu_choice(choice)
            except KeyboardInterrupt:
                print("\n🛑 Прервано пользователем")
                await self.shutdown()
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")

    async def handle_menu_choice(self, choice):
        """Обработка выбора меню"""
        mapping = {
            "1": self.start_sending_campaign,
            "2": self.show_system_status,
            "3": self.reload_sessions,
            "4": self.convert_phone_numbers,
            "5": self.edit_settings,
            "6": self.add_users_manually,
            "7": self.check_new_resources,
            "8": self.chat_management,
            "9": self.cleanup_sessions,
            "10": self.show_detailed_session_stats,
            "0": self.shutdown
        }

        action = mapping.get(choice)
        if not action:
            print("❌ Неверный выбор")
            return

        if asyncio.iscoroutinefunction(action):
            await action()
        else:
            action()

    async def start_sending_campaign(self):
        """Запуск рассылки"""
        print("\n🎯 ЗАПУСК РАССЫЛКИ\n" + "=" * 50)
        sessions = await self.session_manager.load_sessions()
        if not sessions:
            print("❌ Нет доступных сессий!")
            return
        users_data = await self.user_manager.load_all_users()
        available_users = users_data.get("available", [])
        if not available_users:
            print("❌ Нет пользователей для отправки!")
            return

        distribution = await self.user_manager.calculate_distribution(
            len(sessions),
            self.config.get("messages_per_account", 2),
            self.config.get("max_messages_per_account", 10)
        )
        confirm = input(f"\nОтправить {distribution['available_users']} сообщений? (y/n): ").lower()
        if confirm != 'y':
            print("❌ Отменено")
            return

        sent_count = await self.message_handler.send_messages(
            sessions,
            available_users,
            self.config.get("message", "Привет!"),
            self.config.get("delay_ms", 1000),
            distribution.get("actual_per_account", 1)
        )
        print(f"\n✅ Готово! Отправлено: {sent_count} сообщений")
        print("💬 Ответы пользователей будут приходить в Telegram-бота")

    async def show_system_status(self):
        """Показать статус системы"""
        print("\n📊 СТАТУС СИСТЕМЫ\n" + "=" * 50)
        sessions = await self.session_manager.load_sessions()
        users_data = await self.user_manager.load_all_users()

        stats = await self.session_manager.get_session_stats()
        print(f"🔧 Сессии: {stats['total']} (активных: {stats['active']})")

        print(f"👥 Пользователи:")
        for key in ['target', 'processed', 'new', 'phones', 'available']:
            print(f"   • {key.capitalize()}: {len(users_data.get(key, []))}")

        distribution = await self.user_manager.calculate_distribution(len(sessions),
                                                                      self.config.get("messages_per_account", 2))
        self._print_distribution_info(distribution)

        bot_status = "✅ Активен" if notification_bot else "❌ Неактивен"
        print(f"🤖 Бот уведомлений: {bot_status}")

    # ---------------------------
    # Старые методы, которые отсутствовали
    # ---------------------------
    async def reload_sessions(self):
        print("🔄 Перезагрузка сессий...")
        await self.session_manager.load_sessions()
        print("✅ Сессии перезагружены")

    async def convert_phone_numbers(self):
        print("📱 Конвертация номеров...")
        count = await self.user_manager.convert_phones_to_usernames()
        print(f"✅ Конвертировано {count} номеров")

    async def edit_settings(self):
        print("⚙️  Настройки")
        print("⚠️ Редактирование настроек временно недоступно")

    async def add_users_manually(self):
        print("📥 Добавление пользователей вручную")
        users = input("Введите пользователей через запятую: ").split(",")
        users = [u.strip() for u in users if u.strip()]
        if users:
            await self.user_manager.add_new_users(users)
            print(f"✅ Добавлено {len(users)} пользователей")
        else:
            print("❌ Нечего добавлять")

    async def check_new_resources(self):
        print("🔍 Проверка новых ресурсов")
        has_new = await self.user_manager.check_for_new_users()
        print(f"✅ Новые пользователи: {'Да' if has_new else 'Нет'}")

    async def chat_management(self):
        print("🗂️ Управление чатами")
        print("⚠️ Управление чатами временно недоступно")

    async def cleanup_sessions(self):
        print("🧹 Очистка сессий")
        removed = 0
        for user_id, ctx in list(self.auto_responder.conversations.items()):
            if ctx.status == "completed":
                del self.auto_responder.conversations[user_id]
                removed += 1
        print(f"✅ Удалено {removed} завершенных разговоров")

    async def show_detailed_session_stats(self):
        print("📊 Детальная статистика сессий")
        sessions = await self.session_manager.load_sessions()
        for idx, session in enumerate(sessions, 1):
            print(f"   • Сессия {idx}: {session}")

    async def shutdown(self):
        """Корректное завершение работы"""
        if self.shutdown_called:
            return
        self.shutdown_called = True
        print("\n📴 Завершение работы Mass Sender...")

        sessions = self.session_manager.sessions + self.active_sessions
        for client in sessions:
            try:
                await client.disconnect()
            except:
                pass

        if notification_bot:
            await notification_bot.send_shutdown_notification()
        print("✅ Система корректно остановлена")

    def _print_distribution_info(self, distribution):
        """Вывод распределения пользователей и сообщений"""
        print(f"\n📊 РАСПРЕДЕЛЕНИЕ:")
        print(f"   • Доступно пользователей: {distribution.get('available_users',0)}")
        print(f"   • Текущие сессии: {distribution.get('current_sessions',0)}")
        print(f"   • Макс. на аккаунт: {distribution.get('max_per_account',0)}")
        can_send = "✅ ДА" if distribution.get("can_send") else "❌ НЕТ"
        print(f"   • Можно отправить: {can_send}")
        if distribution.get("can_send"):
            print(f"   • Сообщений на аккаунт: {distribution.get('actual_per_account',0)}")
        else:
            print(f"   • Нужно сессий: {distribution.get('needed_sessions',0)}")


async def main():
    print("🤖 ЗАГРУЗКА MASS SENDER...")
    sender = MassSender()
    try:
        await sender.initialize()
        await sender.show_menu()
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        if notification_bot:
            await notification_bot.send_security_notification(
                {"phone": "System", "name": "MassSender"},
                {"name": "Error", "username": "system"},
                f"Критическая ошибка: {e}",
                "🚨 СИСТЕМНАЯ ОШИБКА"
            )
    finally:
        await sender.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
