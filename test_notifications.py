#!/usr/bin/env python3
"""
🧪 ТЕСТИРОВАНИЕ НОВОЙ СИСТЕМЫ УВЕДОМЛЕНИЙ
"""
import asyncio
from notification_bot import init_notification_bot, notify_admin_via_bot

class FakeTelegramUser:
    """Эмуляция пользователя Telegram для тестов"""
    def __init__(self, name, username, phone):
        self.first_name = name
        self.username = username
        self.phone = phone
        self.id = hash(phone)  # Фейковый ID

class FakeClient:
    """Эмуляция клиента Telegram для тестов"""
    def __init__(self, name, phone):
        self.name = name
        self.phone = phone
    
    async def get_me(self):
        user = FakeTelegramUser(self.name, None, self.phone)
        return user

async def test_notification_system():
    """🚀 Тестируем новую систему уведомлений"""
    print("🧪 ТЕСТ СИСТЕМЫ УВЕДОМЛЕНИЙ")
    print("=" * 50)
    
    # Инициализируем бота
    bot = init_notification_bot()
    
    if not bot:
        print("❌ Ошибка инициализации бота")
        return
    
    # Тестируем подключение
    success = await bot.test_connection()
    if not success:
        print("❌ Ошибка соединения с группой")
        return
    
    print("\n📡 Симуляция входящих сообщений...")
    
    # Симулируем разные сценарии
    scenarios = [
        {
            'account': FakeClient("Sergey D.", "+919313919689"),
            'sender': FakeTelegramUser("Иван Петров", "ivan_petrov", "+79123456789"),
            'message': "Привет! Спасибо за информацию, очень интересно!"
        },
        {
            'account': FakeClient("Alex P.", "+15078139699"), 
            'sender': FakeTelegramUser("Anna Smith", "anna_smith", "+1234567890"),
            'message': "Hello! Could you please send me more details?"
        },
        {
            'account': FakeClient("Mike R.", "+919376798654"),
            'sender': FakeTelegramUser("Дмитрий", None, "+79167890123"),
            'message': "Отлично! Когда можем встретиться?"
        }
    ]
    
    # Отправляем тестовые уведомления
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📩 Тест {i}/3: {scenario['sender'].first_name} -> {scenario['account'].name}")
        
        await notify_admin_via_bot(
            scenario['sender'],
            scenario['message'],
            scenario['account']
        )
        
        # Небольшая задержка между уведомлениями
        await asyncio.sleep(2)
    
    print("\n✅ Тестирование завершено!")
    print("🔍 Проверьте группу на наличие уведомлений")

if __name__ == "__main__":
    asyncio.run(test_notification_system())
