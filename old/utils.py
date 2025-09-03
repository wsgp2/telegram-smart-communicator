import logging
import os
import aiofiles
from datetime import datetime

# Импортируем load_config
try:
    from config import load_config
except ImportError:
    # Fallback если config.py не доступен
    def load_config():
        return {
            "log_file": "logs/app.log",
            "log_level": "INFO",
            "enable_file_logging": True,
            "enable_console_logging": True
        }


# Настройка логгера
def setup_logger():
    """Настройка системы логгирования"""
    config = load_config()

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