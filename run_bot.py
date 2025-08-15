#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота Finance Tracker
"""

import os
import subprocess
import sys

def main():
    """Запускаем бота"""
    print("🚀 Запускаю Finance Tracker Telegram Bot...")
    
    # Проверяем наличие токена
    if not os.environ.get('TELEGRAM_BOT_TOKEN'):
        print("❌ TELEGRAM_BOT_TOKEN не установлен!")
        print("💡 Установите переменную окружения:")
        print("   export TELEGRAM_BOT_TOKEN='ваш_токен'")
        return
    
    # Проверяем наличие Google credentials
    if not os.environ.get('GOOGLE_CREDENTIALS_CONTENT'):
        print("⚠️ GOOGLE_CREDENTIALS_CONTENT не установлен")
        print("💡 Бот может не работать без Google Vision API")
    
    try:
        # Запускаем бота
        print("✅ Запускаю бота...")
        subprocess.run([sys.executable, 'telegram_bot_with_graphs.py'], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска бота: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")

if __name__ == '__main__':
    main() 