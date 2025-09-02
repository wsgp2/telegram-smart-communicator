import asyncio
import random
from telethon import events
from notification_bot import notification_bot, init_notification_bot
from user_manager import UserManager
from utils import load_messages_from_file, log_error, log_info, log_warning, add_message_to_file, get_messages_count
import os
import logging
import aiofiles
import json


# Настройка логгера
def setup_logger():
    """Настройка системы логгирования"""
    # Конфиг по умолчанию
    config = {
        "log_file": "logs/app.log",
        "log_level": "INFO",
        "enable_file_logging": True,
        "enable_console_logging": True
    }

    # Пытаемся загрузить реальный конфиг
    try:
        with open("config.json", "r") as f:
            file_config = json.load(f)
            config.update(file_config)
    except:
        pass

    # Создаем папку для логов
    log_dir = os.path.dirname(config["log_file"])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Создаем логгер
    logger = logging.getLogger('mass_sender')
    logger.setLevel(getattr(logging, config["log_level"]))

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Файловый handler
    if config["enable_file_logging"]:
        file_handler = logging.FileHandler(config["log_file"], encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Консольный handler
    if config["enable_console_logging"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# Глобальный логгер
logger = setup_logger()


def log_error(message, exc_info=False):
    """Логгирование ошибок"""
    logger.error(message, exc_info=exc_info)


def log_info(message):
    """Логгирование информации"""
    logger.info(message)


def log_warning(message):
    """Логгирование предупреждений"""
    logger.warning(message)


def log_debug(message):
    """Логгирование отладочной информации"""
    logger.debug(message)


async def load_messages_from_file(messages_file):
    """Загрузка сообщений из файла"""
    if not os.path.exists(messages_file):
        # Создаем файл с сообщениями по умолчанию
        default_messages = [
            "Добрый день! Не смог дозвониться — покупка автомобиля ещё актуальна?",
            "Здравствуйте! Не дозвонился, интерес к покупке автомобиля сохраняется?",
            "Приветствую! Не удалось связаться — покупка автомобиля всё ещё в планах?",
            "Добрый день! Не дозвонился, вопрос по покупке автомобиля остаётся?",
            "Здравствуйте! Не получилось дозвониться — покупка автомобиля ещё нужна?"
        ]

        # Создаем папку если нужно
        os.makedirs(os.path.dirname(messages_file), exist_ok=True)

        async with aiofiles.open(messages_file, 'w', encoding='utf-8') as f:
            for msg in default_messages:
                await f.write(f"{msg}\n")

        log_info(f"Создан файл сообщений: {messages_file}")
        return default_messages

    try:
        async with aiofiles.open(messages_file, 'r', encoding='utf-8') as f:
            content = await f.read()
            messages = [line.strip() for line in content.splitlines() if line.strip()]

        if not messages:
            log_warning(f"Файл сообщений пуст: {messages_file}")
            return await load_default_messages()

        log_info(f"Загружено {len(messages)} сообщений из {messages_file}")
        return messages

    except Exception as e:
        log_error(f"Ошибка загрузки сообщений: {e}")
        return await load_default_messages()


async def load_default_messages():
    """Загрузка сообщений по умолчанию"""
    default_messages = [
        "Добрый день! Не смог дозвониться — покупка автомобиля ещё актуальна?",
        "Здравствуйте! Не дозвонился, интерес к покупке автомобиля сохраняется?",
        "Приветствую! Не удалось связаться — покупка автомобиля всё ещё в планах?"
    ]
    log_warning("Используются сообщения по умолчанию")
    return default_messages


async def add_message_to_file(messages_file, message):
    """Добавление нового сообщения в файл"""
    try:
        async with aiofiles.open(messages_file, 'a', encoding='utf-8') as f:
            await f.write(f"{message}\n")
        log_info(f"Добавлено новое сообщение: {message}")
        return True
    except Exception as e:
        log_error(f"Ошибка добавления сообщения: {e}")
        return False


async def get_messages_count(messages_file):
    """Получение количества сообщений"""
    try:
        messages = await load_messages_from_file(messages_file)
        return len(messages)
    except:
        return 0


class MessageHandler:
    def __init__(self):
        self.user_manager = UserManager()
        self.config = self._load_config()
        self.messages = []

    async def initialize(self):
        """Инициализация загрузки сообщений"""
        try:
            # Используем messages_file из конфига
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
        except:
            return {}


    def is_telegram_service_message(self, event, sender):
        if not sender:
            return False

        text = event.message.text if event and event.message else ""

        if hasattr(sender, 'id') and sender.id in [777000, 42777]:
            return True

        if hasattr(sender, 'phone') and sender.phone == '42777':
            return True

        if hasattr(sender, 'username') and sender.username and sender.username.lower() == 'telegram':
            return True

        if hasattr(sender, 'first_name') and sender.first_name and sender.first_name.strip() == 'Telegram':
            return True

        if text:
            text_lower = text.lower()
            service_patterns = [
                'код для входа в telegram', 'login code for telegram',
                'your telegram code', 'ваш код telegram',
                'new login to your telegram account', 'новый вход в ваш аккаунт telegram'
            ]

            for pattern in service_patterns:
                if pattern in text_lower:
                    return True

            import re
            code_match = re.search(r'\b\d{5,6}\b', text)
            if code_match and ('telegram' in text_lower and ('код' in text_lower or 'code' in text_lower)):
                return True

        return False

    async def notify_telegram_service(self, sender, text, client):
        if not notification_bot:
            return

        try:
            me = await client.get_me()
            message_type = "🔐 СЛУЖЕБНОЕ УВЕДОМЛЕНИЕ"

            if 'код для входа' in text.lower() or 'login code' in text.lower():
                message_type = "🔑 КОД ВХОДА"
            elif 'new login' in text.lower() or 'новый вход' in text.lower():
                message_type = "🚨 НОВЫЙ ВХОД"

            account_info = {'phone': me.phone, 'name': me.first_name or 'Unknown'}
            sender_info = {
                'name': sender.first_name or 'Telegram',
                'username': getattr(sender, 'username', 'telegram_service')
            }

            await notification_bot.send_security_notification(account_info, sender_info, text, message_type)

        except Exception as e:
            log_error(f"Error sending service notification: {e}")


        except Exception as e:
            # Тихо логируем ошибки, не спамим консоль
            print(f"❌ Ошибка обработки ответа (тихий режим): {e}")

    async def send_messages(self, sessions, users, message, delay_ms, msgs_per_acc):
        if not users or not sessions:
            log_warning("Нет пользователей или сессий для отправки")
            return 0
        if not self.messages:
            log_warning("Сообщения не загружены, пытаемся загрузить...")
            success = await self.initialize()
            if not success:
                log_error("Не удалось загрузить сообщения для отправки")
                return 0

        total_sent = 0
        random.shuffle(users)


        tasks = []
        for client in sessions:
            task = self._send_for_client(client, users, message, delay_ms, msgs_per_acc)
            tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, int):
                    total_sent += result
                elif isinstance(result, Exception):
                    log_error(f"Ошибка при отправке: {result}", exc_info=True)

            log_info(f"Всего отправлено сообщений: {total_sent}")

        except Exception as e:
            log_error(f"Критическая ошибка при отправке: {e}", exc_info=True)

        return total_sent

    async def _send_for_client(self, client, users, message, delay_ms, msgs_per_acc):
        try:
            me = await client.get_me()
            sent_count = 0

            for i in range(min(msgs_per_acc, len(users))):
                if not users:
                    break

                target = users.pop()
                try:
                    entity = await client.get_entity(target)

                    # Используем загруженные сообщения
                    if self.messages:
                        random_message = random.choice(self.messages)
                    else:
                        random_message = "Добрый день! Не смог дозвониться — покупка автомобиля ещё актуальна?"

                    # Устанавливаем TTL если включено
                    if self.config.get('auto_ttl_messages', False) and hasattr(client, 'chat_manager'):
                        await client.chat_manager.set_auto_delete_1_month(entity)

                    # Отправляем сообщение
                    sent_message = await client.send_message(entity, random_message)

                    # 🔥 МИНИМАЛЬНЫЙ ВЫВОД: только факт отправки
                    print(f"✅ {me.first_name} -> {target}")

                    # Сохраняем пользователя как обработанного
                    client.sent_users.add(entity.id)
                    sent_count += 1

                    # 🗑️ Автоматически удаляем и скрываем
                    if hasattr(client, 'chat_manager'):
                        try:
                            await client.chat_manager._delayed_delete(sent_message)
                            await client.chat_manager.hide_chat(target)
                        except Exception:
                            pass  # Тихо игнорируем ошибки

                    # Помечаем пользователя как обработанного
                    await self.user_manager.mark_as_processed([target])

                    # Задержка между отправками
                    base_delay = delay_ms / 1000.0
                    jitter = random.uniform(-0.355, 0.355)
                    await asyncio.sleep(max(0.1, base_delay + jitter))

                except Exception as e:
                    print(f"❌ Ошибка отправки {target}: {e}")

            return sent_count

        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return 0

        except Exception as e:
            print(f"❌ Ошибка в _send_for_client: {e}")
            return 0

        except Exception as e:
            log_error(f"Ошибка в _send_for_client: {e}", exc_info=True)
            return 0