#!/usr/bin/env python3
"""
🎨 ВАРИАНТЫ ДИЗАЙНА УВЕДОМЛЕНИЙ
Выберем самый красивый!
"""
import asyncio
from datetime import datetime

# Тестовые данные
account_info = {'phone': '+919313919689', 'name': 'Sergey D.'}
sender_info = {'name': 'Иван Петров', 'username': 'ivan_petrov'}
message_text = "Привет! Спасибо за информацию, очень интересно!"
count = 1

def design_variant_1():
    """🔲 Стиль 1: Классические рамки"""
    return f"""┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🔔 <b>УВЕДОМЛЕНИЕ #{count:03d}</b> 
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

╰─────────────────────────────────────────╯"""

def design_variant_2():
    """✨ Стиль 2: Эмодзи-разделители"""
    return f"""🌟 ═══════════════════════════════════════════ 🌟
        🔔 <b>УВЕДОМЛЕНИЕ #{count:03d}</b>
🌟 ═══════════════════════════════════════════ 🌟

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹"""

def design_variant_3():
    """🎯 Стиль 3: Минималистичный с точками"""
    return f"""• • • • • • • • • • • • • • • • • • • • • • • • • • • • • • •
    🔔 <b>УВЕДОМЛЕНИЕ #{count:03d}</b>
• • • • • • • • • • • • • • • • • • • • • • • • • • • • • • •

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘"""

def design_variant_4():
    """🚀 Стиль 4: Космический"""
    return f"""✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦
    🔔 <b>УВЕДОМЛЕНИЕ #{count:03d}</b>
✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐ ⭐"""

def design_variant_5():
    """📋 Стиль 5: Деловой"""
    return f"""╔══════════════════════════════════════════════════╗
║ 🔔 <b>УВЕДОМЛЕНИЕ #{count:03d}</b>                             ║
╚══════════════════════════════════════════════════╝

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

╰────────────────────────────────────────╯"""

def design_variant_6():
    """🎪 Стиль 6: Игривый"""
    return f"""🎨 ▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱ 🎨
    🔔 <b>УВЕДОМЛЕНИЕ #{count:03d}</b>
🎨 ▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱ 🎨

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} (@{sender_info['username']})
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🌈 ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ ▲ ▼ 🌈"""

if __name__ == "__main__":
    print("🎨 ВАРИАНТЫ ДИЗАЙНА УВЕДОМЛЕНИЙ:")
    print("="*50)
    
    designs = [
        ("Классические рамки", design_variant_1),
        ("Эмодзи-разделители", design_variant_2),
        ("Минималистичный с точками", design_variant_3),
        ("Космический", design_variant_4),
        ("Деловой", design_variant_5),
        ("Игривый", design_variant_6)
    ]
    
    for i, (name, design_func) in enumerate(designs, 1):
        print(f"\n🔹 ВАРИАНТ {i}: {name}")
        print("-" * 50)
        print(design_func())
        print()
