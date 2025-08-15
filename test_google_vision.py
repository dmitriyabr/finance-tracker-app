import os
import json
import re
from datetime import datetime
from typing import List, Dict, Optional

# Для Google Vision API нужно установить: pip install google-cloud-vision
try:
    from google.cloud import vision
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False
    print("⚠️  Google Cloud Vision не установлен")
    print("   Установите: pip install google-cloud-vision")

class GoogleVisionBalanceExtractor:
    def __init__(self):
        """Инициализируем Google Vision API"""
        if not GOOGLE_VISION_AVAILABLE:
            print("❌ Google Cloud Vision недоступен")
            return
            
        try:
            self.client = vision.ImageAnnotatorClient()
            print("✅ Google Cloud Vision API подключен!")
        except Exception as e:
            print(f"❌ Ошибка подключения к Google Vision: {e}")
            print("   Проверьте настройки аутентификации")
            return
        
        # Расширенные паттерны для всех валют
        self.currency_patterns = {
            'RUB': [
                r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*₽',
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
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*د\.إ'
            ],
            'IDR': [
                r'Rp\s*(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)',
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{3})?)\s*Rp',
                r'(\d{1,3}(?:\s\d{3})*(?:\.\d{3})?)\s*рупий'
            ]
        }
        
        # Ключевые слова для поиска основного баланса
        self.balance_keywords = [
            'balance', 'total', 'available', 'current', 'main',
            'баланс', 'доступно', 'основной', 'текущий', 'общий'
        ]

    def extract_balances_from_text(self, text_list: List[str]) -> List[Dict]:
        """Извлекаем все найденные балансы из текста"""
        balances = []
        
        for text in text_list:
            text_lower = text.lower()
            
            # Ищем по всем валютам
            for currency, patterns in self.currency_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            # Очищаем число
                            clean_number = match.replace(' ', '').replace(',', '')
                            
                            # Проверяем, что это число
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
                    # Ищем числа рядом с ключевым словом
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

    def process_image(self, image_path: str) -> Dict:
        """Обрабатываем одно изображение через Google Vision"""
        print(f"\n🔍 Обрабатываем: {os.path.basename(image_path)}")
        print("-" * 50)
        
        if not GOOGLE_VISION_AVAILABLE:
            return {'success': False, 'error': 'Google Vision недоступен'}
        
        try:
            # Читаем изображение
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            # Создаем объект изображения
            image = vision.Image(content=content)
            
            # Распознаем текст
            response = self.client.text_detection(image=image)
            texts = response.text_annotations
            
            if not texts:
                print("❌ Текст не найден")
                return {'success': False, 'error': 'Текст не найден'}
            
            # Получаем весь текст
            full_text = texts[0].description
            text_lines = full_text.split('\n')
            
            print("📝 Распознанный текст:")
            for line in text_lines[:20]:  # Показываем первые 20 строк
                if line.strip():
                    print(f"   '{line}'")
            
            if len(text_lines) > 20:
                print(f"   ... и еще {len(text_lines) - 20} строк")
            
            # Извлекаем балансы
            balances = self.extract_balances_from_text(text_lines)
            
            if balances:
                print(f"\n💰 Найдено балансов: {len(balances)}")
                for i, balance in enumerate(balances, 1):
                    print(f"   {i}. {balance['value']} {balance['currency']}")
                    print(f"      Источник: '{balance['original_text']}'")
                    if 'keyword' in balance:
                        print(f"      Найден по ключевому слову: {balance['keyword']}")
                
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
                print("❌ Баланс не найден")
                return {
                    'success': False,
                    'balance': None,
                    'text_lines': text_lines,
                    'full_text': full_text
                }
                
        except Exception as e:
            print(f"❌ Ошибка при обработке: {e}")
            return {
                'success': False,
                'balance': None,
                'error': str(e)
            }

    def test_all_screenshots(self):
        """Тестируем все скриншоты"""
        screenshots_dir = "test_screenshots"
        
        if not os.path.exists(screenshots_dir):
            print(f"❌ Папка {screenshots_dir} не найдена!")
            return
        
        # Получаем список изображений
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
        image_files = []
        
        for file in os.listdir(screenshots_dir):
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_files.append(os.path.join(screenshots_dir, file))
        
        if not image_files:
            print(f"❌ В папке {screenshots_dir} нет изображений!")
            return
        
        print(f"📱 Найдено изображений: {len(image_files)}")
        print("=" * 60)
        
        results = []
        
        for image_path in image_files:
            result = self.process_image(image_path)
            result['filename'] = os.path.basename(image_path)
            results.append(result)
        
        # Сохраняем результаты
        self.save_results(results)
        
        # Показываем статистику
        self.show_summary(results)
        
        return results

    def save_results(self, results: List[Dict]):
        """Сохраняем результаты в JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"google_vision_results_{timestamp}.json"
        
        save_data = {
            'timestamp': datetime.now().isoformat(),
            'total_images': len(results),
            'successful_extractions': sum(1 for r in results if r['success']),
            'results': results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Результаты сохранены в: {filename}")

    def show_summary(self, results: List[Dict]):
        """Показываем итоговую статистику"""
        print("\n" + "=" * 60)
        print("📊 ИТОГОВАЯ СТАТИСТИКА (Google Vision):")
        print("=" * 60)
        
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = total - successful
        
        print(f"📱 Всего изображений: {total}")
        print(f"✅ Успешно обработано: {successful}")
        print(f"❌ Не удалось обработать: {failed}")
        print(f"📈 Процент успеха: {(successful/total)*100:.1f}%")
        
        if successful > 0:
            print(f"\n💰 Найденные балансы:")
            for result in results:
                if result['success']:
                    balance = result['main_balance']
                    print(f"   {result['filename']}: {balance['value']} {balance['currency']}")

def main():
    print("🧪 ТЕСТИРОВАНИЕ GOOGLE CLOUD VISION API")
    print("=" * 60)
    
    if not GOOGLE_VISION_AVAILABLE:
        print("\n❌ Google Cloud Vision недоступен!")
        print("\n📋 Для использования Google Vision API нужно:")
        print("1. Создать Google Cloud аккаунт")
        print("2. Включить Vision API")
        print("3. Создать ключ аутентификации")
        print("4. Установить библиотеку: pip install google-cloud-vision")
        print("5. Настроить переменную окружения GOOGLE_APPLICATION_CREDENTIALS")
        return
    
    extractor = GoogleVisionBalanceExtractor()
    results = extractor.test_all_screenshots()
    
    if results:
        print("\n🎯 РЕКОМЕНДАЦИИ:")
        if any(r['success'] for r in results):
            print("✅ Google Vision API отлично справляется с задачей!")
            print("   Поддерживает все валюты и языки.")
        else:
            print("❌ Google Vision не смог извлечь балансы.")
            print("   Проверьте качество изображений.")

if __name__ == "__main__":
    main() 