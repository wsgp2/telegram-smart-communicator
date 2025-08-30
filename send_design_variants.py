#!/usr/bin/env python3
"""
🎨 ОТПРАВКА ВСЕХ ВАРИАНТОВ ДИЗАЙНА В ГРУППУ ДЛЯ ВЫБОРА
"""
import asyncio
import aiohttp
from datetime import datetime

# Данные бота
BOT_TOKEN = "8232028536:AAGTCLsTVkOsLy4JJa3nZiJEg62IRLkWhpM"
GROUP_CHAT_ID = "-1003073517667"

# Тестовые данные
account_info = {'phone': '+919313919689', 'name': 'Sergey D.'}
sender_info = {'name': 'Иван Петров', 'username': 'ivan_petrov'}
message_text = "Привет! Спасибо за информацию, очень интересно!"

async def send_message_to_group(text):
    """Отправка сообщения в группу"""
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    
    try:
        async with aiohttp.ClientSession() as session:
            data = {
                'chat_id': GROUP_CHAT_ID,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            async with session.post(f"{api_url}/sendMessage", json=data) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка отправки: {response.status} - {error_text}")
                    return False
                    
    except Exception as e:
        print(f"🔴 Критическая ошибка: {e}")
        return False

async def send_all_design_variants():
    """Отправляем все варианты дизайна в группу"""
    
    # Заголовок
    header = """🎨 <b>ВЫБОР ДИЗАЙНА УВЕДОМЛЕНИЙ</b> 🎨

Вот все варианты дизайна! Выберите самый красивый ⬇️"""
    
    await send_message_to_group(header)
    await asyncio.sleep(1)
    
    # Все варианты дизайна
    designs = [
        ("🔲 ВАРИАНТ 1: Классические рамки", f"""┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🔔 <b>УВЕДОМЛЕНИЕ #001</b> 
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

╰─────────────────────────────────────────╯"""),

        ("✨ ВАРИАНТ 2: Эмодзи-разделители", f"""🌟 ═══════════════════════════════════════════ 🌟
        🔔 <b>УВЕДОМЛЕНИЕ #001</b>
🌟 ═══════════════════════════════════════════ 🌟

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹"""),

        ("🎯 ВАРИАНТ 3: Минималистичный с точками", f"""• • • • • • • • • • • • • • • • • • • • • • • • • • • • • • •
    🔔 <b>УВЕДОМЛЕНИЕ #001</b>
• • • • • • • • • • • • • • • • • • • • • • • • • • • • • • •

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘"""),

        ("🚀 ВАРИАНТ 4: Космический", f"""✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦
    🔔 <b>УВЕДОМЛЕНИЕ #001</b>
✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐"""),

        ("📋 ВАРИАНТ 5: Деловой", f"""╔══════════════════════════════════════════════════╗
║ 🔔 <b>УВЕДОМЛЕНИЕ #001</b>                             ║
╚══════════════════════════════════════════════════╝

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

╰────────────────────────────────────────╯"""),

        ("🎪 ВАРИАНТ 6: Игривый", f"""🎨 ▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱ 🎨
    🔔 <b>УВЕДОМЛЕНИЕ #001</b>
🎨 ▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱ 🎨

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🌈 ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ 🌈"""),

        ("💎 ВАРИАНТ 7: Супер-элегантный", f"""╭─────────────────────────────────────────────────╮
│  🔔  <b>УВЕДОМЛЕНИЕ #001</b>  🔔                    │
╰─────────────────────────────────────────────────╯

  📱  <b>Аккаунт</b>     │  <code>{account_info['phone']}</code> ({account_info['name']})
  👤  <b>От кого</b>     │  {sender_info['name']} (@{sender_info['username']})
  💬  <b>Сообщение</b>   │  {message_text}
  🕐  <b>Время</b>       │  {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

╭─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╮""")
    ]
    
    # Отправляем каждый вариант
    for i, (title, design) in enumerate(designs, 1):
        print(f"📤 Отправляем {title}")
        
        message = f"{title}\n\n{design}"
        success = await send_message_to_group(message)
        
        if success:
            print(f"✅ Вариант {i} отправлен")
        else:
            print(f"❌ Ошибка отправки варианта {i}")
        
        # Пауза между сообщениями
        await asyncio.sleep(2)
    
    # Заключение
    footer = """🤔 <b>ЧТО ДЕЛАТЬ ДАЛЬШЕ?</b>

Напишите номер понравившегося варианта (1-7) и я его установлю! 

Например: <code>Вариант 5</code> или <code>Мне нравится космический</code>

🚀 Готов к внедрению выбранного дизайна!"""
    
    await asyncio.sleep(3)
    await send_message_to_group(footer)
    print("🎉 Все варианты отправлены в группу!")

if __name__ == "__main__":
    asyncio.run(send_all_design_variants())
