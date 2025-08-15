// Finance Tracker JavaScript

// Глобальные переменные для графиков
let currencyChart = null;
let totalBalanceChart = null;
let accountChart = null;

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация графиков
    initCharts();
    
    // Автообновление каждые 30 секунд
    setInterval(refreshAccounts, 30000);
});

// Инициализация формы загрузки изображения
function initUploadForm() {
    const form = document.getElementById('uploadForm');
    const fileInput = document.getElementById('imageFile');
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (!fileInput.files[0]) {
            showError('Пожалуйста, выберите изображение');
            return;
        }
        
        uploadImage(fileInput.files[0]);
    });
    
    // Предпросмотр изображения
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            showImagePreview(file);
        }
    });
}

// Инициализация формы ручного добавления
function initManualForm() {
    const form = document.getElementById('manualForm');
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const value = document.getElementById('manualValue').value;
        const currency = document.getElementById('manualCurrency').value;
        
        if (!value || !currency) {
            showError('Пожалуйста, заполните все поля');
            return;
        }
        
        addManualBalance(value, currency);
    });
}

// Загрузка и обработка изображения
async function uploadImage(file) {
    const formData = new FormData();
    formData.append('image', file);
    
    // Показываем модальное окно загрузки
    const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    loadingModal.show();
    
    try {
        const response = await fetch('/api/process_image', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        // Скрываем модальное окно загрузки
        loadingModal.hide();
        
        if (result.success) {
            showSuccess(result);
            // Очищаем форму
            document.getElementById('uploadForm').reset();
            // Обновляем список балансов
            refreshBalances();
        } else {
            showError(result.error || 'Не удалось распознать баланс');
        }
        
    } catch (error) {
        loadingModal.hide();
        showError('Ошибка при загрузке изображения: ' + error.message);
    }
}

// Добавление баланса вручную
async function addManualBalance(value, currency) {
    try {
        const response = await fetch('/api/add_balance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                value: parseFloat(value),
                currency: currency
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess({
                main_balance: {
                    value: value,
                    currency: currency,
                    original_text: 'Добавлено вручную'
                },
                all_balances: [{
                    value: value,
                    currency: currency,
                    original_text: 'Добавлено вручную'
                }]
            });
            
            // Очищаем форму
            document.getElementById('manualForm').reset();
            // Обновляем список балансов
            refreshBalances();
        } else {
            showError(result.error || 'Не удалось добавить баланс');
        }
        
    } catch (error) {
        showError('Ошибка при добавлении баланса: ' + error.message);
    }
}

// Показ успешного результата
function showSuccess(result) {
    const modal = new bootstrap.Modal(document.getElementById('successModal'));
    const content = document.getElementById('successContent');
    
    const mainBalance = result.main_balance;
    const allBalances = result.all_balances;
    
    let html = `
        <div class="text-center mb-3">
            <i class="fas fa-check-circle text-success fa-3x"></i>
        </div>
        <h4 class="text-center mb-3">
            Найден основной баланс: 
            <span class="text-primary">
                ${formatCurrency(mainBalance.value, mainBalance.currency)}
                            </span>
        </h4>
    `;
    
    if (allBalances.length > 1) {
        html += `
            <div class="alert alert-info">
                <h6><i class="fas fa-info-circle"></i> Все найденные суммы:</h6>
                <ul class="list-unstyled mb-0">
        `;
        
        allBalances.forEach(balance => {
            html += `
                <li class="mb-1">
                    <i class="fas fa-coins text-warning"></i>
                    ${formatCurrency(balance.value, balance.currency)}
                    <small class="text-muted"> - ${balance.original_text}</small>
                </li>
            `;
        });
        
        html += `
                </ul>
            </div>
        `;
    }
    
    if (mainBalance.original_text) {
        html += `
            <div class="alert alert-light">
                <small class="text-muted">
                    <strong>Источник:</strong> "${mainBalance.original_text}"
                </small>
            </div>
        `;
    }
    
    content.innerHTML = html;
    modal.show();
}

// Показ ошибки
function showError(message) {
    const modal = new bootstrap.Modal(document.getElementById('errorModal'));
    const content = document.getElementById('errorContent');
    
    content.innerHTML = `
        <div class="text-center mb-3">
            <i class="fas fa-exclamation-triangle text-danger fa-3x"></i>
        </div>
        <p class="text-center">${message}</p>
        <div class="alert alert-warning">
            <h6><i class="fas fa-lightbulb"></i> Советы:</h6>
            <ul class="mb-0">
                <li>Убедитесь, что на скриншоте четко виден баланс</li>
                <li>Попробуйте другой ракурс или масштаб</li>
                <li>Проверьте, что текст не размыт</li>
            </ul>
        </div>
    `;
    
    modal.show();
}

// Предпросмотр изображения
function showImagePreview(file) {
    if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = function(e) {
            // Можно добавить предпросмотр изображения
            console.log('Изображение загружено:', file.name);
        };
        reader.readAsDataURL(file);
    }
}

// Обновление списка балансов
async function refreshBalances() {
    try {
        const response = await fetch('/api/balances');
        const data = await response.json();
        
        updateBalancesList(data);
        updateTotalBalance(data.total_balance_usd, data.last_updated, data.total_balance_change);
        updateStats(data.total_count, data.balances.length);
        
    } catch (error) {
        console.error('Ошибка при обновлении балансов:', error);
    }
}

// Обновление списка балансов на странице
function updateBalancesList(data) {
    const container = document.getElementById('balancesList');
    
    if (data.balances.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-inbox fa-3x mb-3"></i>
                <p>Нет записей о балансах</p>
                <p>Загрузите скриншот или добавьте баланс вручную</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    data.balances
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .forEach(balance => {
            html += createBalanceItem(balance);
        });
    
    container.innerHTML = html;
}

// Создание элемента баланса
function createBalanceItem(balance) {
    const date = new Date(balance.timestamp).toLocaleDateString('ru-RU');
    const currencySymbol = getCurrencySymbol(balance.currency);
    
    return `
        <div class="balance-item">
            <div class="balance-header">
                <div class="balance-amount">
                    <span class="currency-symbol">${currencySymbol}</span>
                    <span class="amount">${parseFloat(balance.value).toFixed(2)}</span>
                </div>
                <div class="balance-meta">
                    <small class="text-muted">${date}</small>
                    <span class="badge bg-secondary">${balance.source}</span>
                </div>
            </div>
            ${balance.original_text ? `
                <div class="balance-source">
                    <small class="text-muted">Источник: "${balance.original_text.length > 50 ? balance.original_text.substring(0, 50) + '...' : balance.original_text}"</small>
                </div>
            ` : ''}
        </div>
    `;
}

// Получение символа валюты
function getCurrencySymbol(currency) {
    const symbols = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'AED': 'AED',
        'IDR': 'Rp'
    };
    return symbols[currency] || currency;
}

// Форматирование валюты для отображения
function formatCurrency(value, currency) {
    const symbol = getCurrencySymbol(currency);
    return `${symbol}${parseFloat(value).toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
}

// Обновление общего баланса
function updateTotalBalance(totalUsd, lastUpdated, totalChange) {
    const totalBalanceElement = document.querySelector('.display-4');
    const lastUpdatedElement = document.querySelector('.card-body small');
    
    if (totalBalanceElement) {
        let balanceText = `$${totalUsd.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        
        // Добавляем индикатор изменения
        if (totalChange !== undefined && totalChange !== 0) {
            const changeEmoji = totalChange > 0 ? '↗️' : '↘️';
            const changeClass = totalChange > 0 ? 'text-success' : 'text-danger';
            balanceText += ` <span class="balance-change ${changeClass}">${changeEmoji}</span>`;
        }
        
        totalBalanceElement.innerHTML = balanceText;
    }
    
    if (lastUpdatedElement && lastUpdated) {
        lastUpdatedElement.textContent = `Обновлено: ${lastUpdated.substring(0, 10)}`;
    }
}

// Обновление статистики
function updateStats(totalCount, todayCount) {
    const totalElement = document.querySelector('.stat-item h4');
    const todayElement = document.querySelectorAll('.stat-item h4')[1];
    
    if (totalElement) totalElement.textContent = totalCount;
    if (todayElement) todayElement.textContent = todayCount;
}

// Глобальная функция для обновления (вызывается из HTML)
window.refreshBalances = refreshBalances; 

// Инициализация графиков
function initCharts() {
    createCurrencyChart();
    createTotalBalanceChart();
}

// Создание круговой диаграммы распределения по валютам
function createCurrencyChart() {
    const ctx = document.getElementById('currencyChart');
    if (!ctx) return;
    
    // Получаем данные о счетах
    const accountsData = getAccountsDataFromPage();
    if (!accountsData || Object.keys(accountsData.accounts).length === 0) return;
    
    const labels = [];
    const data = [];
    const colors = [
        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
    ];
    
    let i = 0;
    for (const [accountId, account] of Object.entries(accountsData.accounts)) {
        labels.push(account.name);
        data.push(account.balance_usd);
        i++;
    }
    
    currencyChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: $${value.toFixed(2)} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Создание линейного графика динамики общего баланса
function createTotalBalanceChart() {
    const ctx = document.getElementById('totalBalanceChart');
    if (!ctx) return;
    
    // Получаем данные о счетах
    const accountsData = getAccountsDataFromPage();
    if (!accountsData || Object.keys(accountsData.accounts).length === 0) return;
    
    // Создаем временную шкалу на основе последних обновлений
    const labels = [];
    const data = [];
    
    // Группируем все транзакции по времени
    const allTransactions = [];
    for (const [accountId, account] of Object.entries(accountsData.accounts)) {
        if (account.transactions) {
            for (const transaction of account.transactions) {
                allTransactions.push({
                    timestamp: new Date(transaction.timestamp),
                    account_id: accountId,
                    currency: account.currency,
                    balance_usd: account.balance_usd,
                    old_balance_usd: transaction.old_balance * getConversionRate(account.currency),
                    new_balance_usd: transaction.new_balance * getConversionRate(account.currency)
                });
            }
        }
    }
    
    // Сортируем по времени
    allTransactions.sort((a, b) => a.timestamp - b.timestamp);
    
    // Создаем точки данных для общего баланса
    let runningTotal = 0;
    const processedDates = new Set();
    
    for (const transaction of allTransactions) {
        const date = transaction.timestamp.toLocaleDateString('ru-RU');
        
        // Избегаем дублирования дат
        if (processedDates.has(date)) {
            // Если дата уже есть, обновляем общий баланс
            const lastIndex = data.length - 1;
            if (lastIndex >= 0) {
                // Пересчитываем общий баланс на эту дату
                data[lastIndex] = calculateTotalBalanceAtDate(accountsData.accounts, transaction.timestamp);
            }
        } else {
            // Новая дата - добавляем точку
            processedDates.add(date);
            labels.push(date);
            
            // Рассчитываем общий баланс на эту дату
            runningTotal = calculateTotalBalanceAtDate(accountsData.accounts, transaction.timestamp);
            data.push(runningTotal);
        }
    }
    
    // Если данных мало, создаем простой график с текущим балансом
    if (labels.length < 2) {
        labels.push('Сегодня');
        data.push(accountsData.total_balance_usd);
    }
    
    // Добавляем начальную точку, если есть
    if (labels.length > 0 && labels[0] !== 'Сегодня') {
        labels.unshift('Начало');
        data.unshift(0); // Начинаем с нуля
    }
    
    totalBalanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Общий баланс ($)',
                data: data,
                borderColor: '#36A2EB',
                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#36A2EB',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Общий баланс: $${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45
                    }
                }
            }
        }
    });
}

// Функция для расчета общего баланса на определенную дату
function calculateTotalBalanceAtDate(accounts, targetDate) {
    let totalBalance = 0;
    
    for (const [accountId, account] of Object.entries(accounts)) {
        if (account.transactions) {
            // Находим последнюю транзакцию до или в указанную дату
            let lastBalance = 0;
            for (const transaction of account.transactions) {
                if (new Date(transaction.timestamp) <= targetDate) {
                    lastBalance = transaction.new_balance;
                }
            }
            
            // Конвертируем в доллары
            const balanceUsd = lastBalance * getConversionRate(account.currency);
            totalBalance += balanceUsd;
        }
    }
    
    return Math.round(totalBalance * 100) / 100; // Округляем до 2 знаков
}

// Функция для получения курса конвертации валюты
function getConversionRate(currency) {
    const conversion_rates = {
        'RUB': 0.011,
        'USD': 1.0,
        'EUR': 1.09,
        'AED': 0.27,
        'IDR': 0.000065
    };
    
    return conversion_rates[currency] || 1.0;
}

// Получение данных о счетах со страницы
function getAccountsDataFromPage() {
    try {
        // Пытаемся получить данные из глобальной переменной или с сервера
        if (window.accountsData) {
            return window.accountsData;
        }
        
        // Если нет, возвращаем базовую структуру
        return {
            accounts: {},
            total_balance_usd: 0,
            last_updated: null
        };
    } catch (error) {
        console.error('Ошибка получения данных:', error);
        return null;
    }
}

// Обновление графиков
function updateCharts(accountsData) {
    if (currencyChart) {
        currencyChart.destroy();
    }
    if (totalBalanceChart) {
        totalBalanceChart.destroy();
    }
    
    // Сохраняем данные глобально
    window.accountsData = accountsData;
    
    // Пересоздаем графики
    setTimeout(() => {
        createCurrencyChart();
        createTotalBalanceChart();
    }, 100);
}

// Показать график счета
async function showAccountChart(accountId) {
    try {
        const response = await fetch(`/api/account/${accountId}/history`);
        const result = await response.json();
        
        if (result) {
            showAccountChartModal(result);
        } else {
            alert('Не удалось загрузить данные счета');
        }
    } catch (error) {
        console.error('Ошибка загрузки данных счета:', error);
        alert('Произошла ошибка при загрузке данных');
    }
}

// Показать модальное окно с графиком счета
function showAccountChartModal(historyData) {
    const modal = new bootstrap.Modal(document.getElementById('accountChartModal'));
    modal.show();
    
    // Ждем, пока модальное окно откроется
    setTimeout(() => {
        createAccountChart(historyData);
    }, 300);
}

// Создание графика для конкретного счета
function createAccountChart(historyData) {
    const ctx = document.getElementById('accountChart');
    if (!ctx) return;
    
    // Уничтожаем предыдущий график
    if (accountChart) {
        accountChart.destroy();
    }
    
    const account = historyData.account;
    const transactions = historyData.transactions || [];
    
    if (transactions.length === 0) {
        ctx.getContext('2d').clearRect(0, 0, ctx.width, ctx.height);
        ctx.getContext('2d').font = '16px Arial';
        ctx.getContext('2d').fillText('История изменений пуста', 50, 200);
        return;
    }
    
    // Сортируем транзакции по времени
    const sortedTransactions = transactions.sort((a, b) => 
        new Date(a.timestamp) - new Date(b.timestamp)
    );
    
    const labels = [];
    const balanceData = [];
    const changeData = [];
    
    for (const transaction of sortedTransactions) {
        const date = new Date(transaction.timestamp).toLocaleDateString('ru-RU');
        labels.push(date);
        balanceData.push(transaction.new_balance);
        changeData.push(transaction.change);
    }
    
    // Создаем график
    accountChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: `Баланс (${account.currency})`,
                    data: balanceData,
                    borderColor: '#36A2EB',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    borderWidth: 3,
                    fill: false,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'Изменение',
                    data: changeData,
                    borderColor: '#FF6384',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    yAxisID: 'y1',
                    hidden: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: `${account.name} - Динамика баланса`
                },
                legend: {
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Дата'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: `Баланс (${account.currency})`
                    }
                },
                y1: {
                    type: 'linear',
                    display: false,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Изменение'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

// Обновить данные при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Можно добавить автоматическое обновление каждые 30 секунд
    // setInterval(refreshAccounts, 30000);
});

// Функция обновления счетов (для будущего использования)
async function refreshAccounts() {
    try {
        const response = await fetch('/api/accounts');
        const accountsData = await response.json();
        updateAccountsDisplay(accountsData);
        updateCharts(accountsData);
    } catch (error) {
        console.error('Ошибка обновления счетов:', error);
    }
} 

// Обновить отображение счетов
function updateAccountsDisplay(accountsData) {
    const container = document.getElementById('accountsContainer');
    
    if (Object.keys(accountsData.accounts).length === 0) {
        container.innerHTML = `
            <div class="col-12 text-center text-muted">
                <p>У вас пока нет счетов.</p>
                <p>Загрузите скриншот банковского приложения, чтобы создать первый счет!</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    for (const [accountId, account] of Object.entries(accountsData.accounts)) {
        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="card h-100">
                    <div class="card-body">
                        <h6 class="card-title">${account.name}</h6>
                        <div class="balance-info">
                            <div class="usd-balance">
                                <strong>$${account.balance_usd.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong>
                            </div>
                            <div class="local-balance text-muted">
                                <small>${account.balance.toFixed(2)} ${account.currency}</small>
                            </div>
                        </div>
                        ${account.last_updated ? `
                            <small class="text-muted">
                                Обновлено: ${account.last_updated.substring(0, 10)}
                            </small>
                        ` : ''}
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-primary" 
                                    onclick="showAccountHistory('${accountId}')">
                                📊 История
                            </button>
                            <button class="btn btn-sm btn-outline-info" 
                                    onclick="showAccountChart('${accountId}')">
                                📈 График
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    // Обновляем общий баланс
    updateTotalBalance(accountsData.total_balance_usd, accountsData.last_updated, accountsData.total_balance_change);
} 