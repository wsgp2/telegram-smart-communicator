#!/usr/bin/env python3
"""
✨ ЭЛЕГАНТНЫЙ ДИЗАЙН - самый красивый вариант
"""
from datetime import datetime

def elegant_design():
    """💎 Стиль 7: Супер-элегантный"""
    account_info = {'phone': '+919313919689', 'name': 'Sergey D.'}
    sender_info = {'name': 'Иван Петров', 'username': 'ivan_petrov'}
    message_text = "Привет! Спасибо за информацию, очень интересно!"
    count = 1
    
    return f"""╭─────────────────────────────────────────────────╮
│  🔔  <b>УВЕДОМЛЕНИЕ #{count:03d}</b>  🔔                    │
╰─────────────────────────────────────────────────╯

  📱  <b>Аккаунт</b>     │  <code>{account_info['phone']}</code> ({account_info['name']})
  👤  <b>От кого</b>     │  {sender_info['name']} (@{sender_info['username']})
  💬  <b>Сообщение</b>   │  {message_text}
  🕐  <b>Время</b>       │  {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

╭─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╮"""

if __name__ == "__main__":
    print("💎 ЭЛЕГАНТНЫЙ ДИЗАЙН:")
    print("="*50)
    print(elegant_design())
