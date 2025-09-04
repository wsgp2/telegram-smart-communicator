#!/usr/bin/env python3
"""
AUTO RESPONDER - Автоматический опросник покупателей автомобилей
Исправленная версия с поддержкой JSON конфигурации
"""

import asyncio
import re
import os
import json
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Optional, Deque, Any, List
import httpx
from openai import AsyncOpenAI

# Настройка логгера
logger = logging.getLogger('auto_responder')

# Путь к файлу конфигурации по умолчанию
DEFAULT_CONFIG_PATH = "config/auto_responder_config.json"


# ---------------- Конфигурация ---------------
class Config:
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Инициализация конфигурации из словаря или JSON файла
        """
        # Если словарь не передан, пытаемся загрузить из файла
        if config_dict is None:
            config_dict = self._load_from_json()

        self.api_id = config_dict.get("api_id", 2040)
        self.api_hash = config_dict.get("api_hash", "")
        self.auto_responder_enabled = config_dict.get("auto_responder", {}).get("enabled", True)
        self.max_questions = config_dict.get("auto_responder", {}).get("max_questions", 3)
        self.response_timeout_hours = config_dict.get("auto_responder", {}).get("response_timeout_hours", 24)

        # AI Configuration
        ai_config = config_dict.get("auto_responder", {}).get("ai", {})
        self.ai_enabled = ai_config.get("enabled", False)
        self.ai_api_key = ai_config.get("api_key", "")
        self.ai_model = ai_config.get("model", "gpt-4.1")
        self.ai_max_tokens = ai_config.get("max_tokens", 150)

        # Proxy Configuration
        ai_proxy = ai_config.get("proxy", {})
        self.ai_proxy_enabled = ai_proxy.get("enabled", False)
        self.ai_proxy_url = ai_proxy.get("url", "")

    def _load_from_json(self) -> Dict[str, Any]:
        """
        Загружает конфигурацию из JSON файла
        """
        config_paths = [
            DEFAULT_CONFIG_PATH,
            "config.json",
            "data/config.json",
            "../config/auto_responder_config.json",
            "../config.json"
        ]

        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        logger.info(f"Configuration loaded from: {path}")
                        return config_data
                except Exception as e:
                    logger.error(f"Error loading config from {path}: {e}")
                    continue

        logger.warning("No configuration file found, using defaults")
        return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Возвращает конфигурацию по умолчанию
        """
        return {
            "api_id": 2040,
            "api_hash": "",
            "auto_responder": {
                "enabled": True,
                "max_questions": 3,
                "response_timeout_hours": 24,
                "ai": {
                    "enabled": True,
                    "api_key": "",
                    "model": "gpt-4.1",
                    "max_tokens": 150,
                    "proxy": {
                        "enabled": True,
                        "url": ""
                    }
                }
            }
        }

    def save_to_json(self, path: Optional[str] = None):
        """
        Сохраняет текущую конфигурацию в JSON файл
        """
        if path is None:
            path = DEFAULT_CONFIG_PATH

        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(path), exist_ok=True)

        config_dict = {
            "api_id": self.api_id,
            "api_hash": self.api_hash,
            "auto_responder": {
                "enabled": self.auto_responder_enabled,
                "max_questions": self.max_questions,
                "response_timeout_hours": self.response_timeout_hours,
                "ai": {
                    "enabled": self.ai_enabled,
                    "api_key": self.ai_api_key,
                    "model": self.ai_model,
                    "max_tokens": self.ai_max_tokens,
                    "proxy": {
                        "enabled": self.ai_proxy_enabled,
                        "url": self.ai_proxy_url
                    }
                }
            }
        }

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=4)
            logger.info(f"Configuration saved to: {path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config to {path}: {e}")
            return False


# Константы для автоответчика
AUTO_RESPONDER_CONFIG = {
    "max_history": 30,
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
        "дешевый", "дорогой", "недорого", "до", "от", "в пределах", "бмв",
    },
    "phone_regex": re.compile(r"(?:\+7|8)?\s*\(?(\d{3})\)?[\s-]?(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})"),
}

# ---------------- Промты для AI ----------------
CAR_INTEREST_PROMPTS = {
    "conversation": """
Ты профессиональный консультант по продаже автомобилей. Веди естественный диалог с потенциальным покупателем.

ТВОЯ ЦЕЛЬ: Вежливо и деликатно выяснить:
1. Действительно ли клиент заинтересован в покупке автомобиля
2. Какую марку/модель рассматривает (любые варианты, включая сленг)
3. Планируемый бюджет покупки

ПРАВИЛА ОБЩЕНИЯ:
• Будь дружелюбным и профессиональным
• Отвечай естественно, как живой человек
• Не навязывайся, если клиент не заинтересован
• Отвечай кратко - 1-2 предложения
• Если клиент пишет неприлично - отвечай с юмором, но профессионально
• Понимай сленг и разговорную речь

АНАЛИЗ СООБЩЕНИЙ:
• Определяй интерес к покупке из контекста
• Извлекай марки авто из любых формулировок (включая "уебанскую", "крутую" и т.д.)
• Понимай бюджет в любой форме (рублях, тысячах, миллионах)

ОТВЕТ ДОЛЖЕН БЫТЬ естественным продолжением диалога, а не шаблонным.
    """,

    "interest_analysis": """
Проанализируй сообщение клиента и определи его интерес к покупке автомобиля.

ПРИЗНАКИ ИНТЕРЕСА:
- Слова: "хочу", "интересует", "нужно", "планирую", "рассматриваю", "покупка", "купить"
- Положительные ответы: "да", "конечно", "ага", "угу", "yes"
- Вопросы о машинах, марках, ценах
- Упоминание конкретных марок
- Любое обсуждение параметров авто

НЕТ ИНТЕРЕСА:
- Четкое "нет", "не интересует", "не нужно", "не планирую"
- Отказ от продолжения диалога

ПРИ СОМНЕНИЯХ - считай ЗАИНТЕРЕСОВАН.

ОТВЕТЬ ТОЛЬКО: "ЗАИНТЕРЕСОВАН" или "НЕ ЗАИНТЕРЕСОВАН"
    """,

    "brand_extraction": """
Извлеки марку автомобиля из сообщения клиента.

ИЩИ:
- Названия марок (Toyota, BMW, Mercedes, Lada и т.д.)
- Сленговые названия ("бэха" = BMW, "мерс" = Mercedes)
- Описания ("немецкую", "японскую", "корейскую")
- Любые упоминания конкретных авто

ЕСЛИ МАРКА НАЙДЕНА - ответь только названием марки.
ЕСЛИ НЕ НАЙДЕНА - ответь "НЕТ"
    """,

    "budget_extraction": """
Извлеки бюджет покупки из сообщения клиента.

ИЩИ:
- Суммы в рублях, тысячах, миллионах
- Диапазоны ("от 500 до 1000 тысяч")
- Приблизительные суммы ("около миллиона")
- Любые денежные ограничения

ЕСЛИ БЮДЖЕТ НАЙДЕН - ответь суммой в понятном формате.
ЕСЛИ НЕ НАЙДЕН - ответь "НЕТ"
    """,

    "initial_message_generator": """
Сгенерируй уникальное первое сообщение для рассылки по автомобилям в стиле "не дозвонился".

ОБЯЗАТЕЛЬНОЕ РАЗНООБРАЗИЕ ПРИВЕТСТВИЙ (БЕЗ ВРЕМЕНИ ДНЯ):
• "Добрый день" / "Здравствуйте" / "Приветствую"
• "Привет" / "Доброго времени суток" 
• "Рад приветствовать" / "Позвольте обратиться"
• "Добро пожаловать" / "Приветствую вас"

РАЗНООБРАЗИЕ ПРИЧИН ОБРАЩЕНИЯ:
• "Не смог дозвониться" / "Не дозвонился" / "Не удалось связаться"
• "Связаться не получилось" / "Дозвониться не вышло"
• "Не получилось связаться по телефону" / "Связь не удалась"
• "Telephone connection failed" / "Звонок не прошел"

РАЗНООБРАЗИЕ ВОПРОСОВ ОБ АВТО:
• "покупка автомобиля" / "приобретение авто" / "покупка машины"
• "интерес к автомобилю" / "вопрос по авто" / "тема автомобиля"
• "автомобильный вопрос" / "машинный вопрос"

РАЗНООБРАЗИЕ ОКОНЧАНИЙ:
• "ещё актуальна?" / "остаётся в силе?" / "всё ещё интересует?"
• "сохраняется?" / "остаётся?" / "по-прежнему важна?"

КРИТИЧЕСКИ ВАЖНО:
• ИЗБЕГАЙ повторения "Здравствуйте" - используй РАЗНЫЕ приветствия!
• Комбинируй элементы случайным образом
• Каждое сообщение должно звучать по-разному
• Сохраняй вежливость и профессионализм

ОТВЕТЬ ТОЛЬКО готовым сообщением, без пояснений.
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
        self.interested: Optional[bool] = None
        self.config = config


# ---------------- Автоответчик ----------------
class AutoResponder:
    def __init__(self, config: Optional[Config] = None):
        """Инициализация автоответчика"""
        self.config = config if config else Config()
        self.conversations: Dict[str, ConversationContext] = {}
        self.lock = asyncio.Lock()
        self.client = None
        self.enabled = True
        self.ai_enabled = True
        self.max_questions = self.config.max_questions
        self.session_manager = None

        # Статистика
        self.stats = {
            'conversations_started': 0,
            'questions_asked': 0,
            'leads_completed': 0,
            'cars_identified': 0,
            'budgets_collected': 0
        }

        self.initialization_log = []

        self._init_openai_client()

    def _init_openai_client(self):
        self.initialization_log.append("Начало инициализации OpenAI клиента")

        if not self.config.ai_enabled:
            self.initialization_log.append("❌ AI отключен в конфигурации (ai.enabled = False)")
            logger.warning("AI disabled in configuration")
            return

        if not self.config.ai_api_key:
            self.initialization_log.append("❌ API ключ не предоставлен")
            logger.warning("AI API key not provided")
            return

        try:
            # Проверяем валидность API ключа
            if not self.config.ai_api_key.startswith("sk-"):
                self.initialization_log.append(
                    f"❌ Неверный формат API ключа: начинается с '{self.config.ai_api_key[:5]}...'")
                logger.error("Invalid OpenAI API key format")
                return

            if len(self.config.ai_api_key) < 20:
                self.initialization_log.append(f"❌ API ключ слишком короткий: {len(self.config.ai_api_key)} символов")
                logger.error("API key too short")
                return

            self.initialization_log.append(f"✅ API ключ корректного формата: {self.config.ai_api_key[:10]}...")
            self.initialization_log.append(f"🔧 Модель: {self.config.ai_model}")

            # Базовые параметры клиента
            client_kwargs = {"api_key": self.config.ai_api_key}

            # Настройка прокси если включена
            if self.config.ai_proxy_enabled and self.config.ai_proxy_url:
                try:
                    proxy_url = self._parse_proxy_url(self.config.ai_proxy_url)

                    # Устанавливаем переменную окружения для прокси
                    import os
                    os.environ['HTTP_PROXY'] = proxy_url
                    os.environ['HTTPS_PROXY'] = proxy_url

                    self.initialization_log.append(f"🌐 Используется прокси: {proxy_url}")
                    logger.info(f"Using proxy for OpenAI: {proxy_url}")

                except Exception as e:
                    self.initialization_log.append(f"⚠️ Ошибка настройки прокси: {e}")
                    logger.error(f"Failed to setup proxy: {e}")

            self.client = AsyncOpenAI(**client_kwargs)
            self.initialization_log.append("✅ OpenAI клиент создан")
            logger.info("OpenAI client initialized successfully")

        except Exception as e:
            error_msg = f"Ошибка создания OpenAI клиента: {e}"
            self.initialization_log.append(f"❌ {error_msg}")
            logger.error(error_msg)
            self.client = None

        self.enabled = self.config.auto_responder_enabled
        self.ai_enabled = self.config.ai_enabled and self.client is not None

        if self.ai_enabled:
            self.initialization_log.append("✅ AI автоответчик полностью активен")
        else:
            self.initialization_log.append("❌ AI автоответчик неактивен - будут использоваться fallback ответы")
    def get_initialization_log(self) -> List[str]:
        """Возвращает лог инициализации для диагностики"""
        return self.initialization_log.copy()

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
        """Проверяет, содержит ли сообщение интерес к автомобилям (fallback метод)"""
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

    async def ai_analyze_interest(self, message: str, conversation_history: List[str]) -> bool:
        """AI анализ интереса к покупке автомобиля"""
        if not self.ai_enabled:
            return self.is_positive_response(message)
        
        try:
            # Формируем контекст из истории
            # Конвертируем deque в список для слайсинга
            history_list = list(conversation_history) if conversation_history else []
            history_context = "\n".join(history_list[-5:]) if history_list else ""
            full_context = f"История диалога:\n{history_context}\n\nПоследнее сообщение: {message}"
            
            response = await self.client.chat.completions.create(
                model=self.config.ai_model,
                messages=[
                    {"role": "system", "content": CAR_INTEREST_PROMPTS["interest_analysis"]},
                    {"role": "user", "content": full_context}
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip().upper()
            logger.info(f"AI анализ интереса вернул: '{result}'")
            return "ЗАИНТЕРЕСОВАН" in result
            
        except Exception as e:
            logger.error(f"Ошибка AI анализа интереса: {e}")
            return self.is_positive_response(message)

    async def ai_extract_brand(self, message: str, conversation_history: List[str]) -> Optional[str]:
        """AI извлечение марки автомобиля"""
        if not self.ai_enabled:
            return self._extract_brand_keywords(message)
        
        try:
            # Формируем контекст из истории
            # Конвертируем deque в список для слайсинга
            history_list = list(conversation_history) if conversation_history else []
            history_context = "\n".join(history_list[-5:]) if history_list else ""
            full_context = f"История диалога:\n{history_context}\n\nПоследнее сообщение: {message}"
            
            response = await self.client.chat.completions.create(
                model=self.config.ai_model,
                messages=[
                    {"role": "system", "content": CAR_INTEREST_PROMPTS["brand_extraction"]},
                    {"role": "user", "content": full_context}
                ],
                max_tokens=20,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"AI извлечение марки вернуло: '{result}'")
            return result if result != "НЕТ" else None
            
        except Exception as e:
            logger.error(f"Ошибка AI извлечения марки: {e}")
            return self._extract_brand_keywords(message)

    async def ai_extract_budget(self, message: str, conversation_history: List[str]) -> Optional[str]:
        """AI извлечение бюджета"""
        if not self.ai_enabled:
            return self._extract_budget_keywords(message)
        
        try:
            # Формируем контекст из истории
            # Конвертируем deque в список для слайсинга
            history_list = list(conversation_history) if conversation_history else []
            history_context = "\n".join(history_list[-5:]) if history_list else ""
            full_context = f"История диалога:\n{history_context}\n\nПоследнее сообщение: {message}"
            
            response = await self.client.chat.completions.create(
                model=self.config.ai_model,
                messages=[
                    {"role": "system", "content": CAR_INTEREST_PROMPTS["budget_extraction"]},
                    {"role": "user", "content": full_context}
                ],
                max_tokens=30,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"AI извлечение бюджета вернуло: '{result}'")
            return result if result != "НЕТ" else None
            
        except Exception as e:
            logger.error(f"Ошибка AI извлечения бюджета: {e}")
            return self._extract_budget_keywords(message)

    def _extract_brand_keywords(self, message: str) -> Optional[str]:
        """Fallback извлечение марки по ключевым словам"""
        message_lower = message.lower()
        brands = ["toyota", "honda", "bmw", "mercedes", "audi", "volkswagen",
                  "kia", "hyundai", "nissan", "mazda", "subaru", "lexus",
                  "lada", "renault", "peugeot", "ford", "chevrolet", "skoda",
                  "тойота", "хонда", "бмв", "мерседес", "ауди", "фольксваген",
                  "киа", "хендай", "ниссан", "мазда", "субару", "лексус",
                  "лада", "рено", "пежо", "форд", "шевроле", "шкода"]
        
        for brand in brands:
            if brand in message_lower:
                return brand.title()
        return None

    def _extract_budget_keywords(self, message: str) -> Optional[str]:
        """Fallback извлечение бюджета по ключевым словам"""
        message_lower = message.lower()
        
        # Паттерны для поиска бюджета
        budget_patterns = [
            r'(\d+[\s]*(?:млн|миллион[ов]*|миллиард[ов]*|м))',
            r'(\d+[\s]*(?:тыс|тысяч[иа]*|к))',
            r'(\d+[\s]*(?:руб|рублей|р))',
            r'(до[\s]*\d+)',
            r'(от[\s]*\d+[\s]*до[\s]*\d+)',
            r'(около[\s]*\d+)'
        ]
        
        text = re.sub(r"\s+", " ", message_lower.replace(',', '.')).strip()
        for pattern in budget_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        
        return None

    async def generate_initial_message(self) -> str:
        """Генерирует уникальное первое сообщение для рассылки через AI"""
        if not self.ai_enabled:
            # Fallback - возвращаем случайное из базовых
            default_messages = [
                "Добрый день! Не смог дозвониться — покупка автомобиля ещё актуальна?",
                "Здравствуйте! Не дозвонился, интерес к покупке автомобиля сохраняется?",
                "Приветствую! Не удалось связаться — покупка автомобиля всё ещё в планах?"
            ]
            import random
            return random.choice(default_messages)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.ai_model,
                messages=[
                    {"role": "system", "content": CAR_INTEREST_PROMPTS["initial_message_generator"]}
                ],
                max_tokens=50,
                temperature=0.8  # Больше креативности для уникальности
            )
            
            generated_message = response.choices[0].message.content.strip()
            logger.info(f"AI сгенерировал сообщение: {generated_message}")
            return generated_message
            
        except Exception as e:
            logger.error(f"Ошибка генерации AI сообщения: {e}")
            # Fallback
            return "Здравствуйте! Не удалось дозвониться — вопрос по автомобилю ещё актуален?"

    async def generate_ai_response(self, context: ConversationContext, user_message: str) -> str:
        """Генерирует AI ответ с использованием полной истории диалога"""
        if not self.ai_enabled:
            logger.warning("AI not enabled, using fallback response")
            return self._get_fallback_response(context)

        if context:
            context.message_history.append(user_message)

        try:
            # Формируем историю диалога для контекста
            conversation_messages = []
            
            # Добавляем системный промпт
            conversation_messages.append({
                "role": "system", 
                "content": CAR_INTEREST_PROMPTS["conversation"]
            })
            
            # Добавляем контекст о клиенте если есть
            context_info = []
            if context.brand:
                context_info.append(f"Марка: {context.brand}")
            if context.budget:
                context_info.append(f"Бюджет: {context.budget}")
            if context.interested is not None:
                context_info.append(f"Интерес: {'заинтересован' if context.interested else 'не заинтересован'}")
            
            if context_info:
                conversation_messages.append({
                    "role": "system",
                    "content": f"Информация о клиенте: {', '.join(context_info)}"
                })
            
            # Добавляем историю сообщений (последние 10 для контекста)
            if context.message_history and len(context.message_history) > 0:
                # Конвертируем deque в список и берем последние сообщения
                history_list = list(context.message_history)
                history_to_include = history_list[-10:] if len(history_list) > 10 else history_list
                
                for i, msg in enumerate(history_to_include):
                    role = "user" if i % 2 == 0 else "assistant"
                    # 🔧 ИСПРАВЛЕНИЕ: Убираем префикс [AI]: из сообщений для AI
                    clean_msg = msg.replace("[AI]: ", "") if msg.startswith("[AI]: ") else msg
                    conversation_messages.append({
                        "role": role,
                        "content": clean_msg
                    })
            
            # Добавляем текущее сообщение пользователя (если его еще нет)
            current_message_exists = any(msg["content"] == user_message for msg in conversation_messages)
            if not current_message_exists:
                conversation_messages.append({
                    "role": "user",
                    "content": user_message
                })

            logger.info(f"Making OpenAI request with model: {self.config.ai_model}")
            response = await self.client.chat.completions.create(
                model=self.config.ai_model,
                messages=conversation_messages,
                max_tokens=self.config.ai_max_tokens,
                temperature=0.7
            )
            answer = response.choices[0].message.content.strip()
            logger.info(f"AI response received: {answer[:50]}...")
            
            # 🔧 ИСПРАВЛЕНИЕ: Добавляем ответ AI в историю для сохранения контекста
            if context:
                context.message_history.append(f"[AI]: {answer}")
                logger.debug(f"AI ответ добавлен в историю. Всего сообщений: {len(context.message_history)}")
            
            return answer
            
        except Exception as e:
            error_msg = f"Ошибка генерации AI ответа: {e}"
            logger.error(error_msg)
            fallback_response = self._get_fallback_response(context)
            
            # 🔧 ИСПРАВЛЕНИЕ: Добавляем fallback ответ в историю
            if context:
                context.message_history.append(f"[AI]: {fallback_response}")
            
            return fallback_response

    def _get_fallback_response(self, context: ConversationContext) -> str:
        """Запасные ответы когда AI недоступен"""
        if not context or context.questions_asked == 0:
            return "Здравствуйте! Вижу вы интересуетесь покупкой автомобиля. Это актуально для вас?"
        elif not context.interested:
            return "Хорошо, если понадобится помощь с выбором автомобиля - обращайтесь!"
        elif not context.brand:
            return "Какую марку автомобиля вы рассматриваете? Например, BMW, Mercedes, Toyota или что-то другое?"
        elif not context.budget:
            return "Какой бюджет планируете на покупку? Это поможет подобрать оптимальные варианты."
        else:
            return "Отлично! Спасибо за информацию. Наш менеджер свяжется с вами в ближайшее время для консультации."

    async def analyze_response(self, context: ConversationContext, message: str):
        """AI анализ ответа пользователя на интерес, марку и бюджет"""
        
        # 1. Анализ интереса к покупке (если еще не определен)
        if context.interested is None:
            logger.info(f"Анализируем интерес для сообщения: '{message}'")
            interested = await self.ai_analyze_interest(message, context.message_history)
            context.interested = interested
            logger.info(f"AI определил интерес: {'заинтересован' if interested else 'не заинтересован'}")

        # 2. Извлечение марки автомобиля (если еще не определена)
        if not context.brand:
            brand = await self.ai_extract_brand(message, context.message_history)
            if brand:
                context.brand = brand
                self.stats['cars_identified'] += 1
                logger.info(f"AI извлек марку: {brand}")

        # 3. Извлечение бюджета (если еще не определен)
        if not context.budget:
            budget = await self.ai_extract_budget(message, context.message_history)
            if budget:
                context.budget = budget
                self.stats['budgets_collected'] += 1
                logger.info(f"AI извлек бюджет: {budget}")

    async def handle_message(self, user_id: str, message: str, phone: Optional[str] = None,
                             username: Optional[str] = None, first_name: Optional[str] = None) -> Optional[str]:
        """Основной метод обработки сообщений - полностью AI-based"""
        if not self.enabled:
            logger.debug("AutoResponder disabled")
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

        # Если диалог уже завершен, не отвечаем
        if context.status == "completed":
            return None

        # Инициализация диалога
        if context.questions_asked == 0:
            context.questions_asked = 1
            self.stats['conversations_started'] += 1
            logger.info(f"Начат новый диалог с пользователем {user_id}")

        # AI анализ сообщения пользователя
        await self.analyze_response(context, message)

        # Обновляем счетчики
        self.stats['questions_asked'] += 1

        # Проверяем условия завершения диалога
        has_both_info = context.brand and context.budget and context.interested
        reached_max_questions = context.questions_asked >= self.config.max_questions
        not_interested = context.interested is False

        if has_both_info or reached_max_questions or not_interested:
            context.status = "completed"
            
            # Отправляем уведомление менеджерам если есть полная информация
            if has_both_info:
                self.stats['leads_completed'] += 1
                await self._send_lead_notification(context)
                logger.info(f"Лид завершен: {context.brand}, {context.budget}")
            
            # AI генерирует финальный ответ
            response = await self.generate_ai_response(context, message)
            return response

        # Увеличиваем счетчик вопросов для продолжения диалога
        context.questions_asked += 1

        # AI генерирует ответ для продолжения диалога
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
            'ai_enabled': self.ai_enabled,
            'initialization_log': self.get_initialization_log()
        }


# ---------------- Глобальный экземпляр ----------------
auto_responder_instance: Optional[AutoResponder] = None


def init_auto_responder(config_dict: Optional[dict] = None, session_manager=None):
    """
    Инициализация автоответчика

    Args:
        config_dict: Словарь с конфигурацией (опционально)
        session_manager: Менеджер сессий для отправки сообщений
    """
    global auto_responder_instance

    if config_dict:
        config = Config(config_dict)
    else:
        config = Config()

    auto_responder_instance = AutoResponder(config)

    if session_manager:
        auto_responder_instance.set_session_manager(session_manager)

    try:
        asyncio.create_task(auto_responder_instance.cleanup_sessions())
    except RuntimeError:
        pass

    return auto_responder_instance


def get_auto_responder() -> Optional[AutoResponder]:
    return auto_responder_instance


def create_default_config_file(path: Optional[str] = None):
    if path is None:
        path = DEFAULT_CONFIG_PATH

    config = Config()
    config.save_to_json(path)
    print(f"✅ Создан файл конфигурации: {path}")


if __name__ == "__main__":
    if not os.path.exists(DEFAULT_CONFIG_PATH):
        create_default_config_file()

    responder = init_auto_responder()

    if responder:
        stats = responder.get_stats()
        print("\n📊 Статус автоответчика:")
        print(f"   AI включен: {stats['ai_enabled']}")
        print("\n📋 Лог инициализации:")
        for log_entry in stats['initialization_log']:
            print(f"   {log_entry}")
