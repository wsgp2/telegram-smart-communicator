#!/usr/bin/env python3
"""
🔍 Скрипт для получения Chat ID админа
"""
import asyncio
from telethon import TelegramClient
import json

async def get_admin_id():
    # Загружаем конфиг
    with open('config.json', 'r') as f:
        cfg = json.load(f)
    
    client = TelegramClient('temp_admin_id', cfg['api_id'], cfg['api_hash'])
    
    try:
        await client.start()
        
        print("🔍 Поиск вашего Chat ID...")
        
        # Получаем информацию о себе (текущем пользователе)
        me = await client.get_me()
        admin_chat_id = me.id
        
        print(f"✅ Найден Admin Chat ID: {admin_chat_id}")
        print(f"📱 Имя: {me.first_name} {me.last_name or ''}")
        print(f"📞 Телефон: {me.phone}")
        
        # Сохраняем в файл для удобства
        with open('admin_info.txt', 'w') as f:
            f.write(f"Admin Chat ID: {admin_chat_id}\n")
            f.write(f"Name: {me.first_name} {me.last_name or ''}\n")
            f.write(f"Phone: {me.phone}\n")
        
        print("💾 Информация сохранена в admin_info.txt")
        
        return admin_chat_id
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(get_admin_id())
