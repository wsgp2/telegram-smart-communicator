#!/usr/bin/env python3
"""
🗂️ МЕНЕДЖЕР ЧАТОВ - АВТОМАТИЧЕСКОЕ МЬЮТИРОВАНИЕ И АРХИВИРОВАНИЕ
Скрывает чаты с получателями рассылки, но сохраняет возможность получатьф сообщения
"""
import asyncio
import json
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.functions.folders import EditPeerFoldersRequest
from telethon.tl.functions.messages import SetHistoryTTLRequest
from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings, InputFolderPeer


class ChatManager:
    """🗂️ Менеджер для автоматического скрытия чатов"""

    def __init__(self, client):
        self.client = client
        self.auto_delete_delay = 4  # Задержка удаления в секундах (3-5 сек)
        self.processed_chats = set()  # 🎯 Кэш обработанных чатов (оптимизация API запросов)

    async def mute_chat(self, peer, duration=2147483647):
        try:
            await self.client(UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(peer),
                settings=InputPeerNotifySettings(
                    mute_until=duration,
                    sound=None,
                    show_previews=False
                )
            ))
            print(f"✅ Чат замьючен: {peer}")
            return True
        except Exception as e:
            print(f"❌ Ошибка мьютинга чата {peer}: {e}")
            print(f"   Пробуем альтернативный способ...")
            try:
                # Альтернативный способ через edit_2fa
                entity = await self.client.get_entity(peer)
                await self.client.edit_2fa(entity, mute_until=duration)
                print(f"✅ Чат замьючен альтернативным способом: {peer}")
                return True
            except:
                print(f"   Альтернативный способ тоже не сработал")
                return False

    async def archive_chat(self, peer):
        """📂 Архивируем чат (перемещаем в папку архива)"""
        try:
            await self.client(EditPeerFoldersRequest(
                folder_peers=[InputFolderPeer(
                    peer=peer,
                    folder_id=1  # 1 = Архив
                )]
            ))
            print(f"✅ Чат заархивирован: {peer}")
            return True
        except Exception as e:
            print(f"❌ Ошибка архивирования чата {peer}: {e}")
            return False

    async def hide_chat(self, username_or_id):
        try:
            # Получаем уникальный идентификатор чата для кэширования
            if hasattr(username_or_id, 'id'):
                # Это объект пользователя, используем его ID
                chat_id = username_or_id.id
            else:
                # Это строка username или ID
                if isinstance(username_or_id, str) and username_or_id.startswith('@'):
                    username_or_id = username_or_id[1:]  # Убираем @
                chat_id = str(username_or_id)

            # 🎯 ОПТИМИЗАЦИЯ: Проверяем кэш обработанных чатов
            if chat_id in self.processed_chats:
                print(f"✅ Чат {chat_id} уже обработан, пропускаем мьют+архив (оптимизация)")
                return True

            # Получаем peer объект для API запросов
            peer = await self.client.get_input_entity(username_or_id)

            # Мьютим чат (только первый раз!)
            muted = await self.mute_chat(peer)

            # Архивируем чат (только первый раз!)
            archived = await self.archive_chat(peer)

            # Добавляем в кэш обработанных чатов
            if muted and archived:
                self.processed_chats.add(chat_id)
                print(f"🎯 Чат {chat_id} добавлен в кэш (больше не будем мьютить/архивировать)")

            return muted and archived

        except Exception as e:
            print(f"❌ Ошибка скрытия чата {username_or_id}: {e}")
            return False

    async def send_and_hide_message(self, target, message_text):
        """📤➡️🗑️ Отправляем сообщение и удаляем его с задержкой"""
        try:
            print(f"📤 Отправляем: {message_text}")

            # Отправляем сообщение
            sent_message = await self.client.send_message(target, message_text)
            print(f"✅ Сообщение отправлено")

            # Запускаем удаление с задержкой в фоне
            asyncio.create_task(self._delayed_delete(sent_message))

            return sent_message

        except Exception as e:
            print(f"❌ Ошибка отправки сообщения: {e}")
            return None

    async def _delayed_delete(self, message):
        """🗑️ Тихий режим удаления сообщений"""
        try:
            await asyncio.sleep(self.auto_delete_delay)
            await message.delete(revoke=False)
        except Exception:
            pass

    async def delete_incoming_message(self, message):
        try:
            await message.delete(revoke=False)
        except Exception:
            pass

    async def send_hide_and_mute(self, target, message_text):
        print(f"\n🎯 ПОЛНЫЙ ЦИКЛ ДЛЯ {target}")
        print("-" * 30)

        sent_message = await self.send_and_hide_message(target, message_text)
        if not sent_message:
            return False

        await asyncio.sleep(1)
        hidden = await self.hide_chat(target)

        if hidden:
            print(f"✅ Полный цикл завершен для {target}")
            print(f"   📤 Сообщение отправлено")
            print(f"   🗑️ Сообщение будет удалено через 4 сек")
            print(f"   🔇 Чат замьючен")
            print(f"   📂 Чат заархивирован")
        else:
            print(f"⚠️ Сообщение отправлено, но чат не скрыт")

        return hidden

    async def delete_incoming_message(self, message):
        """🗑️ Удаляем входящее сообщение только у себя"""
        try:
            await message.delete(revoke=False)
            print(f"🗑️ Входящее сообщение удалено только у нас")
            return True
        except Exception as e:
            print(f"❌ Ошибка удаления входящего сообщения: {e}")
            return False

    async def set_auto_delete_1_month(self, peer):
        """⏰ Устанавливаем автоудаление сообщений через 1 месяц"""
        try:
            # TTL = 2592000 секунд = 30 дней = 1 месяц
            await self.client(SetHistoryTTLRequest(
                peer=peer,
                period=2592000  # 1 месяц в секундах
            ))
            print(f"⏰ Установлено автоудаление через 1 месяц: {peer}")
            return True
        except Exception as e:
            print(f"❌ Ошибка установки автоудаления: {e}")
            return False

    def clear_processed_chats_cache(self):
        """🗑️ Очищаем кэш обработанных чатов (для нового сеанса)"""
        cleared_count = len(self.processed_chats)
        self.processed_chats.clear()
        print(f"🗑️ Очищен кэш обработанных чатов ({cleared_count} записей)")
        return cleared_count

    async def get_chat_manager_stats(self):
        """Получить статистику менеджера чатов с проверкой доступности"""
        try:
            me = await self.client.get_me()
            stats = self.get_optimization_stats()
            return {
                'account_name': me.first_name or 'Unknown',
                'account_phone': me.phone or 'No phone',
                'processed_chats': stats['processed_chats_count'],
                'saved_api_calls': stats['saved_api_calls'],
                'status': 'active'
            }
        except Exception as e:
            return {
                'account_name': 'Error',
                'account_phone': 'Error',
                'processed_chats': 0,
                'saved_api_calls': 0,
                'status': f'error: {e}'
            }
    def get_optimization_stats(self):
        """📊 Статистика оптимизации API запросов"""
        return {
            'processed_chats_count': len(self.processed_chats),
            'saved_api_calls': len(self.processed_chats) * 2  # 2 запроса на чат (мьют + архив)
        }
