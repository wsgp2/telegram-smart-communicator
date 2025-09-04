#!/usr/bin/env python3
"""
📂 Конфиг для массовой рассылки Telegram + AI автоответчик
- Поддержка новых ключей
- Автосоздание директорий
- Работа с таймстампами
"""

import os
import json
from datetime import datetime

CONFIG_FILE = "config.json"


def ensure_dirs(cfg):
    """Создаем папки, если их нет"""
    for path in [
        os.path.dirname(cfg.get("target_users_file", "data/target_users.txt")),
        os.path.dirname(cfg.get("processed_users_file", "data/processed_users.txt")),
        os.path.dirname(cfg.get("new_users_file", "data/new_users.txt")),
        os.path.dirname(cfg.get("messages_file", "data/messages.txt")),
        os.path.dirname(cfg.get("log_file", "logs/app.log"))
    ]:
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)


def load_config():
    """Загружает конфигурацию, создает файл с дефолтами если отсутствует"""
    default_config = {
        "api_id": "",
        "api_hash": "",
        "accounts_per_proxy": 1,
        "proxy_mode": "auto",
        "target_users_file": "data/target_users.txt",
        "processed_users_file": "data/processed_users.txt",
        "new_users_file": "data/new_users.txt",
        "phone_numbers_file": "data/phone_numbers.txt",
        "messages_file": "data/messages.txt",
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
        "log_file": "logs/app.log",
        "log_level": "INFO",
        "enable_file_logging": True,
        "enable_console_logging": True,
        "auto_responder": {
            "enabled": False,
            "max_questions": 3,
            "response_timeout_hours": 24,
            "ai_enabled": True,
            "ai": {
                "api_key": "",
                "model": "gpt-4o-mini",
                "max_tokens": 70,
                "proxy": {
                    "enabled": True,
                    "url": ""
                }
            }
        }
    }

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        ensure_dirs(default_config)
        return default_config

    # Загружаем существующую конфигурацию
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Автоматически добавляем новые ключи
    def merge_defaults(dflt, conf):
        for k, v in dflt.items():
            if isinstance(v, dict):
                conf.setdefault(k, {})
                merge_defaults(v, conf[k])
            else:
                conf.setdefault(k, v)
        return conf

    cfg = merge_defaults(default_config, cfg)
    ensure_dirs(cfg)
    return cfg


def save_config(cfg):
    """Сохраняет конфиг в файл"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def update_config_timestamp(key):
    """Обновляет таймстамп в конфиге"""
    cfg = load_config()
    cfg[key] = datetime.now().isoformat()
    save_config(cfg)


def update_nested_config(keys: list, value):
    """
    Обновляет вложенный ключ в конфиге
    keys: список ключей, пример ['auto_responder','ai','api_key']
    """
    cfg = load_config()
    d = cfg
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value
    save_config(cfg)
