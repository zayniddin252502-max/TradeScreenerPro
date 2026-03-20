<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradeScreener Pro</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="logo">
                <i class="fas fa-chart-line"></i>
                <span>TRADE<span class="accent">SCREENER</span></span>
            </div>
            
            <nav class="nav-menu">
                <div class="nav-section">Главная</div>
                <a href="#" class="nav-item active" data-page="dashboard">
                    <i class="fas fa-home"></i>
                    <span>Dashboard</span>
                </a>
                
                <div class="nav-section">Скринеры</div>
                <a href="#" class="nav-item" data-page="long">
                    <i class="fas fa-chart-bar"></i>
                    <span>Long Setups</span>
                </a>
                <a href="#" class="nav-item" data-page="squeeze">
                    <i class="fas fa-compress-arrows-alt"></i>
                    <span>Short Squeeze</span>
                </a>
                <a href="#" class="nav-item" data-page="oversold">
                    <i class="fas fa-arrow-down"></i>
                    <span>Oversold Bounce</span>
                </a>
                
                <div class="nav-section">Анализ</div>
                <a href="#" class="nav-item" data-page="arbitrage">
                    <i class="fas fa-exchange-alt"></i>
                    <span>Арбитраж ES/SPX</span>
                </a>
            </nav>
            
            <div class="sidebar-footer">
                <div class="status-indicator">
                    <span class="dot" id="marketDot"></span>
                    <span id="marketStatusText">Загрузка...</span>
                </div>
                <div class="last-update" id="lastUpdate">--:--</div>
                <div style="margin-top: 8px; font-size: 10px; color: #94a3b8;">
                    NYSE/NASDAQ
                </div>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Economic Events Ticker -->
            <div id="econTickerContainer" class="econ-ticker-container">
                <div class="econ-ticker-label">
                    <i class="fas fa-calendar-alt"></i>
                    <span>Экономические события:</span>
                </div>
                <div class="econ-ticker-wrapper">
                    <div id="econTicker" class="econ-ticker">
                        <span class="ticker-item">Загрузка данных...</span>
                    </div>
                </div>
                <div id="econTickerAlert" class="econ-ticker-alert hidden">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
            </div>

            <!-- Header -->
            <header class="header">
                <div class="search-bar">
                    <i class="fas fa-search"></i>
                    <input type="text" placeholder="Поиск тикеров..." id="searchInput">
                    <span class="shortcut">Ctrl K</span>
                </div>
                
                <div class="header-actions">
                    <div id="economicAlerts" class="economic-alerts"></div>
                    <button class="btn-icon" id="refreshBtn" title="Обновить">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                    <button class="btn-primary" id="runAllBtn">
                        <i class="fas fa-play"></i> Запустить всё
                    </button>
                    
                    <!-- Автозапуск -->
                    <div class="autorun-container">
                        <button class="btn-autorun" id="autorunBtn" title="Настроить автозапуск скринеров">
                            <i class="fas fa-robot"></i>
                            <span>Автозапуск</span>
                            <span class="autorun-status-dot" id="autorunDot"></span>
                        </button>
                        <div class="autorun-dropdown" id="autorunDropdown">
                            <div class="autorun-header">
                                <i class="fas fa-robot"></i>
                                <span>Автозапуск скринеров</span>
                            </div>
                            <div class="autorun-status" id="autorunStatus">
                                <span class="status-off">Выключен</span>
                            </div>
                            <div class="autorun-section">
                                <label>Период запуска:</label>
                                <select id="autorunInterval">
                                    <option value="1">Каждый 1 час</option>
                                    <option value="2">Каждые 2 часа</option>
                                    <option value="3">Каждые 3 часа</option>
                                    <option value="4">Каждые 4 часа</option>
                                    <option value="5">Каждые 5 часов</option>
                                    <option value="6">Каждые 6 часов</option>
                                    <option value="12">Каждые 12 часов</option>
                                    <option value="24">Каждые 24 часа</option>
                                </select>
                            </div>
                            <div class="autorun-section">
                                <label>Скринеры:</label>
                                <div class="autorun-screeners">
                                    <label class="checkbox-label">
                                        <input type="checkbox" value="long" checked>
                                        <span>Long Setups</span>
                                    </label>
                                    <label class="checkbox-label">
                                        <input type="checkbox" value="squeeze" checked>
                                        <span>Short Squeeze</span>
                                    </label>
                                    <label class="checkbox-label">
                                        <input type="checkbox" value="oversold" checked>
                                        <span>Oversold Bounce</span>
                                    </label>
                                </div>
                            </div>
                            <div class="autorun-actions">
                                <button class="btn-autorun-start" id="startAutorunBtn">
                                    <i class="fas fa-play"></i> Запустить
                                </button>
                                <button class="btn-autorun-stop hidden" id="stopAutorunBtn">
                                    <i class="fas fa-stop"></i> Остановить
                                </button>
                                <button class="btn-autorun-now" id="runNowBtn">
                                    <i class="fas fa-bolt"></i> Сейчас
                                </button>
                            </div>
                            <div class="autorun-stats hidden" id="autorunStats">
                                <div class="stat-row">
                                    <span>Запусков:</span>
                                    <strong id="autorunRunCount">0</strong>
                                </div>
                                <div class="stat-row">
                                    <span>Сигналов:</span>
                                    <strong id="autorunSignals">0</strong>
                                </div>
                                <div class="stat-row">
                                    <span>Следующий:</span>
                                    <strong id="autorunNextRun">--:--</strong>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <!-- Economic Calendar Banner -->
            <div id="econCalendarBanner" class="econ-banner hidden">
                <div class="econ-content">
                    <i class="fas fa-exclamation-triangle"></i>
                    <span id="econAlertText"></span>
                </div>
            </div>

            <!-- Market Indices -->
            <div class="indices-bar">
                <div class="index-card" id="spx">
                    <div class="index-name">S&P 500</div>
                    <div class="index-value">--.--</div>
                    <div class="index-change">--.--%</div>
                </div>
                <div class="index-card" id="ndx">
                    <div class="index-name">Nasdaq</div>
                    <div class="index-value">--.--</div>
                    <div class="index-change">--.--%</div>
                </div>
                <div class="index-card" id="dji">
                    <div class="index-name">Dow Jones</div>
                    <div class="index-value">--.--</div>
                    <div class="index-change">--.--%</div>
                </div>
                <div class="index-card" id="rut">
                    <div class="index-name">Russell 2000</div>
                    <div class="index-value">--.--</div>
                    <div class="index-change">--.--%</div>
                </div>
                <div class="index-card vix-card" id="vix">
                    <div class="index-name">VIX</div>
                    <div class="index-value">--.--</div>
                    <div class="index-change">--.--%</div>
                </div>
            </div>

            <!-- Progress Panel -->
            <div id="progressContainer" class="progress-panel hidden">
                <div class="progress-header">
                    <div class="progress-status">
                        <i class="fas fa-spinner fa-spin" id="progressIcon"></i>
                        <span id="progressTitle">Обработка...</span>
                    </div>
                    <span class="progress-percent" id="progressPercent">0%</span>
                </div>
                <div class="progress-bar-bg">
                    <div id="progressBar" class="progress-bar-fill" style="width: 0%"></div>
                </div>
                <div class="progress-details">
                    <span id="progressTicker">-</span>
                    <span id="progressCount">0/0</span>
                </div>
                <div class="progress-logs" id="progressLogs">
                    <div class="log-item">Ожидание запуска...</div>
                </div>
                <div class="progress-actions">
                    <button class="btn-text" id="clearQueueBtn">
                        <i class="fas fa-trash"></i> Очистить очередь
                    </button>
                </div>
            </div>

            <!-- Dashboard Page -->
            <div class="content-wrapper" id="dashboardPage">
                <h1 class="page-title">TradeScreener Dashboard</h1>
                <p class="page-subtitle">Автоматический анализ рынка и скрининг акций</p>

                <!-- Economic Calendar Panel -->
                <div class="panel" style="margin-bottom: 24px;">
                    <div class="panel-header">
                        <h3><i class="fas fa-calendar-alt"></i> Экономический календарь</h3>
                        <span class="badge warning" id="econCount">0 событий</span>
                    </div>
                    <div class="panel-body">
                        <div id="economicCalendarList" class="econ-list">
                            <div class="empty-state">Загрузка данных...</div>
                        </div>
                    </div>
                </div>

                <!-- Ticker Input -->
                <div class="ticker-input-panel">
                    <label>Список тикеров для скрининга (через запятую):</label>
                    <div class="input-group">
                        <textarea id="tickerInput" placeholder="AAPL, MSFT, NVDA, TSLA...">AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD, NFLX, CRM</textarea>
                        <div class="input-actions">
                            <button class="btn-secondary" id="loadSp500Btn">
                                <i class="fas fa-list"></i> S&P 500
                            </button>
                            <button class="btn-secondary" id="clearTickersBtn">
                                <i class="fas fa-eraser"></i> Очистить
                            </button>
                        </div>
                    </div>
                    <div class="ticker-count">Тикеров: <span id="tickerCount">10</span></div>
                </div>

                <!-- Main Cards -->
                <div class="main-cards">
                    <div class="feature-card" id="card-long">
                        <div class="card-icon etf">
                            <i class="fas fa-layer-group"></i>
                        </div>
                        <h3>Long Setups</h3>
                        <p>Поиск долгосрочных сетапов с фундаментальным анализом</p>
                        <div class="card-actions">
                            <button class="btn-card" data-screener="long">
                                <i class="fas fa-play"></i> Запустить
                            </button>
                            <span class="badge" id="longCount">0 сигналов</span>
                        </div>
                    </div>

                    <div class="feature-card" id="card-squeeze">
                        <div class="card-icon options">
                            <i class="fas fa-compress-arrows-alt"></i>
                        </div>
                        <h3>Short Squeeze</h3>
                        <p>Анализ уровней, пробоев и ретестов для свинга</p>
                        <div class="card-actions">
                            <button class="btn-card" data-screener="squeeze">
                                <i class="fas fa-play"></i> Запустить
                            </button>
                            <span class="badge" id="squeezeCount">0 алертов</span>
                        </div>
                    </div>

                    <div class="feature-card highlight" id="card-arbitrage">
                        <div class="card-icon arbitrage">
                            <i class="fas fa-exchange-alt"></i>
                        </div>
                        <h3>Арбитраж</h3>
                        <p>Мониторинг базиса ES vs SPX в реальном времени</p>
                        <div class="card-stats">
                            <span class="badge" id="arbConnection">Подключение...</span>
                        </div>
                    </div>
                </div>

                <!-- Results Panel -->
                <div class="panel">
                    <div class="panel-header">
                        <h3><i class="fas fa-bell"></i> Активные Сигналы</h3>
                        <div class="panel-actions">
                            <button class="btn-text" id="exportBtn">
                                <i class="fas fa-download"></i> Экспорт CSV
                            </button>
                            <button class="btn-text" id="clearAlertsBtn">
                                <i class="fas fa-trash"></i> Очистить
                            </button>
                        </div>
                    </div>
                    <div class="panel-body">
                        <div class="results-table-container">
                            <table class="results-table" id="resultsTable">
                                <thead>
                                    <tr>
                                        <th>Тикер</th>
                                        <th>Сигнал</th>
                                        <th>Цена</th>
                                        <th>Скор</th>
                                        <th>Данные</th>
                                        <th>График</th>
                                    </tr>
                                </thead>
                                <tbody id="resultsTableBody">
                                    <tr class="empty-row">
                                        <td colspan="6">
                                            <div class="empty-state">
                                                <i class="fas fa-inbox"></i>
                                                <p>Нет активных сигналов. Запустите скринер.</p>
                                            </div>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Long Screener Page -->
            <div class="content-wrapper hidden" id="longPage">
                <div class="page-header">
                    <h1>Long Setups Screener</h1>
                    <button class="btn-primary" data-screener="long" id="btn-long-page">
                        <i class="fas fa-play"></i> Запустить скрининг
                    </button>
                </div>
                <div class="results-grid" id="longResults"></div>
            </div>

            <!-- Squeeze Page -->
            <div class="content-wrapper hidden" id="squeezePage">
                <div class="page-header">
                    <h1>Short Squeeze Screener</h1>
                    <button class="btn-primary" data-screener="squeeze" id="btn-squeeze-page">
                        <i class="fas fa-play"></i> Запустить скрининг
                    </button>
                </div>
                <div class="results-grid" id="squeezeResults"></div>
            </div>

            <!-- Oversold Page -->
            <div class="content-wrapper hidden" id="oversoldPage">
                <div class="page-header">
                    <h1>Oversold Bounce Screener</h1>
                    <button class="btn-primary" data-screener="oversold" id="btn-oversold-page">
                        <i class="fas fa-play"></i> Запустить скрининг
                    </button>
                </div>
                <div class="results-grid" id="oversoldResults"></div>
            </div>

            <!-- Arbitrage Page -->
            <div class="content-wrapper hidden" id="arbitragePage">
                <div class="page-header">
                    <div>
                        <h1>Арбитраж Монитор <span id="arbLiveBadge" class="live-badge-small">LIVE</span></h1>
                        <span class="update-time" id="arbLastUpdate">--</span>
                        <div id="arbConnectionStatus" style="font-size: 12px; margin-top: 4px; color: var(--text-secondary);">
                            Подключение к Yahoo Finance...
                        </div>
                    </div>
                    <div class="header-actions-group">
                        <button class="btn-secondary" id="saveArbBtn">
                            <i class="fas fa-save"></i> Сохранить историю
                        </button>
                        <button class="btn-icon" id="refreshArbBtn" title="Обновить сейчас">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Arbitrage Stats -->
                <div class="arbitrage-stats" id="arbStats">
                    <div class="stat-card">
                        <span>Всего точек</span>
                        <strong id="arbTotalPoints">0</strong>
                    </div>
                    <div class="stat-card">
                        <span>Период данных</span>
                        <strong id="arbDateRange">--</strong>
                    </div>
                    <div class="stat-card">
                        <span>Текущий базис</span>
                        <strong id="arbCurrentBasis">--</strong>
                    </div>
                    <div class="stat-card">
                        <span>Сигнал</span>
                        <strong id="arbCurrentSignal">--</strong>
                    </div>
                </div>
                
                <!-- Period Selector -->
                <div class="period-selector">
                    <button class="period-btn active" data-period="1d">1 день</button>
                    <button class="period-btn" data-period="7d">7 дней</button>
                    <button class="period-btn" data-period="30d">30 дней</button>
                    <button class="period-btn" data-period="90d">90 дней</button>
                    <button class="period-btn" data-period="all">2 года</button>
                </div>
                
                <div class="chart-container" id="basisChart"></div>
            </div>
        </main>
    </div>

    <!-- Chart Modal -->
    <div id="chartModal" class="modal hidden">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">
                    <h2 id="modalTicker">TICKER</h2>
                    <span id="modalCompany" class="company-name">Company Name</span>
                </div>
                <div class="modal-info">
                    <span id="modalSector" class="badge">Sector</span>
                    <span id="modalPrice" class="price-badge">$0.00</span>
                </div>
                <button class="btn-close" id="closeModalBtn">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div id="chartContainer" class="chart-area"></div>
            </div>
        </div>
    </div>

    <!-- Toast Notifications -->
    <div class="toast-container" id="toastContainer"></div>

    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
