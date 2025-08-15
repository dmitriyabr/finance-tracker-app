#!/usr/bin/env python3
"""
Telegram бот Finance Tracker с графиками
"""

import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from google.cloud import vision
import json
from datetime import datetime
import re

# Импортируем модели и функции из нашего приложения
from models import create_session, Account, Transaction, SystemInfo, convert_to_usd

# Настройка matplotlib для работы без GUI (headless mode)
import matplotlib
matplotlib.use('Agg')  # Используем backend без GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
from matplotlib import rcParams

# Настройка matplotlib для корректной работы
rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'sans-serif']
rcParams['font.size'] = 10
rcParams['figure.figsize'] = (10, 8)
rcParams['savefig.dpi'] = 150
rcParams['savefig.bbox'] = 'tight'
rcParams['savefig.pad_inches'] = 0.1

# Настройка matplotlib для русского языка
rcParams['font.family'] = 'DejaVu Sans'
rcParams['font.size'] = 10

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FinanceTrackerBotWithGraphs:
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
                # Fallback: проверяем GOOGLE_APPLICATION_CREDENTIALS
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
        
        # Паттерны для всех валют
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
        
        self.balance_keywords = [
            'balance', 'total', 'available', 'current', 'main', 'cash',
            'баланс', 'доступно', 'основной', 'текущий', 'общий', 'наличные'
        ]

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

    def process_image(self, image_content):
        """Обрабатываем изображение через Google Vision"""
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
            
            if balances:
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

    def get_accounts_summary(self):
        """Получает сводку по всем счетам"""
        try:
            session = create_session()
            accounts = session.query(Account).all()
            
            total_balance_usd = sum(account.balance_usd for account in accounts)
            
            # Получаем изменение общего баланса (пока упрощенно)
            total_balance_change = 0  # В будущем можно добавить логику расчета изменений
            
            return {
                'total_balance_usd': total_balance_usd,
                'total_balance_change': total_balance_change,
                'accounts_count': len(accounts)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки по счетам: {e}")
            return {
                'total_balance_usd': 0,
                'total_balance_change': 0,
                'accounts_count': 0
            }
        finally:
            session.close()

    def get_accounts_details(self):
        """Получает детальную информацию по всем счетам"""
        try:
            session = create_session()
            accounts = session.query(Account).all()
            
            accounts_details = {}
            for account in accounts:
                accounts_details[account.id] = {
                    'name': account.name,
                    'currency': account.currency,
                    'balance': account.balance,
                    'balance_usd': account.balance_usd,
                    'last_updated': account.last_updated.isoformat() if account.last_updated else None
                }
            
            return accounts_details
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения деталей по счетам: {e}")
            return {}
        finally:
            session.close()

    def create_balance_chart(self):
        """Создаем график распределения по валютам"""
        try:
            session = create_session()
            accounts = session.query(Account).all()
            
            if not accounts:
                session.close()
                return None
            
            # Создаем круговую диаграмму
            fig, ax = plt.subplots(figsize=(10, 8))
            
            labels = []
            sizes = []
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
            
            for i, account in enumerate(accounts):
                labels.append(account.name)
                sizes.append(account.balance_usd)
            
            if not sizes or sum(sizes) == 0:
                plt.close(fig)
                session.close()
                return None
            
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                             colors=colors[:len(sizes)], startangle=90)
            
            # Настройка текста
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            ax.set_title('Распределение активов по валютам', fontsize=16, fontweight='bold', pad=20)
            
            # Добавляем общий баланс
            total_usd = sum(account.balance_usd for account in accounts)
            
            ax.text(0, -1.2, f'Общий баланс: ${total_usd:,.2f}', 
                   ha='center', fontsize=14, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7))
            
            plt.tight_layout()
            
            # Сохраняем в байты
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            session.close()
            
            return img_buffer
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания графика: {e}")
            # Закрываем фигуру в случае ошибки
            try:
                plt.close('all')
            except:
                pass
            if 'session' in locals():
                session.close()
            return None

    def create_account_history_chart(self, account_id):
        """Создаем график истории счета"""
        try:
            # Получаем данные из базы данных
            session = create_session()
            account = session.query(Account).filter_by(id=account_id).first()
            
            if not account:
                session.close()
                return None
            
            # Получаем транзакции для этого счета
            transactions = session.query(Transaction).filter_by(account_id=account_id).order_by(Transaction.timestamp).all()
            
            if not transactions:
                session.close()
                return None
            
            # Сортируем транзакции по времени
            sorted_transactions = sorted(transactions, key=lambda x: x.timestamp)
            
            dates = [t.timestamp for t in sorted_transactions]
            balances = [t.new_balance for t in sorted_transactions]
            changes = [t.change for t in sorted_transactions]
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # График баланса
            ax1.plot(dates, balances, 'o-', linewidth=2, markersize=6, color='#36A2EB')
            ax1.fill_between(dates, balances, alpha=0.3, color='#36A2EB')
            ax1.set_title(f'Динамика баланса: {account.name}', fontsize=14, fontweight='bold')
            ax1.set_ylabel(f'Баланс ({account.currency})', fontsize=12)
            ax1.grid(True, alpha=0.3)
            
            # Форматирование дат
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
            
            # График изменений
            colors = ['green' if c > 0 else 'red' if c < 0 else 'gray' for c in changes]
            ax2.bar(dates, changes, color=colors, alpha=0.7)
            ax2.set_title('Изменения баланса', fontsize=14, fontweight='bold')
            ax2.set_ylabel(f'Изменение ({account.currency})', fontsize=12)
            ax2.grid(True, alpha=0.3)
            
            # Форматирование дат
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax2.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # Сохраняем в байты
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            
            session.close()
            return img_buffer
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания графика истории: {e}")
            # Закрываем фигуру в случае ошибки
            try:
                plt.close('all')
            except:
                pass
            if 'session' in locals():
                session.close()
            return None

    def create_total_balance_history_chart(self):
        """Создаем график общей динамики всех счетов в USD"""
        try:
            session = create_session()
            accounts = session.query(Account).all()
            
            if not accounts:
                session.close()
                return None
            
            # Собираем все транзакции по всем счетам
            all_transactions = []
            for account in accounts:
                transactions = session.query(Transaction).filter_by(account_id=account.id).order_by(Transaction.timestamp).all()
                for transaction in transactions:
                    # Конвертируем в USD
                    transaction_usd = {
                        'timestamp': transaction.timestamp,
                        'balance_usd': transaction.new_balance * convert_to_usd(1, account.currency),
                        'account_name': account.name,
                        'currency': account.currency
                    }
                    all_transactions.append(transaction_usd)
            
            session.close()
            
            if not all_transactions:
                return None
            
            # Сортируем по времени
            sorted_transactions = sorted(all_transactions, key=lambda x: x['timestamp'])
            
            # Группируем по дате и суммируем
            from collections import defaultdict
            daily_totals = defaultdict(float)
            
            for transaction in sorted_transactions:
                date = transaction['timestamp'].strftime('%Y-%m-%d')  # Берем только дату
                daily_totals[date] += transaction['balance_usd']
            
            # Сортируем даты
            dates = sorted(daily_totals.keys())
            totals = [daily_totals[date] for date in dates]
            
            # Конвертируем строки дат в datetime объекты
            from datetime import datetime
            date_objects = [datetime.strptime(date, '%Y-%m-%d') for date in dates]
            
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
            
            # Получаем текущий общий баланс
            current_total = sum(account.balance_usd for account in accounts)
            
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
            
            return img_buffer
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания графика общей динамики: {e}")
            # Закрываем фигуру в случае ошибки
            try:
                plt.close('all')
            except:
                pass
            if 'session' in locals():
                session.close()
            return None

    def update_account_balance_from_image(self, balance_data, image_text, source='telegram'):
        """Обновляем баланс счета в БД на основе распознанного изображения"""
        try:
            session = create_session()
            
            # Ищем существующий аккаунт по валюте
            account = session.query(Account).filter_by(
                currency=balance_data['currency']
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
                
                account_name = account_names.get(balance_data['currency'], f'Счет в {balance_data["currency"]}')
                
                account = Account(
                    name=account_name,
                    currency=balance_data['currency'],
                    balance=0,
                    balance_usd=0,
                    last_updated=datetime.utcnow()
                )
                session.add(account)
                session.flush()  # Получаем ID
            
            # Обновляем баланс
            old_balance = account.balance
            account.balance = float(balance_data['value'])
            account.balance_usd = convert_to_usd(account.balance, account.currency)
            account.last_updated = datetime.utcnow()
            
            # Создаем транзакцию
            transaction = Transaction(
                account_id=account.id,
                timestamp=datetime.utcnow(),
                old_balance=old_balance,
                new_balance=account.balance,
                change=account.balance - old_balance,
                source=source,
                original_text=image_text # Используем распознанный текст
            )
            session.add(transaction)
            
            # Обновляем общий баланс в системной информации
            system_info = session.query(SystemInfo).filter_by(key='total_balance_usd').first()
            if system_info:
                system_info.value = str(account.balance_usd)
                system_info.updated_at = datetime.utcnow()
            else:
                system_info = SystemInfo(
                    key='total_balance_usd',
                    value=str(account.balance_usd),
                    updated_at=datetime.utcnow()
                )
                session.add(system_info)
            
            session.commit()
            
            logger.info(f"✅ Обновлен баланс счета {account.id}: {account.balance} {account.currency} (${account.balance_usd:.2f})")
            
            return {
                'success': True,
                'account': {
                    'id': account.id,
                    'name': account.name,
                    'currency': account.currency,
                    'balance': account.balance,
                    'balance_usd': account.balance_usd,
                    'last_updated': account.last_updated.isoformat()
                },
                'change': account.balance - old_balance
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления баланса из изображения: {e}")
            session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            session.close()

# Создаем экземпляр трекера
finance_tracker = FinanceTrackerBotWithGraphs()

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Получаем текущие данные
    accounts_data = finance_tracker.get_accounts_summary()
    accounts_details = finance_tracker.get_accounts_details()
    
    welcome_text = "💰 **Finance Tracker Bot с графиками**\n\n"
    
    if accounts_data['accounts_count'] > 0:
        welcome_text += f"💵 **Общий баланс: ${accounts_data['total_balance_usd']:,.2f}**\n\n"
        welcome_text += "🏦 **Ваши счета:**\n"
        
        for account_id, account in accounts_details.items():
            welcome_text += f"• {account['name']}: {account['balance']:,.2f} {account['currency']} (≈ ${account['balance_usd']:,.2f})\n"
        
        welcome_text += "\n📱 **Отправьте скриншот** для обновления баланса!"
    else:
        welcome_text += "📭 У вас пока нет счетов.\n\n📱 **Отправьте скриншот** банковского приложения, чтобы создать первый счет!"
    
    welcome_text += "\n\n📊 **Команды:**\n"
    welcome_text += "/balance - показать график распределения\n"
    welcome_text += "/history - показать историю счетов\n"
    welcome_text += "/help - справка"
    
    keyboard = [
        [InlineKeyboardButton("📊 История счетов", callback_data="show_history")],
        [InlineKeyboardButton("📈 График распределения", callback_data="show_balance_chart")],
        [InlineKeyboardButton("📊 Общая динамика", callback_data="show_total_history")]
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

📊 **Команды:**
/start - начать работу с ботом
/balance - показать график распределения
/history - показать историю счетов
/help - показать эту справку

📈 **Функции:**
• График распределения по валютам
• История отдельных счетов
• Общая динамика всех счетов в USD
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /balance - показывает график"""
    await update.message.reply_text("🔄 Создаю график баланса...")
    
    chart_buffer = finance_tracker.create_balance_chart()
    
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
    accounts_data = finance_tracker.get_accounts_summary()
    
    if accounts_data['accounts_count'] == 0:
        await update.message.reply_text("📭 У вас пока нет счетов.\n\nОтправьте скриншот банковского приложения, чтобы создать первый счет!")
        return
    
    # Получаем детали по счетам
    accounts_details = finance_tracker.get_accounts_details()
    
    # Создаем список счетов для выбора
    keyboard = []
    for account_id, account in accounts_details.items():
        keyboard.append([InlineKeyboardButton(
            f"📊 {account['name']} ({account['currency']})", 
            callback_data=f"history_{account_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 **Выберите счет для просмотра истории:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    try:
        photo = update.message.photo[-1]
        processing_msg = await update.message.reply_text("🔄 Обрабатываю скриншот...")
        
        file = await context.bot.get_file(photo.file_id)
        image_content = await file.download_as_bytearray()
        image_bytes = bytes(image_content)
        
        result = finance_tracker.process_image(image_bytes)
        
        if result['success']:
            # Обновляем баланс в базе данных
            transaction_result = finance_tracker.update_account_balance_from_image(
                result['main_balance'], 
                result['full_text'],
                source='telegram'
            )
            
            if transaction_result['success']:
                main_balance = result['main_balance']
                account = transaction_result['account']
                
                success_text = f"✅ **Баланс обновлен!**\n\n"
                success_text += f"🏦 **Счет:** {account['name']}\n"
                success_text += f"💰 **Новый баланс:** {main_balance['value']} ({main_balance['currency']})\n"
                success_text += f"💵 **В долларах:** ${account['balance_usd']:,.2f}\n"
                
                if transaction_result['change'] != 0:
                    change_emoji = "📈" if transaction_result['change'] > 0 else "📉"
                    change_text = f"+{transaction_result['change']:,.2f}" if transaction_result['change'] > 0 else f"{transaction_result['change']:,.2f}"
                    success_text += f"{change_emoji} **Изменение:** {change_text} {main_balance['currency']}\n"
                
                # Получаем общий баланс
                accounts_summary = finance_tracker.get_accounts_summary()
                success_text += f"\n💰 **Общий баланс:** ${accounts_summary['total_balance_usd']:,.2f}"
                
                if accounts_summary.get('total_balance_change', 0) != 0:
                    change = accounts_summary['total_balance_change']
                    change_emoji = "↗️" if change > 0 else "↘️"
                    success_text += f"\n{change_emoji} **Изменение общего баланса:** ${change:,.2f}"
                
                keyboard = [
                    [InlineKeyboardButton("💰 Показать график", callback_data="show_balance_chart")],
                    [InlineKeyboardButton("📊 История", callback_data="show_history")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await processing_msg.edit_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await processing_msg.edit_text(f"❌ Ошибка обновления баланса: {transaction_result['error']}", parse_mode='Markdown')
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
        
        chart_buffer = finance_tracker.create_balance_chart()
        
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
    
    elif query.data == "show_history":
        accounts_data = finance_tracker.get_accounts_summary()
        
        if accounts_data['accounts_count'] == 0:
            await query.edit_message_text("📭 У вас пока нет счетов.\n\nОтправьте скриншот банковского приложения, чтобы создать первый счет!")
            return
        
        # Получаем детали по счетам
        accounts_details = finance_tracker.get_accounts_details()
        
        keyboard = []
        for account_id, account in accounts_details.items():
            keyboard.append([InlineKeyboardButton(
                f"📊 {account['name']} ({account['currency']})", 
                callback_data=f"history_{account_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📊 **Выберите счет для просмотра истории:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == "show_total_history":
        await query.edit_message_text("🔄 Создаю график общей динамики...")
        
        chart_buffer = finance_tracker.create_total_balance_history_chart()
        
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
    
    elif query.data.startswith("history_"):
        account_id = query.data.replace("history_", "")
        await query.edit_message_text("🔄 Создаю график истории...")
        
        chart_buffer = finance_tracker.create_account_history_chart(account_id)
        
        if chart_buffer:
            # Получаем информацию о счете
            accounts_details = finance_tracker.get_accounts_details()
            account = accounts_details.get(int(account_id))
            
            if account:
                caption = f"📊 **История счета: {account['name']}**\n\n"
                caption += f"💰 Текущий баланс: {account['balance']:,.2f} {account['currency']}\n"
                caption += f"💵 В долларах: ${account['balance_usd']:,.2f}"
                
                keyboard = [
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_photo(
                    chat_id=query.from_user.id,
                    photo=chart_buffer,
                    caption=caption,
                    reply_markup=reply_markup
                )
                await query.message.delete()
            else:
                await query.edit_message_text("❌ Счет не найден.")
        else:
            await query.edit_message_text("❌ Не удалось создать график истории для этого счета.")
    
    elif query.data == "back_to_main":
        # Получаем текущие данные для обновления главного меню
        accounts_data = finance_tracker.get_accounts_summary()
        accounts_details = finance_tracker.get_accounts_details()
        
        welcome_text = "💰 **Finance Tracker Bot с графиками**\n\n"
        
        if accounts_data['accounts_count'] > 0:
            welcome_text += f"💵 **Общий баланс: ${accounts_data['total_balance_usd']:,.2f}**\n\n"
            welcome_text += "🏦 **Ваши счета:**\n"
            
            for account_id, account in accounts_details.items():
                welcome_text += f"• {account['name']}: {account['balance']:,.2f} {account['currency']} (≈ ${account['balance_usd']:,.2f})\n"
            
            welcome_text += "\n📱 **Отправьте скриншот** для обновления баланса!"
        else:
            welcome_text += "📭 У вас пока нет счетов.\n\n📱 **Отправьте скриншот** банковского приложения, чтобы создать первый счет!"
        
        welcome_text += "\n\n📊 **Команды:**\n"
        welcome_text += "/balance - показать график распределения\n"
        welcome_text += "/history - показать историю счетов\n"
        welcome_text += "/help - справка"
        
        # Отправляем новое сообщение вместо редактирования
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=welcome_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 История счетов", callback_data="show_history")],
                [InlineKeyboardButton("📈 График распределения", callback_data="show_balance_chart")],
                [InlineKeyboardButton("📊 Общая динамика", callback_data="show_total_history")]
            ]),
            parse_mode='Markdown'
        )
        
        # Удаляем старое сообщение
        try:
            await query.message.delete()
        except:
            pass
    
    elif query.data == "help":
        await help_command(update, context)

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
    
    logger.info("🚀 Запуск Telegram бота Finance Tracker с графиками...")
    application.run_polling()

if __name__ == '__main__':
    main() 