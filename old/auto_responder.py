#!/usr/bin/env python3
"""
AUTO RESPONDER - Автоматический опросник покупателей автомобилей
Интеграция с Mass Sender для выяснения марки и бюджета у заинтересованных клиентов

Основано на архитектуре chatbot_export но адаптировано для автомобильной тематики.
"""

import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from notification_bot import notification_bot


@dataclass
class ConversationContext:
    """Контекст беседы с клиентом"""
    user_id: str                              # ID пользователя (для Telegram это sender.id)
    username: str                             # Username клиента
    phone: Optional[str] = None               # Номер телефона если есть
    first_name: Optional[str] = None          # Имя клиента
    message_history: List[Dict[str, str]] = field(default_factory=list)
    last_message_time: datetime = field(default_factory=datetime.now)
    questions_asked: int = 0                  # Сколько вопросов уже задали
    responses_received: int = 0               # Сколько ответов получили
    car_brand: Optional[str] = None           # Выясненная марка авто
    budget: Optional[str] = None              # Выясненный бюджет
    is_interested: bool = True                # Заинтересован ли клиент
    conversation_complete: bool = False       # Завершен ли опрос
    created_at: datetime = field(default_factory=datetime.now)


class CarInterestPrompts:
    """AI промпты для выяснения интереса к покупке автомобиля"""
    
    INITIAL_INTEREST_CHECK = """
    Ты консультант по продаже автомобилей. 
    Клиент ранее проявил интерес к покупке авто.
    
    Твоя задача - деликатно выяснить:
    1. Действительно ли интерес актуален
    2. Какую марку/модель рассматривает
    3. Какой бюджет планирует
    
    Будь дружелюбным и профессиональным.
    Не навязывайся, если клиент не заинтересован.
    Отвечай кратко - 1-2 предложения максимум.
    """
    
    BRAND_QUESTION = """
    Клиент подтвердил интерес к покупке автомобиля.
    Теперь нужно узнать предпочтения по марке/модели.
    
    Задай вопрос о том, какую марку или модель он рассматривает.
    Можешь упомянуть популярные варианты для подсказки.
    Будь кратким - 1 предложение.
    """
    
    BUDGET_QUESTION = """
    Клиент назвал интересующую марку авто.
    Теперь нужно деликатно выяснить бюджет.
    
    Задай вопрос о планируемом бюджете или ценовом диапазоне.
    Будь тактичным и не давящим.
    1 предложение максимум.
    """
    
    COMPLETION_MESSAGE = """
    Клиент предоставил информацию о марке и бюджете.
    Поблагодари его и скажи, что менеджер скоро с ним свяжется.
    
    Будь благодарным и профессиональным.
    1 предложение.
    """
    
    @classmethod
    def get_prompt_for_stage(cls, context: ConversationContext, user_message: str) -> str:
        """Возвращает промпт для текущей стадии опроса"""
        
        base_context = f"""
        Клиент: {context.username or context.first_name or 'Неизвестный'}
        Вопросов задано: {context.questions_asked}
        Ответов получено: {context.responses_received}
        Известная марка: {context.car_brand or 'неизвестна'}
        Известный бюджет: {context.budget or 'неизвестен'}
        
        Последнее сообщение клиента: "{user_message}"
        """
        
        # Определяем стадию
        if context.questions_asked == 0:
            return cls.INITIAL_INTEREST_CHECK + "\n" + base_context
        elif context.car_brand is None:
            return cls.BRAND_QUESTION + "\n" + base_context  
        elif context.budget is None:
            return cls.BUDGET_QUESTION + "\n" + base_context
        else:
            return cls.COMPLETION_MESSAGE + "\n" + base_context


class AutoResponder:
    """
    Автоматический опросник для клиентов, заинтересованных в покупке автомобиля
    
    Функции:
    - Определение заинтересованности в покупке авто
    - Выяснение предпочитаемой марки/модели
    - Выяснение бюджета
    - Отправка собранной информации менеджерам через бот
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Инициализация автоответчика"""
        self.config = config
        self.auto_responder_config = config.get('auto_responder', {})
        self.enabled = self.auto_responder_config.get('enabled', False)
        
        # Активные разговоры
        self.conversations: Dict[str, ConversationContext] = {}
        
        # Настройки опроса
        self.max_questions = self.auto_responder_config.get('max_questions', 3)
        self.response_timeout_hours = self.auto_responder_config.get('response_timeout_hours', 24)
        self.ai_enabled = self.auto_responder_config.get('ai_enabled', True)
        
        # AI настройки
        self.ai_config = self.auto_responder_config.get('ai', {})
        self.openai_api_key = self.ai_config.get('api_key', '')
        self.model = self.ai_config.get('model', 'gpt-4o-mini')
        self.max_tokens = self.ai_config.get('max_tokens', 100)
        
        # Статистика
        self.stats = {
            'conversations_started': 0,
            'questions_asked': 0,
            'leads_completed': 0,
            'cars_identified': 0,
            'budgets_collected': 0
        }
        
        # Ключевые слова интереса к авто
        self.car_interest_keywords = [
            # Покупка
            'купить', 'покупка', 'приобрести', 'взять', 'нужен автомобиль', 
            'нужна машина', 'ищу авто', 'хочу машину',
            # Марки
            'toyota', 'honda', 'bmw', 'mercedes', 'audi', 'volkswagen', 
            'kia', 'hyundai', 'nissan', 'mazda', 'subaru', 'lexus',
            'lada', 'renault', 'peugeot', 'ford', 'chevrolet', 'skoda',
            # Типы авто
            'седан', 'хэтчбек', 'кроссовер', 'джип', 'внедорожник',
            'универсал', 'купе', 'кабриолет', 'минивэн',
            # Характеристики
            'автомат', 'механика', 'полный привод', 'передний привод',
            'бензин', 'дизель', 'гибрид', 'электро',
            # Бюджет
            'рублей', 'тысяч', 'миллион', 'бюджет', 'цена', 'стоимость',
            'дешевый', 'дорогой', 'недорого', 'до', 'от', 'в пределах'
        ]
        
        print(f"🤖 AutoResponder инициализирован (включен: {self.enabled})")
    
    async def is_car_interest_message(self, message_text: str, conversation_history: List[str] = None) -> bool:
        """Использует ИИ для анализа интереса к покупке авто по всему чату (до 50 сообщений)"""
        
        if not self.ai_enabled or not self.ai_config.get('api_key'):
            # Fallback на хардкод если ИИ недоступен
            return self._is_car_interest_fallback(message_text)
            
        try:
            import openai
            import os
            
            # Подготавливаем контекст для анализа (до 50 сообщений)
            if conversation_history:
                # Берем последние 50 сообщений если больше
                messages_to_analyze = conversation_history[-50:] if len(conversation_history) > 50 else conversation_history
                full_context = "\n".join(messages_to_analyze)
            else:
                full_context = message_text
            
            # Промпт для определения интереса
            system_prompt = """Ты - эксперт по анализу интереса к покупке автомобилей. 

ЗАДАЧА: Определить, проявляет ли пользователь интерес к покупке, продаже или обмену автомобиля.

ПРИЗНАКИ ИНТЕРЕСА:
- Явное намерение купить, продать, обменять автомобиль
- Вопросы о ценах, моделях, характеристиках авто
- Поиск конкретных марок, моделей
- Обсуждение бюджета на покупку авто
- Интерес к автосалонам, дилерам
- Вопросы о кредитах/лизинге на авто

НЕ ИНТЕРЕС:
- Общие разговоры
- Ремонт личного авто
- Технические вопросы по существующему авто
- Случайное упоминание марок в другом контексте

Отвечай только 'ДА' если есть явный интерес к покупке/продаже авто, или 'НЕТ' если интереса нет."""

            # Прокси поддержка
            proxy_config = self.ai_config.get('proxy', {})
            original_proxy_env = {}
            
            if proxy_config.get('enabled', False):
                proxy_url = proxy_config.get('url')
                if proxy_url:
                    for key in ['HTTP_PROXY', 'HTTPS_PROXY']:
                        original_proxy_env[key] = os.environ.get(key)
                        os.environ[key] = proxy_url
            
            try:
                client = openai.OpenAI(api_key=self.ai_config.get('api_key'))
                
                response = client.chat.completions.create(
                    model=self.ai_config.get('model', 'gpt-4o-mini'),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Контекст разговора:\n{full_context}"}
                    ],
                    max_tokens=10,  # Нужен только ДА/НЕТ ответ
                    temperature=0.1  # Низкая температура для более точного анализа
                )
                
                reply = response.choices[0].message.content.strip().upper()
                is_interest = 'ДА' in reply or 'YES' in reply
                
                print(f"🤖 ИИ анализ интереса: {reply} → {'✅ ИНТЕРЕС' if is_interest else '❌ НЕТ'}")
                return is_interest
                
            finally:
                # Восстанавливаем переменные окружения
                if proxy_config.get('enabled', False) and original_proxy_env:
                    for key, value in original_proxy_env.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
                            
        except Exception as e:
            print(f"❌ Ошибка ИИ анализа интереса: {e}")
            # Fallback на хардкод
            return self._is_car_interest_fallback(message_text)
    
    def _is_car_interest_fallback(self, message_text: str) -> bool:
        """Fallback метод определения интереса через ключевые слова"""
        if not message_text:
            return False
            
        car_keywords = [
            "купить", "покупка", "хочу", "ищу", "интересует", "продаю", "продажа",
            "автомобиль", "машина", "авто", "тачка", 
            "toyota", "honda", "bmw", "mercedes", "audi", "nissan", "mazda", "kia",
            "бюджет", "цена", "стоимость", "рублей", "тысяч", "миллион",
            "дилер", "салон", "кредит", "лизинг", "тест-драйв"
        ]
        
        message_lower = message_text.lower()
        keyword_matches = sum(1 for keyword in car_keywords if keyword in message_lower)
        
        return keyword_matches >= 2
    
    async def process_user_message(self, sender, message_text: str, client, conversation_history: List[str] = None) -> Optional[str]:
        """
        Обрабатывает сообщение пользователя и возвращает ответ если нужен
        
        Args:
            sender: Объект отправителя из Telethon
            message_text: Текст сообщения
            client: Telegram клиент
            conversation_history: Список последних сообщений из чата (до 50) для ИИ анализа
            
        Returns:
            Ответ для отправки пользователю или None
        """
        if not self.enabled:
            return None
            
        user_id = str(sender.id)
        
        # Проверяем, есть ли активный разговор
        if user_id in self.conversations:
            # Продолжаем существующий разговор
            return await self._continue_conversation(user_id, message_text, sender, client)
        
        # Проверяем, показывает ли сообщение интерес к авто (с ИИ анализом истории чата)
        if await self.is_car_interest_message(message_text, conversation_history):
            # Начинаем новый разговор
            return await self._start_conversation(user_id, message_text, sender, client)
            
        return None
    
    async def _start_conversation(self, user_id: str, message_text: str, sender, client) -> str:
        """Начинает новый разговор с клиентом"""
        
        # Создаем контекст разговора
        context = ConversationContext(
            user_id=user_id,
            username=sender.username,
            first_name=sender.first_name,
            phone=sender.phone
        )
        
        # Добавляем первое сообщение в историю
        context.message_history.append({
            'type': 'incoming',
            'content': message_text,
            'timestamp': datetime.now().isoformat()
        })
        
        self.conversations[user_id] = context
        self.stats['conversations_started'] += 1
        
        print(f"🚗 Начат опрос клиента {sender.username or sender.first_name} (интерес к авто)")
        
        # Генерируем первый вопрос
        response = await self._generate_ai_response(context, message_text)
        
        if response:
            context.questions_asked += 1
            context.message_history.append({
                'type': 'outgoing',
                'content': response,
                'timestamp': datetime.now().isoformat()
            })
            self.stats['questions_asked'] += 1
            
        return response
    
    async def _continue_conversation(self, user_id: str, message_text: str, sender, client) -> Optional[str]:
        """Продолжает существующий разговор"""
        
        context = self.conversations[user_id]
        
        # Проверяем таймаут
        if datetime.now() - context.last_message_time > timedelta(hours=self.response_timeout_hours):
            # Разговор устарел
            await self._complete_conversation(context, "timeout")
            return None
        
        # Добавляем сообщение в историю
        context.message_history.append({
            'type': 'incoming',
            'content': message_text,
            'timestamp': datetime.now().isoformat()
        })
        
        context.responses_received += 1
        context.last_message_time = datetime.now()
        
        # Анализируем ответ клиента
        await self._analyze_user_response(context, message_text)
        
        # Проверяем, завершен ли опрос
        if context.conversation_complete or context.questions_asked >= self.max_questions:
            await self._complete_conversation(context, "completed")
            return None
        
        # Генерируем следующий вопрос
        response = await self._generate_ai_response(context, message_text)
        
        if response:
            context.questions_asked += 1
            context.message_history.append({
                'type': 'outgoing',
                'content': response,
                'timestamp': datetime.now().isoformat()
            })
            self.stats['questions_asked'] += 1
            
        return response
    
    async def _analyze_user_response(self, context: ConversationContext, message_text: str):
        """Анализирует ответ пользователя и извлекает информацию о марке/бюджете"""
        
        message_lower = message_text.lower()
        
        # Ищем марку автомобиля
        if not context.car_brand:
            car_brands = [
                'toyota', 'honda', 'bmw', 'mercedes', 'audi', 'volkswagen',
                'kia', 'hyundai', 'nissan', 'mazda', 'subaru', 'lexus',
                'lada', 'renault', 'peugeot', 'ford', 'chevrolet', 'skoda',
                'тойота', 'хонда', 'бмв', 'мерседес', 'ауди', 'фольксваген',
                'киа', 'хендай', 'ниссан', 'мазда', 'субару', 'лексус',
                'лада', 'рено', 'пежо', 'форд', 'шевроле', 'шкода'
            ]
            
            for brand in car_brands:
                if brand in message_lower:
                    context.car_brand = brand.title()
                    self.stats['cars_identified'] += 1
                    print(f"✅ Определена марка: {context.car_brand}")
                    break
        
        # Ищем бюджет
        if not context.budget:
            import re
            
            # Ищем числа с указанием валюты
            budget_patterns = [
                r'(\d+(?:\s?\d+)*)\s*(?:тысяч?|тыс\.?|k)',  # "500 тысяч", "500 тыс", "500k"
                r'(\d+(?:\s?\d+)*)\s*(?:рублей?|руб\.?|₽)',  # "500000 рублей", "500000 руб"
                r'(\d+(?:\s?\d+)*)\s*(?:миллионов?|млн\.?)',  # "1.5 миллиона", "1 млн"
                r'до\s+(\d+(?:\s?\d+)*)',  # "до 500000"
                r'от\s+(\d+(?:\s?\d+)*)',  # "от 300000"
                r'(\d+(?:\s?\d+)*)\s*[-–]\s*(\d+(?:\s?\d+)*)',  # "300000 - 500000"
            ]
            
            for pattern in budget_patterns:
                matches = re.findall(pattern, message_lower)
                if matches:
                    if isinstance(matches[0], tuple):
                        # Диапазон
                        context.budget = f"{matches[0][0]}-{matches[0][1]}"
                    else:
                        # Одно число
                        context.budget = matches[0]
                    
                    self.stats['budgets_collected'] += 1
                    print(f"💰 Определен бюджет: {context.budget}")
                    break
        
        # Проверяем, готов ли опрос к завершению
        if context.car_brand and context.budget:
            context.conversation_complete = True
    
    async def _generate_ai_response(self, context: ConversationContext, user_message: str) -> Optional[str]:
        """Генерирует AI ответ для продолжения опроса с поддержкой прокси"""
        
        if not self.ai_enabled or not self.openai_api_key:
            # Используем заготовленные ответы
            return self._get_fallback_response(context)
            
        try:
            import openai
            import os
            
            # Получаем промпт для текущей стадии
            system_prompt = CarInterestPrompts.get_prompt_for_stage(context, user_message)
            
            # 🌐 ПРОКСИ ПОДДЕРЖКА (как в chatbot_export)
            proxy_config = self.ai_config.get('proxy', {})
            original_proxy_env = {}
            
            if proxy_config.get('enabled', False):
                proxy_url = proxy_config.get('url')
                if proxy_url:
                    # Сохраняем оригинальные переменные окружения
                    for key in ['HTTP_PROXY', 'HTTPS_PROXY']:
                        original_proxy_env[key] = os.environ.get(key)
                        os.environ[key] = proxy_url
                    
                    print(f"🌐 Используем прокси для OpenAI API: {proxy_url[:30]}...")
            
            try:
                client = openai.OpenAI(api_key=self.openai_api_key)
                
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.7
                )
                
                reply = response.choices[0].message.content.strip()
                print(f"🤖 AI ответ сгенерирован через прокси: {reply[:50]}...")
                return reply
                
            finally:
                # Восстанавливаем переменные окружения
                if proxy_config.get('enabled', False) and original_proxy_env:
                    for key, value in original_proxy_env.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
            
        except Exception as e:
            print(f"❌ Ошибка генерации AI ответа: {e}")
            return self._get_fallback_response(context)
    
    def _get_fallback_response(self, context: ConversationContext) -> str:
        """Возвращает заготовленный ответ когда AI недоступен"""
        
        if context.questions_asked == 0:
            return "Здравствуйте! Вижу вы интересуетесь покупкой автомобиля. Какую марку рассматриваете?"
        elif not context.car_brand:
            return "Какую марку автомобиля вы рассматриваете? Toyota, BMW, Mercedes или что-то другое?"
        elif not context.budget:
            return "А какой бюджет планируете на покупку?"
        else:
            return "Спасибо за информацию! Наш менеджер скоро с вами свяжется."
    
    async def _complete_conversation(self, context: ConversationContext, reason: str):
        """Завершает разговор и отправляет данные менеджерам"""
        
        # Формируем итоговую информацию
        lead_info = {
            'user_id': context.user_id,
            'username': context.username,
            'first_name': context.first_name,
            'phone': context.phone,
            'car_brand': context.car_brand,
            'budget': context.budget,
            'conversation_length': len(context.message_history),
            'completion_reason': reason,
            'started_at': context.created_at.isoformat(),
            'completed_at': datetime.now().isoformat()
        }
        
        # Отправляем в бот менеджерам
        await self._send_lead_to_managers(lead_info, context)
        
        # Обновляем статистику
        if reason == "completed":
            self.stats['leads_completed'] += 1
        
        # Удаляем из активных разговоров
        if context.user_id in self.conversations:
            del self.conversations[context.user_id]
            
        print(f"✅ Опрос {context.username} завершен ({reason})")
    
    async def _send_lead_to_managers(self, lead_info: Dict[str, Any], context: ConversationContext):
        """Отправляет информацию о лиде менеджерам через бот"""
        
        if not notification_bot:
            print("⚠️ Бот уведомлений недоступен")
            return
            
        try:
            # Формируем красивое уведомление о лиде
            username_display = f"@{lead_info['username']}" if lead_info['username'] else "Без username"
            name_display = lead_info['first_name'] or "Неизвестно"
            phone_display = lead_info['phone'] or "Неизвестно"
            
            brand_display = lead_info['car_brand'] or "❓ Не выяснено"
            budget_display = lead_info['budget'] or "❓ Не указан"
            
            # Определяем статус лида
            if lead_info['car_brand'] and lead_info['budget']:
                lead_status = "🔥 ГОРЯЧИЙ ЛИД"
                status_emoji = "🔥"
            elif lead_info['car_brand'] or lead_info['budget']:
                lead_status = "🟡 ТЁПЛЫЙ ЛИД"
                status_emoji = "🟡"
            else:
                lead_status = "❄️ ХОЛОДНЫЙ ЛИД"
                status_emoji = "❄️"
            
            notification_text = f"""🚗 {lead_status} - ПОКУПАТЕЛЬ АВТОМОБИЛЯ

👤 <b>Клиент:</b> {name_display} ({username_display})
📱 <b>Телефон:</b> <code>{phone_display}</code>

🚙 <b>Интересующая марка:</b> {brand_display}
💰 <b>Планируемый бюджет:</b> {budget_display}

📊 <b>Детали разговора:</b>
• Сообщений в диалоге: {lead_info['conversation_length']}
• Статус завершения: {lead_info['completion_reason']}
• Время начала: {datetime.fromisoformat(lead_info['started_at']).strftime('%d.%m.%Y %H:%M')}

{status_emoji} <b>Рекомендация:</b> {'Срочно связаться!' if status_emoji == '🔥' else 'Связаться в течение дня' if status_emoji == '🟡' else 'Уточнить интерес'}"""

            # Отправляем как security notification (специальный дизайн)
            await notification_bot.send_security_notification(
                account_info={'phone': 'AutoResponder', 'name': 'Система опроса'},
                sender_info={'name': name_display, 'username': lead_info['username'] or 'unknown'},
                message_text=notification_text,
                message_type="🚗 АВТОЛИД"
            )
            
            print(f"📨 Информация о лиде отправлена менеджерам: {name_display}")
            
        except Exception as e:
            print(f"❌ Ошибка отправки лида в бот: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику работы автоответчика"""
        
        active_conversations = len(self.conversations)
        
        return {
            'enabled': self.enabled,
            'active_conversations': active_conversations,
            'total_conversations_started': self.stats['conversations_started'],
            'total_questions_asked': self.stats['questions_asked'],
            'leads_completed': self.stats['leads_completed'],
            'cars_identified': self.stats['cars_identified'],
            'budgets_collected': self.stats['budgets_collected'],
            'ai_enabled': self.ai_enabled
        }
    
    def cleanup_old_conversations(self):
        """Очищает старые неактивные разговоры"""
        
        current_time = datetime.now()
        timeout = timedelta(hours=self.response_timeout_hours)
        
        expired_conversations = []
        for user_id, context in self.conversations.items():
            if current_time - context.last_message_time > timeout:
                expired_conversations.append(user_id)
        
        for user_id in expired_conversations:
            print(f"🧹 Удаляем устаревший разговор: {user_id}")
            del self.conversations[user_id]
        
        return len(expired_conversations)


# Глобальный экземпляр
auto_responder = None

def init_auto_responder(config: Dict[str, Any]):
    """Инициализирует автоответчик с конфигурацией"""
    global auto_responder
    auto_responder = AutoResponder(config)
    return auto_responder

def get_auto_responder() -> Optional[AutoResponder]:
    """Возвращает экземпляр автоответчика"""
    return auto_responder


# Тестирование
if __name__ == "__main__":
    # Тест основной функциональности
    test_config = {
        'auto_responder': {
            'enabled': True,
            'max_questions': 3,
            'ai_enabled': False,  # Используем fallback ответы
            'response_timeout_hours': 24
        }
    }
    
    responder = AutoResponder(test_config)
    
    # Тест определения интереса к авто
    test_messages = [
        "Привет! Хочу купить автомобиль Toyota до 1 миллиона",  # True
        "Здравствуйте! Интересует BMW X5",  # True
        "Привет как дела?",  # False
        "Ищу недорогую машину до 500 тысяч рублей",  # True
        "Планирую покупку седана",  # True
    ]
    
    print("🧪 ТЕСТ ОПРЕДЕЛЕНИЯ ИНТЕРЕСА К АВТО:")
    for msg in test_messages:
        result = responder.is_car_interest_message(msg)
        print(f"  '{msg[:40]}...' → {'✅ ИНТЕРЕС' if result else '❌ НЕ ИНТЕРЕС'}")
    
    print(f"\n📊 Статистика: {responder.get_stats()}")
