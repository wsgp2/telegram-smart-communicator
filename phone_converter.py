#!/usr/bin/env python3
"""
📞 PhoneConverter - конвертация номеров телефонов в username/id
"""

import asyncio
import re
import json
import os
import random
from datetime import datetime
from typing import Optional, Dict, List
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from telethon.errors import FloodWaitError, RPCError, TypeNotFoundError


class PhoneConverter:
    def __init__(self, client, cache_file="data/phone_cache.json"):
        """
        Инициализация конвертера
        client: один Telethon клиент для конвертации
        """
        self.client = client
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.conversion_log = []
        self.stats = {
            'total_attempted': 0,
            'successful_conversions': 0,
            'cache_hits': 0,
            'failed_conversions': 0,
            'session_errors': 0
        }

    def _load_cache(self) -> Dict[str, str]:
        """Загружает кэш из файла"""
        if not os.path.exists(self.cache_file):
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            return {}
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Ошибка загрузки кэша: {e}")
            return {}

    def _save_cache(self):
        """Сохраняет кэш в файл"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения кэша: {e}")

    def format_phone(self, phone: str) -> str:
        """Форматирует номер телефона в международный формат"""
        # Удаляем все не-цифровые символы
        digits = re.sub(r'\D', '', str(phone).strip())

        if not digits:
            return phone

        # Обработка российских номеров
        if digits.startswith('7') and len(digits) == 11:
            return '+' + digits
        elif digits.startswith('8') and len(digits) == 11:
            return '+7' + digits[1:]
        elif len(digits) == 10 and digits[0] in '9438':
            return '+7' + digits
        elif not digits.startswith('+'):
            return '+' + digits
        else:
            return digits

    async def convert_phone_to_username(self, phone: str, max_retries: int = 2) -> Optional[str]:
        self.stats['total_attempted'] += 1

        # Форматируем номер
        formatted_phone = self.format_phone(phone)

        # Проверяем кэш
        if formatted_phone in self.cache:
            self.stats['cache_hits'] += 1
            self.conversion_log.append(f"📦 Из кэша: {formatted_phone} -> {self.cache[formatted_phone]}")
            return self.cache[formatted_phone]

        # Пытаемся конвертировать
        for attempt in range(max_retries):
            try:
                result = await self._attempt_conversion(formatted_phone, attempt)
                if result:
                    self.cache[formatted_phone] = result
                    self._save_cache()
                    self.stats['successful_conversions'] += 1
                    self.conversion_log.append(f"✅ Успех: {formatted_phone} -> {result}")
                    return result

            except FloodWaitError as e:
                wait_time = min(e.seconds, 300)  # Максимум 5 минут ожидания
                print(f"⏳ FloodWait: ожидание {wait_time} секунд...")
                await asyncio.sleep(wait_time)
                continue

            except TypeNotFoundError as e:
                print(f"❌ TypeNotFoundError (9815cec8) - сессия повреждена")
                self.stats['session_errors'] += 1
                raise e  # Пробрасываем ошибку выше для обработки

            except RPCError as e:
                error_msg = str(e).lower()
                if "9815cec8" in error_msg or "cannot get difference" in error_msg:
                    print(f"❌ Известная ошибка сессии: {e}")
                    self.stats['session_errors'] += 1
                    raise e  # Пробрасываем ошибку выше для обработки
                else:
                    self.conversion_log.append(f"⚠️ RPC ошибка попытки {attempt + 1} для {formatted_phone}: {e}")

            except Exception as e:
                self.conversion_log.append(f"⚠️ Ошибка попытки {attempt + 1} для {formatted_phone}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(random.uniform(2, 5))

        self.stats['failed_conversions'] += 1
        self.conversion_log.append(f"❌ Не удалось конвертировать: {formatted_phone}")
        return None

    async def _attempt_conversion(self, phone: str, attempt: int) -> Optional[str]:
        """Одна попытка конвертации с использованием всех доступных методов"""

        # Метод 1: Прямой поиск
        try:
            entity = await asyncio.wait_for(
                self.client.get_entity(phone),
                timeout=15
            )
            if entity:
                identifier = self.extract_identifier(entity)
                if identifier:
                    self.conversion_log.append(f"🎯 Прямой поиск успешен для {phone}")
                    return identifier
        except asyncio.TimeoutError:
            self.conversion_log.append(f"⏱️ Timeout прямого поиска для {phone}")
        except TypeNotFoundError:
            raise 
        except RPCError as e:
            if "9815cec8" in str(e) or "cannot get difference" in str(e).lower():
                raise  
            else:
                self.conversion_log.append(f"⚠️ RPC ошибка прямого поиска для {phone}: {str(e)[:50]}")
        except Exception as e:
            self.conversion_log.append(f"⚠️ Ошибка прямого поиска для {phone}: {str(e)[:50]}")

        try:
            result = await self._method_import_contact(phone)
            if result:
                identifier = self.extract_identifier(result)
                if identifier:
                    self.conversion_log.append(f"📱 Импорт контакта успешен для {phone}")
                    return identifier
        except TypeNotFoundError:
            raise  # Пробрасываем критическую ошибку
        except RPCError as e:
            if "9815cec8" in str(e) or "cannot get difference" in str(e).lower():
                raise  # Пробрасываем критическую ошибку
            else:
                self.conversion_log.append(f"⚠️ RPC ошибка импорта контакта для {phone}: {str(e)[:50]}")
        except Exception as e:
            self.conversion_log.append(f"⚠️ Ошибка импорта контакта для {phone}: {str(e)[:50]}")

        return None

    async def _method_import_contact(self, phone: str):
        try:
            # Номер должен быть БЕЗ знака + для ImportContactsRequest
            phone_for_import = phone.replace('+', '')

            # Создаем временный контакт с уникальным ID
            contact = InputPhoneContact(
                client_id=random.randint(0, 999999),
                phone=phone_for_import,
                first_name=f"TempUser{random.randint(1000, 9999)}",
                last_name=""
            )

            # Импортируем контакт с таймаутом
            result = await asyncio.wait_for(
                self.client(ImportContactsRequest([contact])),
                timeout=20
            )

            if result.users:
                user = result.users[0]

                # Пытаемся удалить временный контакт
                try:
                    await asyncio.wait_for(
                        self.client(DeleteContactsRequest([user])),
                        timeout=10
                    )
                except:
                    pass  # Игнорируем ошибки удаления

                return user

            return None

        except asyncio.TimeoutError:
            self.conversion_log.append(f"⏱️ Timeout импорта контакта {phone}")
            return None
        except Exception as e:
            self.conversion_log.append(f"❌ Ошибка импорта контакта {phone}: {e}")
            return None

    def extract_identifier(self, entity) -> Optional[str]:
        """Извлекает username или ID из entity"""
        try:
            # Приоритет username
            if hasattr(entity, 'username') and entity.username:
                return f"@{entity.username}"
            # Если нет username, используем ID
            elif hasattr(entity, 'id') and entity.id:
                return str(entity.id)
        except:
            pass
        return None

    async def batch_convert(self, phones: List[str], max_concurrent: int = 2) -> Dict[str, str]:
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_phone(phone):
            async with semaphore:
                try:
                    await asyncio.sleep(random.uniform(1.0, 3.0))

                    result = await self.convert_phone_to_username(phone)
                    results[phone] = result

                    # Прогресс
                    converted = len([r for r in results.values() if r])
                    total = len(results)
                    print(f"📊 Прогресс: {total}/{len(phones)} обработано, {converted} успешно")

                    return result

                except (TypeNotFoundError, RPCError) as e:
                    error_msg = str(e).lower()
                    if "9815cec8" in error_msg or "cannot get difference" in error_msg:
                        print(f"❌ Критическая ошибка сессии: {e}")
                        # Останавливаем обработку для этой сессии
                        results[phone] = None
                        return None
                    else:
                        print(f"❌ RPC ошибка для {phone}: {e}")
                        results[phone] = None
                        return None

                except Exception as e:
                    print(f"❌ Ошибка обработки {phone}: {e}")
                    results[phone] = None
                    return None

        print(f"🔄 Начинаем пакетную конвертацию {len(phones)} номеров...")

        # Запускаем все задачи параллельно
        tasks = [process_phone(phone) for phone in phones]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Выводим статистику
        successful = len([r for r in results.values() if r])
        failed = len([r for r in results.values() if not r])

        print(f"\n📊 РЕЗУЛЬТАТЫ КОНВЕРТАЦИИ:")
        print(f"   ✅ Успешно: {successful}")
        print(f"   ❌ Неудачно: {failed}")
        print(f"   📦 Из кэша: {self.stats['cache_hits']}")
        print(f"   🚫 Ошибки сессии: {self.stats['session_errors']}")

        return results

    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику конвертаций"""
        return self.stats.copy()

    def get_log(self, clear: bool = False) -> List[str]:
        """Возвращает лог конвертаций"""
        log = self.conversion_log.copy()
        if clear:
            self.conversion_log.clear()
        return log

    def clear_cache(self):
        """Очищает кэш"""
        self.cache.clear()
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except:
                pass
        self.conversion_log.append("🧹 Кэш очищен")
        print("🧹 Кэш номеров очищен")

    async def check_client_health(self) -> bool:
        """Проверяет работоспособность клиента"""
        try:
            me = await asyncio.wait_for(self.client.get_me(), timeout=10)
            return me is not None
        except (TypeNotFoundError, RPCError) as e:
            error_msg = str(e).lower()
            if "9815cec8" in error_msg or "cannot get difference" in error_msg:
                print(f"❌ Клиент имеет критические ошибки: {e}")
                return False
            return False
        except Exception:
            return False


async def test_converter():
    """Тестовая функция для проверки конвертера"""
    from session_manager import SessionManager

    print("🧪 Тест PhoneConverter")

    # Загружаем сессии
    manager = SessionManager()
    sessions = await manager.load_sessions()

    if not sessions:
        print("❌ Нет доступных сессий для теста")
        return

    client = sessions[0]
    converter = PhoneConverter(client)

    # Проверяем здоровье клиента
    if not await converter.check_client_health():
        print("❌ Клиент не работоспособен")
        return

    # Тестовые номера
    test_phones = [
        "+79123456789",  # Пример российского номера
        "89123456789",  # Без +
        "9123456789"  # Без кода страны
    ]

    print(f"📱 Тестирование {len(test_phones)} номеров...")

    try:
        results = await converter.batch_convert(test_phones)

        print("\n📋 РЕЗУЛЬТАТЫ ТЕСТА:")
        for phone, result in results.items():
            if result:
                print(f"✅ {phone} -> {result}")
            else:
                print(f"❌ {phone} -> не найден")

        print(f"\n📊 Статистика: {converter.get_stats()}")

    except Exception as e:
        print(f"❌ Ошибка теста: {e}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    # Запуск теста
    asyncio.run(test_converter())
