# 🚀 Деплой Finance Tracker на Railway

## 📋 Что нужно сделать:

### **1. Создать аккаунт на Railway:**
- Перейти на [railway.app](https://railway.app)
- Войти через GitHub

### **2. Создать новый проект:**
- Нажать "New Project"
- Выбрать "Deploy from GitHub repo"
- Выбрать ваш репозиторий

### **3. Настроить переменные окружения:**
В Railway Dashboard добавить:
```
GOOGLE_APPLICATION_CREDENTIALS=google-credentials.json
TELEGRAM_BOT_TOKEN=ваш_токен_бота
```

### **4. Загрузить Google credentials:**
- В разделе "Variables" нажать "New Variable"
- Имя: `GOOGLE_APPLICATION_CREDENTIALS`
- Значение: содержимое вашего `google-credentials.json`

### **5. Деплой:**
- Railway автоматически задеплоит приложение
- Получите URL вида: `https://your-app.railway.app`

## 🔧 Что происходит автоматически:

✅ **Flask приложение** запускается на порту 5000
✅ **Telegram бот** запускается параллельно
✅ **Автоматический перезапуск** при ошибках
✅ **Логи** доступны в Railway Dashboard

## 📱 После деплоя:

1. **Web интерфейс** доступен по URL Railway
2. **Telegram бот** работает автоматически
3. **Данные** сохраняются в файл на сервере

## 💡 Преимущества Railway:

- 🆓 **Бесплатно** до 500 часов/месяц
- 🚀 **Автоматический деплой** из GitHub
- 📊 **Мониторинг** и логи
- 🔄 **Автоперезапуск** при сбоях
- 🌐 **HTTPS** из коробки 