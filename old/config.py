import os
import json
from datetime import datetime

CONFIG_FILE = "config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "api_id": "",
            "api_hash": "",
            "accounts_per_proxy": 1,
            "proxy_mode": "auto",
            "target_users_file": "data/target_users.txt",
            "processed_users_file": "data/processed_users.txt",
            "new_users_file": "data/new_users.txt",
            "phone_numbers_file": "data/phone_numbers.txt",
            "message": "Привет!",
            "delay_ms": 1000,
            "messages_per_account": 2,
            "max_messages_per_account": 10,
            "proxy_type": "socks5",
            "admin_username": "",
            "auto_hide_chats": True,
            "auto_delete_delay": 4,
            "auto_ttl_messages": True,
            "max_connections": 100,
            "request_timeout": 30,
            "connection_pool_size": 10,
            "auto_check_new_sessions": True,
            "auto_check_new_users": True,
            "check_interval_minutes": 5,
            "last_session_check": None,
            "last_user_check": None,
            "messages_file": "data/messages.txt",
            "log_file": "logs/app.log",
            "log_level": "INFO",
            "enable_file_logging": True,
            "enable_console_logging": True,
            
            # Автоответчик для опроса клиентов
            "auto_responder": {
                "enabled": False,  # По умолчанию выключен
                "max_questions": 3,  # Максимум вопросов на клиента
                "response_timeout_hours": 24,  # Таймаут ожидания ответа
                "ai_enabled": True,  # Использовать AI для генерации ответов
                "ai": {
                    "api_key": "your_openai_api_key_here",  # OpenAI API ключ
                    "model": "gpt-4.1-mini",  # Модель для генерации ответов
                    "max_tokens": 70,  # Максимум токенов для ответа
                    # Прокси для OpenAI API (как в chatbot_export)
                    "proxy": {
                        "enabled": True,  # Включить прокси по умолчанию
                        "url": "http://user:pass@proxy.example.com:port"  # Тот же прокси что в chatbot_export
                    }
                }
            }
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    defaults = {
        "accounts_per_proxy": 1,
        "proxy_mode": "auto",
        "target_users_file": "data/target_users.txt",
        "processed_users_file": "data/processed_users.txt",
        "new_users_file": "data/new_users.txt",
        "phone_numbers_file": "data/phone_numbers.txt",
        "message": "Привет!",
        "delay_ms": 1000,
        "messages_per_account": 2,
        "max_messages_per_account": 10,
        "proxy_type": "socks5",
        "admin_username": "",
        "auto_hide_chats": True,
        "auto_delete_delay": 4,
        "auto_ttl_messages": True,
        "max_connections": 100,
        "request_timeout": 30,
        "connection_pool_size": 10,
        "auto_check_new_sessions": True,
        "auto_check_new_users": True,
        "check_interval_minutes": 5,
        "last_session_check": None,
        "last_user_check": None,
        "messages_file": "data/messages.txt",
        "log_file": "logs/app.log",
        "log_level": "INFO",
        "enable_file_logging": True,
        "enable_console_logging": True,
        
        # Автоответчик для опроса клиентов
        "auto_responder": {
            "enabled": False,
            "max_questions": 3,
            "response_timeout_hours": 24,
            "ai_enabled": True,
            "ai": {
                "api_key": "your_openai_api_key_here",
                "model": "gpt-4.1-mini", 
                "max_tokens": 70,
                "proxy": {
                    "enabled": True,
                    "url": "http://user:pass@proxy.example.com:port"
                }
            }
        }
    }
    for key, value in defaults.items():
        if key not in cfg:
            cfg[key] = value

    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def update_config_timestamp(key):
    cfg = load_config()
    cfg[key] = datetime.now().isoformat()
    save_config(cfg)
