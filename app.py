#!/usr/bin/env python3
"""
Finance Tracker - Flask приложение с базой данных
"""

from flask import Flask, render_template, request, jsonify
from models import create_session, Account, Transaction, SystemInfo, force_update_exchange_rates, get_current_exchange_rates, convert_to_usd
from datetime import datetime
import os
import re

app = Flask(__name__)

# Инициализация Google Vision API
vision_client = None
try:
    from google.cloud import vision
    
    # Сначала пробуем создать credentials из переменной GOOGLE_CREDENTIALS_CONTENT
    credentials_content = os.environ.get('GOOGLE_CREDENTIALS_CONTENT')
    if credentials_content:
        print("🔧 Создаю credentials из GOOGLE_CREDENTIALS_CONTENT...")
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(credentials_content)
            temp_credentials_path = f.name
            print(f"📝 Создан временный файл: {temp_credentials_path}")
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
        vision_client = vision.ImageAnnotatorClient()
        print("✅ Google Vision API подключен через GOOGLE_CREDENTIALS_CONTENT!")
    else:
        print("❌ GOOGLE_CREDENTIALS_CONTENT не установлен")
        vision_client = None
        
except Exception as e:
    print(f"❌ Ошибка подключения к Google Vision: {e}")
    vision_client = None

# Паттерны для всех валют
currency_patterns = {
    'RUB': [
        r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*₽',
        r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*Р',
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
        r'€(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)'
    ],
    'AED': [
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*AED',
        r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*дирхам',
        r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*د\.إ'
    ],
    'IDR': [
        r'Rp\s*(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)\s*Rp',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)\s*рупий'
    ]
}

def fix_russian_number_format(text, currency):
    """Исправляем формат российских чисел"""
    if currency == 'RUB':
        russian_pattern = r'(\d{1,3}(?:\s\d{3})*),(\d{2})'
        match = re.search(russian_pattern, text)
        if match:
            whole_part = match.group(1).replace(' ', '').replace(',', '')
            decimal_part = match.group(2)
            correct_number = f"{whole_part}.{decimal_part}"
            try:
                float(correct_number)
                return correct_number
            except ValueError:
                pass
    return None

def extract_balance_from_text(text_lines):
    """Извлекаем баланс из распознанного текста"""
    balances = []
    
    for text in text_lines:
        text_lower = text.lower()
        
        for currency, patterns in currency_patterns.items():
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
                                'pattern': pattern
                            })
                        except ValueError:
                            continue
    
    return balances

def process_image_with_db(image_content):
    """Обрабатываем изображение и сохраняем в БД"""
    if not vision_client:
        return {'success': False, 'error': 'Google Vision недоступен'}
    
    try:
        image = vision.Image(content=image_content)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations
        
        if not texts:
            return {'success': False, 'error': 'Текст не найден'}
        
        full_text = texts[0].description
        text_lines = full_text.split('\n')
        
        balances = extract_balance_from_text(text_lines)
        
        if balances:
            for balance in balances:
                if balance['currency'] == 'RUB':
                    corrected_number = fix_russian_number_format(
                        balance['original_text'], 
                        balance['currency']
                    )
                    if corrected_number:
                        balance['value'] = corrected_number
                        balance['corrected'] = True
            
            main_balance = max(balances, key=lambda x: float(x['value']))
            
            # Сохраняем в базу данных
            session = create_session()
            try:
                # Ищем существующий аккаунт по валюте
                account = session.query(Account).filter_by(
                    currency=main_balance['currency']
                ).first()
                
                if not account:
                    # Создаем новый аккаунт
                    account_names = {
                        'RUB': 'Российский счет',
                        'USD': 'Долларовый счет',
                        'EUR': 'Евро счет',
                        'AED': 'Дирхамовый счет',
                        'IDR': 'Рупиевый счет'
                    }
                    
                    account_name = account_names.get(main_balance['currency'], f'Счет в {main_balance["currency"]}')
                    
                    account = Account(
                        name=account_name,
                        currency=main_balance['currency'],
                        balance=0,
                        balance_usd=0,
                        last_updated=datetime.utcnow()
                    )
                    session.add(account)
                    session.flush()  # Получаем ID
                
                # Обновляем баланс
                old_balance = account.balance
                account.balance = float(main_balance['value'])
                account.balance_usd = convert_to_usd(account.balance, account.currency)
                account.last_updated = datetime.utcnow()
                
                # Создаем транзакцию
                transaction = Transaction(
                    account_id=account.id,
                    timestamp=datetime.utcnow(),
                    old_balance=old_balance,
                    new_balance=account.balance,
                    change=account.balance - old_balance,
                    source='web',
                    original_text=main_balance.get('original_text', '')
                )
                session.add(transaction)
                
                session.commit()
                
                return {
                    'success': True,
                    'main_balance': main_balance,
                    'all_balances': balances,
                    'account': {
                        'id': account.id,
                        'name': account.name,
                        'currency': account.currency,
                        'balance': account.balance,
                        'balance_usd': account.balance_usd
                    },
                    'text_lines': text_lines,
                    'full_text': full_text
                }
                
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
        else:
            return {
                'success': False,
                'balance': None,
                'text_lines': text_lines,
                'full_text': full_text
            }
            
    except Exception as e:
        print(f"❌ Ошибка при обработке изображения: {e}")
        return {
            'success': False,
            'balance': None,
            'error': str(e)
        }

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/api/process_image', methods=['POST'])
def api_process_image():
    """API для обработки изображения"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не найден'})
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'})
    
    try:
        image_content = file.read()
        result = process_image_with_db(image_content)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/accounts')
def api_accounts():
    """API для получения списка счетов"""
    try:
        session = create_session()
        accounts = session.query(Account).all()
        
        accounts_data = []
        total_balance_usd = 0
        
        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'name': account.name,
                'currency': account.currency,
                'balance': account.balance,
                'balance_usd': account.balance_usd,
                'last_updated': account.last_updated.isoformat() if account.last_updated else None
            })
            total_balance_usd += account.balance_usd
        
        return jsonify({
            'success': True,
            'accounts': accounts_data,
            'total_balance_usd': round(total_balance_usd, 2)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        session.close()

@app.route('/api/vision_status')
def api_vision_status():
    """API для проверки статуса Google Vision"""
    return jsonify({
        'vision_available': vision_client is not None,
        'status': 'OK' if vision_client else 'UNAVAILABLE'
    })

@app.route('/api/exchange_rates')
def api_exchange_rates():
    """API для получения текущих курсов валют"""
    try:
        rates = get_current_exchange_rates()
        return jsonify({
            'success': True,
            'rates': rates
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/force_update_rates')
def api_force_update_rates():
    """API для принудительного обновления курсов валют"""
    try:
        force_update_exchange_rates()
        return jsonify({
            'success': True,
            'message': 'Курсы валют успешно обновлены'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'OK', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    # Создаем таблицы при запуске
    try:
        from models import create_tables
        create_tables()
        print("✅ Таблицы базы данных созданы")
    except Exception as e:
        print(f"⚠️ Не удалось создать таблицы: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 