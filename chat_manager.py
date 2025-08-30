#!/usr/bin/env python3
"""
🗂️ МЕНЕДЖЕР ЧАТОВ - АВТОМАТИЧЕСКОЕ МЬЮТИРОВАНИЕ И АРХИВИРОВАНИЕ
Скрывает чаты с получателями рассылки, но сохраняет возможность получать сообщения
"""
import asyncio
import json
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.functions.folders import EditPeerFoldersRequest
from telethon.tl.functions.messages import SetHistoryTTLRequest
from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings, InputFolderPeer

# Загружаем конфиг
with open('config.json', 'r') as f:
    cfg = json.load(f)

class ChatManager:
    """🗂️ Менеджер для автоматического скрытия чатов"""
    
    def __init__(self, client):
        self.client = client
        self.auto_delete_delay = 4  # Задержка удаления в секундах (3-5 сек)
    
    async def mute_chat(self, peer, duration=2147483647):
        """🔇 Мьютим чат (по умолчанию навсегда)"""
        try:
            # Используем правильный способ мьютинга
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
        """👻 Полное скрытие чата: мьют + архив"""
        try:
            # Получаем peer объект
            if isinstance(username_or_id, str) and username_or_id.startswith('@'):
                username_or_id = username_or_id[1:]  # Убираем @
            
            peer = await self.client.get_input_entity(username_or_id)
            
            # Мьютим чат
            muted = await self.mute_chat(peer)
            
            # Архивируем чат  
            archived = await self.archive_chat(peer)
            
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
        """🕐🗑️ Удаляем сообщение с задержкой ТОЛЬКО У СЕБЯ"""
        try:
            print(f"⏳ Удаление через {self.auto_delete_delay} секунд...")
            await asyncio.sleep(self.auto_delete_delay)
            
            # revoke=False - удаляем только у себя, получатель видит сообщение
            await message.delete(revoke=False)
            print(f"🗑️ Сообщение удалено только у нас (получатель его видит)")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка удаления сообщения: {e}")
            return False
    
    async def send_hide_and_mute(self, target, message_text):
        """🎯 Полный цикл: отправить → удалить → скрыть чат"""
        print(f"\n🎯 ПОЛНЫЙ ЦИКЛ ДЛЯ {target}")
        print("-" * 30)
        
        # 1. Отправляем и удаляем сообщение
        sent_message = await self.send_and_hide_message(target, message_text)
        if not sent_message:
            return False
        
        # 2. Небольшая пауза перед скрытием чата
        await asyncio.sleep(1)
        
        # 3. Скрываем чат (TTL устанавливается в main.py ДО отправки)
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

async def auto_hide_targets():
    """🎯 Автоматически скрываем чаты с целевыми пользователями"""
    
    print("🗂️ АВТОМАТИЧЕСКОЕ СКРЫТИЕ ЧАТОВ")
    print("=" * 50)
    
    # Подключаемся к сессии
    client = TelegramClient('sessions/186418724_telethon', cfg['api_id'], cfg['api_hash'])
    
    async with client:
        me = await client.get_me()
        print(f"🔐 Подключен как: {me.first_name} ({me.phone})")
        
        chat_manager = ChatManager(client)
        
        # Загружаем список целевых пользователей
        try:
            with open(cfg['target_users_file'], 'r') as f:
                target_users = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"❌ Файл {cfg['target_users_file']} не найден!")
            return
        
        print(f"🎯 Целевых пользователей: {len(target_users)}")
        print(f"📝 Список: {', '.join(target_users)}")
        print()
        
        # Скрываем каждый чат
        hidden_count = 0
        for user in target_users:
            print(f"🔄 Обрабатываем: {user}")
            
            if await chat_manager.hide_chat(user):
                hidden_count += 1
                print(f"   ✅ Скрыт успешно!")
            else:
                print(f"   ❌ Не удалось скрыть")
            print()
            
            # Небольшая задержка между операциями
            await asyncio.sleep(1)
        
        print(f"📊 ИТОГО:")
        print(f"   Обработано: {len(target_users)}")
        print(f"   Скрыто успешно: {hidden_count}")
        print(f"   Ошибок: {len(target_users) - hidden_count}")
        print()
        print(f"✨ Чаты скрыты, но сообщения будут приходить в скрипт!")

async def test_hidden_message_reception():
    """🧪 Тестируем получение сообщений из скрытых чатов"""
    
    print("🧪 ТЕСТ ПОЛУЧЕНИЯ СООБЩЕНИЙ ИЗ СКРЫТЫХ ЧАТОВ")
    print("=" * 50)
    
    client = TelegramClient('sessions/186418724_telethon', cfg['api_id'], cfg['api_hash'])
    
    async with client:
        me = await client.get_me()
        print(f"🔐 Подключен как: {me.first_name} ({me.phone})")
        print(f"📡 Слушаем ВСЕ входящие сообщения (включая из скрытых чатов)...")
        
        from telethon import events
        
        @client.on(events.NewMessage(incoming=True))
        async def hidden_message_test(event):
            sender = await event.get_sender()
            text = event.raw_text
            
            print(f"\n📩 [ПОЛУЧЕНО] Сообщение:")
            print(f"   👤 От: {getattr(sender, 'first_name', 'Unknown')}")
            print(f"   📱 Username: @{getattr(sender, 'username', 'None')}")
            print(f"   📝 Текст: {text}")
            print(f"   🗂️ Статус чата: Возможно скрыт, но сообщение получено!")
        
        await client.run_until_disconnected()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "hide":
            asyncio.run(auto_hide_targets())
        elif sys.argv[1] == "test":
            asyncio.run(test_hidden_message_reception())
        else:
            print("Использование:")
            print("  python3 chat_manager.py hide  - Скрыть чаты с целевыми пользователями")
            print("  python3 chat_manager.py test  - Тестировать получение скрытых сообщений")
    else:
        print("Использование:")
        print("  python3 chat_manager.py hide  - Скрыть чаты с целевыми пользователями") 
        print("  python3 chat_manager.py test  - Тестировать получение скрытых сообщений")
