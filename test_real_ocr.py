import easyocr
import os
import re
from datetime import datetime
import json

class BankBalanceExtractor:
    def __init__(self):
        """Инициализируем EasyOCR с русским и английским языками"""
        print("🔄 Загружаем модели EasyOCR...")
        self.reader = easyocr.Reader(['ru', 'en'])
        print("✅ Модели загружены!")
        
        # Паттерны для поиска баланса
        self.balance_patterns = [
            r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*₽',  # 123 456,78 ₽
            r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*руб',  # 123 456.78 руб
            r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*рубл',  # 123 456,78 рубл
            r'(\d{1,3}(?:\s\d{3})*(?:\.\d{2})?)\s*RUB',  # 123 456.78 RUB
            r'(\d{1,3}(?:\s\d{3})*(?:,\d{2})?)\s*₽',  # 123 456,78 ₽ (без пробела)
        ]
        
        # Ключевые слова для поиска баланса
        self.balance_keywords = [
            'баланс', 'balance', 'доступно', 'available', 'счет', 'account',
            'карта', 'card', 'основной', 'main', 'текущий', 'current'
        ]
        
        # Ключевые слова для исключения (не баланс)
        self.exclude_keywords = [
            'лимит', 'limit', 'кредит', 'credit', 'долг', 'debt', 'минимальный', 'minimum'
        ]

    def extract_balance_from_text(self, text_list):
        """Извлекаем баланс из списка распознанного текста"""
        balances = []
        
        for text, confidence in text_list:
            text_lower = text.lower()
            
            # Проверяем, не является ли это исключением
            if any(exclude in text_lower for exclude in self.exclude_keywords):
                continue
                
            # Ищем по паттернам
            for pattern in self.balance_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    for match in matches:
                        # Очищаем число от пробелов и приводим к стандартному виду
                        clean_number = match.replace(' ', '').replace(',', '.')
                        try:
                            # Проверяем, что это действительно число
                            float(clean_number)
                            balances.append({
                                'value': clean_number,
                                'original_text': text,
                                'confidence': confidence,
                                'pattern': pattern
                            })
                        except ValueError:
                            continue
            
            # Ищем по ключевым словам (если рядом есть число)
            for keyword in self.balance_keywords:
                if keyword in text_lower:
                    # Ищем числа в этом же тексте
                    numbers = re.findall(r'\d{1,3}(?:\s\d{3})*(?:[,.]\d{2})?', text)
                    if numbers:
                        for number in numbers:
                            clean_number = number.replace(' ', '').replace(',', '.')
                            try:
                                float(clean_number)
                                balances.append({
                                    'value': clean_number,
                                    'original_text': text,
                                    'confidence': confidence,
                                    'keyword': keyword
                                })
                            except ValueError:
                                continue
        
        return balances

    def process_image(self, image_path):
        """Обрабатываем одно изображение"""
        print(f"\n🔍 Обрабатываем: {os.path.basename(image_path)}")
        print("-" * 50)
        
        try:
            # Распознаем текст
            results = self.reader.readtext(image_path)
            
            # Преобразуем результаты в удобный формат
            text_list = [(text, confidence) for (bbox, text, confidence) in results]
            
            print("📝 Распознанный текст:")
            for text, confidence in text_list:
                print(f"   '{text}' (уверенность: {confidence:.2f})")
            
            # Извлекаем баланс
            balances = self.extract_balance_from_text(text_list)
            
            if balances:
                print(f"\n💰 Найдено балансов: {len(balances)}")
                for i, balance in enumerate(balances, 1):
                    print(f"   {i}. {balance['value']} ₽")
                    print(f"      Источник: '{balance['original_text']}'")
                    print(f"      Уверенность: {balance['confidence']:.2f}")
                    if 'pattern' in balance:
                        print(f"      Найден по паттерну: {balance['pattern']}")
                    if 'keyword' in balance:
                        print(f"      Найден по ключевому слову: {balance['keyword']}")
                
                # Возвращаем самый вероятный баланс (с наивысшей уверенностью)
                best_balance = max(balances, key=lambda x: x['confidence'])
                return {
                    'success': True,
                    'balance': best_balance['value'],
                    'confidence': best_balance['confidence'],
                    'all_balances': balances,
                    'text_list': text_list
                }
            else:
                print("❌ Баланс не найден")
                return {
                    'success': False,
                    'balance': None,
                    'confidence': 0,
                    'all_balances': [],
                    'text_list': text_list
                }
                
        except Exception as e:
            print(f"❌ Ошибка при обработке: {e}")
            return {
                'success': False,
                'balance': None,
                'confidence': 0,
                'error': str(e)
            }

    def test_all_screenshots(self):
        """Тестируем все скриншоты в папке"""
        screenshots_dir = "test_screenshots"
        
        if not os.path.exists(screenshots_dir):
            print(f"❌ Папка {screenshots_dir} не найдена!")
            return
        
        # Получаем список всех изображений
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
        image_files = []
        
        for file in os.listdir(screenshots_dir):
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_files.append(os.path.join(screenshots_dir, file))
        
        if not image_files:
            print(f"❌ В папке {screenshots_dir} нет изображений!")
            print("Добавьте скриншоты банковских приложений и запустите скрипт снова.")
            return
        
        print(f"📱 Найдено изображений: {len(image_files)}")
        print("=" * 60)
        
        results = []
        
        for image_path in image_files:
            result = self.process_image(image_path)
            result['filename'] = os.path.basename(image_path)
            results.append(result)
        
        # Сохраняем результаты в JSON
        self.save_results(results)
        
        # Показываем итоговую статистику
        self.show_summary(results)
        
        return results

    def save_results(self, results):
        """Сохраняем результаты в JSON файл"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ocr_results_{timestamp}.json"
        
        # Подготавливаем данные для сохранения
        save_data = {
            'timestamp': datetime.now().isoformat(),
            'total_images': len(results),
            'successful_extractions': sum(1 for r in results if r['success']),
            'results': results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Результаты сохранены в: {filename}")

    def show_summary(self, results):
        """Показываем итоговую статистику"""
        print("\n" + "=" * 60)
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
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
                    print(f"   {result['filename']}: {result['balance']} ₽ (уверенность: {result['confidence']:.2f})")

def main():
    print("🧪 ТЕСТИРОВАНИЕ OCR НА РЕАЛЬНЫХ БАНКОВСКИХ СКРИНШОТАХ")
    print("=" * 60)
    
    extractor = BankBalanceExtractor()
    results = extractor.test_all_screenshots()
    
    if results:
        print("\n🎯 РЕКОМЕНДАЦИИ:")
        if any(r['success'] for r in results):
            print("✅ EasyOCR успешно справляется с задачей!")
            print("   Можно использовать для основного приложения.")
        else:
            print("❌ EasyOCR не смог извлечь балансы.")
            print("   Рекомендую использовать платные API (Google Vision, Azure).")

if __name__ == "__main__":
    main() 