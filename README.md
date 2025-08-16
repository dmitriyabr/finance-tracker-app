# 💰 Finance Tracker - Personal Finance Management App

Personal finance tracking application with Telegram bot integration and web interface.

## 🚀 Features

- **📱 Telegram Bot**: Send bank app screenshots to automatically update balances
- **🌐 Web Interface**: View accounts, balances, and transaction history
- **🔍 OCR Integration**: Google Cloud Vision API for accurate text recognition
- **💱 Multi-Currency Support**: RUB, USD, EUR, AED, IDR with USD conversion
- **📊 Visualizations**: Charts and graphs for balance tracking
- **🔄 Real-time Updates**: Automatic balance updates and transaction history

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **OCR**: Google Cloud Vision API
- **Telegram Bot**: python-telegram-bot
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Charts**: Matplotlib, Chart.js
- **Deployment**: Railway

## 📋 Setup

### Prerequisites

1. **Google Cloud Vision API** credentials
2. **Telegram Bot Token** from @BotFather
3. **Python 3.9+**

### Installation

1. Clone the repository:
```bash
git clone https://github.com/dmitriyabr/finance-tracker-app.git
cd finance-tracker-app
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="path/to/google-credentials.json"
export TELEGRAM_BOT_TOKEN="your_bot_token"
export WEB_APP_URL="https://your-railway-app.up.railway.app"
```

4. Run the application:
```bash
# Web interface
python3 app.py

# Telegram bot (in another terminal)
python3 run_telegram_bot.py
```

## 🌐 Usage

### Web Interface
- Open `http://localhost:5001`
- Upload bank screenshots
- View account balances and history
- Interactive charts and visualizations

### Telegram Bot
- Send `/start` to begin
- Send bank app screenshots
- Use `/balance` for balance charts
- Use `/history` for transaction history

## 🚀 Deployment

### Railway (Recommended)

1. Fork this repository
2. Create project on [Railway](https://railway.app)
3. Connect your GitHub repository
4. Set environment variables:
   - `GOOGLE_APPLICATION_CREDENTIALS`
   - `TELEGRAM_BOT_TOKEN`
   - `WEB_APP_URL` (URL вашего веб-приложения на Railway)
5. Deploy automatically

## 📱 Supported Banks

- **Russian Banks**: Sberbank, Tinkoff, VTB, etc.
- **International**: Any bank with clear balance display
- **Currencies**: RUB, USD, EUR, AED, IDR

## 🔧 Configuration

### Environment Variables

- `GOOGLE_APPLICATION_CREDENTIALS`: Path to Google Cloud credentials
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `PORT`: Web server port (default: 5001)

### Data Storage

- Account balances stored in `finance_data.json`
- Transaction history for each account
- Automatic USD conversion rates

## 📊 API Endpoints

- `GET /`: Main web interface
- `GET /api/accounts`: Get all accounts summary
- `POST /api/process_image`: Process uploaded image
- `GET /api/account/<id>/history`: Get account history

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🆘 Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review error logs

---

**Made with ❤️ for personal finance management** 