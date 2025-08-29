#!/usr/bin/env python3
import os
import asyncio
from telethon import TelegramClient
import json

# Загружаем конфиг
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

api_id = config["api_id"]
api_hash = config["api_hash"]

async def check_all_sessions():
    print("🔍 Проверка всех сессий...")
    print("="*60)
    
    session_files = [f for f in os.listdir("sessions") if f.endswith(".session")]
    active_sessions = []
    inactive_sessions = []
    
    for session_file in session_files:
        session_name = os.path.splitext(session_file)[0]
        session_path = os.path.join("sessions", session_name)
        
        try:
            client = TelegramClient(session_path, api_id, api_hash)
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✅ {session_file}")
                print(f"   Имя: {me.first_name} {me.last_name or ''}")
                print(f"   Username: @{me.username or 'НЕТ'}")
                print(f"   Телефон: {me.phone}")
                print(f"   ID: {me.id}")
                
                # Проверяем на Сергея Дышканта
                full_name = f"{me.first_name or ''} {me.last_name or ''}".lower()
                if "сергей" in full_name and "дышкант" in full_name:
                    print(f"   🎯 ЭТО СЕРГЕЙ ДЫШКАНТ!")
                elif "sergei" in full_name and "dyshkant" in full_name:
                    print(f"   🎯 ЭТО SERGEI DYSHKANT!")
                    
                active_sessions.append(session_file)
            else:
                print(f"❌ {session_file} - НЕ АВТОРИЗОВАН")
                inactive_sessions.append(session_file)
                
            await client.disconnect()
            print()
            
        except Exception as e:
            print(f"❌ {session_file} - ОШИБКА: {e}")
            inactive_sessions.append(session_file)
            print()
    
    print("="*60)
    print(f"✅ Активных сессий: {len(active_sessions)}")
    print(f"❌ Неактивных сессий: {len(inactive_sessions)}")
    print("="*60)
    
    return active_sessions, inactive_sessions

if __name__ == "__main__":
    asyncio.run(check_all_sessions())
