# 🚀 Настройка двух сервисов на Railway

## 📋 **Шаг 1: Создание сервисов**

После деплоя на Railway создайте **два сервиса**:

### **Web Service (Веб-приложение)**
- **Имя:** `finance-tracker-web`
- **Procfile:** `Procfile.web`
- **Порт:** Автоматически (Railway назначит)

### **Bot Service (Telegram бот)**
- **Имя:** `finance-tracker-bot`
- **Procfile:** `Procfile.bot`
- **Порт:** Не нужен (бот работает без веб-интерфейса)

## 🔧 **Шаг 2: Настройка переменных окружения**

### **Web Service переменные:**
```
GOOGLE_CREDENTIALS_CONTENT={"type":"service_account",...}
PORT=3000
```

### **Bot Service переменные:**
```
GOOGLE_CREDENTIALS_CONTENT={"type":"service_account",...}
TELEGRAM_BOT_TOKEN=8389454475:AAEPO9rqDtjGgehFzR075A4PNupuPjt7Fb0
```

## 📁 **Шаг 3: Структура файлов**

```
├── Procfile.web          # Для веб-сервиса
├── Procfile.bot          # Для бот-сервиса
├── app_simple.py         # Веб-приложение
├── telegram_bot_with_graphs.py  # Telegram бот
├── requirements.txt       # Зависимости
└── railway.json          # Конфигурация Railway
```

## 🎯 **Результат:**

- **Веб-приложение** будет доступно по URL от Railway
- **Telegram бот** будет работать в фоне
- Оба сервиса будут использовать один и тот же код
- Данные будут синхронизированы через общий файл `finance_data.json`

## ⚠️ **Важно:**

1. **Не удаляйте** `railway.json` - он нужен для конфигурации
2. **Создайте два сервиса** в Railway Dashboard
3. **Настройте переменные** для каждого сервиса отдельно
4. **Деплойте** оба сервиса из одной репозитории 