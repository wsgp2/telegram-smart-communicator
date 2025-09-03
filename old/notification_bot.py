#!/usr/bin/env python3
"""
🤖 ПРОСТОЙ БОТ ДЛЯ УВЕДОМЛЕНИЙ (HTTP API)
Принцип 20/80: минимум кода, максимум результата
"""
import aiohttp
import asyncio
import json
from datetime import datetime


class NotificationBot:
    def __init__(self, bot_token, group_chat_id):
        self.bot_token = bot_token
        self.group_chat_id = group_chat_id
        self.notification_count = 0
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_notification(self, account_info, sender_info, message_text):
        """
        ⚡ Быстрая отправка уведомления через HTTP API
        20% кода, 80% функциональности!
        """
        self.notification_count += 1

        # 🎯 Минималистичный дизайн с точками (Вариант 3)
        notification = f"""• • • • • • • • • • • • • • • • • • • • • • • • • • • • • • •
    🔔 <b>УВЕДОМЛЕНИЕ #{self.notification_count:03d}</b>
• • • • • • • • • • • • • • • • • • • • • • • • • • • • • • •

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
👤 <b>От кого:</b> {sender_info['name']} {f"(@{sender_info['username']})" if sender_info['username'] else ""}
💬 <b>Сообщение:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘ ∘"""

        await self._send_to_group(notification)

    async def send_security_notification(self, account_info, sender_info, message_text, message_type="🔐 СЛУЖЕБНОЕ"):
        """
        🚨 КРИТИЧЕСКОЕ уведомление о безопасности (коды входа, новые входы)
        """
        self.notification_count += 1

        # 🚨 СПЕЦИАЛЬНЫЙ ДИЗАЙН ДЛЯ КРИТИЧЕСКИХ УВЕДОМЛЕНИЙ
        notification = f"""🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨
    {message_type} <b>#{self.notification_count:03d}</b>
🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨 🚨

📱 <b>Аккаунт:</b> <code>{account_info['phone']}</code> ({account_info['name']})
⚠️ <b>От кого:</b> {sender_info['name']}
📨 <b>ВАЖНО:</b> {message_text}
🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡ ⚡"""

        await self._send_to_group(notification)

    async def _send_to_group(self, notification):
        """Внутренний метод отправки в группу"""

        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': self.group_chat_id,
                    'text': notification,
                    'parse_mode': 'HTML'
                }

                async with session.post(f"{self.api_url}/sendMessage", json=data) as response:
                    if response.status == 200:
                        print(f"✅ Уведомление #{self.notification_count} отправлено в группу")
                    else:
                        error_text = await response.text()
                        print(f"❌ Ошибка отправки: {response.status} - {error_text}")

        except Exception as e:
            print(f"🔴 Критическая ошибка бота: {e}")

    async def test_connection(self):
        """🔧 Тест соединения с группой"""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': self.group_chat_id,
                    'text': '🤖 Бот уведомлений подключен и готов к работе!',
                    'parse_mode': 'HTML'
                }

                async with session.post(f"{self.api_url}/sendMessage", json=data) as response:
                    if response.status == 200:
                        print("✅ Тест бота успешен! Группа получила сообщение")
                        return True
                    else:
                        print(f"❌ Тест бота провален: {response.status}")
                        return False

        except Exception as e:
            print(f"🔴 Ошибка теста бота: {e}")
            return False

    async def send_shutdown_notification(self):
        """📴 Уведомление о выключении бота"""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': self.group_chat_id,
                    'text': '📴 <b>Бот уведомлений завершил работу</b>\n'
                            f'🕐 Время остановки: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}\n'
                            f'📊 Всего отправлено уведомлений: <code>{self.notification_count}</code>',
                    'parse_mode': 'HTML'
                }

                async with session.post(f"{self.api_url}/sendMessage", json=data) as response:
                    if response.status == 200:
                        print("✅ Уведомление о выключении отправлено")
                        return True
                    else:
                        print(f"❌ Ошибка отправки уведомления о выключении: {response.status}")
                        return False

        except Exception as e:
            print(f"🔴 Ошибка отправки уведомления о выключении: {e}")
            return False


# 📦 Глобальный экземпляр бота
notification_bot = None


def init_notification_bot():
    """⚡ Быстрая инициализация бота"""
    global notification_bot

    BOT_TOKEN = "8232028536:AAGTCLsTVkOsLy4JJa3nZiJEg62IRLkWhpM"
    GROUP_CHAT_ID = "-1003073517667"

    notification_bot = NotificationBot(BOT_TOKEN, GROUP_CHAT_ID)
    print("🤖 Notification Bot инициализирован")
    return notification_bot


async def notify_admin_via_bot(sender, text, receiving_client):
    """
    🚀 ГЛАВНАЯ ФУНКЦИЯ УВЕДОМЛЕНИЙ
    Заменяет старую notify_admin()
    """
    if not notification_bot:
        return

    try:
        # Информация об аккаунте получившем сообщение
        me = await receiving_client.get_me()
        account_info = {
            'phone': me.phone,
            'name': me.first_name or 'Unknown'
        }

        # Информация об отправителе
        sender_info = {
            'name': sender.first_name or 'Unknown',
            'username': sender.username
        }

        await notification_bot.send_notification(
            account_info, sender_info, text
        )

    except Exception as e:
        print(f"[!] Ошибка уведомления через бота: {e}")


# 🧪 ТЕСТИРОВАНИЕ
async def test_bot():
    """Быстрый тест бота"""
    init_notification_bot()

    # Тест соединения
    success = await notification_bot.test_connection()

    if success:
        # Тестовое уведомление
        fake_account = {'phone': '+919313919689', 'name': 'Sergey D.'}
        fake_sender = {'name': 'Тест Юзер', 'username': 'test_user'}

        await notification_bot.send_notification(
            fake_account, fake_sender, "Тестовое сообщение от системы!"
        )


if __name__ == "__main__":
    asyncio.run(test_bot())