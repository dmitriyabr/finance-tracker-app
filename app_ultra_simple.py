from flask import Flask, jsonify, request
import os
from datetime import datetime
import base64

app = Flask(__name__)

# Инициализация Google Vision API
try:
    from google.cloud import vision
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        # Для Railway - создаем credentials из переменной окружения
        credentials_content = os.environ.get('GOOGLE_CREDENTIALS_CONTENT')
        if credentials_content:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(credentials_content)
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = f.name
            
        self.vision_client = vision.ImageAnnotatorClient()
        print("✅ Google Vision API подключен!")
    else:
        self.vision_client = vision.ImageAnnotatorClient()
        print("✅ Google Vision API подключен!")
except Exception as e:
    print(f"❌ Ошибка подключения к Google Vision: {e}")
    self.vision_client = None

class FinanceTracker:
    def __init__(self):
        """Инициализация трекера финансов"""
        self.accounts = {}
        self.total_balance_usd = 0
        
        # Паттерны для валют
        self.currency_patterns = {
            'RUB': [r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*₽', r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*руб'],
            'USD': [r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\$', r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
            'EUR': [r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*€', r'€(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
            'AED': [r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*AED'],
            'IDR': [r'Rp\s*(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)', r'(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)\s*Rp']
        }
        
        # Курсы валют
        self.conversion_rates = {
            'RUB': 0.011, 'USD': 1.0, 'EUR': 1.09, 'AED': 0.27, 'IDR': 0.000065
        }
    
    def process_image(self, image_content):
        """Обрабатываем изображение через Google Vision"""
        if not self.vision_client:
            return {'success': False, 'error': 'Google Vision недоступен'}
        
        try:
            import re
            image = vision.Image(content=image_content)
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if not texts:
                return {'success': False, 'error': 'Текст не найден'}
            
            full_text = texts[0].description
            text_lines = full_text.split('\n')
            
            # Ищем балансы по всем валютам
            balances = []
            for text in text_lines:
                for currency, patterns in self.currency_patterns.items():
                    for pattern in patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        if matches:
                            for match in matches:
                                clean_number = match.replace(' ', '').replace(',', '')
                                try:
                                    float(clean_number)
                                    balances.append({
                                        'value': clean_number,
                                        'currency': currency,
                                        'original_text': text
                                    })
                                except ValueError:
                                    continue
            
            if balances:
                # Выбираем основной баланс (самый большой)
                main_balance = max(balances, key=lambda x: float(x['value']))
                return {
                    'success': True,
                    'main_balance': main_balance,
                    'all_balances': balances,
                    'full_text': full_text
                }
            else:
                return {
                    'success': False,
                    'error': 'Баланс не найден',
                    'full_text': full_text
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_balance(self, amount, currency, source='manual'):
        """Добавляем или обновляем баланс"""
        timestamp = datetime.now().isoformat()
        
        account_id = f"account_{currency}"
        
        if account_id not in self.accounts:
            account_names = {
                'RUB': 'Российский счет', 'USD': 'Долларовый счет', 'EUR': 'Евро счет',
                'AED': 'Дирхамовый счет', 'IDR': 'Рупиевый счет'
            }
            
            self.accounts[account_id] = {
                'name': account_names.get(currency, f'Счет в {currency}'),
                'currency': currency,
                'balance': 0,
                'balance_usd': 0,
                'last_updated': None,
                'transactions': []
            }
        
        account = self.accounts[account_id]
        old_balance = account['balance']
        account['balance'] = float(amount)
        account['last_updated'] = timestamp
        
        # Конвертируем в USD
        if currency in self.conversion_rates:
            account['balance_usd'] = account['balance'] * self.conversion_rates[currency]
        
        # Добавляем транзакцию
        transaction = {
            'id': len(account['transactions']) + 1,
            'timestamp': timestamp,
            'old_balance': old_balance,
            'new_balance': account['balance'],
            'change': account['balance'] - old_balance,
            'source': source
        }
        
        account['transactions'].append(transaction)
        
        # Обновляем общий баланс
        self.update_total_balance()
        
        return transaction
    
    def update_total_balance(self):
        """Обновляем общий баланс в USD"""
        total_usd = 0
        for account in self.accounts.values():
            total_usd += account['balance_usd']
        self.total_balance_usd = round(total_usd, 2)
    
    def get_summary(self):
        """Получаем сводку по всем счетам"""
        return {
            'accounts': self.accounts,
            'total_balance_usd': self.total_balance_usd,
            'last_updated': datetime.now().isoformat(),
            'total_count': len(self.accounts)
        }

# Создаем экземпляр трекера
finance_tracker = FinanceTracker()

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
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .balance { font-size: 28px; color: #2c3e50; margin: 20px 0; text-align: center; }
            .form { margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
            .form h3 { margin-top: 0; color: #495057; }
            input, select, button { padding: 12px; margin: 8px; font-size: 16px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #007bff; color: white; border: none; cursor: pointer; transition: background 0.3s; }
            button:hover { background: #0056b3; }
            .upload-section { margin: 20px 0; padding: 20px; background: #e3f2fd; border-radius: 8px; }
            .accounts { margin: 30px 0; }
            .account { padding: 15px; border: 1px solid #e9ecef; margin: 10px 0; border-radius: 8px; background: #f8f9fa; }
            .success { color: #28a745; font-weight: bold; }
            .error { color: #dc3545; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💰 Finance Tracker</h1>
            <div class="balance">Общий баланс: $<span id="total">0.00</span></div>
            
            <div class="form">
                <h3>Добавить баланс вручную:</h3>
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
            
            <div class="upload-section">
                <h3>📱 Загрузить скриншот банковского приложения:</h3>
                <input type="file" id="imageFile" accept="image/*">
                <button onclick="processImage()">Распознать баланс</button>
                <div id="imageResult"></div>
            </div>
            
            <div class="accounts">
                <h3>🏦 Ваши счета:</h3>
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
                        showMessage('Баланс добавлен!', 'success');
                    } else {
                        showMessage('Ошибка: ' + data.error, 'error');
                    }
                });
            }
            
            function processImage() {
                const fileInput = document.getElementById('imageFile');
                const file = fileInput.files[0];
                
                if (!file) {
                    alert('Выберите изображение');
                    return;
                }
                
                const formData = new FormData();
                formData.append('image', file);
                
                fetch('/api/process_image', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const balance = data.main_balance;
                        showMessage(`Найден баланс: ${balance.value} ${balance.currency}`, 'success');
                        
                        // Автоматически добавляем найденный баланс
                        fetch('/api/add_balance', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({amount: parseFloat(balance.value), currency: balance.currency})
                        })
                        .then(response => response.json())
                        .then(addData => {
                            if (addData.success) {
                                updateDisplay(addData.accounts);
                                showMessage('Баланс автоматически добавлен!', 'success');
                            }
                        });
                    } else {
                        showMessage('Ошибка: ' + data.error, 'error');
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
            
            function showMessage(message, type) {
                const resultDiv = document.getElementById('imageResult');
                resultDiv.innerHTML = `<div class="${type}">${message}</div>`;
                setTimeout(() => resultDiv.innerHTML = '', 5000);
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
    return jsonify(finance_tracker.get_summary())

@app.route('/api/add_balance', methods=['POST'])
def add_balance():
    """API для добавления баланса"""
    try:
        data = request.get_json()
        amount = data.get('amount', 0)
        currency = data.get('currency', 'USD')
        
        transaction = finance_tracker.add_balance(amount, currency, source='manual')
        accounts_data = finance_tracker.get_summary()
        
        return jsonify({
            'success': True,
            'transaction': transaction,
            'accounts': accounts_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/process_image', methods=['POST'])
def process_image():
    """API для обработки изображения"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'Изображение не найдено'})
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'success': False, 'error': 'Файл не выбран'})
        
        image_content = image_file.read()
        result = finance_tracker.process_image(image_content)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    """Проверка здоровья приложения"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port) 