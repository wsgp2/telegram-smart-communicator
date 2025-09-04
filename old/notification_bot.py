#!/usr/bin/env python3
import aiohttp
import asyncio
from datetime import datetime


class NotificationBot:
    def __init__(self, bot_token, group_chat_id, max_retries=3, retry_delay=5):
        self.bot_token = bot_token
        self.group_chat_id = group_chat_id
        self.notification_count = 0
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _send_to_group(self, text, parse_mode="HTML"):
        session = await self._get_session()
        payload = {'chat_id': self.group_chat_id, 'text': text, 'parse_mode': parse_mode}

        for attempt in range(1, self.max_retries + 1):
            try:
                async with session.post(f"{self.api_url}/sendMessage", json=payload) as resp:
                    if resp.status == 200:
                        print(f"✅ Уведомление #{self.notification_count} отправлено")
                        return True
                    else:
                        error_text = await resp.text()
                        print(f"❌ Ошибка {resp.status}: {error_text}")
            except Exception as e:
                print(f"🔴 Ошибка отправки: {e}")

            await asyncio.sleep(self.retry_delay)
        return False

    async def send_notification(self, account_info, sender_info, message_text):
        self.notification_count += 1
        notification = (
            f"🔔 <b>УВЕДОМЛЕНИЕ #{self.notification_count:03d}</b>\n"
            f"📱 Аккаунт: <code>{account_info['phone']}</code> ({account_info['name']})\n"
            f"👤 От кого: {sender_info['name']} "
            f"{f'(@{sender_info['username']})' if sender_info.get('username') else ''}\n"
            f"💬 Сообщение: {message_text}\n"
            f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
        await self._send_to_group(notification)

    async def send_security_notification(self, account_info, sender_info, message_text, message_type="🔐 СЛУЖЕБНОЕ"):
        self.notification_count += 1
        notification = (
            f"🚨 {message_type} <b>#{self.notification_count:03d}</b> 🚨\n"
            f"📱 Аккаунт: <code>{account_info['phone']}</code> ({account_info['name']})\n"
            f"⚠️ От кого: {sender_info['name']}\n"
            f"📨 ВАЖНО: {message_text}\n"
            f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
        await self._send_to_group(notification)

    async def send_shutdown_notification(self):
        self.notification_count += 1
        text = (
            f"📴 <b>Бот завершил работу</b>\n"
            f"🕐 Время остановки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"📊 Всего уведомлений: <code>{self.notification_count}</code>"
        )
        await self._send_to_group(text)

    async def test_connection(self):
        return await self._send_to_group("🤖 Бот уведомлений подключен и готов к работе!")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# 📦 Глобальный экземпляр
notification_bot = None


def init_notification_bot(bot_token=None, group_chat_id=None):
    global notification_bot
    BOT_TOKEN = bot_token or "токен"
    GROUP_CHAT_ID = group_chat_id or "-1003073517667"
    notification_bot = NotificationBot(BOT_TOKEN, GROUP_CHAT_ID)
    print("🤖 Notification Bot инициализирован")
    return notification_bot
