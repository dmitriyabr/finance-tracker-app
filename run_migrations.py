#!/usr/bin/env python3
"""
Скрипт для запуска миграций Alembic на Railway
"""
import os
import subprocess
import sys

def run_migrations():
    """Запускает миграции Alembic"""
    try:
        # Проверяем, что переменная DATABASE_URL установлена
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("ОШИБКА: Переменная DATABASE_URL не установлена")
            sys.exit(1)
        
        print(f"Подключение к базе данных: {database_url[:50]}...")
        
        # Запускаем миграции
        print("Запуск миграций Alembic...")
        result = subprocess.run([
            sys.executable, '-m', 'alembic', 'upgrade', 'head'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Миграции успешно выполнены!")
            print(result.stdout)
        else:
            print("❌ Ошибка при выполнении миграций:")
            print(result.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations() 