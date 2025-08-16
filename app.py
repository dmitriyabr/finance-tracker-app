#!/usr/bin/env python3
"""
Finance Tracker - Flask приложение с базой данных
"""

from flask import Flask, render_template, request, jsonify
from models import force_update_exchange_rates, get_current_exchange_rates
from core import finance_tracker_core
from datetime import datetime
import os

app = Flask(__name__)

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
        
        # Обрабатываем изображение
        result = finance_tracker_core.process_image(image_content)
        
        if result['success']:
            # Обновляем баланс в базе данных
            transaction_result = finance_tracker_core.update_account_balance_from_image(
                result['main_balance'], 
                result['full_text'],
                source='web'
            )
            
            if transaction_result['success']:
                return jsonify({
                    'success': True,
                    'main_balance': result['main_balance'],
                    'all_balances': result['all_balances'],
                    'account': transaction_result['account'],
                    'text_lines': result['text_lines'],
                    'full_text': result['full_text']
                })
            else:
                return jsonify({'success': False, 'error': transaction_result['error']})
        else:
            return jsonify(result)
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/accounts')
def api_accounts():
    """API для получения списка счетов"""
    return jsonify(finance_tracker_core.get_accounts_for_api())

@app.route('/api/vision_status')
def api_vision_status():
    """API для проверки статуса Google Vision"""
    return jsonify({
        'vision_available': finance_tracker_core.vision_client is not None,
        'status': 'OK' if finance_tracker_core.vision_client else 'UNAVAILABLE'
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

@app.route('/api/balance_history')
def api_balance_history():
    """API для получения истории общего баланса"""
    return jsonify(finance_tracker_core.get_balance_history())

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