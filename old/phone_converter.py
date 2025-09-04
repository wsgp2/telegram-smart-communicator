#!/usr/bin/env python3
"""
📞 PhoneConverter - конвертация номера телефона в username/id
- Асинхронно
- С кэшированием
- Параллельные методы поиска
"""

import asyncio
import re
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest, SearchRequest
from telethon.tl.types import InputPhoneContact
from functools import lru_cache

class PhoneConverter:
    def __init__(self, client, cache_size=1024):
        self.client = client
        self.cache = {}  # Можно заменить на LRU кэш для больших объемов

    async def convert_phone_to_username(self, phone):
        """Конвертирует номер телефона в username или id"""
        formatted_phone = self.format_phone(phone)

        # Проверяем кэш
        if formatted_phone in self.cache:
            return self.cache[formatted_phone]

        # Запускаем все методы параллельно
        methods = [
            self._method_direct_search(formatted_phone),
            self._method_import_contact(formatted_phone),
            self._method_search_contacts(formatted_phone)
        ]

        for task in asyncio.as_completed(methods):
            try:
                entity = await asyncio.wait_for(task, timeout=5)  # таймаут на метод
                if entity:
                    identifier = self.extract_identifier(entity)
                    self.cache[formatted_phone] = identifier
                    return identifier
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        # Если ничего не найдено
        self.cache[formatted_phone] = None
        return None

    def format_phone(self, phone):
        """Форматирует номер телефона в международный вид +7..."""
        digits = re.sub(r'\D', '', str(phone))

        if digits.startswith('7') and len(digits) == 11:
            return '+' + digits
        elif digits.startswith('8') and len(digits) == 11:
            return '+7' + digits[1:]
        elif len(digits) == 10:
            return '+7' + digits
        else:
            return '+' + digits

    async def _method_direct_search(self, phone):
        """Прямой поиск по номеру через get_entity"""
        try:
            return await self.client.get_entity(phone)
        except:
            return None

    async def _method_import_contact(self, phone):
        """Поиск через импорт контакта"""
        try:
            contact = InputPhoneContact(client_id=0, phone=phone, first_name="FindUser", last_name="Temp")
            result = await self.client(ImportContactsRequest([contact]))
            if result.users:
                user = result.users[0]
                # Удаляем временный контакт
                try:
                    await self.client(DeleteContactsRequest([user]))
                except:
                    pass
                return user
        except:
            return None

    async def _method_search_contacts(self, phone):
        """Поиск через SearchRequest"""
        try:
            result = await self.client(SearchRequest(q=phone, limit=5))
            for user in result.users:
                if hasattr(user, 'phone') and user.phone == phone.replace('+', ''):
                    return user
        except:
            return None

    def extract_identifier(self, entity):
        """Возвращает username (@username) или id"""
        if hasattr(entity, 'username') and entity.username:
            return f"@{entity.username}"
        elif hasattr(entity, 'id'):
            return str(entity.id)
        return None
