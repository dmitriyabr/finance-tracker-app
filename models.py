#!/usr/bin/env python3
"""
SQLAlchemy модели для Finance Tracker
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import SQLAlchemyError
import json

# Кэш для курсов валют
_exchange_rates_cache = {}
_cache_expiry = None
_cache_duration = timedelta(hours=1)  # Обновляем курсы каждый час

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

# Функция для конвертации валют в USD (с актуальными курсами)
def convert_to_usd(amount, currency):
    """
    Конвертирует сумму из указанной валюты в USD
    Использует актуальные курсы валют через API с кэшированием
    """
    if currency.upper() == 'USD':
        return amount
    
    # Проверяем кэш
    if _is_cache_valid():
        rate = _exchange_rates_cache.get(currency.upper())
        if rate is not None:
            return amount * rate
    
    # Получаем свежие курсы
    try:
        _update_exchange_rates_cache()
        rate = _exchange_rates_cache.get(currency.upper())
        if rate is not None:
            return amount * rate
        else:
            print(f"⚠️ Курс для валюты {currency} не найден, используем 1.0")
            return amount
    except Exception as e:
        print(f"⚠️ Ошибка получения курсов валют: {e}, используем фиксированные курсы")
        return _convert_with_fixed_rates(amount, currency)

def _is_cache_valid():
    """Проверяет, действителен ли кэш курсов валют"""
    global _cache_expiry
    return _cache_expiry and datetime.utcnow() < _cache_expiry

def _update_exchange_rates_cache():
    """Обновляет кэш курсов валют через API"""
    global _exchange_rates_cache, _cache_expiry
    
    try:
        import requests
        
        # Используем бесплатный API для курсов валют
        api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            rates = data['rates']
            
            # Сохраняем курсы в кэш (инвертируем, так как API возвращает USD к валюте)
            _exchange_rates_cache = {currency: 1/rate for currency, rate in rates.items()}
            _exchange_rates_cache['USD'] = 1.0  # USD всегда 1.0
            
            # Устанавливаем время истечения кэша
            _cache_expiry = datetime.utcnow() + _cache_duration
            
            print("✅ Курсы валют обновлены")
        else:
            print(f"⚠️ Ошибка API курсов валют: {response.status_code}")
            raise Exception(f"API вернул статус {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ Ошибка обновления курсов валют: {e}")
        # Если не удалось обновить, используем фиксированные курсы
        _exchange_rates_cache = _get_fixed_rates()
        _cache_expiry = datetime.utcnow() + timedelta(minutes=30)  # Короткий кэш для фиксированных курсов

def _get_fixed_rates():
    """Возвращает фиксированные курсы валют"""
    return {
        'RUB': 0.011,  # 1 RUB = 0.011 USD
        'EUR': 1.08,   # 1 EUR = 1.08 USD
        'AED': 0.27,   # 1 AED = 0.27 USD
        'IDR': 0.000065, # 1 IDR = 0.000065 USD
        'USD': 1.0     # 1 USD = 1.0 USD
    }

def _convert_with_fixed_rates(amount, currency):
    """
    Резервная функция с фиксированными курсами валют
    Используется при ошибках API
    """
    fixed_rates = _get_fixed_rates()
    rate = fixed_rates.get(currency.upper(), 1.0)
    return amount * rate

def force_update_exchange_rates():
    """
    Принудительно обновляет курсы валют
    Возвращает True если успешно, False если ошибка
    """
    try:
        _update_exchange_rates_cache()
        return True
    except Exception as e:
        print(f"❌ Ошибка принудительного обновления курсов: {e}")
        return False

def get_current_exchange_rates():
    """
    Возвращает текущие курсы валют из кэша
    """
    if not _is_cache_valid():
        _update_exchange_rates_cache()
    
    return _exchange_rates_cache.copy()

if __name__ == '__main__':
    # Создаем таблицы и мигрируем данные
    create_tables()
    migrate_from_json() 