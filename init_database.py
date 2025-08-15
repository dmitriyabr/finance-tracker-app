#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных Finance Tracker
"""

import os
import sys
from models import create_tables, migrate_from_json

def main():
    """Основная функция инициализации"""
    print("🚀 Инициализация базы данных Finance Tracker...")
    
    # Проверяем наличие переменной DATABASE_URL
    if not os.environ.get('DATABASE_URL'):
        print("⚠️ DATABASE_URL не установлен")
        print("💡 Убедитесь, что PostgreSQL сервис запущен на Railway")
        return
    
    try:
        # Создаем таблицы
        print("📊 Создаем таблицы...")
        create_tables()
        
        # Мигрируем данные из JSON
        print("🔄 Мигрируем данные из JSON...")
        migrate_from_json()
        
        print("✅ База данных инициализирована успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 