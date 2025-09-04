import logging
import os
import aiofiles
from datetime import datetime

# Импорт конфигурации
try:
    from config import load_config
except ImportError:
    # Fallback, если config.py недоступен
    def load_config():
        return {
            "log_file": "logs/app.log",
            "log_level": "INFO",
            "enable_file_logging": True,
            "enable_console_logging": True
        }


# --- Логгер ---
def setup_logger():
    """Настройка системы логирования"""
    config = load_config()

    # Создаем папку для логов
    log_dir = os.path.dirname(config["log_file"])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Создаем логгер
    logger = logging.getLogger('mass_sender')
    logger.setLevel(getattr(logging, config.get("log_level", "INFO").upper()))

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Файловый handler
    if config.get("enable_file_logging", True):
        file_handler = logging.FileHandler(config["log_file"], encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Консольный handler
    if config.get("enable_console_logging", True):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# Глобальный логгер
logger = setup_logger()


def log_error(message, exc_info=False):
    logger.error(message, exc_info=exc_info)


def log_info(message):
    logger.info(message)


def log_warning(message):
    logger.warning(message)


def log_debug(message):
    logger.debug(message)


# --- Работа с файлами сообщений ---
async def load_messages_from_file(messages_file):
    """Асинхронная загрузка сообщений из файла"""
    if not os.path.exists(messages_file):
        return await _create_default_messages_file(messages_file)

    try:
        async with aiofiles.open(messages_file, 'r', encoding='utf-8') as f:
            lines = await f.readlines()
            messages = [line.strip() for line in lines if line.strip()]

        if not messages:
            log_warning(f"Файл сообщений пуст: {messages_file}")
            return await _default_messages()

        log_info(f"Загружено {len(messages)} сообщений из {messages_file}")
        return messages

    except Exception as e:
        log_error(f"Ошибка загрузки сообщений из {messages_file}: {e}")
        return await _default_messages()


async def _create_default_messages_file(messages_file):
    """Создание файла сообщений с дефолтными сообщениями"""
    messages = await _default_messages()
    os.makedirs(os.path.dirname(messages_file), exist_ok=True)
    try:
        async with aiofiles.open(messages_file, 'w', encoding='utf-8') as f:
            for msg in messages:
                await f.write(f"{msg}\n")
        log_info(f"Создан файл сообщений: {messages_file}")
    except Exception as e:
        log_error(f"Ошибка создания файла сообщений {messages_file}: {e}")
    return messages


async def _default_messages():
    """Сообщения по умолчанию"""
    messages = [
        "Добрый день! Не смог дозвониться — покупка автомобиля ещё актуальна?",
        "Здравствуйте! Не дозвонился, интерес к покупке автомобиля сохраняется?",
        "Приветствую! Не удалось связаться — покупка автомобиля всё ещё в планах?"
    ]
    log_warning("Используются сообщения по умолчанию")
    return messages


async def add_message_to_file(messages_file, message):
    """Асинхронное добавление сообщения в файл"""
    try:
        os.makedirs(os.path.dirname(messages_file), exist_ok=True)
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
    except Exception as e:
        log_error(f"Ошибка подсчета сообщений: {e}")
        return 0
