#!/usr/bin/env python3
"""
Telegram бот Finance Tracker с базой данных
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from google.cloud import vision
import re
from datetime import datetime

# Настройка matplotlib для работы без GUI (headless mode)
import matplotlib
matplotlib.use('Agg')  # Используем backend без GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
from matplotlib import rcParams

# Настройка matplotlib для корректной работы
rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'sans-serif']
rcParams['font.size'] = 10
rcParams['figure.figsize'] = (10, 8)
rcParams['savefig.dpi'] = 150
rcParams['savefig.bbox'] = 'tight'
rcParams['savefig.pad_inches'] = 0.1

# Импортируем модели и функции из нашего приложения
from models import create_session, Account, Transaction, SystemInfo, convert_to_usd

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FinanceTrackerBotDB:
    def __init__(self):
        """Инициализация бота"""
        # Инициализация Google Vision API
        try:
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
                self.vision_client = vision.ImageAnnotatorClient()
                print("✅ Google Vision API подключен через GOOGLE_CREDENTIALS_CONTENT!")
            else:
                print("❌ GOOGLE_CREDENTIALS_CONTENT не установлен")
                self.vision_client = None
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Vision: {e}")
            self.vision_client = None
        
        # Паттерны для всех валют (те же, что и в веб-приложении)
        self.currency_patterns = {
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

    def fix_russian_number_format(self, text, currency):
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

    def extract_balance_from_text(self, text_lines):
        """Извлекаем баланс из распознанного текста"""
        balances = []
        
        for text in text_lines:
            text_lower = text.lower()
            
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
                                    'pattern': pattern
                                })
                            except ValueError:
                                continue
        
        return balances

    def process_image_with_db(self, image_content):
        """Обрабатываем изображение и сохраняем в БД"""
        if not self.vision_client:
            return {'success': False, 'error': 'Google Vision недоступен'}
        
        try:
            image = vision.Image(content=image_content)
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if not texts:
                return {'success': False, 'error': 'Текст не найден'}
            
            full_text = texts[0].description
            text_lines = full_text.split('\n')
            
            balances = self.extract_balance_from_text(text_lines)
            
            if balances:
                for balance in balances:
                    if balance['currency'] == 'RUB':
                        corrected_number = self.fix_russian_number_format(
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
                        source='telegram',
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
            logger.error(f"❌ Ошибка при обработке изображения: {e}")
            return {
                'success': False,
                'balance': None,
                'error': str(e)
            }

    def get_accounts_summary(self):
        """Получаем сводку по всем счетам из БД"""
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
                    'last_updated': account.last_updated
                })
                total_balance_usd += account.balance_usd
            
            return {
                'accounts': accounts_data,
                'total_balance_usd': round(total_balance_usd, 2),
                'total_count': len(accounts_data)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки: {e}")
            return {'accounts': [], 'total_balance_usd': 0, 'total_count': 0}
        finally:
            session.close()

    def create_balance_chart(self):
        """Создаем график распределения по валютам"""
        try:
            accounts_data = self.get_accounts_summary()
            
            if not accounts_data['accounts']:
                return None
            
            # Создаем круговую диаграмму
            fig, ax = plt.subplots(figsize=(10, 8))
            
            labels = []
            sizes = []
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
            
            for i, account in enumerate(accounts_data['accounts']):
                labels.append(account['name'])
                sizes.append(account['balance_usd'])
            
            if not sizes or sum(sizes) == 0:
                plt.close(fig)
                return None
            
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                             colors=colors[:len(sizes)], startangle=90)
            
            # Настройка текста
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            ax.set_title('Распределение активов по валютам', fontsize=16, fontweight='bold', pad=20)
            
            # Добавляем общий баланс
            total_usd = accounts_data['total_balance_usd']
            ax.text(0, -1.2, f'Общий баланс: ${total_usd:,.2f}', 
                   ha='center', fontsize=14, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7))
            
            plt.tight_layout()
            
            # Сохраняем в байты
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            
            return img_buffer
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания графика: {e}")
            try:
                plt.close('all')
            except:
                pass
            return None

    def create_total_balance_history_chart(self):
        """Создаем график общей динамики всех счетов в USD"""
        try:
            session = create_session()
            
            # Получаем все транзакции, отсортированные по времени
            transactions = session.query(Transaction).order_by(Transaction.timestamp).all()
            
            if not transactions:
                session.close()
                return None
            
            # Группируем по дате и суммируем
            from collections import defaultdict
            daily_totals = defaultdict(float)
            
            for transaction in transactions:
                date = transaction.timestamp.date()
                # Получаем аккаунт для конвертации в USD
                account = session.query(Account).filter_by(id=transaction.account_id).first()
                if account:
                    # Используем текущий курс для конвертации
                    transaction_usd = transaction.new_balance * convert_to_usd(1, account.currency)
                    daily_totals[date] += transaction_usd
            
            if not daily_totals:
                session.close()
                return None
            
            # Сортируем даты
            dates = sorted(daily_totals.keys())
            totals = [daily_totals[date] for date in dates]
            
            # Конвертируем даты в datetime объекты
            date_objects = [datetime.combine(date, datetime.min.time()) for date in dates]
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # График общей динамики
            ax.plot(date_objects, totals, 'o-', linewidth=2, markersize=6, color='#36A2EB')
            ax.fill_between(date_objects, totals, alpha=0.3, color='#36A2EB')
            
            ax.set_title('Динамика общего баланса (все счета)', fontsize=16, fontweight='bold')
            ax.set_ylabel('Общий баланс (USD)', fontsize=12)
            ax.set_xlabel('Дата', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # Форматирование дат
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            # Добавляем текущий общий баланс
            accounts_data = self.get_accounts_summary()
            current_total = accounts_data['total_balance_usd']
            
            ax.text(0.02, 0.98, f'Текущий баланс: ${current_total:,.2f}', 
                   transform=ax.transAxes, fontsize=12, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7),
                   verticalalignment='top')
            
            plt.tight_layout()
            
            # Сохраняем в байты
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            
            session.close()
            return img_buffer
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания графика общей динамики: {e}")
            try:
                plt.close('all')
            except:
                pass
            return None

# Создаем экземпляр бота
finance_bot = FinanceTrackerBotDB()

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Получаем текущие данные из БД
    accounts_data = finance_bot.get_accounts_summary()
    
    welcome_text = "💰 **Finance Tracker Bot с базой данных**\n\n"
    
    if accounts_data['total_count'] > 0:
        welcome_text += f"💵 **Общий баланс: ${accounts_data['total_balance_usd']:,.2f}**\n\n"
        welcome_text += "🏦 **Ваши счета:**\n"
        
        for account in accounts_data['accounts']:
            welcome_text += f"• {account['name']}: {account['balance']:,.2f} {account['currency']} (≈ ${account['balance_usd']:,.2f})\n"
        
        welcome_text += "\n📱 **Отправьте скриншот** для обновления баланса!"
    else:
        welcome_text += "📭 У вас пока нет счетов.\n\n📱 **Отправьте скриншот** банковского приложения, чтобы создать первый счет!"
    
    welcome_text += "\n\n📊 **Команды:**\n"
    welcome_text += "/balance - показать график распределения\n"
    welcome_text += "/history - показать общую динамику\n"
    welcome_text += "/help - справка"
    
    keyboard = [
        [InlineKeyboardButton("📊 График распределения", callback_data="show_balance_chart")],
        [InlineKeyboardButton("📈 Общая динамика", callback_data="show_total_history")]
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

🔍 **Поддерживаемые валюты:**
• ₽ RUB (рубли), $ USD (доллары), € EUR (евро)
• AED (дирхамы), Rp IDR (рупии)

💰 **Система счетов:**
• Каждая валюта = отдельный счет
• Баланс обновляется, а не суммируется
• Все валюты конвертируются в доллары
• Данные синхронизированы с веб-приложением

📊 **Команды:**
/start - начать работу с ботом
/balance - показать график распределения
/history - показать общую динамику
/help - показать эту справку

📈 **Функции:**
• График распределения по валютам
• Общая динамика всех счетов в USD
• Автоматическое распознавание балансов
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /balance - показывает график"""
    await update.message.reply_text("🔄 Создаю график баланса...")
    
    chart_buffer = finance_bot.create_balance_chart()
    
    if chart_buffer:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=chart_buffer,
            caption="График распределения активов\n\nОтправьте скриншот для обновления баланса!",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("📭 У вас пока нет счетов.\n\nОтправьте скриншот банковского приложения, чтобы создать первый счет!")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /history"""
    await update.message.reply_text("🔄 Создаю график общей динамики...")
    
    chart_buffer = finance_bot.create_total_balance_history_chart()
    
    if chart_buffer:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=chart_buffer,
            caption="📊 Динамика общего баланса (все счета)\n\nОтправьте скриншот для обновления баланса!",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Не удалось создать график общей динамики.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    try:
        photo = update.message.photo[-1]
        processing_msg = await update.message.reply_text("🔄 Обрабатываю скриншот...")
        
        file = await context.bot.get_file(photo.file_id)
        image_content = await file.download_as_bytearray()
        image_bytes = bytes(image_content)
        
        result = finance_bot.process_image_with_db(image_bytes)
        
        if result['success']:
            account = result['account']
            
            success_text = f"✅ **Баланс обновлен!**\n\n"
            success_text += f"🏦 **Счет:** {account['name']}\n"
            success_text += f"💰 **Новый баланс:** {account['balance']:,.2f} {account['currency']}\n"
            success_text += f"💵 **В долларах:** ${account['balance_usd']:,.2f}\n"
            
            # Обновляем общий баланс
            accounts_data = finance_bot.get_accounts_summary()
            success_text += f"\n💰 **Общий баланс:** ${accounts_data['total_balance_usd']:,.2f}"
            
            keyboard = [
                [InlineKeyboardButton("💰 Показать график", callback_data="show_balance_chart")],
                [InlineKeyboardButton("📊 Общая динамика", callback_data="show_total_history")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        else:
            error_text = f"❌ **Не удалось распознать баланс**\n\n"
            error_text += f"🔍 **Распознанный текст:**\n"
            
            if result.get('text_lines'):
                for i, line in enumerate(result['text_lines'][:5]):
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
    
    if query.data == "show_balance_chart":
        await query.edit_message_text("🔄 Создаю график баланса...")
        
        chart_buffer = finance_bot.create_balance_chart()
        
        if chart_buffer:
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=chart_buffer,
                caption="💰 **График распределения активов**\n\nОтправьте скриншот для обновления баланса!",
                reply_markup=reply_markup
            )
            await query.message.delete()
        else:
            await query.edit_message_text("📭 У вас пока нет счетов.\n\nОтправьте скриншот банковского приложения, чтобы создать первый счет!")
    
    elif query.data == "show_total_history":
        await query.edit_message_text("🔄 Создаю график общей динамики...")
        
        chart_buffer = finance_bot.create_total_balance_history_chart()
        
        if chart_buffer:
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=chart_buffer,
                caption="📊 **Динамика общего баланса (все счета)**\n\nОтправьте скриншот для обновления баланса!",
                reply_markup=reply_markup
            )
            await query.message.delete()
        else:
            await query.edit_message_text("❌ Не удалось создать график общей динамики.")
    
    elif query.data == "back_to_main":
        # Получаем текущие данные для обновления главного меню
        accounts_data = finance_bot.get_accounts_summary()
        
        welcome_text = "💰 **Finance Tracker Bot с базой данных**\n\n"
        
        if accounts_data['total_count'] > 0:
            welcome_text += f"💵 **Общий баланс: ${accounts_data['total_balance_usd']:,.2f}**\n\n"
            welcome_text += "🏦 **Ваши счета:**\n"
            
            for account in accounts_data['accounts']:
                welcome_text += f"• {account['name']}: {account['balance']:,.2f} {account['currency']} (≈ ${account['balance_usd']:,.2f})\n"
            
            welcome_text += "\n📱 **Отправьте скриншот** для обновления баланса!"
        else:
            welcome_text += "📭 У вас пока нет счетов.\n\n📱 **Отправьте скриншот** банковского приложения, чтобы создать первый счет!"
        
        welcome_text += "\n\n📊 **Команды:**\n"
        welcome_text += "/balance - показать график распределения\n"
        welcome_text += "/history - показать общую динамику\n"
        welcome_text += "/help - справка"
        
        # Отправляем новое сообщение вместо редактирования
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=welcome_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 График распределения", callback_data="show_balance_chart")],
                [InlineKeyboardButton("📈 Общая динамика", callback_data="show_total_history")]
            ]),
            parse_mode='Markdown'
        )
        
        # Удаляем старое сообщение
        try:
            await query.message.delete()
        except:
            pass

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"❌ Ошибка: {context.error}")
    
    try:
        if update and hasattr(update, 'effective_message') and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка при обработке запроса. Попробуйте позже."
            )
        elif update and hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка при обработке запроса")
    except Exception as e:
        logger.error(f"❌ Ошибка в error_handler: {e}")

def main():
    """Основная функция"""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("❌ Не установлен TELEGRAM_BOT_TOKEN")
        print("❌ Установите переменную окружения TELEGRAM_BOT_TOKEN")
        print("Пример: export TELEGRAM_BOT_TOKEN='your_bot_token_here'")
        return
    
    application = Application.builder().token(bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🚀 Запуск Telegram бота Finance Tracker с базой данных...")
    application.run_polling()

if __name__ == '__main__':
    main() 