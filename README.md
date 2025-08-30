# 🚀 Telegram Smart Communicator

> **Интеллектуальная система массовых рассылок с двусторонней коммуникацией**

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Telethon](https://img.shields.io/badge/telethon-1.24+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

## 📋 Описание

**Telegram Smart Communicator** - это продвинутая система для массовых рассылок в Telegram с уникальной возможностью **двусторонней коммуникации**. Не просто отправляет сообщения, но и **отслеживает ответы**, автоматически уведомляя администратора о всех входящих сообщениях от получателей.

### ✨ Ключевые особенности

- 🎯 **Smart Sender** - Массовая рассылка с уникальными сообщениями
- 📱 **Smart Receiver** - Мониторинг ответов в режиме реального времени  
- 🔔 **Auto Notifications** - Мгновенные уведомления админу о всех ответах
- 🛡️ **Intelligent Filtering** - Отслеживание только релевантных сообщений
- 🔄 **24/7 Operation** - Непрерывная работа после завершения рассылки
- 🌐 **Multi-Proxy Support** - Поддержка различных типов прокси
- 📊 **Detailed Analytics** - Подробная статистика отправки и ошибок

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM SMART COMMUNICATOR              │
├─────────────────────────────────────────────────────────────┤
│  📤 SENDER MODULE                   📥 RECEIVER MODULE      │
│  ├─ Mass messaging                  ├─ Event monitoring     │
│  ├─ Unique messages                 ├─ Response tracking    │
│  ├─ Multi-account support           ├─ Admin notifications  │
│  └─ Proxy integration               └─ 24/7 listening       │
├─────────────────────────────────────────────────────────────┤
│  🔧 CORE FEATURES                                           │
│  ├─ Session Management              ├─ Error Handling       │
│  ├─ Config Management               ├─ Detailed Logging     │
│  ├─ User Filtering                  └─ Statistics          │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Быстрый старт

### Требования
- Python 3.8+
- Telegram API credentials (api_id, api_hash)
- Авторизованные сессии Telegram аккаунтов

### Установка
```bash
git clone https://github.com/SergD/telegram-smart-communicator.git
cd telegram-smart-communicator
pip install telethon
```

### Настройка
1. Отредактируйте `config.json` или используйте встроенный редактор
2. Поместите файлы сессий (*.session) в папку `sessions/`
3. Укажите список получателей в `target_users.txt`

### Запуск
```bash
python main.py
```

## 📁 Структура проекта

```
telegram-smart-communicator/
├── 📄 main.py                    # Основной модуль приложения
├── 📄 config.json               # Конфигурация (создается автоматически)
├── 📄 target_users.txt          # Список получателей
├── 📂 sessions/                 # Папка с сессиями Telegram
├── 📂 proxies/                  # Файлы с прокси-серверами  
├── 📂 EXAMPLES/                 # Примеры использования Telethon
│   ├── example_message_monitor.py
│   ├── example_auto_replier.py
│   └── example_all_updates.py
├── 📄 MONITORING_RESEARCH.md    # Исследование лучших практик
└── 📄 README.md                 # Документация проекта
```

## 💡 Как это работает

### 1️⃣ Этап отправки (SENDER)
- Загружает авторизованные сессии
- Распределяет их по прокси-серверам
- Отправляет уникальные сообщения получателям
- Сохраняет ID отправленных пользователей

### 2️⃣ Этап мониторинга (RECEIVER)  
- Устанавливает Event Handlers на входящие сообщения
- Фильтрует только ответы от получателей рассылки
- Мгновенно уведомляет администратора о каждом ответе
- Работает в режиме 24/7

### 3️⃣ Система уведомлений
```python
📩 Сообщение от [Имя пользователя]: [Текст ответа]
```

## 🛠️ Технологии

- **[Telethon](https://github.com/LonamiWebs/Telethon)** - Telegram MTProto API
- **Python AsyncIO** - Асинхронное программирование  
- **Event-Driven Architecture** - Архитектура на основе событий
- **Multi-Session Management** - Управление множественными сессиями

## 📈 Статистика проекта

- ✅ **929 строк кода** добавлено в последнем релизе
- 🎯 **Поддержка 20+ аккаунтов** одновременно
- 🔄 **100% uptime** мониторинга после рассылки
- 🛡️ **Smart filtering** - только релевантные сообщения

## 🤝 Вклад в проект

Приветствуются pull requests, issues и предложения по улучшению!

## 📄 Лицензия

MIT License - используйте свободно для любых целей.

---

**Создано с ❤️ для эффективной коммуникации в Telegram**

> 💡 **Tip**: Этот проект превращает обычную рассылку в полноценную систему двусторонней коммуникации!