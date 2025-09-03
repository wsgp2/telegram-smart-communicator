#!/usr/bin/env python3
"""
AUTO RESPONDER - Автоматический опросник покупателей автомобилей
Оптимизированная версия для конфигурации
"""

import asyncio
import re
import os
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Optional, Deque, Any, List
import aiohttp
import httpx
from openai import AsyncOpenAI




# ---------------- Конфигурация ---------------
class Config:
    def __init__(self, config_dict: Dict[str, Any]):
        self.api_id = config_dict.get("api_id", 2040)
        self.api_hash = config_dict.get("api_hash", "")
        self.auto_responder_enabled = config_dict.get("auto_responder", {}).get("enabled", True)
        self.max_questions = config_dict.get("auto_responder", {}).get("max_questions", 3)
        self.response_timeout_hours = config_dict.get("auto_responder", {}).get("response_timeout_hours", 24)
        
        # AI Configuration
        ai_config = config_dict.get("auto_responder", {}).get("ai", {})
        self.ai_enabled = ai_config.get("enabled", False)
        self.ai_api_key = ai_config.get("api_key", "")
        self.ai_model = ai_config.get("model", "gpt-4o-mini")  # Исправлено имя модели
        self.ai_max_tokens = ai_config.get("max_tokens", 150)
        
        # Proxy Configuration
        ai_proxy = ai_config.get("proxy", {})
        self.ai_proxy_enabled = ai_proxy.get("enabled", False)
        self.ai_proxy_url = ai_proxy.get("url", "")


# Константы для автоответчика
AUTO_RESPONDER_CONFIG = {
    "max_history": 50,
    "keywords_car_interest": {
        "купить", "покупка", "приобрести", "взять", "нужен автомобиль",
        "нужна машина", "ищу авто", "хочу машину", "toyota", "honda",
        "bmw", "mercedes", "audi", "volkswagen", "kia", "hyundai",
        "nissan", "mazda", "subaru", "lexus", "lada", "renault",
        "peugeot", "ford", "chevrolet", "skoda", "седан", "хэтчбек",
        "кроссовер", "джип", "внедорожник", "универсал", "купе",
        "кабриолет", "минивэн", "автомат", "механика", "полный привод",
        "передний привод", "бензин", "дизель", "гибрид", "электро",
        "рублей", "тысяч", "миллион", "бюджет", "цена", "стоимость",
        "дешевый", "дорогой", "недорого", "до", "от", "в пределах"
    },
    "phone_regex": re.compile(r"(?:\+7|8)?\s*\(?(\d{3})\)?[\s-]?(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})"),
}

# ---------------- Промты для AI ----------------
CAR_INTEREST_PROMPTS = {
    "initial": """
    Ты консультант по продаже автомобилей. 
    Клиент ранее проявил интерес к покупке авто.

    Твоя задача - деликатно выяснить:
    1. Действительно ли интерес актуален
    2. Какую марку/модель рассматривает
    3. Какой бюджет планирует

    Будь дружелюбным и профессиональным.
    Не навязывайся, если клиент не заинтересован.
    Отвечай кратко - 1-2 предложения максимум.
    """,

    "brand": """
    Клиент подтвердил интерес к покупке автомобиля.
    Теперь нужно узнать предпочтения по марке/модели.

    Задай вопрос о том, какую марку или модель он рассматривает.
    Можешь упомянуть популярные варианты для подсказки.
    Будь кратким - 1 предложение.
    """,

    "budget": """
    Клиент назвал интересующую марку авто.
    Теперь нужно деликатно выяснить бюджет.

    Задай вопрос о планируемом бюджете или ценовом диапазоне.
    Будь тактичным и не давящим.
    1 предложение максимум.
    """,

    "completion": """
    Клиент предоставил всю необходимую информацию о покупке автомобиля.
    Поблагодари его за предоставленные данные и сообщи, что менеджер скоро свяжется для консультации.

    Будь благодарным и профессиональным. Не задавай больше вопросов.
    1-2 предложения.
    """
}


# ---------------- Контекст беседы ----------------
class ConversationContext:
    def __init__(self, user_id: str, config: Config):
        self.user_id = user_id
        self.message_history: Deque[str] = deque(maxlen=AUTO_RESPONDER_CONFIG["max_history"])
        self.questions_asked: int = 0
        self.last_message_time: datetime = datetime.utcnow()
        self.brand: Optional[str] = None
        self.budget: Optional[str] = None
        self.phone: Optional[str] = None
        self.status: str = "active"
        self.username: Optional[str] = None
        self.first_name: Optional[str] = None
        self.interested: bool = False
        self.config = config


# ---------------- Автоответчик ----------------
class AutoResponder:
    def _init_openai_client(self):
        """Инициализация OpenAI клиента с обработкой ошибок"""
        if not self.config.ai_enabled or not self.config.ai_api_key:
            logger.warning("AI disabled or no API key provided")
            return
            
        try:
            # Проверяем валидность API ключа
            if self.config.ai_api_key.startswith("sk-") and len(self.config.ai_api_key) > 20:
                client_kwargs = {"api_key": self.config.ai_api_key}
                
                # Настройка прокси если включена
                if self.config.ai_proxy_enabled and self.config.ai_proxy_url:
                    try:
                        proxy_url = self._parse_proxy_url(self.config.ai_proxy_url)
                        client_kwargs["http_client"] = httpx.AsyncClient(
                            proxies={"all://": proxy_url},
                            timeout=30.0,
                            verify=False  # Для прокси может потребоваться
                        )
                        logger.info(f"Using proxy for OpenAI: {proxy_url}")
                    except Exception as e:
                        logger.error(f"Failed to setup proxy: {e}")
                        # Создаем клиент без прокси
                        client_kwargs["http_client"] = httpx.AsyncClient(timeout=30.0)
                
                self.client = AsyncOpenAI(**client_kwargs)
                logger.info("OpenAI client initialized successfully")
            else:
                logger.error("Invalid OpenAI API key format")
                
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
        self.enabled = config.auto_responder_enabled
        self.ai_enabled = config.ai_enabled and self.client is not None
        self.max_questions = config.max_questions
        self.session_manager = None

        # Статистика
        self.stats = {
            'conversations_started': 0,
            'questions_asked': 0,
            'leads_completed': 0,
            'cars_identified': 0,
            'budgets_collected': 0
        }

    def _parse_proxy_url(self, proxy_url: str) -> str:
        """Парсинг и форматирование URL прокси"""
        if not proxy_url.startswith(("http://", "https://", "socks5://")):
            proxy_url = "http://" + proxy_url
        return proxy_url
        
    def set_session_manager(self, session_manager):
        """Установка менеджера сессий для отправки сообщений"""
        self.session_manager = session_manager

    def get_context(self, user_id: str) -> ConversationContext:
        if user_id not in self.conversations:
            self.conversations[user_id] = ConversationContext(user_id, self.config)
        return self.conversations[user_id]

    def is_car_interest(self, message: str) -> bool:
        """Проверяет, содержит ли сообщение интерес к автомобилям"""
        if not message:
            return False

        message_lower = message.lower()
        return any(keyword.lower() in message_lower for keyword in AUTO_RESPONDER_CONFIG["keywords_car_interest"])

    def is_positive_response(self, message: str) -> bool:
        """Проверяет, является ли ответ положительным"""
        if not message:
            return False

        message_lower = message.lower()
        positive_words = {"да", "конечно", "ага", "угу", "yes", "yeah", "хочу", "интересно", "интересует"}
        negative_words = {"нет", "не", "no", "not", "не хочу", "не интересно"}

        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)

        return positive_count > negative_count

    async def generate_ai_response(self, context: ConversationContext, user_message: str) -> str:
        """Генерирует AI ответ с использованием промтов"""
        if not self.ai_enabled:
            return self._get_fallback_response(context)

        context.message_history.append(user_message)

        # Определяем стадию разговора
        if context.questions_asked == 0:
            system_prompt = CAR_INTEREST_PROMPTS["initial"]
        elif not context.interested:
            if self.is_positive_response(user_message):
                context.interested = True
                system_prompt = CAR_INTEREST_PROMPTS["brand"]
            else:
                return "Хорошо, если понадобится помощь с выбором автомобиля - обращайтесь!"
        elif context.brand is None:
            system_prompt = CAR_INTEREST_PROMPTS["brand"]
        elif context.budget is None:
            system_prompt = CAR_INTEREST_PROMPTS["budget"]
        else:
            system_prompt = CAR_INTEREST_PROMPTS["completion"]

        try:
            response = await self.client.chat.completions.create(
                model=self.config.ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=self.config.ai_max_tokens,
            )
            answer = response.choices[0].message.content.strip()
            return answer
        except Exception as e:
            return self._get_fallback_response(context)

    def _get_fallback_response(self, context: ConversationContext) -> str:
        """Запасные ответы когда AI недоступен"""
        if context.questions_asked == 0:
            return "Здравствуйте! Вижу вы интересуетесь покупкой автомобиля. Это актуально для вас?"
        elif not context.interested:
            return "Хорошо, если понадобится помощь с выбором автомобиля - обращайтесь!"
        elif not context.brand:
            return "Какую марку автомобиля вы рассматриваете? Например, BMW, Mercedes, Toyota или что-то другое?"
        elif not context.budget:
            return "Какой бюджет планируете на покупку? Это поможет подобрать оптимальные варианты."
        else:
            return "Отлично! Спасибо за информацию. Наш менеджер свяжется с вами в ближайшее время для консультации."

    def analyze_response(self, context: ConversationContext, message: str):
        """Анализирует ответ пользователя на наличие марки и бюджета"""
        message_lower = message.lower()

        # Поиск марки автомобиля (только если еще не определена)
        if not context.brand:
            brands = ["toyota", "honda", "bmw", "mercedes", "audi", "volkswagen",
                      "kia", "hyundai", "nissan", "mazda", "subaru", "lexus",
                      "lada", "renault", "peugeot", "ford", "chevrolet", "skoda",
                      "тойота", "хонда", "бмв", "мерседес", "ауди", "фольксваген",
                      "киа", "хендай", "ниссан", "мазда", "субару", "лексус",
                      "лада", "рено", "пежо", "форд", "шевроле", "шкода"]

            for brand in brands:
                if brand in message_lower:
                    context.brand = brand.title()
                    self.stats['cars_identified'] += 1
                    break

        # Поиск бюджета (только если еще не определен)
        if not context.budget:
            # Проверяем различные форматы указания бюджета
            budget_patterns = [
                r'(\d+(?:\s?\d+)*)\s*(?:тысяч?|тыс\.?|k)\s*(?:рублей?|руб\.?|₽)?',
                r'(\d+(?:\s?\d+)*)\s*(?:рублей?|руб\.?|₽)',
                r'(\d+(?:\s?\d+)*)\s*(?:миллионов?|млн\.?)\s*(?:рублей?|руб\.?|₽)?',
                r'до\s+(\d+(?:\s?\d+)*)\s*(?:тысяч?|тыс\.?|рублей?|руб\.?|₽|млн\.?)',
                r'от\s+(\d+(?:\s?\d+)*)\s*(?:тысяч?|тыс\.?|рублей?|руб\.?|₽|млн\.?)',
                r'(\d+(?:\s?\d+)*)\s*[-–]\s*(\d+(?:\s?\d+)*)\s*(?:тысяч?|тыс\.?|рублей?|руб\.?|₽|млн\.?)',
                r'(\d+)\s*млн',
                r'(\d+)\s*миллион',
            ]

            for pattern in budget_patterns:
                matches = re.findall(pattern, message_lower.replace(',', '').replace(' ', ''))
                if matches:
                    if isinstance(matches[0], tuple):
                        # Диапазон цен
                        min_price, max_price = matches[0]
                        context.budget = f"{min_price}-{max_price} тыс. руб."
                    else:
                        # Конкретная сумма
                        amount = matches[0]
                        # Определяем масштаб суммы
                        if 'млн' in message_lower or 'миллион' in message_lower:
                            context.budget = f"{amount} млн. руб."
                        elif len(amount) <= 3:
                            context.budget = f"{amount} тыс. руб."
                        else:
                            # Форматируем крупные суммы с пробелами
                            formatted_amount = f"{int(amount):,}".replace(',', ' ')
                            context.budget = f"{formatted_amount} руб."

                    self.stats['budgets_collected'] += 1
                    break

            # Дополнительная проверка для явного указания бюджета
            if not context.budget and any(
                    word in message_lower for word in ['бюджет', 'цена', 'стоимость', 'рублей', 'тысяч', 'миллион']):
                # Если явно говорится о бюджете, но не распознан формат, сохраняем весь текст
                context.budget = message.strip()
                self.stats['budgets_collected'] += 1

    async def handle_message(self, user_id: str, message: str, phone: Optional[str] = None,
                             username: Optional[str] = None, first_name: Optional[str] = None) -> Optional[str]:
        """Основной метод обработки сообщений"""
        if not self.enabled:
            return None

        async with self.lock:
            context = self.get_context(user_id)
            context.last_message_time = datetime.utcnow()
            if phone:
                context.phone = self._normalize_phone(phone)
            if username:
                context.username = username
            if first_name:
                context.first_name = first_name

        if context.status == "completed":
            return None

        if context.questions_asked == 0 and not self.is_car_interest(message):
            return None

        if context.questions_asked == 0:
            self.stats['conversations_started'] += 1

        self.analyze_response(context, message)

        if context.questions_asked > 0:  
            context.questions_asked += 1
            self.stats['questions_asked'] += 1

        # Проверяем, завершен ли опрос (есть и марка и бюджет)
        has_both_info = context.brand and context.budget
        reached_max_questions = context.questions_asked >= self.config.max_questions

        if has_both_info or reached_max_questions:
            context.status = "completed"
            self.stats['leads_completed'] += 1
            await self._send_lead_notification(context)

            if has_both_info:
                return "Спасибо за информацию! Наш менеджер свяжется с вами в ближайшее время для консультации."
            else:
                return "Спасибо! Мы передали вашу информацию менеджеру, он свяжется с вами для уточнения деталей."

        # Генерируем ответ
        response = await self.generate_ai_response(context, message)
        return response

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Нормализует номер телефона"""
        match = AUTO_RESPONDER_CONFIG["phone_regex"].search(phone)
        if match:
            return f"+7{match.group(1)}{match.group(2)}{match.group(3)}{match.group(4)}"
        return None

    async def send_response(self, user_id: str, response: str) -> bool:
        """Отправляет ответ пользователю"""
        if not self.session_manager:
            return False

        try:
            sessions = await self.session_manager.load_sessions()
            if not sessions:
                return False

            client = sessions[0]
            await client.send_message(user_id, response)
            return True

        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e):
                async with self.lock:
                    if user_id in self.conversations:
                        self.conversations[user_id].status = "blocked"
                return False
            else:
                return False

    async def _send_lead_notification(self, context: ConversationContext):
        """Отправляет уведомление о завершенном лиде"""
        try:
            from notification_bot import notification_bot

            if not notification_bot:
                return

            username_display = f"@{context.username}" if context.username else "Без username"
            name_display = context.first_name or "Неизвестно"
            phone_display = context.phone or "Неизвестно"
            brand_display = context.brand or "❓ Не выяснено"
            budget_display = context.budget or "❓ Не указан"

            notification_text = f"""🚗 АВТОЛИД - ПОКУПАТЕЛЬ АВТОМОБИЛЯ

👤 <b>Клиент:</b> {name_display} ({username_display})
📱 <b>Телефон:</b> <code>{phone_display}</code>

🚙 <b>Марка:</b> {brand_display}
💰 <b>Бюджет:</b> {budget_display}

📊 <b>Вопросов задано:</b> {context.questions_asked}
⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

            await notification_bot.send_security_notification(
                {'phone': 'AutoResponder', 'name': 'Система опроса'},
                {'name': name_display, 'username': context.username or 'unknown'},
                notification_text,
                "🚗 АВТОЛИД"
            )

        except ImportError:
            pass

    async def cleanup_sessions(self):
        """Очищает старые сессии"""
        while True:
            await asyncio.sleep(600)
            now = datetime.utcnow()
            to_remove = []
            async with self.lock:
                for user_id, ctx in self.conversations.items():
                    if (ctx.status in ["completed", "blocked"] or
                            (now - ctx.last_message_time) > timedelta(hours=self.config.response_timeout_hours)):
                        to_remove.append(user_id)
                for user_id in to_remove:
                    del self.conversations[user_id]

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        return {
            'active_conversations': len(self.conversations),
            'total_conversations_started': self.stats['conversations_started'],
            'total_questions_asked': self.stats['questions_asked'],
            'leads_completed': self.stats['leads_completed'],
            'cars_identified': self.stats['cars_identified'],
            'budgets_collected': self.stats['budgets_collected'],
        }


# ---------------- Глобальный экземпляр ----------------
auto_responder_instance: Optional[AutoResponder] = None


def init_auto_responder(config_dict: dict, session_manager=None):
    global auto_responder_instance
    config = Config(config_dict)



    auto_responder_instance = AutoResponder()
    if session_manager:
        auto_responder_instance.set_session_manager(session_manager)
    asyncio.create_task(auto_responder_instance.cleanup_sessions())


def get_auto_responder() -> Optional[AutoResponder]:
    return auto_responder_instance
