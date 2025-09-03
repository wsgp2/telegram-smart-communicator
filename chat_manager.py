#!/usr/bin/env python3
import asyncio
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.functions.folders import EditPeerFoldersRequest
from telethon.tl.functions.messages import SetHistoryTTLRequest
from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings, InputFolderPeer
from collections import defaultdict
from typing import Callable

class ChatManager:
    """Асинхронный менеджер чатов с кэшированием и очередью сообщений"""

    def __init__(self, client: TelegramClient, auto_responder: Callable = None, auto_delete_delay: int = 4):
        self.client = client
        self.auto_responder = auto_responder  # callback для автоответа
        self.auto_delete_delay = auto_delete_delay
        self.processed_chats = set()  # кэш обработанных чатов
        self.entity_cache = {}  # кэш InputEntity для уменьшения API запросов
        self.message_queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self.running = False

    # -----------------------
    # Основной цикл обработки сообщений
    # -----------------------
    async def run(self):
        """Асинхронный цикл обработки сообщений из очереди"""
        if self.running:
            return
        self.running = True
        while True:
            msg_data = await self.message_queue.get()
            target = msg_data.get("target")
            text = msg_data.get("text")
            await self.send_hide_and_mute(target, text)
            self.message_queue.task_done()

    # -----------------------
    # Добавление сообщения в очередь
    # -----------------------
    async def queue_message(self, target, text: str):
        """Добавляем сообщение в очередь на обработку"""
        await self.message_queue.put({"target": target, "text": text})

    # -----------------------
    # Получение InputEntity с кэшированием
    # -----------------------
    async def get_peer(self, username_or_id):
        if username_or_id in self.entity_cache:
            return self.entity_cache[username_or_id]

        if hasattr(username_or_id, 'id'):
            entity = await self.client.get_input_entity(username_or_id)
            self.entity_cache[username_or_id] = entity
            return entity

        if isinstance(username_or_id, str) and username_or_id.startswith('@'):
            username_or_id = username_or_id[1:]

        entity = await self.client.get_input_entity(username_or_id)
        self.entity_cache[username_or_id] = entity
        return entity

    # -----------------------
    # Мьют чата
    # -----------------------
    async def mute_chat(self, peer, duration=2147483647):
        try:
            await self.client(UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(peer),
                settings=InputPeerNotifySettings(mute_until=duration, sound=None, show_previews=False)
            ))
            return True
        except:
            return False

    # -----------------------
    # Архив чата
    # -----------------------
    async def archive_chat(self, peer, folder_id=1):
        try:
            await self.client(EditPeerFoldersRequest(folder_peers=[InputFolderPeer(peer=peer, folder_id=folder_id)]))
            return True
        except:
            return False

    # -----------------------
    # Полный цикл: отправка + автоответ + мьют + архив
    # -----------------------
    async def send_hide_and_mute(self, target, message_text):
        try:
            peer = await self.get_peer(target)

            # Отправка сообщения
            sent_msg = await self.client.send_message(peer, message_text)
            asyncio.create_task(self._delayed_delete(sent_msg))

            # Мьют и архив, только если чат еще не обработан
            if str(target) not in self.processed_chats:
                muted = await self.mute_chat(peer)
                archived = await self.archive_chat(peer)
                if muted and archived:
                    self.processed_chats.add(str(target))

            # Вызов автоответчика
            if self.auto_responder:
                asyncio.create_task(self.auto_responder(peer, message_text))

            return True
        except Exception as e:
            print(f"❌ Ошибка send_hide_and_mute для {target}: {e}")
            return False

    # -----------------------
    # Удаление сообщений с задержкой
    # -----------------------
    async def _delayed_delete(self, message):
        try:
            await asyncio.sleep(self.auto_delete_delay)
            await message.delete(revoke=False)
        except:
            pass

    # -----------------------
    # Настройка автоудаления через 1 месяц
    # -----------------------
    async def set_auto_delete_1_month(self, peer):
        try:
            await self.client(SetHistoryTTLRequest(peer=peer, period=2592000))
            return True
        except:
            return False

    # -----------------------
    # Очистка кэшей
    # -----------------------
    def clear_cache(self):
        processed = len(self.processed_chats)
        self.processed_chats.clear()
        self.entity_cache.clear()
        print(f"🗑️ Очистка кэша: {processed} чатов сброшено")

    # -----------------------
    # Статистика
    # -----------------------
    async def get_stats(self):
        try:
            me = await self.client.get_me()
            return {
                "account_name": me.first_name,
                "account_phone": me.phone,
                "processed_chats": len(self.processed_chats),
                "queued_messages": self.message_queue.qsize(),
            }
        except:
            return {
                "account_name": "Error",
                "account_phone": "Error",
                "processed_chats": len(self.processed_chats),
                "queued_messages": self.message_queue.qsize(),
            }
