#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к базе данных PostgreSQL на Railway
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def test_database_connection():
    """Тестирует подключение к базе данных"""
    try:
        # Получаем URL базы данных из переменных окружения
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("❌ ОШИБКА: Переменная DATABASE_URL не установлена")
            return False
        
        print(f"🔗 Подключение к базе данных: {database_url[:50]}...")
        
        # Создаем движок SQLAlchemy
        engine = create_engine(database_url)
        
        # Тестируем подключение
        with engine.connect() as connection:
            # Выполняем простой запрос
            result = connection.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Подключение успешно! PostgreSQL версия: {version}")
            
            # Проверяем существующие таблицы
            result = connection.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result.fetchall()]
            if tables:
                print(f"📋 Найденные таблицы: {', '.join(tables)}")
            else:
                print("📋 Таблицы не найдены (возможно, миграции еще не выполнены)")
            
            return True
            
    except SQLAlchemyError as e:
        print(f"❌ Ошибка SQLAlchemy: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1) 