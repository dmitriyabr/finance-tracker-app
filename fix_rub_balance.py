#!/usr/bin/env python3
"""
Скрипт для исправления баланса российского счета
"""

import json
import os

def fix_rub_balance():
    """Исправляем баланс российского счета"""
    
    if not os.path.exists('finance_data.json'):
        print("❌ Файл finance_data.json не найден")
        return
    
    with open('finance_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("📊 Текущие данные:")
    print(f"   • Счетов: {len(data.get('accounts', {}))}")
    print(f"   • Общий баланс: ${data.get('total_balance_usd', 0):,.2f}")
    
    # Ищем российский счет
    rub_account = None
    for account_id, account in data.get('accounts', {}).items():
        if account['currency'] == 'RUB':
            rub_account = account
            break
    
    if not rub_account:
        print("❌ Российский счет не найден")
        return
    
    print(f"\n🇷🇺 Российский счет найден:")
    print(f"   • ID: {account_id}")
    print(f"   • Текущий баланс: {rub_account['balance']:,.2f} RUB")
    print(f"   • В долларах: ${rub_account['balance_usd']:,.2f}")
    
    # Исправляем баланс: 25028830 -> 250288.30
    old_balance = rub_account['balance']
    new_balance = 250288.30  # Правильный баланс
    
    print(f"\n🔧 Исправляем баланс:")
    print(f"   • Было: {old_balance:,.2f} RUB")
    print(f"   • Станет: {new_balance:,.2f} RUB")
    
    # Обновляем баланс
    rub_account['balance'] = new_balance
    
    # Пересчитываем в доллары (1 RUB = 0.011 USD)
    rub_account['balance_usd'] = new_balance * 0.011
    
    print(f"   • Новый баланс в долларах: ${rub_account['balance_usd']:,.2f}")
    
    # Пересчитываем общий баланс
    total_usd = 0
    for account in data['accounts'].values():
        total_usd += account['balance_usd']
    
    data['total_balance_usd'] = round(total_usd, 2)
    
    print(f"\n💰 Новый общий баланс: ${data['total_balance_usd']:,.2f}")
    
    # Сохраняем исправленные данные
    with open('finance_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Баланс исправлен и сохранен!")
    
    return data

if __name__ == '__main__':
    fix_rub_balance() 