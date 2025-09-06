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
from telethon.errors import FloodWaitError, RPCError, TypeNotFoundError, MsgidDecreaseRetryError
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
        self.all_time_processed_users = {}
        self.session_processed_users = {}
        self.processed_users_file = "data/all_processed_users.json"
        self.victim_phones_file = "data/victim_phones.txt"
        self.session_phone_map = {}  # Карта ID аккаунта -> номер телефона
        self.is_running = False
        self.is_sending = False
        self.check_interval = 10 * 60
        self.auto_responder = None
        self.messages_list = []
        self.first_run = True

        self.load_processed_users_history()
        self.load_victim_phones()

        # Словарь для отслеживания обработанных пользователей по сессиям
        self.session_processed_users = {}

        self.known_error_patterns = [
            "9815cec8",
            "type not found",
            "cannot get difference",
            "constructor not found",
            "auth key duplicated",
            "session revoked",
            "user deactivated",
            "auth key invalid",
            "msgiddecrease",
            "internal issues",
            "too many requests",
            "sendmessagerequest",
            "timestamp outdated",
            "persistenttimestamp",
            "connection reset",
            "server closed"  ,
            "GeneralProxyError: Socket error:"
        ]

    def load_victim_phones(self):
        """Загружает номера телефонов жертв из файла"""
        self.victim_phones = set()
        try:
            if os.path.exists(self.victim_phones_file):
                with open(self.victim_phones_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.victim_phones.add(line)
                print(f"📱 Загружено {len(self.victim_phones)} номеров жертв")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки номеров жертв: {e}")
            self.victim_phones = set()

    def save_victim_phones(self):
        """Сохраняет номера телефонов жертв в файл"""
        try:
            os.makedirs("data", exist_ok=True)
            with open(self.victim_phones_file, 'w', encoding='utf-8') as f:
                for phone in sorted(self.victim_phones):
                    f.write(f"{phone}\n")
            print(f"💾 Сохранено {len(self.victim_phones)} номеров жертв")
        except Exception as e:
            print(f"❌ Ошибка сохранения номеров жертв: {e}")

    def add_victim_phone(self, phone):
        """Добавляет номер телефона жертвы"""
        if phone:
            self.victim_phones.add(phone)
            self.save_victim_phones()





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

        # Проверка работоспособности сессий с перемещением битых
        await self.check_sessions_health()

        # Очистка цифровых ID из кэша и target_users
        await self.clean_numeric_ids()

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
        """Проверка работоспособности сессий с сохранением номеров телефонов"""
        print("🔍 Проверка работоспособности сессий...")

        healthy_sessions = []
        check_timeout = 10

        for i, client in enumerate(self.active_sessions[:]):
            try:
                print(f"   Проверка сессии {i + 1}/{len(self.active_sessions)}...", end='\r')

                if not client.is_connected():
                    await client.connect()

                me = await asyncio.wait_for(client.get_me(), timeout=check_timeout)
                if me:
                    healthy_sessions.append(client)

                    # Получаем ID аккаунта и номер телефона
                    account_id = str(me.id)
                    phone_display = getattr(me, 'phone', 'unknown')

                    # Форматируем номер телефона

                    name_display = getattr(me, 'first_name', 'unknown')
                    username_display = getattr(me, 'username', name_display)

                    print(f"✅ Сессия {name_display} ({phone_display}) работоспособна                    ")

                    # Инициализация ID сессии для отслеживания
                    session_id = f"{me.id}_{me.phone}"
                    if session_id not in self.session_processed_users:
                        self.session_processed_users[session_id] = set()

            except (asyncio.TimeoutError, ConnectionError, RPCError, Exception) as e:
                error_reason = type(e).__name__
                session_name = "unknown"

                if hasattr(client, 'session') and hasattr(client.session, 'filename'):
                    session_name = os.path.basename(client.session.filename)
                elif hasattr(client, '_session_file'):
                    session_name = os.path.basename(client._session_file)

                if "socks5://" in str(e) or "proxy" in session_name.lower():
                    error_reason = "proxy_error"
                    print(f"❌ Сессия {session_name} с прокси не работает - перемещаем")
                else:
                    print(f"❌ Ошибка сессии {i + 1}: {str(e)[:50]} - перемещаем в broken_sessions")

                await self.move_broken_session(client, error_reason, i)

                if client in self.active_sessions:
                    self.active_sessions.remove(client)

        self.active_sessions = healthy_sessions

        print("\n" + "=" * 60)
        print(f"📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ СЕССИЙ:")
        print(f"   ✅ Рабочих сессий: {len(healthy_sessions)}")
        print(f"   ❌ Битых сессий: {len(self.broken_sessions)}")
        print("=" * 60)

    async def move_broken_session(self, client, reason="unknown", session_index=None):
        """Перемещение битой сессии"""
        try:
            session_file = None

            try:
                if hasattr(client, 'is_connected') and client.is_connected():
                    await asyncio.wait_for(client.disconnect(), timeout=3)
            except:
                pass

            if hasattr(client, '_connection'):
                client._connection = None

            await asyncio.sleep(0.5)

            if hasattr(client, 'session') and hasattr(client.session, 'filename'):
                session_file = client.session.filename
            elif hasattr(client, '_session_file'):
                session_file = client._session_file

            if session_file and os.path.exists(session_file):
                filename = os.path.basename(session_file)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = os.path.join("broken_sessions", f"{filename}_{reason}_{timestamp}")

                for attempt in range(3):
                    try:
                        shutil.move(session_file, dest_path)
                        print(f"   📁 Сессия {filename} перемещена в broken_sessions/{reason}")
                        self.broken_sessions.append(filename)
                        break
                    except (PermissionError, OSError) as e:
                        if attempt == 2:
                            try:
                                shutil.copy2(session_file, dest_path)
                                print(f"   📁 Сессия {filename} скопирована в broken_sessions/{reason}")
                                try:
                                    os.rename(session_file, f"{session_file}.to_delete")
                                except:
                                    pass
                            except:
                                print(f"   ⚠️ Не удалось обработать сессию {filename}")
                        else:
                            await asyncio.sleep(1)
            else:
                if session_index is not None:
                    print(f"   ⚠️ Файл сессии {session_index + 1} не найден")

        except Exception as e:
            print(f"   ❌ Ошибка при обработке битой сессии: {str(e)[:50]}")

    async def clean_numeric_ids(self):
        """Очистка цифровых ID из кэша и target_users"""
        print("\n🧹 Очистка цифровых ID...")
        cleaned_count = 0

        cache_file = "data/phone_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)

                original_size = len(cache)
                cleaned_cache = {
                    phone: identifier
                    for phone, identifier in cache.items()
                    if identifier and (
                            identifier.startswith('@') or
                            not identifier.isdigit()
                    )
                }

                if len(cleaned_cache) < original_size:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cleaned_cache, f, ensure_ascii=False, indent=2)
                    cleaned_count = original_size - len(cleaned_cache)
                    print(f"   📦 Удалено {cleaned_count} цифровых ID из кэша")

            except Exception as e:
                print(f"   ⚠️ Ошибка очистки кэша: {e}")

        user_files = [
            self.config.get("target_users_file", "data/target_users.txt"),
            "data/available_users.txt",
            "data/new_users.txt"
        ]

        for file_path in user_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        users = [line.strip() for line in f if line.strip()]

                    original_count = len(users)
                    filtered_users = [
                        user for user in users
                        if user.startswith('@') or not user.isdigit()
                    ]

                    if len(filtered_users) < original_count:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(filtered_users))
                        removed = original_count - len(filtered_users)
                        print(f"   📝 Удалено {removed} цифровых ID из {os.path.basename(file_path)}")
                        cleaned_count += removed

                except Exception as e:
                    print(f"   ⚠️ Ошибка очистки {file_path}: {e}")

        if cleaned_count > 0:
            print(f"✅ Всего очищено цифровых ID: {cleaned_count}")
        else:
            print("   ✅ Цифровых ID не найдено")

        return cleaned_count

    async def convert_phone_numbers(self):
        """Конвертация с фильтрацией цифровых ID и сохранением успешных результатов"""
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

        tasks = []
        phones_per_session = len(phones) // len(self.active_sessions) + 1

        for i, client in enumerate(self.active_sessions):
            start_idx = i * phones_per_session
            end_idx = min(start_idx + phones_per_session, len(phones))
            session_phones = phones[start_idx:end_idx]

            if session_phones:
                task = self._convert_phones_batch(client, session_phones, i)
                tasks.append(task)

        print(f"📊 Распределение: {len(phones)} номеров на {len(self.active_sessions)} сессий")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = {}
        converted = []
        failed = []
        numeric_ids_filtered = 0

        # Файл для сохранения успешных конвертаций
        successful_conversions_file = "data/successful_conversions.txt"

        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Ошибка в задаче конвертации: {result}")
                continue

            if isinstance(result, dict):
                for phone, identifier in result.items():
                    if identifier:
                        if identifier.startswith('@'):
                            converted.append(identifier)
                            all_results[phone] = identifier
                            # Сохраняем успешную конвертацию
                            self._save_successful_conversion(phone, identifier, successful_conversions_file)
                        elif not identifier.isdigit():
                            converted.append(identifier)
                            all_results[phone] = identifier
                            # Сохраняем успешную конвертацию (даже без @)
                            self._save_successful_conversion(phone, identifier, successful_conversions_file)
                        else:
                            numeric_ids_filtered += 1
                            print(f"   🚫 Пропущен цифровой ID: {identifier}")
                    else:
                        failed.append(phone)
                        all_results[phone] = None

        if converted:
            await self.user_manager.add_new_users(converted)
            print(f"✅ Успешно сконвертировано: {len(converted)} номеров")

        if numeric_ids_filtered > 0:
            print(f"🚫 Отфильтровано цифровых ID: {numeric_ids_filtered}")

        if failed:
            await self.user_manager.save_users_async("data/failed_numbers.txt", failed)
            print(f"⚠️ Не удалось конвертировать: {len(failed)} номеров")

        await self.user_manager.save_users_async(phones_file, [])

        print(f"📝 Успешные конвертации сохранены в {successful_conversions_file}")

        return len(converted)

    def _save_successful_conversion(self, phone, username, filename):
        """Сохраняет успешную конвертацию в файл"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{phone}:{username}\n")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения конвертации: {e}")

    async def _convert_phones_batch(self, client, phones_list, session_index):
        """Конвертация пакета с обработкой ошибок сессии"""
        try:
            try:
                me = await asyncio.wait_for(client.get_me(), timeout=5)
                if not me:
                    raise Exception("Сессия не отвечает")
            except Exception as e:
                print(f"❌ Сессия {session_index + 1} недоступна для конвертации")
                await self.move_broken_session(client, "convert_check_failed", session_index)
                return {phone: None for phone in phones_list}

            converter = PhoneConverter(client)
            results = await converter.batch_convert(phones_list, max_concurrent=2)

            if converter.stats.get('session_errors', 0) > 0:
                print(f"⚠️ Сессия {session_index + 1} имеет ошибки, помечаем для проверки")

            return results

        except Exception as e:
            print(f"❌ Ошибка конвертации пакета сессией {session_index + 1}: {e}")
            return {phone: None for phone in phones_list}

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
        """Возвращает AI сгенерированное уникальное сообщение"""
        if not self.auto_responder or not self.auto_responder.ai_enabled:
            raise Exception("❌ AI автоответчик не активен - рассылка прекращена для избежания банов!")

        try:
            ai_message = await self.auto_responder.generate_initial_message()
            return ai_message
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА AI генерации: {e}")
            raise Exception(f"❌ AI генерация сообщений недоступна - рассылка остановлена! Ошибка: {e}")

    def load_processed_users_history(self):
        """Загружает историю всех обработанных пользователей"""
        try:
            if os.path.exists(self.processed_users_file):
                with open(self.processed_users_file, 'r', encoding='utf-8') as f:
                    self.all_time_processed_users = json.load(f)
                print(
                    f"📚 Загружена история: {sum(len(users) for users in self.all_time_processed_users.values())} пользователей")
        except Exception as e:
            print(f"⚠️ Не удалось загрузить историю: {e}")
            self.all_time_processed_users = {}

    def save_processed_users_history(self):
        """Сохраняет историю всех обработанных пользователей"""
        try:
            with open(self.processed_users_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_time_processed_users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Не удалось сохранить историю: {e}")

    async def send_messages_to_users(self):
        """Отправка с генерацией уникальных сообщений для каждой сессии"""
        print("\n✉️ ЭТАП 2: Отправка рассылки")

        await self.clean_numeric_ids()

        moved = await self.user_manager.move_new_to_target()
        if moved > 0:
            print(f"📋 Перенесено в target: {moved} пользователей")

        users_data = await self.user_manager.load_all_users()
        available_users = users_data.get("available", [])

        filtered_users = [
            user for user in available_users
            if user.startswith('@') or not user.isdigit()
        ]

        if len(filtered_users) < len(available_users):
            removed = len(available_users) - len(filtered_users)
            print(f"🚫 Отфильтровано {removed} цифровых ID из списка рассылки")
            available_users = filtered_users

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
        print(f"📝 Генерируем {len(self.active_sessions)} уникальных AI сообщений (по одному на сессию)...")

        session_messages = {}
        working_sessions = []

        for i, client in enumerate(self.active_sessions):
            try:
                me = await asyncio.wait_for(client.get_me(), timeout=10)

                try:
                    unique_message = await self.get_smart_message()
                    session_messages[client] = unique_message
                    print(f"🤖 Сессия #{i + 1} ({me.first_name}): {unique_message[:50]}...")
                    working_sessions.append(client)
                except Exception as e:
                    if "AI генерация сообщений недоступна" in str(e) or "AI автоответчик не активен" in str(e):
                        print(f"🛑 {str(e)}")
                        print("🛡️ Рассылка остановлена для защиты от банов!")
                        return 0
                    session_messages[client] = self.get_random_message()
                    working_sessions.append(client)

            except Exception as e:
                print(f"❌ Сессия {i + 1} не отвечает: {e}")
                await self.move_broken_session(client, "send_check_failed")

        if not working_sessions:
            print("❌ Нет рабочих сессий для отправки")
            return 0

        self.active_sessions = working_sessions

        sent_count = await self.send_messages_with_retry(
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

    async def send_messages_with_retry(self, sessions, users, session_messages, delay_ms, messages_per_account):
        """Отправка сообщений с сохранением в постоянную историю"""
        sent_count = 0
        failed_users = []

        for i, user in enumerate(users):
            if not self.is_running:
                break

            session_index = i % len(sessions)
            client = sessions[session_index]
            message = session_messages[client]

            try:
                success = await self.try_send_message(client, user, message)

                if success:
                    sent_count += 1

                    # Получаем ID сессии
                    me = await client.get_me()
                    session_id = f"{me.id}_{me.phone}"

                    # Добавляем в текущий цикл
                    if session_id not in self.session_processed_users:
                        self.session_processed_users[session_id] = set()
                    self.session_processed_users[session_id].add(user)

                    # Добавляем в постоянное хранилище
                    if session_id not in self.all_time_processed_users:
                        self.all_time_processed_users[session_id] = []
                    if user not in self.all_time_processed_users[session_id]:
                        self.all_time_processed_users[session_id].append(user)

                    # Сохраняем после каждых 50 сообщений
                    if sent_count % 50 == 0:
                        self.save_processed_users_history()
                        print(f"📤 Отправлено {sent_count}/{len(users)} сообщений")
                else:
                    failed_users.append(user)

            except Exception as e:
                print(f"❌ Ошибка отправки пользователю {user}: {e}")
                failed_users.append(user)

            await asyncio.sleep(delay_ms / 1000)

        # Сохраняем историю в конце
        self.save_processed_users_history()
        if failed_users:
            await self.user_manager.save_users_async("data/failed_users.txt", failed_users)
            print(f"⚠️ {len(failed_users)} пользователей не получили сообщения")

        return sent_count

    async def initialize_auto_responder(self):
        """Инициализация автоответчика"""
        print("🤖 Инициализация AI автоответчика...")

        try:
            self.auto_responder = init_auto_responder(self.config, self.session_manager)

            if self.auto_responder and self.auto_responder.ai_enabled:
                print("✅ AI автоответчик успешно инициализирован")

                # Передаем карту номеров телефонов в автоответчик
                if hasattr(self.auto_responder, 'session_phone_map'):
                    self.auto_responder.session_phone_map = self.session_phone_map

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

    async def try_send_message(self, client, user, message, max_retries=3):
        """Попытка отправки сообщения с обработкой ошибок"""
        for attempt in range(max_retries):
            try:
                try:
                    me = await asyncio.wait_for(client.get_me(), timeout=5)
                    if not me:
                        raise Exception("Сессия не отвечает")
                except Exception as e:
                    print(f"❌ Сессия не отвечает: {e}")
                    return False

                await client.send_message(user, message)
                print(f"✅ [{me.first_name}] -> {user}: отправлено")
                return True

            except FloodWaitError as e:
                wait_time = e.seconds
                print(f"⏳ FloodWait: ожидание {wait_time} секунд для сессии")
                await asyncio.sleep(wait_time)
                continue

            except RPCError as e:
                error_str = str(e).lower()

                if "too many requests" in error_str and "sendmessagerequest" in error_str:
                    print(f"⚠️ Too many requests для сессии, пробуем другую сессию")

                    alternative_session = await self.find_alternative_session(client)
                    if alternative_session:
                        print(f"🔄 Переключаемся на альтернативную сессию")
                        try:
                            me_alt = await alternative_session.get_me()
                            await alternative_session.send_message(user, message)
                            print(f"✅ [{me_alt.first_name}] -> {user}: отправлено через альтернативную сессию")

                            # Добавляем в отслеживание для альтернативной сессии
                            session_id_alt = f"{me_alt.id}_{me_alt.phone}"
                            if session_id_alt not in self.session_processed_users:
                                self.session_processed_users[session_id_alt] = set()
                            self.session_processed_users[session_id_alt].add(user)

                            if hasattr(alternative_session, 'processed_users'):
                                alternative_session.processed_users.add(user)
                            else:
                                alternative_session.processed_users = {user}

                            return True
                        except Exception as alt_e:
                            print(f"❌ Ошибка альтернативной сессии: {alt_e}")
                            continue
                    else:
                        print(f"❌ Нет альтернативных сессий для переключения")
                        return False

                elif self.is_known_error(e):
                    print(f"⚠️ Известная ошибка RPC: {e}")
                    if attempt == max_retries - 1:
                        return False
                    await asyncio.sleep(5)
                    continue
                else:
                    print(f"❌ Неизвестная ошибка RPC: {e}")
                    if attempt == max_retries - 1:
                        return False
                    await asyncio.sleep(3)
                    continue

            except Exception as e:
                print(f"❌ Общая ошибка отправки: {e}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(2)
                continue

        return False

    async def find_alternative_session(self, excluded_session):
        """Поиск альтернативной рабочей сессии"""
        for session in self.active_sessions:
            if session != excluded_session:
                try:
                    me = await asyncio.wait_for(session.get_me(), timeout=5)
                    if me:
                        return session
                except:
                    continue
        return None

    async def check_messages_from_processed(self):
        """Проверка сообщений от обработанных пользователей"""
        print("\n👀 ЭТАП 3: Проверка сообщений от processed_users")

        users_data = await self.user_manager.load_all_users()
        processed_users = users_data.get("processed", [])

        if not processed_users:
            print("⚠️ Нет обработанных пользователей для проверки")
            return

        print(f"📊 Проверяем сообщения от {len(processed_users)} пользователей")

        # Обновляем информацию о отслеживании
        for client in self.active_sessions:
            try:
                me = await client.get_me()
                session_id = f"{me.id}_{me.phone}"

                if session_id in self.session_processed_users:
                    tracked = len(self.session_processed_users[session_id])
                    if tracked > 0:
                        print(f"✅ {me.first_name}: отслеживает {tracked} пользователей из текущей рассылки")

                # Также синхронизируем с атрибутом клиента
                if hasattr(client, 'processed_users') and len(client.processed_users) > 0:
                    print(f"   📌 В атрибуте клиента: {len(client.processed_users)} пользователей")

            except Exception as e:
                print(f"❌ Ошибка настройки проверки: {e}")

    async def setup_message_listeners(self):
        """Настройка прослушки входящих сообщений"""
        print("\n🎧 ЭТАП 4: Запуск прослушки сообщений")

        sessions_to_remove = []

        for client in self.active_sessions[:]:
            try:
                try:
                    me = await asyncio.wait_for(client.get_me(), timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    print(f"❌ Сессия {i + 1} не отвечает (timeout)")
                    sessions_to_remove.append(client)
                    continue

                    # Устанавливаем ID сессии для отслеживания
                    client._session_id = f"{me.id}_{me.phone}"

                except Exception as e:
                    print(f"❌ Сессия недоступна для прослушки: {e}")
                    sessions_to_remove.append(client)
                    continue

                # Удаляем старые обработчики если есть
                if hasattr(client, '_message_handlers'):
                    for handler in client._message_handlers:
                        try:
                            client.remove_event_handler(handler)
                        except:
                            pass
                    client._message_handlers = []

                @client.on(events.NewMessage(incoming=True))
                async def handler(event, current_client=client):
                    try:
                        await self.handle_incoming_message(current_client, event)
                    except (TypeNotFoundError, RPCError, MsgidDecreaseRetryError) as e:
                        if isinstance(e, MsgidDecreaseRetryError):
                            print(f"⚠️ Внутренние проблемы Telegram в обработчике")
                            return
                        if self.is_known_error(e):
                            print(f"⚠️ Известная ошибка в обработчике, удаляем сессию: {e}")
                            await self.move_broken_session(current_client, "handler_error")
                            if current_client in self.active_sessions:
                                self.active_sessions.remove(current_client)
                        else:
                            print(f"❌ Ошибка в обработчике сообщений: {e}")
                    except Exception as e:
                        print(f"❌ Общая ошибка в обработчике: {e}")

                if not hasattr(client, '_message_handlers'):
                    client._message_handlers = []
                client._message_handlers.append(handler)

                print(f"✅ {me.first_name}: прослушка активна")

            except (TypeNotFoundError, RPCError, MsgidDecreaseRetryError) as e:
                if isinstance(e, MsgidDecreaseRetryError):
                    print(f"⚠️ Внутренние проблемы Telegram, пропускаем сессию")
                elif self.is_known_error(e):
                    print(f"⚠️ Известная ошибка сессии, помечаем для удаления")
                    sessions_to_remove.append(client)
                else:
                    print(f"❌ Ошибка настройки прослушки: {e}")
            except Exception as e:
                print(f"❌ Общая ошибка настройки прослушки: {e}")
                sessions_to_remove.append(client)

        for client in sessions_to_remove:
            await self.move_broken_session(client, "listener_setup_failed")
            if client in self.active_sessions:
                self.active_sessions.remove(client)

    async def handle_incoming_message(self, client, event):
        """Обработка входящего сообщения с использованием простого файла"""
        try:
            # Проверка работоспособности сессии
            if self.auto_responder:
                try:
                    me_info = await client.get_me()
                    account_phone = me_info.phone if me_info else None
                except Exception:
                    account_phone = None
                await self.process_auto_response(client, sender, text, account_phone)

            sender = await event.get_sender()
            if not sender:
                return

            # Получаем ID сессии
            session_id = getattr(client, '_session_id', None)
            if not session_id:
                session_id = f"{me.id}_{me.phone}"
                client._session_id = session_id

            # Определяем идентификатор отправителя
            sender_identifiers = []
            if sender.username:
                sender_identifiers.append(f"@{sender.username}")
                sender_identifiers.append(sender.username)
            sender_identifiers.append(str(sender.id))

            # Проверяем в постоянной истории
            is_processed_user = False

            # Проверяем в истории всех времен
            if session_id in self.all_time_processed_users:
                all_time_users = self.all_time_processed_users[session_id]
                for identifier in sender_identifiers:
                    if identifier in all_time_users:
                        is_processed_user = True
                        break

            # Также проверяем в текущем цикле
            if not is_processed_user and session_id in self.session_processed_users:
                current_users = self.session_processed_users[session_id]
                for identifier in sender_identifiers:
                    if identifier in current_users:
                        is_processed_user = True
                        break

            # Если сообщение не от обработанного пользователя - игнорируем
            if not is_processed_user:
                return

            text = event.raw_text
            timestamp = datetime.now().strftime("%H:%M:%S")

            print(f"\n[{timestamp}] 📩 {sender.first_name} -> {me.first_name}: {text[:50]}...")

            # Отправляем уведомление
            if notification_bot:
                account_info = {'phone': me.phone or 'Unknown', 'name': me.first_name or 'Unknown'}
                sender_info = {'name': sender.first_name or 'Unknown', 'username': sender.username or 'unknown'}
                asyncio.create_task(notification_bot.send_notification(account_info, sender_info, text))

            # Обрабатываем автоответ с передачей номера телефона аккаунта
            if self.auto_responder:
                await self.process_auto_response(client, sender, text)
                try:
                    me_info = await client.get_me()
                    account_phone = me_info.phone if me_info else None
                except:
                    account_phone = None
                await self.process_auto_response(client, sender, text, account_phone)
            # Удаляем сообщения
            try:
                dialogs = await client.get_dialogs()
                for dialog in dialogs:
                    if dialog.entity.id == sender.id:
                        async for message in client.iter_messages(dialog.entity, limit=None):
                            try:
                                await message.delete(revoke=False)
                            except Exception as del_e:
                                print(f"⚠️ Не удалось удалить сообщение: {del_e}")
                        print(f"   🗑️ Все сообщения в диалоге с {sender.first_name} удалены")
                        break
            except Exception as e:
                print(f"   ⚠️ Ошибка при удалении сообщений: {e}")

        except (TypeNotFoundError, RPCError, MsgidDecreaseRetryError) as e:
            if isinstance(e, MsgidDecreaseRetryError):
                print(f"⚠️ Внутренние проблемы Telegram")
                return
            if self.is_known_error(e):
                print(f"⚠️ Известная ошибка, удаляем сессию: {e}")
                await self.move_broken_session(client, "known_error_in_handler")
                if client in self.active_sessions:
                    self.active_sessions.remove(client)
            else:
                print(f"❌ Ошибка обработки сообщения: {e}")

        except Exception as e:
            print(f"❌ Общая ошибка обработки сообщения: {e}")

    async def process_auto_response(self, client, sender, message_text, account_phone=None):
        """Обработка автоответа"""
        try:
            if not self.auto_responder:
                return

            user_id = sender.username if sender.username else str(sender.id)
            if sender.username:
                user_id = f"@{sender.username}"

            # Получаем информацию об аккаунте, если не передана
            if account_phone is None:
                try:
                    me_info = await client.get_me()
                    account_phone = me_info.phone if me_info else None
                except:
                    account_phone = None

            response = await self.auto_responder.handle_message(
                user_id=user_id,
                message=message_text,
                phone=sender.phone if hasattr(sender, 'phone') else None,
                username=sender.username,
                first_name=sender.first_name,
            )

            if response:
                await asyncio.sleep(random.uniform(3, 8))

                try:
                    await client(SetTypingRequest(sender, SendMessageTypingAction()))
                    await asyncio.sleep(random.uniform(2, 4))
                except:
                    pass

                await client.send_message(sender, response)

                me = await client.get_me()
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 {me.first_name} -> {sender.first_name}: {response[:50]}...")

        except Exception as e:
            print(f"❌ Ошибка автоответа: {e}")

    async def main_loop(self):
        """Основной цикл БЕЗ очистки истории"""
        print("\n🔄 Запуск основного цикла...")
        self.is_running = True

        while self.is_running:
            try:
                print(f"\n{'=' * 60}")
                print(f"⏰ НАЧАЛО ЦИКЛА - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'=' * 60}")

                # ИСПРАВЛЕНИЕ: Очищаем только текущий цикл, НЕ историю
                self.session_processed_users.clear()

                # Показываем статистику истории
                total_in_history = sum(len(users) for users in self.all_time_processed_users.values())

                await self.check_sessions_health()

                if not self.active_sessions:
                    print("❌ Нет рабочих сессий, пропускаем цикл")
                    await asyncio.sleep(300)
                    continue

                converted = await self.convert_phone_numbers()
                sent = await self.send_messages_to_users()
                await self.check_messages_from_processed()
                await self.setup_message_listeners()

                print(f"\n📊 ИТОГИ ЦИКЛА:")
                print(f"   • Конвертировано: {converted} номеров")
                print(f"   • Отправлено: {sent} сообщений")
                print(f"   • Рабочих сессий: {len(self.active_sessions)}")
                print(f"   • Новых пользователей в истории: {sent}")
                print(f"   • Всего в истории: {total_in_history + sent}")

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

        for client in self.active_sessions:
            try:
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
        print("4. 📊 Показать статистику битых сессий")
        print("5. ❌ Выход")
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
            broken_dir = "broken_sessions"
            if os.path.exists(broken_dir):
                try:
                    files = os.listdir(broken_dir)
                    print(f"🗑️ Найдено {len(files)} битых сессий")
                    shutil.rmtree(broken_dir)
                    os.makedirs(broken_dir, exist_ok=True)
                    print("✅ Папка broken_sessions очищена")
                except Exception as e:
                    print(f"❌ Ошибка очистки: {e}")
            else:
                print("⚠️ Папка broken_sessions не существует")
        elif choice == "4":
            broken_dir = "broken_sessions"
            if os.path.exists(broken_dir):
                files = os.listdir(broken_dir)
                if files:
                    print("\n📊 БИТЫЕ СЕССИИ:")
                    for file in files:
                        parts = file.split('_')
                        if len(parts) >= 2:
                            reason = parts[-2] if len(parts) > 2 else "unknown"
                            print(f"   • {parts[0]}: {reason}")
                    print(f"\n   Всего: {len(files)} файлов")
                else:
                    print("✅ Нет битых сессий")
            else:
                print("✅ Папка broken_sessions не существует")
        elif choice == "5":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор")

    async def cleanup_all_dialogs(self):
        """Удаляет ВСЕ сообщения из всех диалогов у всех сессий"""
        print("\n🗑️ ОЧИСТКА ВСЕХ ДИАЛОГОВ...")

        for client in self.active_sessions:
            try:
                me = await client.get_me()
                print(f"\n📱 Очистка сессии {me.first_name}...")

                dialogs = await client.get_dialogs()
                for dialog in dialogs:
                    if dialog.is_user:  # Только личные чаты
                        try:
                            # Удаляем все сообщения в диалоге
                            deleted_count = 0
                            async for message in client.iter_messages(dialog.entity, limit=None):
                                try:
                                    await message.delete()
                                    deleted_count += 1
                                except:
                                    pass

                            if deleted_count > 0:
                                print(f"   ✅ Удалено {deleted_count} сообщений из диалога с {dialog.name}")
                        except Exception as e:
                            print(f"   ⚠️ Ошибка очистки диалога с {dialog.name}: {e}")

                print(f"✅ Сессия {me.first_name} очищена")

            except Exception as e:
                print(f"❌ Ошибка очистки сессии: {e}")

        print("✅ Очистка всех диалогов завершена")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Программа завершена")
