#!/usr/bin/env python3
"""
Общая логика для Finance Tracker
"""

import os
import re
from datetime import datetime
from google.cloud import vision
from models import create_session, Account, Transaction, SystemInfo, convert_to_usd

class FinanceTrackerCore:
    """Общая логика для веб-приложения и телеграм бота"""
    
    def __init__(self):
        """Инициализация общего трекера"""
        # Инициализация Google Vision API
        self.vision_client = self._init_vision_client()
        
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
                r'€(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)'
            ],
            'AED': [
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*AED',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*дирхам',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*د\.إ'
            ],
            'IDR': [
                r'Rp\s*(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{3})?)\s*Rp',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{3})?)\s*рупий'
            ]
        }
        
        self.balance_keywords = [
            'balance', 'total', 'available', 'current', 'main', 'cash',
            'баланс', 'доступно', 'основной', 'текущий', 'общий', 'наличные'
        ]

    def _init_vision_client(self):
        """Инициализация Google Vision API"""
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
                vision_client = vision.ImageAnnotatorClient()
                print("✅ Google Vision API подключен через GOOGLE_CREDENTIALS_CONTENT!")
                return vision_client
            else:
                print("❌ GOOGLE_CREDENTIALS_CONTENT не установлен")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка подключения к Google Vision: {e}")
            return None

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
            print(f"❌ Ошибка при обработке изображения: {e}")
            return {
                'success': False,
                'balance': None,
                'error': str(e)
            }

    def update_account_balance_from_image(self, balance_data, image_text, source='web'):
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
                original_text=image_text
            )
            session.add(transaction)
            
            session.commit()
            
            print(f"✅ Обновлен баланс счета {account.id}: {account.balance} {account.currency} (${account.balance_usd:.2f})")
            
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
            print(f"❌ Ошибка обновления баланса из изображения: {e}")
            session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            session.close()

    def get_accounts_summary(self):
        """Получает сводку по всем счетам"""
        try:
            session = create_session()
            accounts = session.query(Account).all()
            
            total_balance_usd = sum(account.balance_usd for account in accounts)
            
            return {
                'total_balance_usd': total_balance_usd,
                'accounts_count': len(accounts)
            }
            
        except Exception as e:
            print(f"❌ Ошибка получения сводки по счетам: {e}")
            return {
                'total_balance_usd': 0,
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
            print(f"❌ Ошибка получения деталей по счетам: {e}")
            return {}
        finally:
            session.close()

    def get_accounts_for_api(self):
        """Получает список счетов для API"""
        try:
            session = create_session()
            accounts = session.query(Account).all()
            
            accounts_data = []
            total_balance_usd = 0
            
            for account in accounts:
                # Получаем дату последней транзакции для этого счета
                last_transaction = session.query(Transaction).filter_by(
                    account_id=account.id
                ).order_by(Transaction.timestamp.desc()).first()
                
                last_updated = last_transaction.timestamp if last_transaction else account.last_updated
                
                accounts_data.append({
                    'id': account.id,
                    'name': account.name,
                    'currency': account.currency,
                    'balance': account.balance,
                    'balance_usd': account.balance_usd,
                    'last_updated': last_updated.isoformat() if last_updated else None
                })
                total_balance_usd += account.balance_usd
            
            return {
                'success': True,
                'accounts': accounts_data,
                'total_balance_usd': round(total_balance_usd, 2)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    def get_balance_history(self):
        """Получает историю общего баланса"""
        try:
            session = create_session()
            
            # Получаем все транзакции, отсортированные по времени
            transactions = session.query(Transaction).join(Account).order_by(Transaction.timestamp).all()
            
            if not transactions:
                # Если нет транзакций, возвращаем текущий общий баланс
                accounts = session.query(Account).all()
                total_balance_usd = sum(convert_to_usd(account.balance, account.currency) for account in accounts)
                
                if total_balance_usd > 0:
                    # Возвращаем текущий баланс как одну точку
                    today = datetime.utcnow().strftime('%Y-%m-%d')
                    return {
                        'success': True,
                        'history': [{'date': today, 'balance': round(total_balance_usd, 2)}]
                    }
                else:
                    return {
                        'success': True,
                        'history': []
                    }
            
            # Создаем временную шкалу всех дат с транзакциями
            all_dates = sorted(list(set(t.timestamp.strftime('%Y-%m-%d') for t in transactions)))
            
            # Для каждой даты считаем общий баланс всех счетов
            balance_history = {}
            
            # Отслеживаем последний известный баланс каждого счета
            last_known_balances = {}
            
            for date_str in all_dates:
                # Получаем все транзакции на эту дату
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                start_of_day = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Получаем транзакции на эту дату
                day_transactions = session.query(Transaction).filter(
                    Transaction.timestamp >= start_of_day,
                    Transaction.timestamp <= end_of_day
                ).order_by(Transaction.timestamp).all()
                
                # Обновляем последние известные балансы для счетов с транзакциями на эту дату
                for transaction in day_transactions:
                    last_known_balances[transaction.account_id] = transaction.new_balance
                
                # Считаем общий баланс в USD на эту дату
                total_usd = 0
                for account in session.query(Account).all():
                    # Используем последний известный баланс или 0, если транзакций не было
                    balance = last_known_balances.get(account.id, 0)
                    total_usd += convert_to_usd(balance, account.currency)
                
                balance_history[date_str] = round(total_usd, 2)
            
            # Преобразуем в список для графика
            history_data = [
                {'date': date, 'balance': balance} 
                for date, balance in sorted(balance_history.items())
            ]
            
            return {
                'success': True,
                'history': history_data
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    def create_total_balance_history_chart(self):
        """Создаем график общей динамики всех счетов в USD"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import io
            
            # Используем ту же логику, что и get_balance_history
            history_result = self.get_balance_history()
            
            if not history_result['success'] or not history_result['history']:
                return None
            
            # Получаем данные для графика
            history_data = history_result['history']
            
            if len(history_data) == 0:
                return None
            
            # Конвертируем строки дат в datetime объекты
            dates = [datetime.strptime(item['date'], '%Y-%m-%d') for item in history_data]
            balances = [item['balance'] for item in history_data]
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # График общей динамики
            ax.plot(dates, balances, 'o-', linewidth=2, markersize=6, color='#36A2EB')
            ax.fill_between(dates, balances, alpha=0.3, color='#36A2EB')
            
            ax.set_title('Динамика общего баланса (все счета)', fontsize=16, fontweight='bold')
            ax.set_ylabel('Общий баланс (USD)', fontsize=12)
            ax.set_xlabel('Дата', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # Форматирование дат
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            # Получаем текущий общий баланс
            current_total = balances[-1] if balances else 0
            
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
            print(f"❌ Ошибка создания графика общей динамики: {e}")
            # Закрываем фигуру в случае ошибки
            try:
                plt.close('all')
            except:
                pass
            return None

# Создаем глобальный экземпляр
finance_tracker_core = FinanceTrackerCore() 