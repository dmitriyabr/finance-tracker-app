import easyocr
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt

def create_test_images():
    """Создаем тестовые изображения, имитирующие банковские скриншоты"""
    
    # Создаем изображение с разными стилями текста (как в банковских приложениях)
    img = Image.new('RGB', (400, 300), color='white')
    draw = ImageDraw.Draw(img)
    
    # Имитируем разные стили текста, которые встречаются в банках
    texts = [
        ("Баланс:", (50, 50), (0, 0, 0), 24),
        ("123 456,78 ₽", (50, 80), (0, 100, 0), 32),  # Зеленый цвет для баланса
        ("Доступно:", (50, 130), (100, 100, 100), 20),
        ("98 765,43 ₽", (50, 160), (0, 0, 0), 28),
        ("Сбербанк", (250, 50), (0, 50, 150), 22),  # Логотип банка
        ("Карта ****1234", (250, 80), (80, 80, 80), 18),
        ("Обновлено: 15.12.2024", (50, 220), (120, 120, 120), 16),
        ("15:30:45", (50, 240), (120, 120, 120), 16)
    ]
    
    for text, pos, color, size in texts:
        try:
            # Пытаемся использовать системный шрифт
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", size)
        except:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
            except:
                font = ImageFont.load_default()
        
        draw.text(pos, text, fill=color, font=font)
    
    img.save('test_bank_screen.png')
    return 'test_bank_screen.png'

def test_easyocr(image_path):
    """Тестируем EasyOCR на созданном изображении"""
    print("Тестируем EasyOCR...")
    
    # Инициализируем EasyOCR с русским и английским языками
    reader = easyocr.Reader(['ru', 'en'])
    
    # Читаем изображение
    results = reader.readtext(image_path)
    
    print("\nРезультаты EasyOCR:")
    print("-" * 50)
    
    extracted_text = []
    for (bbox, text, confidence) in results:
        print(f"Текст: '{text}' | Уверенность: {confidence:.2f}")
        extracted_text.append(text.lower())
    
    # Анализируем, нашли ли мы баланс
    balance_keywords = ['баланс', 'balance', '₽', 'руб', 'рубль', 'рублей']
    found_balance = False
    
    for text in extracted_text:
        for keyword in balance_keywords:
            if keyword in text:
                found_balance = True
                break
    
    print("\n" + "=" * 50)
    if found_balance:
        print("✅ УСПЕХ: Найден текст, похожий на баланс!")
    else:
        print("❌ ПРОБЛЕМА: Баланс не найден")
    
    return results, found_balance

def test_alternative_ocr():
    """Тестируем альтернативные OCR решения"""
    print("\n" + "=" * 60)
    print("АЛЬТЕРНАТИВНЫЕ OCR РЕШЕНИЯ:")
    print("=" * 60)
    
    alternatives = [
        {
            "name": "Tesseract OCR",
            "description": "Бесплатный, но требует установки",
            "pros": ["Бесплатный", "Хорошо работает с текстом", "Настраиваемый"],
            "cons": ["Сложнее в установке", "Медленнее EasyOCR"],
            "cost": "Бесплатно"
        },
        {
            "name": "Google Cloud Vision API",
            "description": "Платный, но очень точный",
            "pros": ["Очень высокая точность", "Работает с любыми изображениями", "Простая интеграция"],
            "cons": ["Платный ($1.50 за 1000 запросов)", "Требует Google аккаунт"],
            "cost": "$1.50 за 1000 запросов"
        },
        {
            "name": "Azure Computer Vision",
            "description": "Платный, хорошая точность",
            "pros": ["Высокая точность", "Хорошая документация", "Интеграция с Microsoft экосистемой"],
            "cons": ["Платный ($1.00 за 1000 запросов)", "Требует Azure аккаунт"],
            "cost": "$1.00 за 1000 запросов"
        },
        {
            "name": "EasyOCR + AI доработка",
            "description": "Гибридный подход",
            "pros": ["Бесплатный OCR", "AI улучшает точность", "Гибкость"],
            "cons": ["Сложнее в реализации", "Может быть медленнее"],
            "cost": "Бесплатно + возможные AI API"
        }
    ]
    
    for alt in alternatives:
        print(f"\n🔍 {alt['name']}")
        print(f"   Описание: {alt['description']}")
        print(f"   Плюсы: {', '.join(alt['pros'])}")
        print(f"   Минусы: {', '.join(alt['cons'])}")
        print(f"   Стоимость: {alt['cost']}")

if __name__ == "__main__":
    print("🧪 ТЕСТИРОВАНИЕ OCR ДЛЯ БАНКОВСКИХ СКРИНШОТОВ")
    print("=" * 60)
    
    # Создаем тестовое изображение
    image_path = create_test_images()
    print(f"✅ Создано тестовое изображение: {image_path}")
    
    # Тестируем EasyOCR
    results, found_balance = test_easyocr(image_path)
    
    # Показываем альтернативы
    test_alternative_ocr()
    
    print("\n" + "=" * 60)
    print("РЕКОМЕНДАЦИЯ:")
    if found_balance:
        print("EasyOCR показал хорошие результаты. Можно попробовать его для начала.")
    else:
        print("EasyOCR не справился. Рекомендую использовать платные API для лучшей точности.")
    
    print("\nСледующие шаги:")
    print("1. Установить зависимости: pip install easyocr opencv-python pillow matplotlib")
    print("2. Протестировать на реальных скриншотах")
    print("3. Если точность низкая - перейти на платные API") 