from flask import Flask, render_template, request, jsonify
import os
import json
import re
from datetime import datetime
import requests
from google.cloud import vision
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class FinanceTracker:
    def __init__(self):
        """Инициализация приложения"""
        self.data_file = 'finance_data.json'
        self.load_data()
        
        # Инициализация Google Vision API
        try:
            # Прямое указание пути к credentials
            import os
            if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), 
                    'google-credentials.json'
                )
            
            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("✅ Google Vision API подключен!")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Vision: {e}")
            self.vision_client = None
        
        # Паттерны для всех валют (исправленные)
        self.currency_patterns = {
            'RUB': [
                r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*₽',
                r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*Р',  # Кириллица
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*руб',
                r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*рубл'
            ],
            'USD': [
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\$',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*USD',
                r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'EUR': [
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*€',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*EUR',
                r'€(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'AED': [
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*AED',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*дирхам',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*د\.إ'
            ],
            'IDR': [
                r'Rp\s*(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)',
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)\s*Rp',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{3})?)\s*рупий'
            ]
        }
        
        # Ключевые слова для основного баланса
        self.balance_keywords = [
            'balance', 'total', 'available', 'current', 'main', 'cash',
            'баланс', 'доступно', 'основной', 'текущий', 'общий', 'наличные'
        ]

    def load_data(self):
        """Загружаем данные из файла"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info("✅ Данные загружены")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки данных: {e}")
                self.data = {'accounts': {}, 'total_balance_usd': 0, 'last_updated': None}
        else:
            self.data = {'accounts': {}, 'total_balance_usd': 0, 'last_updated': None}
            logger.info("📁 Создан новый файл данных")

    def save_data(self):
        """Сохраняем данные в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            logger.info("💾 Данные сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")

    def extract_balance_from_text(self, text_lines):
        """Извлекаем баланс из распознанного текста"""
        balances = []
        
        for text in text_lines:
            text_lower = text.lower()
            
            # Ищем по всем валютам
            for currency, patterns in self.currency_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            # Очищаем число
                            clean_number = match.replace(' ', '').replace(',', '')
                            
                            try:
                                float(clean_number)
                                balances.append({
                                    'value': clean_number,
                                    'currency': currency,
                                    'original_text': text,
                                    'pattern': pattern
                                })
                            except ValueError:
                                continue
            
            # Ищем по ключевым словам
            for keyword in self.balance_keywords:
                if keyword in text_lower:
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
                                            'original_text': text,
                                            'keyword': keyword,
                                            'pattern': pattern
                                        })
                                    except ValueError:
                                        continue
        
        return balances

    def fix_russian_number_format(self, text, currency):
        """Исправляем формат российских чисел (запятая как разделитель десятичных знаков)"""
        if currency == 'RUB':
            # Ищем числа в формате "250 288,30" или "250288,30"
            # и конвертируем их в правильный формат
            import re
            
            # Паттерн для российских чисел: цифры, пробелы, запятая, 2 цифры
            russian_pattern = r'(\d{1,3}(?:\s\d{3})*),(\d{2})'
            match = re.search(russian_pattern, text)
            
            if match:
                # Получаем целую и дробную части
                whole_part = match.group(1).replace(' ', '')  # "250288"
                decimal_part = match.group(2)  # "30"
                
                # Собираем правильное число
                correct_number = f"{whole_part}.{decimal_part}"
                
                try:
                    # Проверяем, что получилось валидное число
                    float(correct_number)
                    return correct_number
                except ValueError:
                    pass
        
        return None

    def process_image(self, image_content):
        """Обрабатываем изображение через Google Vision"""
        if not self.vision_client:
            return {'success': False, 'error': 'Google Vision недоступен'}
        
        try:
            # Создаем объект изображения
            image = vision.Image(content=image_content)
            
            # Распознаем текст
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if not texts:
                return {'success': False, 'error': 'Текст не найден'}
            
            # Получаем весь текст
            full_text = texts[0].description
            text_lines = full_text.split('\n')
            
            # Извлекаем балансы
            balances = self.extract_balance_from_text(text_lines)
            
            # Дополнительная обработка для российских рублей
            if balances:
                for balance in balances:
                    if balance['currency'] == 'RUB':
                        # Пытаемся исправить формат числа
                        corrected_number = self.fix_russian_number_format(
                            balance['original_text'], 
                            balance['currency']
                        )
                        if corrected_number:
                            balance['value'] = corrected_number
                            balance['corrected'] = True
            
            if balances:
                # Выбираем основной баланс (самый большой по значению)
                main_balance = max(balances, key=lambda x: float(x['value']))
                
                return {
                    'success': True,
                    'main_balance': main_balance,
                    'all_balances': balances,
                    'text_lines': text_lines,
                    'full_text': full_text
                }
            else:
                return {
                    'success': False,
                    'balance': None,
                    'text_lines': text_lines,
                    'full_text': full_text
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке изображения: {e}")
            return {
                'success': False,
                'balance': None,
                'error': str(e)
            }

    def identify_account(self, balance_data, image_text):
        """Определяем, какой это счет по контексту"""
        # Простая логика определения счета по валюте и контексту
        currency = balance_data['currency']
        
        # Если у нас уже есть счет с такой валютой, используем его
        for account_id, account in self.data['accounts'].items():
            if account['currency'] == currency:
                return account_id
        
        # Иначе создаем новый счет
        account_id = f"account_{len(self.data['accounts']) + 1}"
        
        # Определяем название счета по валюте
        account_names = {
            'RUB': 'Российский счет',
            'USD': 'Долларовый счет',
            'EUR': 'Евро счет',
            'AED': 'Дирхамовый счет',
            'IDR': 'Рупиевый счет'
        }
        
        account_name = account_names.get(currency, f'Счет в {currency}')
        
        self.data['accounts'][account_id] = {
            'name': account_name,
            'currency': currency,
            'balance': 0,
            'balance_usd': 0,
            'last_updated': None,
            'transactions': []
        }
        
        return account_id

    def update_account_balance(self, account_id, balance_data, source='image_upload'):
        """Обновляем баланс счета (не суммируем, а заменяем)"""
        timestamp = datetime.now().isoformat()
        
        # Получаем счет
        account = self.data['accounts'][account_id]
        
        # Обновляем баланс
        old_balance = account['balance']
        account['balance'] = float(balance_data['value'])
        account['last_updated'] = timestamp
        
        # Конвертируем в доллары
        account['balance_usd'] = self.convert_to_usd(account['balance'], account['currency'])
        
        # Добавляем транзакцию
        transaction = {
            'id': len(account['transactions']) + 1,
            'timestamp': timestamp,
            'old_balance': old_balance,
            'new_balance': account['balance'],
            'change': account['balance'] - old_balance,
            'source': source,
            'original_text': balance_data.get('original_text', '')
        }
        
        account['transactions'].append(transaction)
        
        # Обновляем общий баланс в долларах
        self.update_total_balance_usd()
        
        # Сохраняем данные
        self.save_data()
        
        logger.info(f"✅ Обновлен баланс счета {account_id}: {account['balance']} {account['currency']} (${account['balance_usd']:.2f})")
        return transaction

    def convert_to_usd(self, amount, currency):
        """Конвертируем валюту в доллары"""
        # Актуальные курсы валют (в реальном приложении нужно использовать API)
        conversion_rates = {
            'RUB': 0.011,  # 1 RUB = 0.011 USD
            'USD': 1.0,    # 1 USD = 1 USD
            'EUR': 1.09,   # 1 EUR = 1.09 USD
            'AED': 0.27,   # 1 AED = 0.27 USD
            'IDR': 0.000065 # 1 IDR = 0.000065 USD
        }
        
        if currency in conversion_rates:
            return amount * conversion_rates[currency]
        else:
            return amount  # Если валюта неизвестна, возвращаем как есть

    def update_total_balance_usd(self):
        """Обновляем общий баланс в долларах"""
        # Сохраняем предыдущий баланс
        if 'total_balance_usd' in self.data:
            self.data['previous_total_balance_usd'] = self.data['total_balance_usd']
        
        total_usd = 0
        for account in self.data['accounts'].values():
            total_usd += account['balance_usd']
        
        self.data['total_balance_usd'] = round(total_usd, 2)
        self.data['last_updated'] = datetime.now().isoformat()

    def get_accounts_summary(self):
        """Получаем сводку по всем счетам"""
        # Рассчитываем изменение общего баланса
        total_change = 0
        if self.data.get('previous_total_balance_usd'):
            total_change = self.data['total_balance_usd'] - self.data['previous_total_balance_usd']
        
        return {
            'accounts': self.data['accounts'],
            'total_balance_usd': self.data['total_balance_usd'],
            'total_balance_change': round(total_change, 2),
            'last_updated': self.data['last_updated'],
            'total_count': len(self.data['accounts'])
        }

    def get_account_history(self, account_id, limit=20):
        """Получаем историю операций по счету"""
        if account_id in self.data['accounts']:
            account = self.data['accounts'][account_id]
            return {
                'account': account,
                'transactions': account['transactions'][-limit:]
            }
        return None

# Создаем экземпляр приложения
finance_tracker = FinanceTracker()

@app.route('/')
def index():
    """Главная страница"""
    accounts_data = finance_tracker.get_accounts_summary()
    
    # Конвертируем данные в JSON для JavaScript
    import json
    accounts_json = json.dumps(accounts_data, ensure_ascii=False)
    
    return render_template('index.html', 
                         accounts=accounts_data['accounts'],
                         total_balance_usd=accounts_data['total_balance_usd'],
                         total_balance_change=accounts_data['total_balance_change'],
                         last_updated=accounts_data['last_updated'],
                         total_count=accounts_data['total_count'],
                         accounts_json=accounts_json)

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """API для получения сводки по счетам"""
    return jsonify(finance_tracker.get_accounts_summary())

@app.route('/api/process_image', methods=['POST'])
def process_image():
    """API для обработки изображения"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'Изображение не найдено'})
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'success': False, 'error': 'Файл не выбран'})
        
        # Читаем содержимое изображения
        image_content = image_file.read()
        
        # Обрабатываем через Google Vision
        result = finance_tracker.process_image(image_content)
        
        if result['success']:
            # Определяем, какой это счет
            account_id = finance_tracker.identify_account(
                result['main_balance'], 
                result['full_text']
            )
            
            # Обновляем баланс счета
            transaction = finance_tracker.update_account_balance(
                account_id,
                result['main_balance'], 
                source='image_upload'
            )
            
            # Получаем обновленные данные
            accounts_data = finance_tracker.get_accounts_summary()
            
            return jsonify({
                'success': True,
                'account_id': account_id,
                'transaction': transaction,
                'accounts': accounts_data
            })
        else:
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке API запроса: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/account/<account_id>/history', methods=['GET'])
def get_account_history(account_id):
    """API для получения истории по счету"""
    history = finance_tracker.get_account_history(account_id)
    if history:
        return jsonify(history)
    else:
        return jsonify({'success': False, 'error': 'Счет не найден'})

if __name__ == '__main__':
    logger.info("🚀 Запуск приложения Finance Tracker...")
    app.run(debug=True, host='0.0.0.0', port=5001) 