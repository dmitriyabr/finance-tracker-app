#!/usr/bin/env python3
"""
Скрипт для миграции данных из старой структуры в новую систему счетов
"""

import json
import os
from datetime import datetime

def migrate_data():
    """Мигрируем данные из старой структуры в новую"""
    
    # Читаем старые данные
    if not os.path.exists('finance_data.json'):
        print("❌ Файл finance_data.json не найден")
        return
    
    with open('finance_data.json', 'r', encoding='utf-8') as f:
        old_data = json.load(f)
    
    print("📊 Найдены старые данные:")
    print(f"   • Записей: {len(old_data.get('balances', []))}")
    print(f"   • Общий баланс: {old_data.get('total_balance', 0)}")
    
    # Создаем новую структуру
    new_data = {
        'accounts': {},
        'total_balance_usd': 0,
        'last_updated': None
    }
    
    # Курсы валют для конвертации в доллары
    conversion_rates = {
        'RUB': 0.011,  # 1 RUB = 0.011 USD
        'USD': 1.0,    # 1 USD = 1 USD
        'EUR': 1.09,   # 1 EUR = 1.09 USD
        'AED': 0.27,   # 1 AED = 0.27 USD
        'IDR': 0.000065 # 1 IDR = 0.000065 USD
    }
    
    # Группируем балансы по валютам
    currency_groups = {}
    
    for balance in old_data.get('balances', []):
        currency = balance['currency']
        value = float(balance['value'])
        
        if currency not in currency_groups:
            currency_groups[currency] = []
        
        currency_groups[currency].append({
            'value': value,
            'timestamp': balance['timestamp'],
            'source': balance['source'],
            'original_text': balance.get('original_text', '')
        })
    
    # Создаем счета для каждой валюты
    for currency, balances in currency_groups.items():
        # Берем последний баланс (самый актуальный)
        latest_balance = max(balances, key=lambda x: x['timestamp'])
        
        # Определяем название счета
        account_names = {
            'RUB': 'Российский счет',
            'USD': 'Долларовый счет',
            'EUR': 'Евро счет',
            'AED': 'Дирхамовый счет',
            'IDR': 'Рупиевый счет'
        }
        
        account_name = account_names.get(currency, f'Счет в {currency}')
        account_id = f"account_{len(new_data['accounts']) + 1}"
        
        # Конвертируем в доллары
        balance_usd = latest_balance['value'] * conversion_rates.get(currency, 1.0)
        
        # Создаем счет
        new_data['accounts'][account_id] = {
            'name': account_name,
            'currency': currency,
            'balance': latest_balance['value'],
            'balance_usd': balance_usd,
            'last_updated': latest_balance['timestamp'],
            'transactions': []
        }
        
        # Добавляем транзакции
        for i, balance in enumerate(balances):
            transaction = {
                'id': i + 1,
                'timestamp': balance['timestamp'],
                'old_balance': 0 if i == 0 else balances[i-1]['value'],
                'new_balance': balance['value'],
                'change': balance['value'] - (0 if i == 0 else balances[i-1]['value']),
                'source': balance['source'],
                'original_text': balance['original_text']
            }
            new_data['accounts'][account_id]['transactions'].append(transaction)
    
    # Вычисляем общий баланс в долларах
    total_usd = sum(account['balance_usd'] for account in new_data['accounts'].values())
    new_data['total_balance_usd'] = round(total_usd, 2)
    new_data['last_updated'] = datetime.now().isoformat()
    
    # Сохраняем новые данные
    with open('finance_data_new.json', 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Миграция завершена!")
    print(f"   • Создано счетов: {len(new_data['accounts'])}")
    print(f"   • Общий баланс: ${new_data['total_balance_usd']:,.2f}")
    
    # Показываем детали по счетам
    for account_id, account in new_data['accounts'].items():
        print(f"   • {account['name']}: {account['balance']:,.2f} {account['currency']} (≈ ${account['balance_usd']:,.2f})")
    
    print("\n📁 Новые данные сохранены в finance_data_new.json")
    print("💡 Для применения миграции переименуйте файл в finance_data.json")
    
    return new_data

if __name__ == '__main__':
    migrate_data() 