// Глобальное состояние
let isRunning = false;
let activeJobs = [];
let economicTickerInterval = null;
let autorunInterval = null;

// Инициализация приложения
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    updateMarketStatus();
    updateEconomicCalendar();
    loadEconomicTicker();
    loadMarketIndices();
    loadAutorunStatus();
    
    // Автообновление
    setInterval(updateMarketStatus, 60000);
    setInterval(checkQueueStatus, 1000);
    setInterval(loadMarketIndices, 30000);
    setInterval(updateEconomicCalendar, 300000);
    
    // Обновление бегущей строки каждую минуту
    setInterval(loadEconomicTicker, 60000);
    
    // Обновление статуса автозапуска каждые 10 секунд
    setInterval(loadAutorunStatus, 10000);
});

function setupEventListeners() {
    // Навигация по страницам
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            switchPage(page);
        });
    });

    // Кнопка "Запустить всё"
    document.getElementById('runAllBtn')?.addEventListener('click', async function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        if (isRunning) {
            showToast('Скрининг уже выполняется, дождитесь завершения', 'warning');
            return;
        }
        
        const tickers = getTickers();
        if (tickers.length === 0) {
            showToast('Введите тикеры для скрининга', 'warning');
            return;
        }
        
        if (tickers.length > 1000) {
            showToast('Максимум 1000 тикеров', 'error');
            return;
        }
        
        setRunningState(true);
        showToast('Добавление всех скринеров в очередь...', 'info');
        
        try {
            const screeners = [
                {type: 'long', name: 'Long Setups'},
                {type: 'squeeze', name: 'Short Squeeze'},
                {type: 'oversold', name: 'Oversold Bounce'}
            ];
            
            // Добавляем все скринеры в очередь (сервер выполнит их последовательно)
            const jobIds = [];
            for (const screener of screeners) {
                const result = await addToQueue(screener.type, tickers);
                if (result.success) {
                    jobIds.push({job_id: result.job_id, name: screener.name});
                    showToast(`${screener.name} добавлен в очередь (#${jobIds.length})`, 'success');
                } else {
                    showToast(`Ошибка добавления ${screener.name}: ${result.error}`, 'error');
                }
            }
            
            if (jobIds.length === 0) {
                throw new Error('Не удалось добавить ни один скринер в очередь');
            }
            
            showToast(`В очереди ${jobIds.length} скринеров. Сервер выполняет последовательно...`, 'info');
            
            // Ждем завершения всех скринеров (сервер выполняет их по очереди)
            for (let i = 0; i < jobIds.length; i++) {
                const job = jobIds[i];
                showToast(`Ожидание завершения ${job.name} (${i+1}/${jobIds.length})...`, 'info');
                await waitForJobCompletion(job.job_id);
            }
            
            showToast('Все скринеры успешно завершены!', 'success');
            
        } catch (error) {
            console.error('Error:', error);
            showToast('Ошибка выполнения: ' + error.message, 'error');
        } finally {
            setRunningState(false);
        }
    });

    // Отдельные кнопки скринеров
    document.querySelectorAll('[data-screener]').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            if (isRunning) {
                showToast('Дождитесь завершения текущего скрининга', 'warning');
                return;
            }
            
            const type = btn.dataset.screener;
            const tickers = getTickers();
            
            if (tickers.length === 0) {
                showToast('Введите тикеры для скрининга', 'warning');
                return;
            }
            
            setRunningState(true);
            
            try {
                const result = await addToQueue(type, tickers);
                if (result.success) {
                    await waitForJobCompletion(result.job_id);
                    showToast(`${getScreenerName(type)} завершен!`, 'success');
                }
            } catch (error) {
                showToast('Ошибка: ' + error.message, 'error');
            } finally {
                setRunningState(false);
            }
        });
    });

    // Очистка очереди
    document.getElementById('clearQueueBtn')?.addEventListener('click', async () => {
        try {
            await fetch('/api/queue/clear', {method: 'POST'});
            showToast('Очередь очищена', 'info');
            setRunningState(false);
        } catch (e) {
            showToast('Ошибка очистки очереди', 'error');
        }
    });

    // Загрузка S&P 500
    document.getElementById('loadSp500Btn')?.addEventListener('click', () => {
        const sp500 = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'WMT', 'JPM', 
                      'V', 'PG', 'MA', 'UNH', 'HD', 'LLY', 'MRK', 'PEP', 'KO', 'ABBV'];
        document.getElementById('tickerInput').value = sp500.join(', ');
        updateTickerCount();
    });

    // Очистка тикеров
    document.getElementById('clearTickersBtn')?.addEventListener('click', () => {
        document.getElementById('tickerInput').value = '';
        updateTickerCount();
    });

    // Подсчет тикеров при вводе
    document.getElementById('tickerInput')?.addEventListener('input', updateTickerCount);

    // Закрытие модалки
    document.getElementById('closeModalBtn')?.addEventListener('click', closeModal);
    document.getElementById('chartModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'chartModal') closeModal();
    });

    // Экспорт CSV
    document.getElementById('exportBtn')?.addEventListener('click', exportResults);
    document.getElementById('clearAlertsBtn')?.addEventListener('click', clearResults);
    
    // ========== АВТОЗАПУСК ==========
    setupAutorunListeners();
    
    // Горячие клавиши
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            document.getElementById('searchInput')?.focus();
        }
        if (e.key === 'Escape') {
            closeModal();
            closeAutorunDropdown();
        }
    });
}

function setupAutorunListeners() {
    const autorunBtn = document.getElementById('autorunBtn');
    const autorunDropdown = document.getElementById('autorunDropdown');
    const startBtn = document.getElementById('startAutorunBtn');
    const stopBtn = document.getElementById('stopAutorunBtn');
    const runNowBtn = document.getElementById('runNowBtn');
    
    // Открыть/закрыть dropdown
    autorunBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        autorunDropdown?.classList.toggle('show');
    });
    
    // Закрыть при клике вне
    document.addEventListener('click', (e) => {
        if (!autorunDropdown?.contains(e.target) && e.target !== autorunBtn) {
            closeAutorunDropdown();
        }
    });
    
    // Запустить автозапуск
    startBtn?.addEventListener('click', async () => {
        const tickers = getTickers();
        if (tickers.length === 0) {
            showToast('Введите тикеры для автозапуска', 'warning');
            return;
        }
        
        const interval = parseInt(document.getElementById('autorunInterval')?.value || '1');
        const screeners = Array.from(document.querySelectorAll('.autorun-screeners input:checked'))
            .map(cb => cb.value);
        
        if (screeners.length === 0) {
            showToast('Выберите хотя бы один скринер', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/autorun/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tickers, interval_hours: interval, screeners})
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`Автозапуск включен! Период: ${interval}ч`, 'success');
                updateAutorunUI(true);
                loadAutorunStatus();
            } else {
                showToast(data.error || 'Ошибка запуска автозапуска', 'error');
            }
        } catch (e) {
            showToast('Ошибка сети', 'error');
        }
    });
    
    // Остановить автозапуск
    stopBtn?.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/autorun/stop', {method: 'POST'});
            const data = await response.json();
            
            if (data.success) {
                showToast('Автозапуск остановлен', 'info');
                showToast(`Статистика: ${data.stats.total_runs} запусков, ${data.stats.total_signals} сигналов`, 'info');
                updateAutorunUI(false);
                loadAutorunStatus();
            }
        } catch (e) {
            showToast('Ошибка остановки', 'error');
        }
    });
    
    // Запустить сейчас
    runNowBtn?.addEventListener('click', async () => {
        const tickers = getTickers();
        if (tickers.length === 0) {
            showToast('Введите тикеры', 'warning');
            return;
        }
        
        const screeners = Array.from(document.querySelectorAll('.autorun-screeners input:checked'))
            .map(cb => cb.value);
        
        if (screeners.length === 0) {
            showToast('Выберите хотя бы один скринер', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/autorun/run-now', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tickers, screeners})
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`${data.job_ids.length} скринеров добавлены в очередь`, 'success');
                setRunningState(true);
                closeAutorunDropdown();
            } else {
                showToast(data.error || 'Ошибка', 'error');
            }
        } catch (e) {
            showToast('Ошибка сети', 'error');
        }
    });
}

function closeAutorunDropdown() {
    document.getElementById('autorunDropdown')?.classList.remove('show');
}

async function loadAutorunStatus() {
    try {
        const response = await fetch('/api/autorun/status');
        const data = await response.json();
        
        updateAutorunUI(data.enabled);
        
        // Обновляем статистику
        const statsEl = document.getElementById('autorunStats');
        const runCountEl = document.getElementById('autorunRunCount');
        const signalsEl = document.getElementById('autorunSignals');
        const nextRunEl = document.getElementById('autorunNextRun');
        
        if (data.enabled) {
            statsEl?.classList.remove('hidden');
            if (runCountEl) runCountEl.textContent = data.run_count || 0;
            if (signalsEl) signalsEl.textContent = data.total_signals_found || 0;
            if (nextRunEl && data.next_run) {
                const nextDate = new Date(data.next_run);
                nextRunEl.textContent = nextDate.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'});
            }
        } else {
            statsEl?.classList.add('hidden');
        }
        
    } catch (e) {
        console.error('Autorun status error:', e);
    }
}

function updateAutorunUI(enabled) {
    const btn = document.getElementById('autorunBtn');
    const startBtn = document.getElementById('startAutorunBtn');
    const stopBtn = document.getElementById('stopAutorunBtn');
    const statusEl = document.getElementById('autorunStatus');
    const statsEl = document.getElementById('autorunStats');
    
    if (enabled) {
        btn?.classList.add('active');
        startBtn?.classList.add('hidden');
        stopBtn?.classList.remove('hidden');
        if (statusEl) statusEl.innerHTML = '<span class="status-on">● Работает</span>';
        statsEl?.classList.remove('hidden');
    } else {
        btn?.classList.remove('active');
        startBtn?.classList.remove('hidden');
        stopBtn?.classList.add('hidden');
        if (statusEl) statusEl.innerHTML = '<span class="status-off">Выключен</span>';
        statsEl?.classList.add('hidden');
    }
}

// ========== БЕГУЩАЯ СТРОКА ЭКОНОМИЧЕСКИХ СОБЫТИЙ ==========

async function loadEconomicTicker() {
    try {
        const response = await fetch('/api/economic-ticker');
        const data = await response.json();
        
        if (data.events && data.events.length > 0) {
            updateEconomicTicker(data.events, data.has_critical);
        } else {
            document.getElementById('econTicker').innerHTML = 
                '<span class="ticker-item info">Нет ближайших экономических событий</span>';
        }
    } catch (e) {
        console.error('Economic ticker error:', e);
    }
}

function updateEconomicTicker(events, hasCritical) {
    const container = document.getElementById('econTickerContainer');
    const ticker = document.getElementById('econTicker');
    const alert = document.getElementById('econTickerAlert');
    
    // Проверяем наличие критических событий (сегодня или завтра)
    const criticalEvents = events.filter(e => e.alert_level === 'critical');
    const warningEvents = events.filter(e => e.alert_level === 'warning');
    
    // Обновляем стиль контейнера
    container.classList.remove('critical', 'warning');
    if (criticalEvents.length > 0) {
        container.classList.add('critical');
        alert.classList.remove('hidden');
    } else if (warningEvents.length > 0) {
        container.classList.add('warning');
        alert.classList.remove('hidden');
    } else {
        alert.classList.add('hidden');
    }
    
    // Формируем элементы бегущей строки
    const tickerItems = events.map(event => {
        const alertClass = event.alert_level;
        const daysText = event.is_today ? 'СЕГОДНЯ!' : 
                        event.is_tomorrow ? 'ЗАВТРА!' : 
                        `через ${event.days_until} дн.`;
        
        return `
            <span class="ticker-item ${alertClass}">
                <span class="event-symbol">${event.symbol}</span>
                <span class="event-type">${event.type}</span>
                <span class="event-name">${event.event}</span>
                <span class="event-date">${event.date} ${event.time}</span>
                <span class="countdown">${daysText}</span>
            </span>
        `;
    });
    
    // Дублируем для бесконечной прокрутки
    ticker.innerHTML = [...tickerItems, ...tickerItems].join('<span class="ticker-separator">•</span>');
}

// ========== ОСТАЛЬНЫЕ ФУНКЦИИ ==========

function setRunningState(running) {
    isRunning = running;
    
    const buttons = [
        document.getElementById('runAllBtn'),
        ...document.querySelectorAll('[data-screener]')
    ].filter(Boolean);
    
    buttons.forEach(btn => {
        btn.disabled = running;
        if (running) {
            btn.classList.add('btn-disabled');
            if (!btn.dataset.originalText) {
                btn.dataset.originalText = btn.innerHTML;
            }
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Выполняется...';
        } else {
            btn.classList.remove('btn-disabled');
            if (btn.dataset.originalText) {
                btn.innerHTML = btn.dataset.originalText;
            }
        }
    });
    
    const progressPanel = document.getElementById('progressContainer');
    if (progressPanel) {
        if (running) {
            progressPanel.classList.remove('hidden');
        } else {
            setTimeout(() => {
                if (!isRunning) progressPanel.classList.add('hidden');
            }, 2000);
        }
    }
}

async function waitForJobCompletion(jobId) {
    return new Promise((resolve, reject) => {
        let checkCount = 0;
        const maxChecks = 3600;
        
        const interval = setInterval(async () => {
            try {
                checkCount++;
                
                if (checkCount > maxChecks) {
                    clearInterval(interval);
                    reject(new Error('Timeout waiting for job completion'));
                    return;
                }
                
                const response = await fetch(`/api/queue/results/${jobId}`);
                
                if (response.status === 200) {
                    clearInterval(interval);
                    const data = await response.json();
                    if (data.data && data.data.length > 0) {
                        displayResultsInTable(data.data, data.type);
                        updateBadge(data.type, data.count);
                    }
                    resolve(data);
                } else if (response.status === 202) {
                    const status = await fetch('/api/queue/status').then(r => r.json());
                    updateProgressUI(status.progress);
                    
                    if (status.logs) {
                        updateLogs(status.logs);
                    }
                } else {
                    clearInterval(interval);
                    const error = await response.text();
                    reject(new Error(error));
                }
            } catch (error) {
                clearInterval(interval);
                reject(error);
            }
        }, 1000);
    });
}

async function checkQueueStatus() {
    try {
        const response = await fetch('/api/queue/status');
        const data = await response.json();
        
        if (data.running && !isRunning) {
            setRunningState(true);
        }
        
        if (!data.running && isRunning && data.queue_length === 0) {
            setTimeout(async () => {
                const check = await fetch('/api/queue/status').then(r => r.json());
                if (!check.running && check.queue_length === 0) {
                    setRunningState(false);
                }
            }, 1000);
        }
        
        updateProgressUI(data.progress);
        
    } catch (e) {
        console.error('Status check error:', e);
    }
}

async function addToQueue(type, tickers) {
    try {
        const response = await fetch('/api/queue/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({type, tickers})
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to add to queue');
        }
        
        return data;
    } catch (error) {
        console.error('Add to queue error:', error);
        throw error;
    }
}

function updateProgressUI(progress) {
    if (!progress) return;
    
    const percent = document.getElementById('progressPercent');
    const bar = document.getElementById('progressBar');
    const ticker = document.getElementById('progressTicker');
    const count = document.getElementById('progressCount');
    const title = document.getElementById('progressTitle');
    
    if (percent) percent.textContent = progress.percent + '%';
    if (bar) bar.style.width = progress.percent + '%';
    if (ticker) ticker.textContent = progress.ticker || '-';
    if (count) count.textContent = `${progress.current}/${progress.total}`;
    if (title) title.textContent = progress.status === 'completed' ? 'Завершено' : 'Обработка...';
}

function updateLogs(logs) {
    const container = document.getElementById('progressLogs');
    if (!container || !logs) return;
    
    container.innerHTML = logs.slice(0, 20).map(log => 
        `<div class="log-item">${escapeHtml(log)}</div>`
    ).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getTickers() {
    const input = document.getElementById('tickerInput');
    if (!input || !input.value.trim()) return [];
    
    return input.value
        .split(/[,\n]/)
        .map(t => t.trim().toUpperCase())
        .filter(t => t.length > 0 && t.length <= 5 && /^[A-Z]+$/.test(t));
}

function updateTickerCount() {
    const count = getTickers().length;
    const element = document.getElementById('tickerCount');
    if (element) element.textContent = count;
}

function getScreenerName(type) {
    const names = {
        'long': 'Long Setups',
        'squeeze': 'Short Squeeze',
        'oversold': 'Oversold Bounce'
    };
    return names[type] || type;
}

function displayResultsInTable(results, type) {
    const tbody = document.getElementById('resultsTableBody');
    if (!tbody) return;
    
    if (!results || results.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="6">
                    <div class="empty-state">
                        <i class="fas fa-inbox"></i>
                        <p>Нет сигналов для отображения</p>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    const rows = results.map(item => {
        let details = '';
        if (item.trend) details += `Тренд: ${item.trend}<br>`;
        if (item.rsi) details += `RSI: ${item.rsi}<br>`;
        if (item.rvol) details += `RVOL: ${item.rvol}x<br>`;
        if (item.pe) details += `P/E: ${item.pe}<br>`;
        if (item.drop_5d) details += `Падение: ${item.drop_5d}%<br>`;
        if (item.level_info) details += `Уровень: ${item.level_info}`;
        
        const gradeClass = (item.grade && (
            item.grade.includes('BUY') || 
            item.grade.includes('BREAKOUT') || 
            item.grade.includes('BOUNCE') ||
            item.grade.includes('PERFECT') ||
            item.grade.includes('STRONG')
        )) ? 'buy' : 'watch';
        
        return `
            <tr data-ticker="${item.ticker}">
                <td>
                    <strong class="ticker-link" onclick="openChartModal('${item.ticker}')" 
                            style="cursor: pointer; color: var(--primary);">
                        ${item.ticker}
                    </strong>
                </td>
                <td>
                    <span class="grade-badge ${gradeClass}">${item.grade}</span>
                </td>
                <td>$${item.price}</td>
                <td><span class="score">${item.score}</span></td>
                <td class="details-cell">${details || '-'}</td>
                <td>
                    <button class="btn-icon-small" onclick="openChartModal('${item.ticker}')" 
                            title="Открыть график ${item.ticker}">
                        <i class="fas fa-chart-line"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    
    tbody.innerHTML = rows;
    
    displayResultsInGrid(type, results);
}

function displayResultsInGrid(type, results) {
    const containerId = type === 'long' ? 'longResults' : 
                       type === 'squeeze' ? 'squeezeResults' : 
                       type === 'oversold' ? 'oversoldResults' : null;
    
    if (!containerId) return;
    
    const container = document.getElementById(containerId);
    if (!container) return;
    
    if (!results || results.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет результатов</div>';
        return;
    }
    
    const cards = results.map(item => {
        const gradeClass = (item.grade && (
            item.grade.includes('BUY') || 
            item.grade.includes('BREAKOUT') || 
            item.grade.includes('BOUNCE') ||
            item.grade.includes('PERFECT') ||
            item.grade.includes('STRONG')
        )) ? 'buy' : 'watch';
        
        return `
            <div class="result-card" onclick="openChartModal('${item.ticker}')" 
                 style="cursor: pointer;">
                <div class="result-header">
                    <span class="ticker">${item.ticker}</span>
                    <span class="grade ${gradeClass}">${item.grade}</span>
                </div>
                <div class="result-price">$${item.price}</div>
                <div class="result-metrics">
                    <div class="metric"><span>Скор:</span><strong>${item.score}</strong></div>
                    ${item.rsi ? `<div class="metric"><span>RSI:</span><strong>${item.rsi}</strong></div>` : ''}
                    ${item.rvol ? `<div class="metric"><span>RVOL:</span><strong>${item.rvol}x</strong></div>` : ''}
                    ${item.pe ? `<div class="metric"><span>P/E:</span><strong>${item.pe}</strong></div>` : ''}
                    ${item.drop_5d ? `<div class="metric"><span>Падение:</span><strong>${item.drop_5d}%</strong></div>` : ''}
                    ${item.potential ? `<div class="metric"><span>Потенциал:</span><strong>+${item.potential}%</strong></div>` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = cards;
}

function updateBadge(type, count) {
    const badgeMap = {
        'long': 'longCount',
        'squeeze': 'squeezeCount',
        'oversold': 'oversoldCount'
    };
    
    const badgeId = badgeMap[type];
    if (!badgeId) return;
    
    const badge = document.getElementById(badgeId);
    if (badge) {
        badge.textContent = `${count} сигналов`;
        badge.style.background = count > 0 ? '#d1fae5' : '';
        badge.style.color = count > 0 ? '#065f46' : '';
    }
}

async function openChartModal(ticker) {
    const modal = document.getElementById('chartModal');
    const title = document.getElementById('modalTicker');
    const company = document.getElementById('modalCompany');
    const sector = document.getElementById('modalSector');
    const price = document.getElementById('modalPrice');
    
    if (!modal) return;
    
    modal.classList.remove('hidden');
    title.textContent = ticker;
    company.textContent = 'Загрузка...';
    sector.textContent = '-';
    price.textContent = '-';
    
    try {
        const response = await fetch(`/api/chart-data/${ticker}`);
        const data = await response.json();
        
        if (data.error) {
            showToast('Ошибка загрузки данных', 'error');
            closeModal();
            return;
        }
        
        company.textContent = data.info?.name || ticker;
        sector.textContent = data.info?.sector || '-';
        price.textContent = data.info?.marketCap ? 
            `$${(data.info.marketCap / 1e9).toFixed(2)}B` : 
            (data.info?.pe ? `P/E: ${data.info.pe}` : '-');
        
        renderChart(data);
        
    } catch (error) {
        showToast('Ошибка загрузки графика', 'error');
    }
}

function renderChart(data) {
    const trace = {
        x: data.dates,
        open: data.open,
        high: data.high,
        low: data.low,
        close: data.close,
        type: 'candlestick',
        name: data.ticker,
        increasing: {line: {color: '#10b981'}},
        decreasing: {line: {color: '#ef4444'}}
    };
    
    const sma20 = {
        x: data.dates,
        y: data.sma20,
        type: 'scatter',
        mode: 'lines',
        name: 'SMA20',
        line: {color: '#6366f1', width: 1}
    };
    
    const sma50 = {
        x: data.dates,
        y: data.sma50,
        type: 'scatter',
        mode: 'lines',
        name: 'SMA50',
        line: {color: '#f59e0b', width: 1}
    };
    
    const layout = {
        title: false,
        xaxis: {title: 'Дата'},
        yaxis: {title: 'Цена ($)'},
        plot_bgcolor: '#f8fafc',
        paper_bgcolor: '#f8fafc',
        font: {family: '-apple-system, BlinkMacSystemFont, sans-serif'},
        margin: {t: 10, r: 10, b: 40, l: 40},
        showlegend: true,
        legend: {orientation: 'h', y: -0.2}
    };
    
    const config = {responsive: true, displayModeBar: false};
    
    Plotly.newPlot('chartContainer', [trace, sma20, sma50], layout, config);
}

function closeModal() {
    document.getElementById('chartModal')?.classList.add('hidden');
}

function switchPage(page) {
    document.querySelectorAll('.content-wrapper').forEach(p => p.classList.add('hidden'));
    const targetPage = document.getElementById(page + 'Page');
    if (targetPage) targetPage.classList.remove('hidden');
    
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
    
    if (page === 'arbitrage') {
        initArbitrageChart();
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };
    
    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// API функции
async function updateMarketStatus() {
    try {
        const response = await fetch('/api/market-status');
        const data = await response.json();
        
        const dot = document.getElementById('marketDot');
        const text = document.getElementById('marketStatusText');
        const time = document.getElementById('lastUpdate');
        
        if (dot && text) {
            if (data.is_open) {
                dot.className = 'dot open';
                text.textContent = 'Рынок открыт';
            } else {
                dot.className = 'dot closed';
                text.textContent = data.status_text || 'Закрыт';
            }
        }
        
        if (time) time.textContent = data.time;
        
    } catch (e) {
        console.error('Market status error:', e);
    }
}

async function updateEconomicCalendar() {
    try {
        const response = await fetch('/api/economic-calendar');
        const data = await response.json();
        
        const banner = document.getElementById('econCalendarBanner');
        const alertText = document.getElementById('econAlertText');
        const list = document.getElementById('economicCalendarList');
        const count = document.getElementById('econCount');
        
        if (data.events && data.events.length > 0) {
            if (banner) banner.classList.remove('hidden');
            if (alertText) alertText.textContent = `${data.events.length} важных событий на этой неделе`;
            if (count) {
                count.textContent = `${data.events.length} событий`;
                count.classList.add('warning');
            }
            
            if (list) {
                list.innerHTML = data.events.map(e => `
                    <div class="econ-item ${e.urgent ? 'urgent' : e.days_until <= 2 ? 'soon' : ''}">
                        <div class="econ-symbol">${e.symbol}</div>
                        <div class="econ-info">
                            <div class="econ-title">${e.event}</div>
                            <div class="econ-date">${e.date} ${e.time} (через ${e.days_until} дн.)</div>
                        </div>
                        <span class="econ-badge ${e.impact}">${e.impact}</span>
                    </div>
                `).join('');
            }
        } else {
            if (banner) banner.classList.add('hidden');
            if (count) count.textContent = '0 событий';
        }
        
    } catch (e) {
        console.error('Economic calendar error:', e);
    }
}

async function loadMarketIndices() {
    try {
        const response = await fetch('/api/market-indices');
        const data = await response.json();
        
        if (data.data) {
            Object.entries(data.data).forEach(([symbol, info]) => {
                const card = document.getElementById(symbol.toLowerCase());
                if (card) {
                    const valueEl = card.querySelector('.index-value');
                    const changeEl = card.querySelector('.index-change');
                    
                    if (valueEl) valueEl.textContent = info.value.toFixed(2);
                    if (changeEl) {
                        changeEl.textContent = (info.positive ? '+' : '') + info.change + '%';
                        changeEl.className = 'index-change ' + (info.positive ? 'positive' : 'negative');
                    }
                }
            });
        }
    } catch (e) {
        console.error('Indices error:', e);
    }
}

function exportResults() {
    const rows = document.querySelectorAll('#resultsTableBody tr');
    if (rows.length === 0 || rows[0].classList.contains('empty-row')) {
        showToast('Нет данных для экспорта', 'warning');
        return;
    }
    
    let csv = 'Тикер,Сигнал,Цена,Скор\n';
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 4) {
            const ticker = cells[0].textContent.trim();
            const signal = cells[1].textContent.trim();
            const price = cells[2].textContent.trim().replace('$', '');
            const score = cells[3].textContent.trim();
            csv += `${ticker},${signal},${price},${score}\n`;
        }
    });
    
    const blob = new Blob([csv], {type: 'text/csv;charset=utf-8;'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `tradescreener_results_${new Date().toISOString().slice(0,10)}.csv`;
    link.click();
    
    showToast('CSV файл скачан', 'success');
}

function clearResults() {
    document.getElementById('resultsTableBody').innerHTML = `
        <tr class="empty-row">
            <td colspan="6">
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>Нет активных сигналов. Запустите скринер.</p>
                </div>
            </td>
        </tr>
    `;
    
    ['long', 'squeeze', 'oversold'].forEach(type => {
        updateBadge(type, 0);
        const grid = document.getElementById(type + 'Results');
        if (grid) grid.innerHTML = '';
    });
    
    showToast('Результаты очищены', 'info');
}

// Арбитраж
let arbitrageChart = null;
let currentPeriod = '1d';

async function initArbitrageChart() {
    // Загрузка данных арбитража
}

// Делаем функции глобальными для onclick в HTML
window.openChartModal = openChartModal;
