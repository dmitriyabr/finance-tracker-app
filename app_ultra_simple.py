from flask import Flask, jsonify
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    """Главная страница - простой HTML"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Finance Tracker</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            .balance { font-size: 24px; color: #2c3e50; margin: 20px 0; }
            .form { margin: 20px 0; }
            input, select, button { padding: 10px; margin: 5px; font-size: 16px; }
            button { background: #3498db; color: white; border: none; cursor: pointer; }
            .accounts { margin: 20px 0; }
            .account { padding: 10px; border: 1px solid #ddd; margin: 5px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💰 Finance Tracker</h1>
            <div class="balance">Общий баланс: $<span id="total">0.00</span></div>
            
            <div class="form">
                <h3>Добавить баланс:</h3>
                <input type="number" id="amount" placeholder="Сумма" step="0.01">
                <select id="currency">
                    <option value="RUB">Рубли (RUB)</option>
                    <option value="USD">Доллары (USD)</option>
                    <option value="EUR">Евро (EUR)</option>
                    <option value="AED">Дирхамы (AED)</option>
                    <option value="IDR">Рупии (IDR)</option>
                </select>
                <button onclick="addBalance()">Добавить</button>
            </div>
            
            <div class="accounts">
                <h3>Ваши счета:</h3>
                <div id="accountsList">Нет счетов</div>
            </div>
        </div>
        
        <script>
            let accounts = {};
            
            function addBalance() {
                const amount = document.getElementById('amount').value;
                const currency = document.getElementById('currency').value;
                
                if (!amount) {
                    alert('Введите сумму');
                    return;
                }
                
                fetch('/api/add_balance', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({amount: parseFloat(amount), currency: currency})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateDisplay(data.accounts);
                        document.getElementById('amount').value = '';
                    } else {
                        alert('Ошибка: ' + data.error);
                    }
                });
            }
            
            function updateDisplay(accountsData) {
                accounts = accountsData.accounts;
                document.getElementById('total').textContent = accountsData.total_balance_usd.toFixed(2);
                
                const accountsList = document.getElementById('accountsList');
                if (Object.keys(accounts).length === 0) {
                    accountsList.innerHTML = 'Нет счетов';
                    return;
                }
                
                let html = '';
                for (const [id, account] of Object.entries(accounts)) {
                    html += `
                        <div class="account">
                            <strong>${account.name}</strong><br>
                            ${account.balance.toFixed(2)} ${account.currency}<br>
                            ≈ $${account.balance_usd.toFixed(2)}
                        </div>
                    `;
                }
                accountsList.innerHTML = html;
            }
            
            // Загружаем данные при старте
            fetch('/api/accounts')
                .then(response => response.json())
                .then(data => updateDisplay(data));
        </script>
    </body>
    </html>
    """
    return html

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """API для получения сводки по счетам"""
    return jsonify({
        'accounts': {},
        'total_balance_usd': 0,
        'last_updated': datetime.now().isoformat(),
        'total_count': 0
    })

@app.route('/api/add_balance', methods=['POST'])
def add_balance():
    """API для добавления баланса"""
    try:
        from flask import request
        data = request.get_json()
        amount = data.get('amount', 0)
        currency = data.get('currency', 'USD')
        
        # Простая конвертация в USD
        conversion_rates = {
            'RUB': 0.011, 'USD': 1.0, 'EUR': 1.09, 'AED': 0.27, 'IDR': 0.000065
        }
        
        balance_usd = amount * conversion_rates.get(currency, 1.0)
        
        return jsonify({
            'success': True,
            'message': f'Добавлено {amount} {currency}',
            'accounts': {
                'accounts': {
                    f'account_{currency}': {
                        'name': f'Счет в {currency}',
                        'currency': currency,
                        'balance': amount,
                        'balance_usd': balance_usd
                    }
                },
                'total_balance_usd': balance_usd,
                'total_count': 1
            }
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