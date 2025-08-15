import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from google.cloud import vision
import json
from datetime import datetime
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FinanceTrackerBot:
    def __init__(self):
        """Инициализация бота"""
        self.data_file = 'finance_data.json'
        self.load_data()
        
        # Инициализация Google Vision API
        try:
            # Прямое указание пути к credentials
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
                whole_part = whole_part.replace(',', '')  # Убираем все запятые
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

    def update_account_balance(self, account_id, balance_data, source='telegram'):
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
        total_usd = 0
        for account in self.data['accounts'].values():
            total_usd += account['balance_usd']
        
        self.data['total_balance_usd'] = round(total_usd, 2)
        self.data['last_updated'] = datetime.now().isoformat()

    def get_accounts_summary(self, limit=10):
        """Получаем сводку по всем счетам"""
        return {
            'accounts': self.data['accounts'],
            'total_balance_usd': self.data['total_balance_usd'],
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

# Создаем экземпляр трекера
finance_tracker = FinanceTrackerBot()

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """
💰 **Finance Tracker Bot**

Отправьте скриншот банковского приложения, и я автоматически обновлю баланс счета!

📱 **Как работает:**
1. Сделайте скриншот главного экрана банковского приложения
2. Отправьте его в этот чат
3. Я автоматически определю счет и обновлю баланс
4. Все валюты конвертируются в доллары

🔍 **Поддерживаемые валюты:**
• ₽ RUB (рубли)
• $ USD (доллары)
• € EUR (евро)
• AED (дирхамы)
• Rp IDR (рупии)

📊 **Команды:**
/balance - показать текущий баланс
/history - показать историю
/help - показать эту справку
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Показать баланс", callback_data="show_balance")],
        [InlineKeyboardButton("📊 История", callback_data="show_history")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
❓ **Помощь по использованию бота**

📱 **Отправка скриншотов:**
• Отправьте скриншот главного экрана банковского приложения
• Убедитесь, что баланс четко виден на изображении
• Поддерживаются форматы: JPG, PNG, JPEG

🔍 **Распознавание:**
• Бот автоматически найдет все суммы на скриншоте
• Выберет основной баланс (самую большую сумму)
• Определит, какой это счет по валюте
• Обновит баланс (не суммирует!)

💰 **Система счетов:**
• Каждая валюта = отдельный счет
• Баланс обновляется, а не суммируется
• Все валюты конвертируются в доллары
• Сохраняется история изменений

📊 **Команды:**
/start - начать работу с ботом
/balance - показать текущий баланс
/history - показать историю операций
/help - показать эту справку

💡 **Советы:**
• Делайте качественные скриншоты
• Убедитесь, что текст не размыт
• Баланс должен быть хорошо виден
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /balance"""
    accounts_data = finance_tracker.get_accounts_summary()
    
    if accounts_data['total_count'] == 0:
        await update.message.reply_text("📭 У вас пока нет счетов.\n\nОтправьте скриншот банковского приложения, чтобы создать первый счет!")
        return
    
    # Форматируем общий баланс
    total_balance_usd = accounts_data['total_balance_usd']
    
    # Показываем все счета
    balance_text = f"💰 **Общий баланс: ${total_balance_usd:,.2f}**\n\n"
    balance_text += "🏦 **Ваши счета:**\n"
    
    for account_id, account in accounts_data['accounts'].items():
        currency_symbol = get_currency_symbol(account['currency'])
        date = account['last_updated'][:10] if account['last_updated'] else 'Нет данных'
        
        balance_text += f"• **{account['name']}**\n"
        balance_text += f"  {currency_symbol}{account['balance']:,.2f} ({account['currency']})\n"
        balance_text += f"  ≈ ${account['balance_usd']:,.2f}\n"
        balance_text += f"  📅 {date}\n\n"
    
    balance_text += f"📈 **Всего счетов:** {accounts_data['total_count']}"
    
    keyboard = [
        [InlineKeyboardButton("📊 Полная история", callback_data="show_history")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(balance_text, reply_markup=reply_markup, parse_mode='Markdown')

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /history"""
    accounts_data = finance_tracker.get_accounts_summary()
    
    if accounts_data['total_count'] == 0:
        await update.message.reply_text("📭 У вас пока нет счетов.\n\nОтправьте скриншот банковского приложения, чтобы создать первый счет!")
        return
    
    history_text = f"📊 **История операций**\n\n"
    
    # Показываем историю по всем счетам
    for account_id, account in accounts_data['accounts'].items():
        history_text += f"🏦 **{account['name']}**\n"
        history_text += f"Текущий баланс: {get_currency_symbol(account['currency'])}{account['balance']:,.2f} ({account['currency']})\n"
        history_text += f"В долларах: ${account['balance_usd']:,.2f}\n\n"
        
        if account['transactions']:
            history_text += "📈 **Последние изменения:**\n"
            # Показываем последние 5 транзакций
            for transaction in account['transactions'][-5:]:
                date = transaction['timestamp'][:19].replace('T', ' ')
                change = transaction['change']
                change_text = f"+{change:,.2f}" if change > 0 else f"{change:,.2f}"
                change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                
                history_text += f"{change_emoji} {change_text} ({date})\n"
        else:
            history_text += "📝 История изменений пуста\n"
        
        history_text += "\n" + "─" * 30 + "\n\n"
    
    # Разбиваем на части, если текст слишком длинный
    if len(history_text) > 4000:
        parts = [history_text[i:i+4000] for i in range(0, len(history_text), 4000)]
        for i, part in enumerate(parts):
            await update.message.reply_text(f"📊 **История (часть {i+1}/{len(parts)})**\n\n{part}", parse_mode='Markdown')
    else:
        await update.message.reply_text(history_text, parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    try:
        # Получаем фото с наилучшим качеством
        photo = update.message.photo[-1]
        
        # Отправляем сообщение о начале обработки
        processing_msg = await update.message.reply_text("🔄 Обрабатываю скриншот...")
        
        # Скачиваем фото
        file = await context.bot.get_file(photo.file_id)
        image_content = await file.download_as_bytearray()
        
        # Конвертируем bytearray в bytes для Google Vision API
        image_bytes = bytes(image_content)
        
        # Обрабатываем через Google Vision
        result = finance_tracker.process_image(image_bytes)
        
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
                source='telegram'
            )
            
            # Формируем ответ
            main_balance = result['main_balance']
            currency_symbol = get_currency_symbol(main_balance['currency'])
            account = finance_tracker.data['accounts'][account_id]
            
            success_text = f"✅ **Баланс обновлен!**\n\n"
            success_text += f"🏦 **Счет:** {account['name']}\n"
            success_text += f"💰 **Новый баланс:** {currency_symbol}{main_balance['value']} ({main_balance['currency']})\n"
            success_text += f"💵 **В долларах:** ${account['balance_usd']:,.2f}\n"
            
            if transaction['change'] != 0:
                change_emoji = "📈" if transaction['change'] > 0 else "📉"
                change_text = f"+{transaction['change']:,.2f}" if transaction['change'] > 0 else f"{transaction['change']:,.2f}"
                success_text += f"{change_emoji} **Изменение:** {change_text} {main_balance['currency']}\n"
            
            if len(result['all_balances']) > 1:
                success_text += f"\n🔍 **Все найденные суммы:**\n"
                for balance in result['all_balances']:
                    symbol = get_currency_symbol(balance['currency'])
                    success_text += f"• {symbol}{balance['value']} ({balance['currency']})\n"
            
            if main_balance['original_text']:
                success_text += f"\n📝 **Источник:** \"{main_balance['original_text'][:100]}{'...' if len(main_balance['original_text']) > 100 else ''}\""
            
            # Обновляем общий баланс
            accounts_data = finance_tracker.get_accounts_summary()
            success_text += f"\n\n💰 **Общий баланс:** ${accounts_data['total_balance_usd']:,.2f}"
            
            keyboard = [
                [InlineKeyboardButton("💰 Показать баланс", callback_data="show_balance")],
                [InlineKeyboardButton("📊 История", callback_data="show_history")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        else:
            error_text = f"❌ **Не удалось распознать баланс**\n\n"
            error_text += f"🔍 **Распознанный текст:**\n"
            
            if result.get('text_lines'):
                # Показываем первые 10 строк распознанного текста
                for i, line in enumerate(result['text_lines'][:10]):
                    if line.strip():
                        error_text += f"{i+1}. {line}\n"
            
            error_text += "\n💡 **Советы:**\n"
            error_text += "• Убедитесь, что баланс четко виден\n"
            error_text += "• Попробуйте другой ракурс\n"
            error_text += "• Проверьте качество изображения"
            
            await processing_msg.edit_text(error_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке фото: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка при обработке изображения: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    # Создаем фейковый update для команд
    fake_update = type('Update', (), {
        'message': query.message,
        'effective_message': query.message
    })()
    
    if query.data == "show_balance":
        await balance_command(fake_update, context)
    elif query.data == "show_history":
        await history_command(fake_update, context)
    elif query.data == "help":
        await help_command(fake_update, context)
    elif query.data == "refresh_balance":
        await balance_command(fake_update, context)

def get_currency_symbol(currency):
    """Получение символа валюты"""
    symbols = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'AED': 'AED',
        'IDR': 'Rp'
    }
    return symbols.get(currency, currency)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"❌ Ошибка: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке запроса. Попробуйте позже."
        )

def main():
    """Основная функция"""
    # Получаем токен бота из переменной окружения
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("❌ Не установлен TELEGRAM_BOT_TOKEN")
        print("❌ Установите переменную окружения TELEGRAM_BOT_TOKEN")
        print("Пример: export TELEGRAM_BOT_TOKEN='your_bot_token_here'")
        return
    
    # Создаем приложение
    application = Application.builder().token(bot_token).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("🚀 Запуск Telegram бота Finance Tracker...")
    application.run_polling()

if __name__ == '__main__':
    main() 