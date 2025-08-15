#!/usr/bin/env python3
"""
Простой скрипт для создания таблиц в базе данных Railway
"""
import os
import sys
from models import create_tables, migrate_from_json

def main():
    """Основная функция"""
    try:
        print("🔗 Подключение к базе данных Railway...")
        
        # Проверяем переменную окружения
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("❌ ОШИБКА: Переменная DATABASE_URL не установлена")
            sys.exit(1)
        
        print(f"📊 URL базы данных: {database_url[:50]}...")
        
        # Создаем таблицы
        print("🏗️ Создание таблиц...")
        create_tables()
        
        # Мигрируем данные из JSON
        print("📦 Миграция данных из JSON...")
        migrate_from_json()
        
        print("✅ Все операции завершены успешно!")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 