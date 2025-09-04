#!/usr/bin/env python3
import asyncio
import os
import sys
import json
import random
import shutil
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from session_manager import SessionManager
from user_manager import UserManager
from message_handler import MessageHandler
from notification_bot import init_notification_bot, notification_bot
from config import load_config, save_config
from auto_responder import init_auto_responder, get_auto_responder
from phone_converter import PhoneConverter
from proxy_manager import ProxyManager
from telethon import events
from telethon.errors import FloodWaitError, RPCError, TypeNotFoundError
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction


class AutoMassSender:
    def __init__(self):
        self.config = load_config()
        self.session_manager = SessionManager()
        self.user_manager = UserManager()
        self.message_handler = MessageHandler()
        self.proxy_manager = ProxyManager()
        self.active_sessions = []
        self.broken_sessions = []
        self.is_running = False
        self.is_sending = False
        self.check_interval = 10 * 60
        self.auto_responder = None
        self.messages_list = []
        self.first_run = True
        self.known_error_patterns = [
            "9815cec8",
            "type not found", 
            "cannot get difference",
            "constructor not found"
        ]

    async def initialize(self):
        """Полная инициализация системы"""
        print("🚀 Инициализация автоматического Mass Sender...")

        # Создание директорий
        os.makedirs("sessions", exist_ok=True)
        os.makedirs("proxies", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        os.makedirs("broken_sessions", exist_ok=True)

        # Загрузка сообщений
        await self.load_messages()
        # Инициализация компонентов
        if self.config.get("notification_bot", {}).get("enabled", False):
            bot_token = self.config.get("notification_bot", {}).get("token")
            chat_id = self.config.get("notification_bot", {}).get("admin_chat_id")
            init_notification_bot(bot_token, chat_id)
        else:
            print("⚠️ Notification Bot отключен в конфигурации")

        # Загрузка сессий
        self.active_sessions = await self.session_manager.load_sessions()
        # Проверка работоспособности сессий
        await self.check_sessions_health()

        if not self.active_sessions:
            print("❌ Нет доступных сессий!")
            return False

        print(f"✅ Загружено {len(self.active_sessions)} рабочих сессий")

        # Инициализация автоответчика
        await self.initialize_auto_responder()

        print("✅ Система инициализирована")
        return True

    def is_known_error(self, error: Exception) -> bool:
        """Проверяет, является ли ошибка известной проблемой сессии"""
        error_str = str(error).lower()
        return any(pattern in error_str for pattern in self.known_error_patterns)

    async def check_sessions_health(self):
        """Проверка работоспособности сессий"""
        print("🔍 Проверка работоспособности сессий...")

        healthy_sessions = []
        check_timeout = 15  # Таймаут проверки в секундах

        for client in self.active_sessions:
            try:
                # Устанавливаем таймаут для проверки сессии
                me = await asyncio.wait_for(client.get_me(), timeout=check_timeout)
                if me:
                    healthy_sessions.append(client)
                    phone_display = getattr(me, 'phone', 'unknown')
                    print(f"✅ Сессия {phone_display} работоспособна")

            except asyncio.TimeoutError:
                print(f"⏱️ Таймаут проверки сессии, перемещаем в broken_sessions")
                await self.move_broken_session(client, "timeout")

            except TypeNotFoundError as e:
                print(f"❌ TypeNotFoundError - поврежденная сессия")
                await self.move_broken_session(client, "type_error")

            except RPCError as e:
                if self.is_known_error(e):
                    print(f"❌ Известная ошибка сессии: {e}")
                    await self.move_broken_session(client, "known_error")
                else:
                    print(f"❌ RPC ошибка в сессии: {e}")
                    await self.move_broken_session(client, "rpc_error")

            except Exception as e:
                print(f"❌ Общая ошибка в сессии: {e}")
                await self.move_broken_session(client, "general_error")

        self.active_sessions = healthy_sessions
        print(f"📊 Осталось здоровых сессий: {len(healthy_sessions)}")

    async def move_broken_session(self, client, reason="unknown"):
        """Перемещение битой сессии с улучшенной обработкой"""
        try:
            session_file = None
            
            # Сначала безопасно отключаем клиент
            try:
                if hasattr(client, 'is_connected') and client.is_connected():
                    await asyncio.wait_for(client.disconnect(), timeout=5)
            except (asyncio.TimeoutError, Exception) as e:
                print(f"⚠️ Не удалось корректно отключить сессию: {e}")
                # Принудительное закрытие соединения
                if hasattr(client, '_connection'):
                    client._connection = None

            # Ждем освобождения ресурсов
            await asyncio.sleep(1)

            # Пытаемся получить путь к файлу сессии
            if hasattr(client, 'session') and hasattr(client.session, 'filename'):
                session_file = client.session.filename
            elif hasattr(client, '_session_file'):
                session_file = client._session_file

            if session_file and os.path.exists(session_file):
                filename = os.path.basename(session_file)
                dest_path = os.path.join("broken_sessions", f"{filename}.{reason}")

                try:
                    # Пробуем переместить файл
                    shutil.move(session_file, dest_path)
                    print(f"📁 Сессия {filename} перемещена в broken_sessions (причина: {reason})")
                    self.broken_sessions.append(filename)

                except (PermissionError, OSError) as e:
                    # Если не получается переместить, пробуем скопировать
                    print(f"⚠️ Не удалось переместить {filename}: {e}")
                    try:
                        shutil.copy2(session_file, dest_path)
                        print(f"📁 Сессия {filename} скопирована в broken_sessions")
                        # Помечаем оригинальный файл для удаления позже
                        try:
                            os.rename(session_file, f"{session_file}.to_delete")
                        except:
                            pass
                    except Exception as copy_error:
                        print(f"⚠️ Не удалось скопировать сессию: {copy_error}")

            else:
                print("⚠️ Не удалось найти файл сессии для перемещения")
        
        except Exception as e:
            print(f"❌ Ошибка при обработке битой сессии: {e}")

        finally:
            # Убеждаемся что клиент отключен
            try:
                if hasattr(client, 'disconnect'):
                    await client.disconnect()
            except:
                pass

    async def load_messages(self):
        """Загружает сообщения из файла"""
        messages_file = self.config.get("messages_file", "data/messages.txt")
        self.messages_list = []

        try:
            if os.path.exists(messages_file):
                with open(messages_file, 'r', encoding='utf-8') as f:
                    self.messages_list = [line.strip() for line in f if line.strip()]

            if not self.messages_list:
                self.messages_list = ["Привет! Как дела?"]

            print(f"📝 Загружено {len(self.messages_list)} сообщений")
                        
        except Exception as e:
            print(f"❌ Ошибка загрузки сообщений: {e}")
            self.messages_list = ["Привет! Как дела?"]

    def get_random_message(self):
        """Возвращает случайное сообщение"""
        if not self.messages_list:
            return "Привет! Как дела?"
        return random.choice(self.messages_list)

    async def get_smart_message(self):
        """
        Возвращает AI сгенерированное уникальное сообщение
        Если AI не работает - прекращаем рассылку (НЕТ захардкоженных!)
        """
        if not self.auto_responder or not self.auto_responder.ai_enabled:
            raise Exception("❌ AI автоответчик не активен - рассылка прекращена для избежания банов!")
        
        try:
            # Генерируем уникальное AI сообщение
            ai_message = await self.auto_responder.generate_initial_message()
            print(f"🤖 AI сгенерировал: {ai_message}")
            return ai_message
        
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА AI генерации: {e}")
            raise Exception(f"❌ AI генерация сообщений недоступна - рассылка остановлена! Ошибка: {e}")

    async def initialize_auto_responder(self):
        """Инициализация автоответчика"""
        print("🤖 Инициализация AI автоответчика...")

        try:
            # Инициализируем автоответчик с конфигурацией
            self.auto_responder = init_auto_responder(self.config, self.session_manager)
            
            if self.auto_responder and self.auto_responder.ai_enabled:
                print("✅ AI автоответчик успешно инициализирован")
                
                # Выводим диагностическую информацию
                stats = self.auto_responder.get_stats()
                print("\n📋 Лог инициализации автоответчика:")
                for log_entry in stats.get('initialization_log', []):
                    print(f"   {log_entry}")
            else:
                print("❌ AI автоответчик не активен")

        except Exception as e:
            print(f"❌ Ошибка инициализации автоответчика: {e}")
            import traceback
            traceback.print_exc()

    async def convert_phone_numbers(self):
        """Конвертация номеров телефонов с использованием всех доступных сессий"""
        print("\n📱 ЭТАП 1: Конвертация номеров телефонов")

        phones_file = self.config.get("phone_numbers_file", "data/phone_numbers.txt")

        if not os.path.exists(phones_file):
            print("⚠️ Файл с номерами не найден")
            return 0

        phones = await self.user_manager.load_users_async(phones_file)
        if not phones:
            print("⚠️ Нет номеров для конвертации")
            return 0

        print(f"📞 Найдено {len(phones)} номеров для конвертации")

        if not self.active_sessions:
            print("❌ Нет активных сессий для конвертации")
            return 0

        # Создаем задачи для конвертации по сессиям
        tasks = []
        phones_per_session = len(phones) // len(self.active_sessions) + 1

        for i, client in enumerate(self.active_sessions):
            start_idx = i * phones_per_session
            end_idx = min(start_idx + phones_per_session, len(phones))
            session_phones = phones[start_idx:end_idx]

            if session_phones:
                task = self._convert_phones_batch(client, session_phones)
                tasks.append(task)

        print(f"📊 Распределение: {len(phones)} номеров на {len(self.active_sessions)} сессий")

        # Запускаем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = {}
        converted = []
        failed = []

        # Обрабатываем результаты
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка в задаче конвертации: {result}")
                continue

            for phone, username in result.items():
                if username:
                    converted.append(username)
                    all_results[phone] = username
            else:
                    failed.append(phone)
                    all_results[phone] = None

        # Сохраняем результаты
        if converted:
            await self.user_manager.add_new_users(converted)
            print(f"✅ Успешно сконвертировано: {len(converted)} номеров")

        if failed:
            await self.user_manager.save_users_async("data/failed_numbers.txt", failed)
            print(f"⚠️ Не удалось конвертировать: {len(failed)} номеров")

        # Очищаем файл с номерами
        await self.user_manager.save_users_async(phones_file, [])

        return len(converted)

    async def _convert_phones_batch(self, client, phones_list):
        """Конвертация пакета номеров одной сессией"""
        try:
            converter = PhoneConverter(client)
            results = await converter.batch_convert(phones_list, max_concurrent=2)
            return results
        except Exception as e:
            print(f"❌ Ошибка конвертации пакета: {e}")
            # Возвращаем словарь с неудачными результатами
            return {phone: None for phone in phones_list}

    async def send_messages_to_users(self):
        """Отправка сообщений пользователям"""
        print("\n✉️ ЭТАП 2: Отправка рассылки")

        moved = await self.user_manager.move_new_to_target()
        if moved > 0:
            print(f"📋 Перенесено в target: {moved} пользователей")

        users_data = await self.user_manager.load_all_users()
        available_users = users_data.get("available", [])

        if not available_users:
            print("⚠️ Нет пользователей для рассылки")
            return 0

        print(f"📊 Готово к отправке: {len(available_users)} сообщений")

        distribution = await self.user_manager.calculate_distribution(
            len(self.active_sessions),
            self.config.get("messages_per_account", 2),
            self.config.get("max_messages_per_account", 10)
        )

        if not distribution.get("can_send"):
            print(f"❌ Недостаточно сессий. Нужно: {distribution.get('needed_sessions')}")
            return 0

        print(f"📊 Сообщений на аккаунт: {distribution.get('actual_per_account')}")

        session_messages = {}
        working_sessions = []

        for client in self.active_sessions:
            try:
                me = await asyncio.wait_for(client.get_me(), timeout=10)
                session_messages[client] = await self.get_smart_message()
                print(f"💬 {me.first_name}: {session_messages[client][:50]}...")
                working_sessions.append(client)
            except Exception as e:
                if "AI генерация сообщений недоступна" in str(e) or "AI автоответчик не активен" in str(e):
                    print(f"🛑 {str(e)}")
                    print("🛡️ Рассылка остановлена для защиты от банов!")
                    return 0
                print(f"❌ Сессия не отвечает: {e}")
                await self.move_broken_session(client, "send_check_failed")

        if not working_sessions:
            print("❌ Нет рабочих сессий для отправки")
            return 0

        # Обновляем список активных сессий
        self.active_sessions = working_sessions

        sent_count = await self.message_handler.send_messages(
            working_sessions,
            available_users,
            session_messages,
            self.config.get("delay_ms", 1000),
            distribution.get("actual_per_account", 1)
        )

        print(f"✅ Отправлено сообщений: {sent_count}")

        await self.user_manager.save_users_async(
            self.config["target_users_file"],
            []
        )

        return sent_count

    async def check_messages_from_processed(self):
        """Проверка сообщений от обработанных пользователей"""
        print("\n👀 ЭТАП 3: Проверка сообщений от processed_users")

        users_data = await self.user_manager.load_all_users()
        processed_users = users_data.get("processed", [])

        if not processed_users:
            print("⚠️ Нет обработанных пользователей для проверки")
            return

        print(f"📊 Проверяем сообщения от {len(processed_users)} пользователей")

        for client in self.active_sessions:
            try:
                if not hasattr(client, 'sent_users'):
                    client.sent_users = set()

                for user in processed_users:
                    try:
                        entity = await asyncio.wait_for(client.get_entity(user), timeout=10)
                        client.sent_users.add(entity.id)
                    except Exception:
                        continue
            
                me = await client.get_me()
                print(f"✅ {me.first_name}: отслеживает {len(client.sent_users)} пользователей")

            except Exception as e:
                print(f"❌ Ошибка настройки проверки: {e}")

    async def setup_message_listeners(self):
        """Настройка прослушки входящих сообщений"""
        print("\n🎧 ЭТАП 4: Запуск прослушки сообщений")

        sessions_to_remove = []

        for client in self.active_sessions:
            try:
                # Удаляем старые обработчики если есть
                if hasattr(client, '_message_handlers'):
                    for handler in client._message_handlers:
                        client.remove_event_handler(handler)

                # Создаем новый обработчик
                async def create_handler(current_client):
                    async def handler(event):
                        try:
                            await self.handle_incoming_message(current_client, event)
                        except Exception as e:
                            if self.is_known_error(e):
                                print(f"⚠️ Известная ошибка в обработчике: {e}")
                            else:
                                print(f"❌ Ошибка в обработчике сообщений: {e}")

                    return handler

                handler = await create_handler(client)
                client.add_event_handler(handler, events.NewMessage(incoming=True))

                # Сохраняем ссылку на обработчик
                if not hasattr(client, '_message_handlers'):
                    client._message_handlers = []
                client._message_handlers.append(handler)

                me = await client.get_me()
                print(f"✅ {me.first_name}: прослушка активна")

            except (TypeNotFoundError, RPCError) as e:
                if self.is_known_error(e):
                    print(f"⚠️ Известная ошибка сессии, помечаем для удаления")
                    sessions_to_remove.append(client)
                else:
                    print(f"❌ Ошибка настройки прослушки: {e}")

        # Удаляем битые сессии после цикла
        for client in sessions_to_remove:
            await self.move_broken_session(client, "listener_setup_failed")
            if client in self.active_sessions:
                self.active_sessions.remove(client)

    async def handle_incoming_message(self, client, event):
        """Обработка входящего сообщения"""
        try:
            sender = await event.get_sender()
            if not sender or not hasattr(client, 'sent_users'):
                return

            if sender.id not in client.sent_users:
                return

            text = event.raw_text
            me = await client.get_me()
            timestamp = datetime.now().strftime("%H:%M:%S")

            print(f"\n[{timestamp}] 📩 {sender.first_name} -> {me.first_name}: {text}")

            if notification_bot:
                account_info = {'phone': me.phone or 'Unknown', 'name': me.first_name or 'Unknown'}
                sender_info = {'name': sender.first_name or 'Unknown', 'username': sender.username or 'unknown'}
                asyncio.create_task(notification_bot.send_notification(account_info, sender_info, text))

            if self.auto_responder:
                asyncio.create_task(self.handle_auto_response(client, sender, text))

            # Удаляем сообщение из чата
            try:
                await event.message.delete(revoke=False)
            except:
                pass

        except (TypeNotFoundError, RPCError) as e:
            if self.is_known_error(e):
                print(f"⚠️ Пропускаем известную ошибку: {e}")
            else:
                print(f"❌ Ошибка обработки сообщения: {e}")

        except Exception as e:
            print(f"❌ Ошибка обработки сообщения: {e}")

    async def handle_auto_response(self, client, sender, text):
        """Обработка автоответа"""
        try:
            response = await self.auto_responder.handle_message(
                str(sender.id),
                text,
                phone=getattr(sender, 'phone', None),
                username=getattr(sender, 'username', None),
                first_name=getattr(sender, 'first_name', None)
            )

            if response:
                # 🔧 ИСПРАВЛЕНИЕ: Добавляем индикатор "печатает..." для реалистичности
                try:
                    await client.send_read_acknowledge(sender.id)  # Отмечаем как прочитанное
                    await client(SetTypingRequest(
                        peer=sender.id, 
                        action=SendMessageTypingAction()
                    ))
                    await asyncio.sleep(1.5)  # Имитируем время набора текста
                except:
                    pass  # Игнорируем ошибки typing action
                
                await client.send_message(sender.id, response)
                print(f"🤖 Автоответ -> {sender.first_name}: {response[:50]}...")

        except Exception as e:
            print(f"❌ Ошибка автоответчика: {e}")

    async def main_loop(self):
        """Основной цикл программы"""
        print("\n🔄 Запуск основного цикла...")
        self.is_running = True

        while self.is_running:
            try:
                print(f"\n{'=' * 60}")
                print(f"⏰ НАЧАЛО ЦИКЛА - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'=' * 60}")

                # Проверяем работоспособность сессий
                await self.check_sessions_health()

                if not self.active_sessions:
                    print("❌ Нет рабочих сессий, пропускаем цикл")
                    await asyncio.sleep(300)  # Ждем 5 минут и пробуем снова
                    continue

                converted = await self.convert_phone_numbers()
                sent = await self.send_messages_to_users()
                await self.check_messages_from_processed()
                await self.setup_message_listeners()

                print(f"\n📊 ИТОГИ ЦИКЛА:")
                print(f"   • Конвертировано: {converted} номеров")
                print(f"   • Отправлено: {sent} сообщений")
                print(f"   • Рабочих сессий: {len(self.active_sessions)}")
                print(f"   • Нерабочих сессий: {len(self.broken_sessions)}")

                if notification_bot and (converted > 0 or sent > 0):
                    await notification_bot.send_security_notification(
                        {"phone": "System", "name": "AutoMassSender"},
                        {"name": "Cycle", "username": "system"},
                        f"Цикл завершен. Конвертировано: {converted}, Отправлено: {sent}, Сессий: {len(self.active_sessions)}",
                        "✅ ЦИКЛ ЗАВЕРШЕН"
                    )

                print(f"\n⏳ Ожидание {self.check_interval // 60} минут до следующего цикла...")
                await asyncio.sleep(self.check_interval)

            except KeyboardInterrupt:
                print("\n🛑 Получен сигнал остановки")
                break
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)

    async def run(self):
        """Запуск автоматического режима"""
        success = await self.initialize()
        if not success:
            print("❌ Не удалось инициализировать систему")
            return
            
            print("\n" + "=" * 60)
        print("🚀 АВТОМАТИЧЕСКИЙ MASS SENDER ЗАПУЩЕН")
        print(f"⏱️ Проверка каждые {self.check_interval // 60} минут")
        print("🛑 Для остановки нажмите Ctrl+C")
        print("=" * 60)

        try:
            # Запускаем основной цикл
            await self.main_loop()
        except KeyboardInterrupt:
            print("\n🛑 Остановка по запросу пользователя")
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы"""
        print("\n📴 Завершение работы...")
        self.is_running = False

        # Отключаем все сессии
        for client in self.active_sessions:
            try:
                # Удаляем обработчики событий
                if hasattr(client, '_message_handlers'):
                    for handler in client._message_handlers:
                        try:
                            client.remove_event_handler(handler)
                        except:
                            pass
        
                await client.disconnect()
            except:
                pass

        if notification_bot:
            try:
                await notification_bot.send_shutdown_notification()
            except:
                pass
            try:
                await notification_bot.close_session()
            except:
                pass

        print("✅ Система остановлена")


async def main():
    """Главная функция"""
    print("\n" + "=" * 60)
    print("🤖 АВТОМАТИЧЕСКИЙ MASS SENDER")
    print("=" * 60)

    sender = AutoMassSender()

    while True:
        print("\n1. 🚀 Запустить автоматический режим")
        print("2. 🧪 Тест одного цикла")
        print("3. 🧹 Очистить broken_sessions")
        print("4. ❌ Выход")
        print("-" * 40)

        choice = input("Выбор: ").strip()

        if choice == "1":
            await sender.run()
            break
        elif choice == "2":
            success = await sender.initialize()
            if success:
                print("\n🧪 Запуск тестового цикла...")
                await sender.convert_phone_numbers()
                await sender.send_messages_to_users()
                await sender.check_messages_from_processed()
                await sender.setup_message_listeners()
                print("✅ Тестовый цикл завершен")
                await sender.shutdown()
        elif choice == "3":
            # Очистка broken_sessions
            broken_dir = "broken_sessions"
            if os.path.exists(broken_dir):
                try:
                    shutil.rmtree(broken_dir)
                    os.makedirs(broken_dir, exist_ok=True)
                    print("🧹 Папка broken_sessions очищена")
                except Exception as e:
                    print(f"❌ Ошибка очистки: {e}")
            else:
                print("⚠️ Папка broken_sessions не существует")
        elif choice == "4":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Программа завершена")
