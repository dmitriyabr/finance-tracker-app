from flask import Flask, jsonify, request
import os
from datetime import datetime
import base64

app = Flask(__name__)

# Инициализация Google Vision API
vision_client = None
try:
    from google.cloud import vision
    import os
    
    # Сначала пробуем создать credentials из переменной GOOGLE_CREDENTIALS_CONTENT
    credentials_content = os.environ.get('GOOGLE_CREDENTIALS_CONTENT')
    if credentials_content:
        print("🔧 Создаю credentials из GOOGLE_CREDENTIALS_CONTENT...")
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(credentials_content)
            temp_credentials_path = f.name
            print(f"📝 Создан временный файл: {temp_credentials_path}")
        
        # Устанавливаем путь
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
        vision_client = vision.ImageAnnotatorClient()
        print("✅ Google Vision API подключен через GOOGLE_CREDENTIALS_CONTENT!")
    else:
        print("❌ GOOGLE_CREDENTIALS_CONTENT не установлен")
        
        # Fallback: проверяем GOOGLE_APPLICATION_CREDENTIALS
        credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            print(f"✅ Credentials файл найден: {credentials_path}")
            vision_client = vision.ImageAnnotatorClient()
            print("✅ Google Vision API подключен!")
        else:
            print("❌ GOOGLE_APPLICATION_CREDENTIALS не работает")
            vision_client = None
        
except Exception as e:
    print(f"❌ Ошибка подключения к Google Vision: {e}")
    import traceback
    traceback.print_exc()
    vision_client = None

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
        if not vision_client:
            return {'success': False, 'error': 'Google Vision недоступен'}
        
        try:
            import re
            image = vision.Image(content=image_content)
            response = vision_client.text_detection(image=image)
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
    """Главная страница - полноценный HTML с графиками"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Finance Tracker Pro</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .main-container { 
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                margin: 20px;
                padding: 30px;
            }
            .balance-card {
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
                border-radius: 20px;
                padding: 30px;
                text-align: center;
                margin: 20px 0;
                box-shadow: 0 10px 30px rgba(79, 172, 254, 0.3);
            }
            .balance-amount {
                font-size: 3rem;
                font-weight: bold;
                margin: 10px 0;
            }
            .balance-change {
                font-size: 1.2rem;
                opacity: 0.9;
            }
            .form-section {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 25px;
                margin: 20px 0;
                border: 1px solid #e9ecef;
            }
            .upload-section {
                background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
                border-radius: 15px;
                padding: 25px;
                margin: 20px 0;
                border: none;
            }
            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                border-radius: 25px;
                padding: 12px 30px;
                font-weight: 600;
                transition: all 0.3s;
            }
            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            .btn-success {
                background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%);
                border: none;
                border-radius: 25px;
                padding: 12px 30px;
                font-weight: 600;
            }
            .account-card {
                background: white;
                border-radius: 15px;
                padding: 20px;
                margin: 15px 0;
                border: 1px solid #e9ecef;
                transition: all 0.3s;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            }
            .account-card:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            }
            .account-name {
                font-size: 1.2rem;
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 10px;
            }
            .account-balance-usd {
                font-size: 1.8rem;
                font-weight: bold;
                color: #27ae60;
                margin-bottom: 5px;
            }
            .account-balance-local {
                font-size: 1rem;
                color: #7f8c8d;
            }
            .chart-container {
                background: white;
                border-radius: 15px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            }
            .success-message {
                background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%);
                color: white;
                padding: 15px;
                border-radius: 10px;
                margin: 15px 0;
                text-align: center;
                font-weight: 600;
            }
            .error-message {
                background: linear-gradient(135deg, #ff6b6b 0%, #ffa5a5 100%);
                color: white;
                padding: 15px;
                border-radius: 10px;
                margin: 15px 0;
                text-align: center;
                font-weight: 600;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }
            .stat-card {
                background: white;
                border-radius: 15px;
                padding: 20px;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            }
            .stat-number {
                font-size: 2rem;
                font-weight: bold;
                color: #667eea;
            }
            .stat-label {
                color: #7f8c8d;
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="main-container">
                <div class="text-center mb-4">
                    <h1 class="display-4 fw-bold text-gradient">💰 Finance Tracker Pro</h1>
                    <p class="lead text-muted">Умное управление финансами с AI</p>
                </div>
                
                <!-- Общий баланс -->
                <div class="balance-card">
                    <h3>Общий баланс</h3>
                    <div class="balance-amount">$<span id="total">0.00</span></div>
                    <div class="balance-change" id="balanceChange"></div>
                </div>
                
                <!-- Статистика -->
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number" id="totalAccounts">0</div>
                        <div class="stat-label">Счетов</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="totalTransactions">0</div>
                        <div class="stat-label">Транзакций</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="lastUpdate">-</div>
                        <div class="stat-label">Обновлено</div>
                    </div>
                </div>
                
                <!-- Форма добавления баланса -->
                <div class="form-section">
                    <h4>💳 Добавить баланс вручную</h4>
                    <div class="row">
                        <div class="col-md-4">
                            <input type="number" id="amount" class="form-control" placeholder="Сумма" step="0.01">
                        </div>
                        <div class="col-md-4">
                            <select id="currency" class="form-select">
                                <option value="RUB">Рубли (RUB)</option>
                                <option value="USD">Доллары (USD)</option>
                                <option value="EUR">Евро (EUR)</option>
                                <option value="AED">Дирхамы (AED)</option>
                                <option value="IDR">Рупии (IDR)</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <button onclick="addBalance()" class="btn btn-primary w-100">Добавить</button>
                        </div>
                    </div>
                </div>
                
                <!-- Загрузка скриншота -->
                <div class="upload-section">
                    <h4>📱 Загрузить скриншот банковского приложения</h4>
                    <div class="row">
                        <div class="col-md-6">
                            <input type="file" id="imageFile" class="form-control" accept="image/*">
                        </div>
                        <div class="col-md-3">
                            <button onclick="processImage()" class="btn btn-primary w-100">Распознать</button>
                        </div>
                        <div class="col-md-3">
                            <button onclick="testAPI()" class="btn btn-success w-100">🧪 Тест API</button>
                        </div>
                    </div>
                    <div id="imageResult"></div>
                </div>
                
                <!-- Графики -->
                <div class="row">
                    <div class="col-md-6">
                        <div class="chart-container">
                            <h5>📊 Распределение по валютам</h5>
                            <canvas id="currencyChart"></canvas>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-container">
                            <h5>📈 Динамика общего баланса</h5>
                            <canvas id="totalBalanceChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <!-- Счета -->
                <div class="chart-container">
                    <h4>🏦 Ваши счета</h4>
                    <div id="accountsList">Нет счетов</div>
                </div>
            </div>
        </div>
        
        <script>
            let accounts = {};
            let currencyChart = null;
            let totalBalanceChart = null;
            
            function addBalance() {
                const amount = document.getElementById('amount').value;
                const currency = document.getElementById('currency').value;
                
                if (!amount) {
                    showMessage('Введите сумму', 'error');
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
                console.log('🔄 Начинаю обработку изображения...');
                
                const fileInput = document.getElementById('imageFile');
                const file = fileInput.files[0];
                
                if (!file) {
                    showMessage('Выберите изображение', 'error');
                    return;
                }
                
                console.log('📁 Файл выбран:', file.name, 'Размер:', file.size, 'байт');
                
                const formData = new FormData();
                formData.append('image', file);
                
                console.log('📤 Отправляю запрос к /api/process_image...');
                
                fetch('/api/process_image', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    console.log('📥 Получен ответ:', response.status, response.statusText);
                    return response.json();
                })
                .then(data => {
                    console.log('📋 Данные ответа:', data);
                    
                    if (data.success) {
                        const balance = data.main_balance;
                        showMessage(`Найден баланс: ${balance.value} ${balance.currency}`, 'success');
                        
                        // Автоматически добавляем найденный баланс
                        console.log('💾 Автоматически добавляю баланс...');
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
                })
                .catch(error => {
                    console.error('❌ Ошибка при обработке изображения:', error);
                    showMessage('Ошибка сети: ' + error.message, 'error');
                });
            }
            
            function updateDisplay(accountsData) {
                accounts = accountsData.accounts;
                
                // Обновляем общий баланс
                document.getElementById('total').textContent = formatNumber(accountsData.total_balance_usd);
                
                // Обновляем статистику
                document.getElementById('totalAccounts').textContent = accountsData.total_count;
                document.getElementById('totalTransactions').textContent = getTotalTransactions();
                document.getElementById('lastUpdate').textContent = formatDate(accountsData.last_updated);
                
                // Обновляем список счетов
                updateAccountsList();
                
                // Обновляем графики
                updateCharts();
            }
            
            function updateAccountsList() {
                const accountsList = document.getElementById('accountsList');
                if (Object.keys(accounts).length === 0) {
                    accountsList.innerHTML = '<p class="text-muted text-center">Нет счетов</p>';
                    return;
                }
                
                let html = '';
                for (const [id, account] of Object.entries(accounts)) {
                    html += `
                        <div class="account-card">
                            <div class="account-name">${account.name}</div>
                            <div class="account-balance-usd">$${formatNumber(account.balance_usd)}</div>
                            <div class="account-balance-local">${formatNumber(account.balance)} ${account.currency}</div>
                            <small class="text-muted">Обновлено: ${formatDate(account.last_updated)}</small>
                        </div>
                    `;
                }
                accountsList.innerHTML = html;
            }
            
            function updateCharts() {
                updateCurrencyChart();
                updateTotalBalanceChart();
            }
            
            function updateCurrencyChart() {
                const ctx = document.getElementById('currencyChart').getContext('2d');
                
                if (currencyChart) {
                    currencyChart.destroy();
                }
                
                const labels = [];
                const data = [];
                const colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'];
                
                for (const [id, account] of Object.entries(accounts)) {
                    labels.push(account.currency);
                    data.push(account.balance_usd);
                }
                
                currencyChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: data,
                            backgroundColor: colors.slice(0, labels.length),
                            borderWidth: 2,
                            borderColor: '#fff'
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
            }
            
            function updateTotalBalanceChart() {
                const ctx = document.getElementById('totalBalanceChart').getContext('2d');
                
                if (totalBalanceChart) {
                    totalBalanceChart.destroy();
                }
                
                // Создаем демо-данные для графика
                const labels = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг'];
                const data = [0, 0, 0, 0, 0, 0, 0, parseFloat(document.getElementById('total').textContent)];
                
                totalBalanceChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Общий баланс (USD)',
                            data: data,
                            borderColor: '#667eea',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'top'
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });
            }
            
            function getTotalTransactions() {
                let total = 0;
                for (const account of Object.values(accounts)) {
                    total += account.transactions ? account.transactions.length : 0;
                }
                return total;
            }
            
            function formatNumber(num) {
                if (num === undefined || num === null) return '0.00';
                return parseFloat(num).toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }
            
            function formatDate(dateString) {
                if (!dateString) return '-';
                const date = new Date(dateString);
                return date.toLocaleDateString('ru-RU');
            }
            
            function showMessage(message, type) {
                const resultDiv = document.getElementById('imageResult');
                const className = type === 'success' ? 'success-message' : 'error-message';
                resultDiv.innerHTML = `<div class="${className}">${message}</div>`;
                setTimeout(() => resultDiv.innerHTML = '', 5000);
            }
            
            function testAPI() {
                console.log('🧪 Тестирую API...');
                showMessage('Тестирую API...', 'success');
                
                // Тест 1: Проверка здоровья
                fetch('/health')
                    .then(response => response.json())
                    .then(data => {
                        console.log('✅ Health check:', data);
                        showMessage('Health: OK', 'success');
                    })
                    .catch(error => {
                        console.error('❌ Health check failed:', error);
                        showMessage('Health: FAILED', 'error');
                    });
                
                // Тест 2: Статус Google Vision
                fetch('/api/vision_status')
                    .then(response => response.json())
                    .then(data => {
                        console.log('✅ Vision status:', data);
                        showMessage(`Vision: ${data.vision_available ? 'OK' : 'FAILED'}`, data.vision_available ? 'success' : 'error');
                    })
                    .catch(error => {
                        console.error('❌ Vision status failed:', error);
                        showMessage('Vision: FAILED', 'error');
                    });
                
                // Тест 3: Получение счетов
                fetch('/api/accounts')
                    .then(response => response.json())
                    .then(data => {
                        console.log('✅ Accounts:', data);
                        showMessage(`Accounts: ${data.total_count} счетов`, 'success');
                    })
                    .catch(error => {
                        console.error('❌ Accounts failed:', error);
                        showMessage('Accounts: FAILED', 'error');
                    });
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
        print("🔄 Начинаю обработку изображения...")
        
        if 'image' not in request.files:
            print("❌ Изображение не найдено в request.files")
            return jsonify({'success': False, 'error': 'Изображение не найдено'})
        
        image_file = request.files['image']
        if image_file.filename == '':
            print("❌ Файл не выбран")
            return jsonify({'success': False, 'error': 'Файл не выбран'})
        
        print(f"📁 Получен файл: {image_file.filename}")
        
        image_content = image_file.read()
        print(f"📊 Размер изображения: {len(image_content)} байт")
        
        # Проверяем Google Vision API
        if not vision_client:
            print("❌ Google Vision API недоступен")
            return jsonify({'success': False, 'error': 'Google Vision API недоступен'})
        
        print("🔍 Отправляю изображение в Google Vision...")
        result = finance_tracker.process_image(image_content)
        
        print(f"📋 Результат обработки: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Ошибка в API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vision_status')
def vision_status():
    """Проверка статуса Google Vision API"""
    status = {
        'vision_available': vision_client is not None,
        'credentials_set': bool(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')),
        'credentials_content': bool(os.environ.get('GOOGLE_CREDENTIALS_CONTENT')),
        'timestamp': datetime.now().isoformat()
    }
    return jsonify(status)

@app.route('/health')
def health():
    """Проверка здоровья приложения"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port) 