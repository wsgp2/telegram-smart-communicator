#!/usr/bin/env python3
# 📨 Простой скрипт для мониторинга входящих сообщений
import os
import sys
import time

from telethon import TelegramClient, events, utils


def получить_переменную(название, сообщение, тип=str):
    """Получает переменную из окружения или запрашивает у пользователя"""
    if название in os.environ:
        return os.environ[название]
    while True:
        значение = input(сообщение)
        try:
            return тип(значение)
        except ValueError as e:
            print(e, file=sys.stderr)
            time.sleep(1)


# Настройки подключения
сессия = os.environ.get('TG_SESSION', 'монитор_сообщений')
api_id = получить_переменную('TG_API_ID', 'Введите ваш API ID: ', int)
api_hash = получить_переменную('TG_API_HASH', 'Введите ваш API Hash: ')
прокси = None  # Для настройки прокси: https://github.com/Anorov/PySocks

# Создаем и запускаем клиента
клиент = TelegramClient(сессия, api_id, api_hash, proxy=прокси).start()


# 🔍 МОНИТОРИНГ СООБЩЕНИЙ
# pattern - это регулярное выражение для фильтрации сообщений
# "(?i)" - игнорирует регистр, | разделяет варианты
# Сейчас отслеживает только сообщения с "привет" или "hello"
@клиент.on(events.NewMessage(pattern=r'(?i).*\b(привет|hello|hi|здравствуй)\b'))
async def обработчик_сообщений(событие):
    отправитель = await событие.get_sender()
    имя = utils.get_display_name(отправитель)
    print(f'💬 {имя} написал: {событие.text}')

try:
    print('🔄 Мониторинг запущен (Нажмите Ctrl+C для остановки)')
    клиент.run_until_disconnected()
finally:
    клиент.disconnect()

# 💡 ПРИМЕЧАНИЕ: Можно использовать более простой способ:
#
#   with клиент:
#       клиент.run_until_disconnected()
#
# Это автоматически подключает и отключает клиента
