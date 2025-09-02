#!/usr/bin/env python3
"""
MASS SENDER С УВЕДОМЛЕНИЯМИ И УПРАВЛЕНИЕМ ЧАТАМИ
Главный модуль системы с меню и автоматическим управлением
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from session_manager import SessionManager
from user_manager import UserManager
from message_handler import MessageHandler
from notification_bot import init_notification_bot, notification_bot
from config import load_config, save_config
import subprocess
import sys



class MassSender:
    def __init__(self):
        self.config = load_config()
        self.session_manager = SessionManager()
        self.user_manager = UserManager()
        self.message_handler = MessageHandler()
        self.is_running = False
        self.active_sessions = []

    async def initialize(self):
        """Инициализация системы"""
        print("🚀 Инициализация Mass Sender...")

        # Создаем необходимые папки
        os.makedirs("sessions", exist_ok=True)
        os.makedirs("proxies", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        # Создаем необходимые файлы если их нет
        for file in ["target_users.txt", "processed_users.txt", "new_users.txt", "phone_numbers.txt"]:
            filepath = os.path.join("data", file)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    pass

        init_notification_bot()

        print("✅ Система инициализирована")

    async def show_menu(self):
        """Главное меню системы"""
        while True:
            print("\n" + "=" * 60)
            print("🤖 MASS SENDER")
            print("=" * 60)
            print("1. 🎯 Запустить рассылку")
            print("2. 📊 Показать статус системы")
            print("3. 🔄 Перезагрузить сессии")
            print("4. 📱 Конвертировать номера телефонов")
            print("5. ⚙️  Настройки")
            print("6. 📥 Добавить пользователей вручную")
            print("7. 🔍 Проверить новые ресурсы")
            print("8. 🗂️ Управление чатами")
            print("0. ❌ Выход")
            print("=" * 60)

            try:
                choice = input("Выберите опцию: ").strip()

                if choice == "1":
                    await self.start_sending_campaign()
                elif choice == "2":
                    await self.show_system_status()
                elif choice == "3":
                    await self.reload_sessions()
                elif choice == "4":
                    await self.convert_phone_numbers()
                elif choice == "5":
                    self.edit_settings()
                elif choice == "6":
                    await self.add_users_manually()
                elif choice == "7":
                    await self.check_new_resources()
                elif choice == "8":
                    await self.chat_management()
                elif choice == "0":
                    await self.shutdown()
                    break
                else:
                    print("❌ Неверный выбор")
            except KeyboardInterrupt:
                print("\n🛑 Прервано пользователем")
                await self.shutdown()
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")


    async def start_sending_campaign(self):
        """Запуск кампании рассылки (чистый вывод)"""
        print("\n🎯 ЗАПУСК РАССЫЛКИ")
        print("=" * 50)

        sessions = await self.session_manager.load_sessions()
        if not sessions:
            print("❌ Нет доступных сессий!")
            return

        print(f"✅ Сессии: {len(sessions)}")

        users_data = await self.user_manager.load_all_users()
        available_users = users_data["available"]

        if not available_users:
            print("❌ Нет пользователей для отправки!")
            return

        print(f"✅ Пользователей: {len(available_users)}")

        distribution = await self.user_manager.calculate_distribution(
            len(sessions),
            self.config["messages_per_account"],
            self.config["max_messages_per_account"]
        )
        confirm = input(f"\nОтправить {distribution['available_users']} сообщений? (y/n): ").lower()
        if confirm != 'y':
            print("❌ Отменено")
            return
        print("\n📤 Отправляем...")
        sent_count = await self.message_handler.send_messages(
            sessions,
            available_users,
            self.config["message"],
            self.config["delay_ms"],
            distribution["actual_per_account"]
        )

        print(f"\n✅ Готово! Отправлено: {sent_count} сообщений")
        print("💬 Ответы пользователей будут приходить в Telegram-бота")



    async def shutdown(self):
        """Корректное завершение работы"""
        print("\n📴 Завершение работы...")

        # Останавливаем фоновое прослушивание
        await self.background_listener.stop_listener()

        # Отключаем все сессии
        sessions = self.session_manager.sessions + self.active_sessions
        for client in sessions:
            try:
                await client.disconnect()
            except:
                pass

        # Отправляем уведомление о выключении
        if notification_bot:
            await notification_bot.send_shutdown_notification()

        print("✅ Система корректно остановлена")

    async def show_system_status(self):
        """Показать статус системы"""
        print("\n📊 СТАТУС СИСТЕМЫ")
        print("=" * 50)

        sessions = await self.session_manager.load_sessions()
        users_data = await self.user_manager.load_all_users()

        # Статистика сессий
        session_stats = await self.session_manager.get_session_stats()
        print(f"🔧 Сессии: {session_stats['total']} (активных: {session_stats['active']})")

        # Статистика пользователей
        print(f"👥 Пользователи:")
        print(f"   • Целевые: {len(users_data['target'])}")
        print(f"   • Обработанные: {len(users_data['processed'])}") 
        print(f"   • Новые: {len(users_data['new'])}")
        print(f"   • Номера телефонов: {len(users_data['phones'])}")
        print(f"   • Доступно для отправки: {len(users_data['available'])}")




        print("=" * 50)
        if sessions:
            distribution = await self.user_manager.calculate_distribution(
                len(sessions),
                self.config["messages_per_account"]
            )
            self._print_distribution_info(distribution)

        # Статус бота
        bot_status = "✅ Активен" if notification_bot else "❌ Неактивен"
        print(f"🤖 Бот уведомлений: {bot_status}")

        print("=" * 50)

    def _print_distribution_info(self, distribution):
        """Печать информации о распределении"""
        print(f"\n📊 РАСПРЕДЕЛЕНИЕ:")
        print(f"   • Доступно пользователей: {distribution['available_users']}")
        print(f"   • Текущие сессии: {distribution['current_sessions']}")
        print(f"   • Макс. на аккаунт: {distribution['max_per_account']}")
        print(f"   • Можно отправить: {'✅ ДА' if distribution['can_send'] else '❌ НЕТ'}")

        if distribution['can_send']:
            print(f"   • Сообщений на аккаунт: {distribution['actual_per_account']}")
        else:
            print(f"   • Нужно сессий: {distribution['needed_sessions']}")

    async def reload_sessions(self):
        """Перезагрузить сессии"""
        print("\n🔄 ПЕРЕЗАГРУЗКА СЕССИЙ")
        print("=" * 50)

        old_count = len(self.session_manager.sessions)
        sessions = await self.session_manager.load_sessions(force_reload=True)
        new_count = len(sessions)

        print(f"✅ Загружено сессий: {new_count}")
        if new_count > old_count:
            print(f"🎉 Добавлено новых сессий: {new_count - old_count}")

        return sessions

    async def convert_phone_numbers(self):
        """Конвертировать номера телефонов"""
        print("\n📱 КОНВЕРТАЦИЯ НОМЕРОВ")
        print("=" * 50)

        phones = await self.user_manager.load_users_async(self.config["phone_numbers_file"])
        if not phones:
            print("❌ Нет номеров для конвертации!")
            print("💡 Добавьте номера в data/phone_numbers.txt")
            return

        print(f"✅ Найдено номеров: {len(phones)}")
        print(f"📋 Первые 5: {', '.join(phones[:5])}{'...' if len(phones) > 5 else ''}")

        confirm = input("\nНачать конвертацию? (y/n): ").lower()
        if confirm != 'y':
            print("❌ Отменено")
            return

        converted = await self.user_manager.convert_phones_to_usernames()
        if converted > 0:
            print(f"\n✅ Сконвертировано: {converted} номеров")

            # Предлагаем переместить в целевые
            move = input("Переместить сконвертированных пользователей в целевые? (y/n): ").lower()
            if move == 'y':
                moved = await self.user_manager.move_new_to_target()
                print(f"✅ Перемещено: {moved} пользователей")
        else:
            print("❌ Не удалось сконвертировать номера")

    def edit_settings(self):
        """Редактирование настроек"""
        print("\n⚙️ НАСТРОЙКИ")
        print("=" * 50)

        cfg = load_config()
        print("Текущие настройки:")

        for key, value in cfg.items():
            if key not in ['last_session_check', 'last_user_check']:
                print(f"   {key}: {value}")

        print("\nРедактирование (оставьте пустым чтобы не менять):")

        for key in cfg:
            if key in ['api_id', 'api_hash', 'admin_username', 'message']:
                new_val = input(f"{key} [{cfg[key]}]: ").strip()
                if new_val:
                    cfg[key] = new_val
            elif key in ['delay_ms', 'messages_per_account', 'max_messages_per_account',
                         'accounts_per_proxy', 'check_interval_minutes']:
                try:
                    new_val = input(f"{key} [{cfg[key]}]: ").strip()
                    if new_val:
                        cfg[key] = int(new_val)
                except:
                    pass
            elif key in ['auto_hide_chats', 'auto_ttl_messages',
                         'auto_check_new_sessions', 'auto_check_new_users']:
                new_val = input(f"{key} [{'Да' if cfg[key] else 'Нет'}] (y/n): ").strip().lower()
                if new_val:
                    cfg[key] = (new_val == 'y')

        save_config(cfg)
        self.config = cfg
        print("✅ Настройки сохранены")

    async def add_users_manually(self):
        """Добавить пользователей вручную"""
        print("\n📥 ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ")
        print("=" * 50)

        print("Введите username'ы (каждый с новой строки, Ctrl+D для завершения):")
        print("Формат: @username или username")

        users = []
        try:
            while True:
                line = input().strip()
                if line:
                    if not line.startswith('@'):
                        line = '@' + line
                    users.append(line)
        except EOFError:
            pass

        if not users:
            print("❌ Не добавлено пользователей")
            return

        await self.user_manager.add_new_users(users)
        print(f"✅ Добавлено пользователей: {len(users)}")
        print(f"📋 Добавлены: {', '.join(users[:5])}{'...' if len(users) > 5 else ''}")

    async def check_new_resources(self):
        """Проверить новые ресурсы"""
        print("\n🔍 ПРОВЕРКА НОВЫХ РЕСУРСОВ")
        print("=" * 50)

        # Проверяем новые сессии
        print("🔄 Проверяем новые сессии...")
        sessions = await self.session_manager.reload_sessions_if_needed()
        print(f"✅ Сессии: {len(sessions)}")

        # Проверяем новых пользователей
        print("📥 Проверяем новых пользователей...")
        has_new_users = await self.user_manager.check_for_new_users()
        if has_new_users:
            added = await self.user_manager.move_new_to_target()
            print(f"✅ Добавлено новых пользователей: {added}")
        else:
            print("❌ Новых пользователей нет")

        # Проверяем новые номера
        print("📱 Проверяем новые номера...")
        has_new_phones = await self.user_manager.check_for_new_phones()
        if has_new_phones:
            print(f"✅ Найдены новые номера")
            convert = input("Конвертировать сейчас? (y/n): ").lower()
            if convert == 'y':
                await self.convert_phone_numbers()
        else:
            print("❌ Новых номеров нет")

        print("✅ Проверка завершена")



    async def chat_management(self):
        """Управление чатами"""
        print("\n🗂️ УПРАВЛЕНИЕ ЧАТАМИ")
        print("=" * 50)
        print("1. 📊 Статистика чатов")
        print("2. 🗑️ Очистить кэш чатов")
        print("3. 🔙 Назад")

        choice = input("Выберите опцию: ").strip()

        if choice == "1":
            sessions = await self.session_manager.load_sessions()
            if not sessions:
                print("❌ Нет доступных сессий")
                return

            print("\n📊 СТАТИСТИКА ЧАТОВ ПО СЕССИЯМ")
            print("-" * 50)

            for i, client in enumerate(sessions, 1):
                try:
                    me = await client.get_me()
                    phone_display = f"+{me.phone}" if me.phone else "No phone"

                    if hasattr(client, 'chat_manager'):
                        stats = client.chat_manager.get_optimization_stats()
                        print(f"{i}. {me.first_name or 'Unknown'} ({phone_display}):")
                        print(f"   • Обработано чатов: {stats['processed_chats_count']}")
                        print(f"   • Сэкономлено API запросов: {stats['saved_api_calls']}")
                    else:
                        print(f"{i}. {me.first_name or 'Unknown'} ({phone_display}):")
                        print(f"   • ChatManager не активирован")

                except Exception as e:
                    print(f"{i}. ❌ Ошибка получения данных: {e}")

                print()

        elif choice == "2":
            sessions = await self.start_listener_console()
            if not sessions:
                print("❌ Нет доступных сессий")
                return

            total_cleared = 0
            cleared_sessions = 0

            print("\n🗑️ ОЧИСТКА КЭША ЧАТОВ")
            print("-" * 50)

            for client in sessions:
                try:
                    me = await client.get_me()
                    if hasattr(client, 'chat_manager'):
                        cleared = client.chat_manager.clear_processed_chats_cache()
                        if cleared > 0:
                            total_cleared += cleared
                            cleared_sessions += 1
                            print(f"✅ {me.first_name}: очищено {cleared} чатов")
                        else:
                            print(f"ℹ️ {me.first_name}: кэш пуст")
                    else:
                        print(f"❌ {me.first_name}: ChatManager не активирован")

                except Exception as e:
                    print(f"❌ Ошибка очистки: {e}")

            print(f"\n📊 Итог: очищено {total_cleared} чатов в {cleared_sessions} сессиях")

        elif choice == "3":
            return
        else:
            print("❌ Неверный выбор")


async def main():
    """Главная функция"""
    print("🤖 ЗАГРУЗКА MASS SENDER...")

    sender = None
    try:
        sender = MassSender()
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
        if sender:
            await sender.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
