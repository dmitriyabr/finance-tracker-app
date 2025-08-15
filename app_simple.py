from flask import Flask, render_template, request, jsonify
import os
import json
from datetime import datetime

app = Flask(__name__)

class SimpleFinanceTracker:
    def __init__(self):
        """Инициализация упрощенного приложения"""
        self.data_file = 'finance_data.json'
        self.load_data()
    
    def load_data(self):
        """Загружаем данные из файла"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                self.data = {'accounts': {}, 'total_balance_usd': 0, 'last_updated': None}
        else:
            self.data = {'accounts': {}, 'total_balance_usd': 0, 'last_updated': None}
    
    def save_data(self):
        """Сохраняем данные в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def add_manual_balance(self, amount, currency):
        """Добавляем баланс вручную"""
        timestamp = datetime.now().isoformat()
        
        # Создаем или обновляем счет
        account_id = f"account_{currency}"
        
        if account_id not in self.data['accounts']:
            account_names = {
                'RUB': 'Российский счет',
                'USD': 'Долларовый счет',
                'EUR': 'Евро счет',
                'AED': 'Дирхамовый счет',
                'IDR': 'Рупиевый счет'
            }
            
            self.data['accounts'][account_id] = {
                'name': account_names.get(currency, f'Счет в {currency}'),
                'currency': currency,
                'balance': 0,
                'balance_usd': 0,
                'last_updated': None,
                'transactions': []
            }
        
        account = self.data['accounts'][account_id]
        old_balance = account['balance']
        account['balance'] = float(amount)
        account['last_updated'] = timestamp
        
        # Простая конвертация в USD
        conversion_rates = {
            'RUB': 0.011, 'USD': 1.0, 'EUR': 1.09, 'AED': 0.27, 'IDR': 0.000065
        }
        
        if currency in conversion_rates:
            account['balance_usd'] = account['balance'] * conversion_rates[currency]
        
        # Добавляем транзакцию
        transaction = {
            'id': len(account['transactions']) + 1,
            'timestamp': timestamp,
            'old_balance': old_balance,
            'new_balance': account['balance'],
            'change': account['balance'] - old_balance,
            'source': 'manual'
        }
        
        account['transactions'].append(transaction)
        
        # Обновляем общий баланс
        total_usd = 0
        for acc in self.data['accounts'].values():
            total_usd += acc['balance_usd']
        
        self.data['total_balance_usd'] = round(total_usd, 2)
        self.data['last_updated'] = timestamp
        
        self.save_data()
        return transaction
    
    def get_accounts_summary(self):
        """Получаем сводку по всем счетам"""
        return {
            'accounts': self.data['accounts'],
            'total_balance_usd': self.data['total_balance_usd'],
            'last_updated': self.data['last_updated'],
            'total_count': len(self.data['accounts'])
        }

# Создаем экземпляр трекера
finance_tracker = SimpleFinanceTracker()

@app.route('/')
def index():
    """Главная страница"""
    accounts_data = finance_tracker.get_accounts_summary()
    
    # Конвертируем данные в JSON для JavaScript
    accounts_json = json.dumps(accounts_data, ensure_ascii=False)
    
    return render_template('index.html', 
                         accounts=accounts_data['accounts'],
                         total_balance_usd=accounts_data['total_balance_usd'],
                         last_updated=accounts_data['last_updated'],
                         total_count=accounts_data['total_count'],
                         accounts_json=accounts_json)

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """API для получения сводки по счетам"""
    return jsonify(finance_tracker.get_accounts_summary())

@app.route('/api/add_balance', methods=['POST'])
def add_balance():
    """API для добавления баланса вручную"""
    try:
        data = request.get_json()
        amount = data.get('amount')
        currency = data.get('currency')
        
        if not amount or not currency:
            return jsonify({'success': False, 'error': 'Не указаны сумма или валюта'})
        
        transaction = finance_tracker.add_manual_balance(amount, currency)
        accounts_data = finance_tracker.get_accounts_summary()
        
        return jsonify({
            'success': True,
            'transaction': transaction,
            'accounts': accounts_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    """Проверка здоровья приложения"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port) 