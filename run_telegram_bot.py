#!/usr/bin/env python3
"""
Запуск Telegram бота Finance Tracker
"""

import os
import subprocess
import sys

def main():
    """Запускаем Telegram бота"""
    print("🚀 Запуск Telegram бота Finance Tracker...")
    
    # Проверяем наличие токена
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ Не установлен TELEGRAM_BOT_TOKEN")
        print("Установите переменную окружения TELEGRAM_BOT_TOKEN")
        return
    
    # Запускаем бота
    try:
        subprocess.run([sys.executable, 'telegram_bot_with_graphs.py'], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

if __name__ == '__main__':
    main() 