#!/usr/bin/env python3
"""
SQLAlchemy модели для Finance Tracker
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Создаем базовый класс для моделей
Base = declarative_base()

class Account(Base):
    """Модель счета"""
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    currency = Column(String(10), nullable=False)  # RUB, USD, EUR, AED, IDR
    balance = Column(Float, default=0.0)
    balance_usd = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Связь с транзакциями
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Account(name='{self.name}', currency='{self.currency}', balance={self.balance})>"

class Transaction(Base):
    """Модель транзакции"""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    old_balance = Column(Float, default=0.0)
    new_balance = Column(Float, default=0.0)
    change = Column(Float, default=0.0)
    source = Column(String(50), default='unknown')  # 'telegram', 'web', 'api'
    original_text = Column(Text, nullable=True)
    
    # Связь с аккаунтом
    account = relationship("Account", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(account_id={self.account_id}, change={self.change}, source='{self.source}')>"

class SystemInfo(Base):
    """Системная информация"""
    __tablename__ = 'system_info'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SystemInfo(key='{self.key}', value='{self.value}')>"

# Функция для создания подключения к БД
def get_database_url():
    """Получаем URL базы данных из переменных окружения Railway"""
    # Railway автоматически создает переменную DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        # Fallback для локальной разработки
        database_url = "postgresql://postgres:password@localhost:5432/finance_tracker"
    
    return database_url

# Создаем движок базы данных
def create_database_engine():
    """Создаем движок SQLAlchemy"""
    database_url = get_database_url()
    
    # Railway использует PostgreSQL, который может требовать SSL
    if database_url.startswith('postgresql://') and 'railway.app' in database_url:
        # Добавляем SSL параметры для Railway
        if '?' not in database_url:
            database_url += '?sslmode=require'
        else:
            database_url += '&sslmode=require'
    
    engine = create_engine(database_url, echo=False)
    return engine

# Создаем сессию
def create_session():
    """Создаем сессию базы данных"""
    engine = create_database_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

# Функция для создания всех таблиц
def create_tables():
    """Создаем все таблицы в базе данных"""
    engine = create_database_engine()
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы базы данных созданы")

# Функция для миграции данных из JSON
def migrate_from_json(json_file_path='finance_data.json'):
    """Мигрируем данные из старого JSON файла"""
    import json
    
    if not os.path.exists(json_file_path):
        print(f"❌ Файл {json_file_path} не найден")
        return
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        session = create_session()
        
        # Мигрируем аккаунты
        if 'accounts' in old_data:
            for account_id, account_data in old_data['accounts'].items():
                # Проверяем, существует ли уже аккаунт
                existing_account = session.query(Account).filter_by(
                    currency=account_data['currency']
                ).first()
                
                if not existing_account:
                    new_account = Account(
                        name=account_data['name'],
                        currency=account_data['currency'],
                        balance=account_data['balance'],
                        balance_usd=account_data['balance_usd'],
                        last_updated=datetime.fromisoformat(account_data['last_updated']) if account_data.get('last_updated') else datetime.utcnow()
                    )
                    session.add(new_account)
                    
                    # Мигрируем транзакции
                    if 'transactions' in account_data:
                        for tx_data in account_data['transactions']:
                            new_transaction = Transaction(
                                account_id=new_account.id,
                                timestamp=datetime.fromisoformat(tx_data['timestamp']) if tx_data.get('timestamp') else datetime.utcnow(),
                                old_balance=tx_data.get('old_balance', 0),
                                new_balance=tx_data.get('new_balance', 0),
                                change=tx_data.get('change', 0),
                                source=tx_data.get('source', 'migration'),
                                original_text=tx_data.get('original_text', '')
                            )
                            session.add(new_transaction)
        
        # Сохраняем общий баланс
        if 'total_balance_usd' in old_data:
            system_info = SystemInfo(
                key='total_balance_usd',
                value=str(old_data['total_balance_usd'])
            )
            session.add(system_info)
        
        session.commit()
        print("✅ Миграция данных завершена успешно")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        session.rollback()
    finally:
        session.close()

# Функция для конвертации валют в USD (упрощенная версия)
def convert_to_usd(amount, currency):
    """
    Конвертирует сумму из указанной валюты в USD
    Это упрощенная версия - в реальном приложении нужно использовать API курсов валют
    """
    # Простые курсы валют (для демонстрации)
    exchange_rates = {
        'RUB': 0.011,  # 1 RUB = 0.011 USD
        'EUR': 1.08,   # 1 EUR = 1.08 USD
        'AED': 0.27,   # 1 AED = 0.27 USD
        'IDR': 0.000065, # 1 IDR = 0.000065 USD
        'USD': 1.0     # 1 USD = 1.0 USD
    }
    
    rate = exchange_rates.get(currency.upper(), 1.0)
    return amount * rate

if __name__ == '__main__':
    # Создаем таблицы и мигрируем данные
    create_tables()
    migrate_from_json() 