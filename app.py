"""
TradeScreener Pro - Главный файл приложения
Версия с бегущей строкой экономических данных (FOMC, FED, NONFARM)
"""

from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, timezone
import threading
import time
import json
import os
import csv
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Импорт модулей скринеров
from modules.arbitrage import ArbitrageMonitor
from modules.long_screener import LongScreener
from modules.squeeze_screener import SqueezeScreener
from modules.oversold_screener import OversoldScreener

app = Flask(__name__)

# Получение порта из переменных окружения (для Render)
PORT = int(os.environ.get("PORT", "5000"))

# Создаем папки для сохранения данных
os.makedirs('results', exist_ok=True)
os.makedirs('history', exist_ok=True)

HISTORY_FILE = 'history/arbitrage_history.json'
MAX_HISTORY_DAYS = 730

# ========== ЭКОНОМИЧЕСКИЙ КАЛЕНДАРЬ ==========
# Важные события для рынка акций США
# Настройки предупреждений
ECONOMIC_ALERT_SETTINGS = {
    'critical_days': 1,      # Красный: за 1 день (сегодня/завтра)
    'warning_days': 3,       # Оранжевый: за 3 дня
    'info_days': 14,         # Обычный: за 14 дней
    'ticker_days': 30        # Бегущая строка: за 30 дней
}

# Даты важных экономических событий 2025-2026
ECONOMIC_CALENDAR = [
    # ========== FOMC MEETINGS (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    # FOMC Statement - заявление по процентной ставке
    {'date': '2025-01-29', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    {'date': '2025-03-19', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    {'date': '2025-05-07', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    {'date': '2025-06-18', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    {'date': '2025-07-30', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    {'date': '2025-09-17', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    {'date': '2025-11-06', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    {'date': '2025-12-17', 'time': '14:00', 'event': 'FOMC Statement', 'impact': 'high', 'symbol': '🏦', 'type': 'FOMC'},
    
    # FOMC Minutes - протоколы заседаний (через 3 недели)
    {'date': '2025-02-19', 'time': '14:00', 'event': 'FOMC Minutes', 'impact': 'high', 'symbol': '📋', 'type': 'FOMC-MINUTES'},
    {'date': '2025-04-09', 'time': '14:00', 'event': 'FOMC Minutes', 'impact': 'high', 'symbol': '📋', 'type': 'FOMC-MINUTES'},
    {'date': '2025-05-28', 'time': '14:00', 'event': 'FOMC Minutes', 'impact': 'high', 'symbol': '📋', 'type': 'FOMC-MINUTES'},
    {'date': '2025-07-09', 'time': '14:00', 'event': 'FOMC Minutes', 'impact': 'high', 'symbol': '📋', 'type': 'FOMC-MINUTES'},
    {'date': '2025-08-27', 'time': '14:00', 'event': 'FOMC Minutes', 'impact': 'high', 'symbol': '📋', 'type': 'FOMC-MINUTES'},
    {'date': '2025-10-08', 'time': '14:00', 'event': 'FOMC Minutes', 'impact': 'high', 'symbol': '📋', 'type': 'FOMC-MINUTES'},
    {'date': '2025-11-26', 'time': '14:00', 'event': 'FOMC Minutes', 'impact': 'high', 'symbol': '📋', 'type': 'FOMC-MINUTES'},
    
    # ========== NON-FARM PAYROLLS (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    # Первые пятницы месяца, 8:30 ET
    {'date': '2025-04-04', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-05-02', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-06-06', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-07-03', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-08-01', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-09-05', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-10-03', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-11-07', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    {'date': '2025-12-05', 'time': '08:30', 'event': 'Non-Farm Payrolls', 'impact': 'high', 'symbol': '💼', 'type': 'NFP'},
    
    # ========== CPI - Consumer Price Index (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    # Около 10-15 числа каждого месяца, 8:30 ET
    {'date': '2025-04-10', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-05-13', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-06-11', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-07-15', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-08-12', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-09-11', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-10-15', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-11-12', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    {'date': '2025-12-11', 'time': '08:30', 'event': 'CPI m/m', 'impact': 'high', 'symbol': '📈', 'type': 'CPI'},
    
    # ========== PPI - Producer Price Index (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    # Около 11-14 числа каждого месяца, 8:30 ET
    {'date': '2025-04-11', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-05-13', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-06-12', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-07-15', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-08-13', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-09-11', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-10-14', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-11-13', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    {'date': '2025-12-12', 'time': '08:30', 'event': 'PPI m/m', 'impact': 'high', 'symbol': '🏭', 'type': 'PPI'},
    
    # ========== GDP - Gross Domestic Product (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    # Ежеквартально, предварительные данные
    {'date': '2025-04-30', 'time': '08:30', 'event': 'GDP q/q (Preliminary)', 'impact': 'high', 'symbol': '🇺🇸', 'type': 'GDP'},
    {'date': '2025-07-30', 'time': '08:30', 'event': 'GDP q/q (Preliminary)', 'impact': 'high', 'symbol': '🇺🇸', 'type': 'GDP'},
    {'date': '2025-10-30', 'time': '08:30', 'event': 'GDP q/q (Preliminary)', 'impact': 'high', 'symbol': '🇺🇸', 'type': 'GDP'},
    
    # ========== RETAIL SALES (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    # Около 15 числа каждого месяца, 8:30 ET
    {'date': '2025-04-15', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-05-15', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-06-17', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-07-16', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-08-15', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-09-16', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-10-16', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-11-14', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    {'date': '2025-12-16', 'time': '08:30', 'event': 'Retail Sales m/m', 'impact': 'high', 'symbol': '🛒', 'type': 'RETAIL'},
    
    # ========== INITIAL JOBLESS CLAIMS (СРЕДНЕЕ ВЛИЯНИЕ) ==========
    # Каждый четверг, 8:30 ET
    {'date': '2025-04-03', 'time': '08:30', 'event': 'Initial Jobless Claims', 'impact': 'medium', 'symbol': '📋', 'type': 'JOBLESS'},
    {'date': '2025-04-10', 'time': '08:30', 'event': 'Initial Jobless Claims', 'impact': 'medium', 'symbol': '📋', 'type': 'JOBLESS'},
    {'date': '2025-04-17', 'time': '08:30', 'event': 'Initial Jobless Claims', 'impact': 'medium', 'symbol': '📋', 'type': 'JOBLESS'},
    {'date': '2025-04-24', 'time': '08:30', 'event': 'Initial Jobless Claims', 'impact': 'medium', 'symbol': '📋', 'type': 'JOBLESS'},
    
    # ========== FED CHAIR POWELL SPEECHES (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    {'date': '2025-03-07', 'time': '10:00', 'event': 'Fed Chair Powell Testimony', 'impact': 'high', 'symbol': '🎤', 'type': 'FED'},
    {'date': '2025-06-24', 'time': '10:00', 'event': 'Fed Chair Powell Testimony', 'impact': 'high', 'symbol': '🎤', 'type': 'FED'},
    {'date': '2025-07-16', 'time': '14:00', 'event': 'Fed Chair Powell Speech', 'impact': 'high', 'symbol': '🎤', 'type': 'FED'},
    {'date': '2025-08-22', 'time': '10:00', 'event': 'Fed Chair Powell (Jackson Hole)', 'impact': 'high', 'symbol': '🎤', 'type': 'FED'},
    
    # ========== ISM MANUFACTURING (СРЕДНЕЕ ВЛИЯНИЕ) ==========
    {'date': '2025-04-01', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-05-01', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-06-02', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-07-01', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-08-01', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-09-02', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-10-01', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-11-03', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    {'date': '2025-12-01', 'time': '10:00', 'event': 'ISM Manufacturing PMI', 'impact': 'medium', 'symbol': '🏭', 'type': 'ISM'},
    
    # ========== CONSUMER CONFIDENCE (СРЕДНЕЕ ВЛИЯНИЕ) ==========
    {'date': '2025-04-29', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    {'date': '2025-05-27', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    {'date': '2025-06-24', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    {'date': '2025-07-29', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    {'date': '2025-08-26', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    {'date': '2025-09-30', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    {'date': '2025-10-28', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    {'date': '2025-11-25', 'time': '10:00', 'event': 'Consumer Confidence', 'impact': 'medium', 'symbol': '💰', 'type': 'CONFIDENCE'},
    
    # ========== HOUSING STARTS (СРЕДНЕЕ ВЛИЯНИЕ) ==========
    {'date': '2025-04-17', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    {'date': '2025-05-16', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    {'date': '2025-06-17', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    {'date': '2025-07-17', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    {'date': '2025-08-19', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    {'date': '2025-09-17', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    {'date': '2025-10-17', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    {'date': '2025-11-18', 'time': '08:30', 'event': 'Housing Starts', 'impact': 'medium', 'symbol': '🏠', 'type': 'HOUSING'},
    
    # ========== INDUSTRIAL PRODUCTION (СРЕДНЕЕ ВЛИЯНИЕ) ==========
    {'date': '2025-04-16', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    {'date': '2025-05-15', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    {'date': '2025-06-17', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    {'date': '2025-07-16', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    {'date': '2025-08-15', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    {'date': '2025-09-16', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    {'date': '2025-10-16', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    {'date': '2025-11-14', 'time': '09:15', 'event': 'Industrial Production', 'impact': 'medium', 'symbol': '⚙️', 'type': 'INDUSTRIAL'},
    
    # ========== UNEMPLOYMENT RATE (ВЫСОКОЕ ВЛИЯНИЕ) ==========
    {'date': '2025-04-04', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-05-02', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-06-06', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-07-03', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-08-01', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-09-05', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-10-03', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-11-07', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
    {'date': '2025-12-05', 'time': '08:30', 'event': 'Unemployment Rate', 'impact': 'high', 'symbol': '📉', 'type': 'UNEMPLOYMENT'},
]

# Глобальное состояние
screening_state = {
    'queue': [],
    'running': False,
    'current_job': None,
    'progress': {'job_id': None, 'current': 0, 'total': 0, 'ticker': '', 'status': 'idle', 'percent': 0},
    'results': {},
    'logs': []
}

# Состояние автозапуска
autorun_state = {
    'enabled': False,
    'interval_hours': 1,
    'tickers': [],
    'screeners': ['long', 'squeeze', 'oversold'],
    'last_run': None,
    'next_run': None,
    'run_count': 0,
    'total_signals_found': 0
}
autorun_lock = threading.Lock()

arbitrage_history = []
last_arbitrage_update = None
history_lock = threading.Lock()

arb_monitor = ArbitrageMonitor()
long_screener = LongScreener()
squeeze_screener = SqueezeScreener()
oversold_screener = OversoldScreener()

lock = threading.Lock()

def get_ny_time():
    """Получить текущее время в Нью-Йорке (EST/EDT)"""
    # Получаем UTC время
    utc_now = datetime.now(timezone.utc)
    # EST = UTC-5, EDT = UTC-4 (летнее время)
    # Для простоты используем EST (UTC-5) - зимнее время
    # Летнее время: UTC-4 (март-ноябрь)
    
    # Определяем, действует ли сейчас летнее время (EDT)
    # EDT: второе воскресенье марта - первое воскресенье ноября
    year = utc_now.year
    
    # Второе воскресенье марта
    march_second_sunday = datetime(year, 3, 8, 7, 0, tzinfo=timezone.utc)  # 2:00 AM EST = 7:00 AM UTC
    while march_second_sunday.weekday() != 6:  # 6 = воскресенье
        march_second_sunday += timedelta(days=1)
    
    # Первое воскресенье ноября
    november_first_sunday = datetime(year, 11, 1, 6, 0, tzinfo=timezone.utc)  # 1:00 AM EST = 6:00 AM UTC
    while november_first_sunday.weekday() != 6:
        november_first_sunday += timedelta(days=1)
    
    # Проверяем, действует ли EDT
    is_edt = march_second_sunday <= utc_now < november_first_sunday
    
    # Смещение: EST = -5, EDT = -4
    offset_hours = -4 if is_edt else -5
    
    ny_time = utc_now + timedelta(hours=offset_hours)
    return ny_time, offset_hours

def is_market_open():
    """Проверка открыт ли рынок NYSE (по времени Нью-Йорка)"""
    ny_time, offset = get_ny_time()
    weekday = ny_time.weekday()
    
    # Выходные: суббота(5), воскресенье(6)
    if weekday >= 5:
        return False
    
    # Рынок открыт: 9:30 - 16:00 EST/EDT
    hour = ny_time.hour
    minute = ny_time.minute
    
    # 9:30 = открытие
    if hour == 9 and minute >= 30:
        return True
    if 10 <= hour < 16:
        return True
    
    return False

def get_next_market_open():
    """Время до открытия рынка"""
    ny_time, offset = get_ny_time()
    
    if is_market_open():
        return "Открыт", "var(--success)"
    
    # Находим следующий рабочий день
    next_day = ny_time
    days_added = 0
    while next_day.weekday() >= 5:  # Пропускаем выходные
        next_day += timedelta(days=1)
        days_added += 1
    
    # Если сегодня будний день, но рынок уже закрылся
    if days_added == 0 and ny_time.hour >= 16:
        next_day += timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
    
    return f"Закрыт (откроется {next_day.strftime('%d.%m')} 9:30)", "var(--danger)"

def get_economic_events_for_ticker():
    """
    Получение экономических событий для бегущей строки
    Возвращает события с информацией о днях до события
    """
    now = datetime.now()
    upcoming = []
    settings = ECONOMIC_ALERT_SETTINGS
    
    for event in ECONOMIC_CALENDAR:
        event_date = datetime.strptime(event['date'], '%Y-%m-%d')
        days_until = (event_date - now).days
        hours_until = days_until * 24 + (event_date.hour - now.hour)
        
        # Показываем события в пределах ticker_days (30 дней)
        if -1 <= days_until <= settings['ticker_days']:
            is_today = days_until == 0
            is_tomorrow = days_until == 1
            is_this_week = days_until <= 7
            
            # Определяем уровень предупреждения
            if days_until <= settings['critical_days']:
                alert_level = 'critical'  # Красный: сегодня/завтра
            elif days_until <= settings['warning_days']:
                alert_level = 'warning'   # Оранжевый: 2-3 дня
            else:
                alert_level = 'info'      # Обычный: > 3 дней
            
            upcoming.append({
                **event,
                'days_until': days_until,
                'hours_until': hours_until,
                'is_today': is_today,
                'is_tomorrow': is_tomorrow,
                'is_this_week': is_this_week,
                'urgent': days_until <= settings['critical_days'],
                'alert_level': alert_level
            })
    
    return sorted(upcoming, key=lambda x: x['days_until'])

def check_upcoming_events():
    """Проверка приближающихся важных событий для панели"""
    now = datetime.now()
    upcoming = []
    settings = ECONOMIC_ALERT_SETTINGS
    
    for event in ECONOMIC_CALENDAR:
        event_date = datetime.strptime(event['date'], '%Y-%m-%d')
        days_until = (event_date - now).days
        
        # Показываем события в пределах info_days (14 дней)
        if 0 <= days_until <= settings['info_days']:
            # Определяем уровень предупреждения
            if days_until <= settings['critical_days']:
                alert_level = 'critical'
            elif days_until <= settings['warning_days']:
                alert_level = 'warning'
            else:
                alert_level = 'info'
            
            upcoming.append({
                **event,
                'days_until': days_until,
                'urgent': days_until <= settings['critical_days'],
                'alert_level': alert_level
            })
    
    return sorted(upcoming, key=lambda x: x['days_until'])

def save_screening_to_excel(job_id, results, screener_type):
    """Сохранение результатов скрининга в CSV"""
    if not results:
        return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{screener_type}_{timestamp}_{job_id}.csv"
    filepath = os.path.join('results', filename)
    
    try:
        if len(results) > 0:
            fieldnames = list(results[0].keys())
        else:
            fieldnames = ['ticker', 'grade', 'price', 'score']
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
        
        print(f"💾 Сохранено: {filepath}")
        return filepath
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return None

def log_message(msg):
    with lock:
        timestamp = datetime.now().strftime('%H:%M:%S')
        screening_state['logs'].insert(0, f"[{timestamp}] {msg}")
        if len(screening_state['logs']) > 50:
            screening_state['logs'] = screening_state['logs'][:50]

def load_arbitrage_history():
    global arbitrage_history, last_arbitrage_update
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                arbitrage_history = data.get('data', [])
                last_update = data.get('last_update')
                if last_update:
                    last_arbitrage_update = datetime.fromisoformat(last_update)
                print(f"✅ Загружено {len(arbitrage_history)} точек истории")
                clean_old_history()
        else:
            arbitrage_history = []
    except Exception as e:
        print(f"❌ Ошибка загрузки истории: {e}")
        arbitrage_history = []

def save_arbitrage_history():
    try:
        with history_lock:
            data = {
                'last_update': datetime.now().isoformat(),
                'count': len(arbitrage_history),
                'data': arbitrage_history
            }
            temp_file = HISTORY_FILE + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, HISTORY_FILE)
            return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def clean_old_history():
    global arbitrage_history
    cutoff_date = datetime.now() - timedelta(days=MAX_HISTORY_DAYS)
    original_count = len(arbitrage_history)
    arbitrage_history = [
        item for item in arbitrage_history 
        if datetime.fromisoformat(item.get('timestamp', '2000-01-01')) > cutoff_date
    ]
    if len(arbitrage_history) < original_count:
        print(f"🧹 Удалено {original_count - len(arbitrage_history)} старых точек")

def auto_save_worker():
    while True:
        time.sleep(300)
        if arbitrage_history:
            if save_arbitrage_history():
                print(f"💾 Автосохранение: {len(arbitrage_history)} точек")

def worker_thread():
    """Главный поток - выполняет задачи последовательно (чтобы не банили)"""
    while True:
        job = None
        
        with lock:
            if screening_state['queue'] and not screening_state['running']:
                job = screening_state['queue'].pop(0)
                screening_state['running'] = True
                screening_state['current_job'] = job
        
        if job:
            job_id = job['id']
            screener_type = job['type']
            tickers = job['tickers']
            
            log_message(f"🚀 Старт {screener_type}: {len(tickers)} тикеров")
            screening_state['progress'] = {
                'job_id': job_id, 'current': 0, 'total': len(tickers), 
                'ticker': '-', 'status': 'running', 'percent': 0
            }
            
            results = []
            start_time = time.time()
            
            try:
                for i, ticker in enumerate(tickers):
                    try:
                        screening_state['progress'].update({
                            'current': i + 1,
                            'ticker': ticker,
                            'percent': round((i + 1) / len(tickers) * 100, 1)
                        })
                        
                        if i % 10 == 0:
                            log_message(f"Прогресс: {i+1}/{len(tickers)}...")
                        
                        result = None
                        if screener_type == 'long':
                            result = long_screener.analyze_ticker(ticker)
                        elif screener_type == 'squeeze':
                            result = squeeze_screener.analyze_ticker(ticker)
                        elif screener_type == 'oversold':
                            result = oversold_screener.analyze_ticker(ticker)
                        
                        if result and result.get('grade') not in ['PASS', '👀 WATCH', '❌ DOWNTREND']:
                            results.append(result)
                            log_message(f"✅ Сигнал: {ticker} - {result.get('grade')}")
                        
                        # Задержка между тикерами чтобы не банили
                        if i < len(tickers) - 1:
                            time.sleep(0.5)
                            
                    except Exception as e:
                        log_message(f"❌ {ticker}: {str(e)[:30]}")
                        continue
                
                elapsed = round(time.time() - start_time, 1)
                
                saved_file = save_screening_to_excel(job_id, results, screener_type)
                if saved_file:
                    log_message(f"💾 Сохранено в: {os.path.basename(saved_file)}")
                
                with lock:
                    screening_state['results'][job_id] = {
                        'type': screener_type,
                        'completed_at': datetime.now().isoformat(),
                        'elapsed_seconds': elapsed,
                        'saved_file': saved_file,
                        'count': len(results),
                        'data': sorted(results, key=lambda x: x.get('score', 0), reverse=True)
                    }
                
                screening_state['progress']['status'] = 'completed'
                screening_state['progress']['percent'] = 100
                
                log_message(f"✨ Готово! {len(results)} сигналов за {elapsed}s")
                
            except Exception as e:
                log_message(f"🔥 Ошибка: {str(e)[:50]}")
            
            finally:
                # Важно: сбрасываем флаг running чтобы следующая задача запустилась
                with lock:
                    screening_state['running'] = False
                    screening_state['current_job'] = None
        
        time.sleep(0.5)

def autorun_worker():
    """Рабочий поток автозапуска скринеров"""
    global autorun_state
    
    while True:
        try:
            with autorun_lock:
                if not autorun_state['enabled']:
                    time.sleep(5)
                    continue
                
                now = datetime.now()
                
                # Проверяем, нужно ли запустить
                if autorun_state['next_run'] is None:
                    # Первый запуск - через interval_hours
                    autorun_state['next_run'] = now + timedelta(hours=autorun_state['interval_hours'])
                    log_message(f"⏰ Автозапуск активирован. Следующий запуск: {autorun_state['next_run'].strftime('%H:%M:%S')}")
                    continue
                
                # Проверяем время следующего запуска
                if now >= autorun_state['next_run']:
                    # Проверяем, не идет ли уже скрининг
                    if screening_state['running'] or screening_state['queue']:
                        log_message("⏳ Автозапуск отложен - скрининг уже выполняется")
                        # Откладываем на 5 минут
                        autorun_state['next_run'] = now + timedelta(minutes=5)
                        continue
                    
                    # Запускаем все скринеры
                    log_message(f"🤖 Автозапуск #{autorun_state['run_count'] + 1} начинается...")
                    
                    tickers = autorun_state['tickers']
                    screeners = autorun_state['screeners']
                    total_signals = 0
                    
                    for screener_type in screeners:
                        try:
                            job_id = f"auto_{screener_type}_{now.strftime('%H%M%S')}"
                            
                            with lock:
                                screening_state['queue'].append({
                                    'id': job_id,
                                    'type': screener_type,
                                    'tickers': tickers.copy(),
                                    'added_at': datetime.now().isoformat(),
                                    'is_autorun': True
                                })
                            
                            log_message(f"📥 Автозапуск: добавлен {screener_type}")
                            
                            # Ждем завершения этого скринера
                            max_wait = 3600  # Максимум 1 час на скринер
                            wait_start = time.time()
                            
                            while time.time() - wait_start < max_wait:
                                with lock:
                                    job_done = job_id in screening_state['results']
                                    job_running = screening_state['current_job'] and screening_state['current_job']['id'] == job_id
                                    
                                    if job_done:
                                        result = screening_state['results'][job_id]
                                        signals = result.get('count', 0)
                                        total_signals += signals
                                        log_message(f"✅ Автозапуск {screener_type}: {signals} сигналов")
                                        break
                                    elif not job_running and job_id not in [j['id'] for j in screening_state['queue']]:
                                        # Задача пропала из очереди без результата
                                        log_message(f"⚠️ Автозапуск {screener_type}: задача не выполнена")
                                        break
                                
                                time.sleep(1)
                            
                            # Небольшая пауза между скринерами
                            time.sleep(3)
                            
                        except Exception as e:
                            log_message(f"❌ Автозапуск {screener_type}: ошибка - {str(e)[:50]}")
                            continue
                    
                    # Обновляем статистику
                    with autorun_lock:
                        autorun_state['last_run'] = now
                        autorun_state['run_count'] += 1
                        autorun_state['total_signals_found'] += total_signals
                        autorun_state['next_run'] = now + timedelta(hours=autorun_state['interval_hours'])
                    
                    log_message(f"🎯 Автозапуск завершен! Всего сигналов: {total_signals}")
                    log_message(f"⏰ Следующий запуск: {autorun_state['next_run'].strftime('%H:%M:%S')}")
            
            time.sleep(10)  # Проверяем каждые 10 секунд
            
        except Exception as e:
            log_message(f"🔥 Ошибка автозапуска: {str(e)[:50]}")
            time.sleep(30)

# Запуск рабочих потоков
load_arbitrage_history()
save_worker = threading.Thread(target=auto_save_worker, daemon=True)
save_worker.start()
worker = threading.Thread(target=worker_thread, daemon=True)
worker.start()
autorun_worker_thread = threading.Thread(target=autorun_worker, daemon=True)
autorun_worker_thread.start()

# ========== API ROUTES ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/market-status')
def market_status():
    """Статус рынка NYSE/NASDAQ"""
    ny_time, offset = get_ny_time()
    is_open = is_market_open()
    status_text, color = get_next_market_open()
    
    # Определяем сессию
    hour = ny_time.hour
    if hour < 9 or (hour == 9 and ny_time.minute < 30):
        session = 'Pre-market'
    elif is_open:
        session = 'Market'
    else:
        session = 'After-hours'
    
    return jsonify({
        'is_open': is_open,
        'status_text': status_text,
        'color': color,
        'time': ny_time.strftime('%H:%M'),
        'market': 'NYSE/NASDAQ',
        'session': session,
        'timezone': f'GMT{offset:+d}' if offset < 0 else f'GMT+{offset}',
        'your_local_time': datetime.now().strftime('%H:%M')
    })

@app.route('/api/economic-calendar')
def economic_calendar():
    """Ближайшие экономические события для панели"""
    events = check_upcoming_events()
    return jsonify({
        'events': events,
        'now': datetime.now().isoformat()
    })

@app.route('/api/economic-ticker')
def economic_ticker():
    """Данные для бегущей строки экономических событий"""
    events = get_economic_events_for_ticker()
    settings = ECONOMIC_ALERT_SETTINGS
    
    # Проверяем есть ли критические события (сегодня или завтра)
    has_critical = any(e['alert_level'] in ['critical', 'warning'] for e in events)
    
    # Считаем события по уровням
    critical_count = sum(1 for e in events if e['alert_level'] == 'critical')
    warning_count = sum(1 for e in events if e['alert_level'] == 'warning')
    info_count = sum(1 for e in events if e['alert_level'] == 'info')
    
    return jsonify({
        'events': events,
        'has_critical': has_critical,
        'now': datetime.now().isoformat(),
        'next_event': events[0] if events else None,
        'settings': settings,
        'counts': {
            'critical': critical_count,
            'warning': warning_count,
            'info': info_count,
            'total': len(events)
        }
    })

@app.route('/api/economic-events')
def get_all_economic_events():
    """Получить все экономические события с фильтрацией"""
    event_type = request.args.get('type', 'all')
    impact = request.args.get('impact', 'all')
    days = request.args.get('days', 30, type=int)
    
    now = datetime.now()
    filtered_events = []
    
    for event in ECONOMIC_CALENDAR:
        event_date = datetime.strptime(event['date'], '%Y-%m-%d')
        days_until = (event_date - now).days
        
        # Фильтр по дням
        if days_until < -1 or days_until > days:
            continue
        
        # Фильтр по типу
        if event_type != 'all' and event['type'] != event_type:
            continue
        
        # Фильтр по влиянию
        if impact != 'all' and event['impact'] != impact:
            continue
        
        filtered_events.append({
            **event,
            'days_until': days_until,
            'is_past': days_until < 0
        })
    
    # Группировка по типам
    events_by_type = {}
    for event in filtered_events:
        event_type_key = event['type']
        if event_type_key not in events_by_type:
            events_by_type[event_type_key] = []
        events_by_type[event_type_key].append(event)
    
    return jsonify({
        'events': sorted(filtered_events, key=lambda x: x['days_until']),
        'events_by_type': events_by_type,
        'counts': {
            'total': len(filtered_events),
            'by_type': {k: len(v) for k, v in events_by_type.items()}
        },
        'settings': ECONOMIC_ALERT_SETTINGS,
        'event_types': list(set(e['type'] for e in ECONOMIC_CALENDAR)),
        'impact_levels': ['high', 'medium', 'low']
    })

@app.route('/api/market-indices')
def market_indices():
    try:
        indices = {
            'SPX': yf.Ticker('^GSPC').history(period='1d'),
            'NDX': yf.Ticker('^IXIC').history(period='1d'),
            'DJI': yf.Ticker('^DJI').history(period='1d'),
            'RUT': yf.Ticker('^RUT').history(period='1d'),
            'VIX': yf.Ticker('^VIX').history(period='1d')
        }
        
        result = {'timestamp': datetime.now().isoformat(), 'data': {}}
        
        for name, data in indices.items():
            if not data.empty and data['Open'].iloc[-1] != 0:
                close_val = float(data['Close'].iloc[-1])
                open_val = float(data['Open'].iloc[-1])
                change = ((close_val - open_val) / open_val) * 100
                last_update = data.index[-1].strftime('%H:%M') if hasattr(data.index[-1], 'strftime') else '--:--'
                
                result['data'][name] = {
                    'value': round(close_val, 2),
                    'change': round(change, 2),
                    'positive': bool(change >= 0),
                    'last_update': last_update
                }
            else:
                result['data'][name] = {'value': 0, 'change': 0, 'positive': False, 'last_update': '--:--'}
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/arbitrage')
def arbitrage_data():
    global arbitrage_history, last_arbitrage_update
    
    try:
        data = arb_monitor.get_current_basis()
        current_time = datetime.now()
        
        if data.get('error') or data.get('basis_pct') == 0:
            return jsonify({
                'error': 'No data from Yahoo Finance',
                'connected': False,
                'timestamp': current_time.isoformat(),
                'time': current_time.strftime('%H:%M:%S'),
                'history': arbitrage_history[-100:] if arbitrage_history else []
            })
        
        data['timestamp'] = current_time.isoformat()
        data['time'] = current_time.strftime('%H:%M:%S')
        data['date'] = current_time.strftime('%Y-%m-%d')
        data['connected'] = True
        
        with history_lock:
            arbitrage_history.append({
                'time': current_time.strftime('%H:%M'),
                'date': current_time.strftime('%Y-%m-%d'),
                'datetime': current_time.strftime('%Y-%m-%d %H:%M'),
                'basis': data['basis_pct'],
                'z_score': data.get('z_score', 0),
                'vix': data.get('vix', 0),
                'es_price': data.get('es_price', 0),
                'spx_price': data.get('spx_price', 0),
                'signal': data.get('signal', 'NEUTRAL'),
                'timestamp': current_time.isoformat()
            })
            
            if len(arbitrage_history) > 500000:
                arbitrage_history = arbitrage_history[-450000:]
            
            last_arbitrage_update = current_time
        
        now = datetime.now()
        periods = {
            '1d': [x for x in arbitrage_history if datetime.fromisoformat(x['timestamp']) > now - timedelta(days=1)],
            '7d': [x for x in arbitrage_history if datetime.fromisoformat(x['timestamp']) > now - timedelta(days=7)],
            '30d': [x for x in arbitrage_history if datetime.fromisoformat(x['timestamp']) > now - timedelta(days=30)],
            '90d': [x for x in arbitrage_history if datetime.fromisoformat(x['timestamp']) > now - timedelta(days=90)],
            'all': arbitrage_history
        }
        
        stats = {}
        if arbitrage_history:
            recent = [x['basis'] for x in arbitrage_history[-1000:]]
            stats = {
                'total_points': len(arbitrage_history),
                'first_date': arbitrage_history[0]['date'] if arbitrage_history else None,
                'last_date': arbitrage_history[-1]['date'] if arbitrage_history else None,
                'avg_basis': round(np.mean(recent), 4) if recent else 0,
                'max_basis': round(max(recent), 4) if recent else 0,
                'min_basis': round(min(recent), 4) if recent else 0,
            }
        
        data['periods'] = periods
        data['stats'] = stats
        data['history'] = arbitrage_history[-100:]
        
        return jsonify(data)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'connected': False,
            'timestamp': datetime.now().isoformat(),
            'history': arbitrage_history[-100:] if arbitrage_history else []
        }), 500

@app.route('/api/arbitrage/save', methods=['POST'])
def force_save_arbitrage():
    success = save_arbitrage_history()
    return jsonify({
        'success': success,
        'points_saved': len(arbitrage_history),
        'file': HISTORY_FILE
    })

@app.route('/api/chart-data/<ticker>')
def chart_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        
        if hist.empty:
            return jsonify({'error': 'No data'}), 404
        
        data = {
            'ticker': ticker,
            'dates': hist.index.strftime('%Y-%m-%d').tolist(),
            'open': hist['Open'].tolist(),
            'high': hist['High'].tolist(),
            'low': hist['Low'].tolist(),
            'close': hist['Close'].tolist(),
            'volume': hist['Volume'].tolist(),
            'sma20': hist['Close'].rolling(20).mean().fillna(0).tolist(),
            'sma50': hist['Close'].rolling(50).mean().fillna(0).tolist()
        }
        
        info = stock.info
        data['info'] = {
            'name': info.get('longName', ticker),
            'sector': info.get('sector', '-'),
            'marketCap': info.get('marketCap', 0),
            'pe': info.get('trailingPE', None),
            'dividend': info.get('dividendYield', None)
        }
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/queue/add', methods=['POST'])
def add_to_queue():
    data = request.json
    screener_type = data.get('type', 'long')
    tickers = data.get('tickers', [])
    
    if not tickers:
        return jsonify({'error': 'No tickers provided'}), 400
    
    if len(tickers) > 1000:
        return jsonify({'error': 'Max 1000 tickers allowed'}), 400
    
    job_id = f"{screener_type}_{datetime.now().strftime('%H%M%S')}_{len(tickers)}"
    
    with lock:
        screening_state['queue'].append({
            'id': job_id,
            'type': screener_type,
            'tickers': tickers,
            'added_at': datetime.now().isoformat()
        })
        queue_pos = len(screening_state['queue'])
    
    log_message(f"📥 Добавлено: {job_id} ({len(tickers)} тикеров)")
    
    return jsonify({
        'success': True,
        'job_id': job_id,
        'queue_position': queue_pos,
        'estimated_minutes': round(len(tickers) * 0.5 / 60, 1),
        'message': f'Added {len(tickers)} tickers'
    })

@app.route('/api/queue/status')
def queue_status():
    with lock:
        # Получаем список задач в очереди
        queue_preview = []
        for job in screening_state['queue'][:5]:  # Первые 5 задач
            queue_preview.append({
                'id': job['id'],
                'type': job['type'],
                'tickers_count': len(job['tickers'])
            })
        
        return jsonify({
            'running': screening_state['running'],
            'current_job': screening_state['current_job'],
            'progress': screening_state['progress'],
            'queue_length': len(screening_state['queue']),
            'queue_preview': queue_preview,
            'logs': screening_state['logs'][:20]
        })

@app.route('/api/queue/results/<job_id>')
def get_results(job_id):
    with lock:
        if job_id in screening_state['results']:
            return jsonify(screening_state['results'][job_id])
        # Проверяем, является ли эта задача текущей
        if screening_state['current_job'] and screening_state['current_job']['id'] == job_id:
            return jsonify({'status': 'running', 'progress': screening_state['progress']}), 202
        # Проверяем, есть ли задача в очереди
        for job in screening_state['queue']:
            if job['id'] == job_id:
                position = screening_state['queue'].index(job) + 1
                return jsonify({'status': 'queued', 'queue_position': position}), 202
        return jsonify({'error': 'Job not found'}), 404

@app.route('/api/queue/clear', methods=['POST'])
def clear_queue():
    with lock:
        screening_state['queue'] = []
    log_message("🧹 Очередь очищена")
    return jsonify({'success': True})

# ========== АВТОЗАПУСК API ==========

@app.route('/api/autorun/status')
def autorun_status():
    """Получить статус автозапуска"""
    with autorun_lock:
        status = autorun_state.copy()
        # Конвертируем datetime в строки для JSON
        if status['last_run']:
            status['last_run'] = status['last_run'].isoformat()
        if status['next_run']:
            status['next_run'] = status['next_run'].isoformat()
        
        # Добавляем оставшееся время
        if status['next_run'] and status['enabled']:
            next_run = datetime.fromisoformat(status['next_run'])
            remaining = next_run - datetime.now()
            status['time_remaining'] = {
                'hours': remaining.seconds // 3600,
                'minutes': (remaining.seconds % 3600) // 60,
                'seconds': remaining.seconds % 60,
                'total_seconds': int(remaining.total_seconds())
            }
        else:
            status['time_remaining'] = None
        
        return jsonify(status)

@app.route('/api/autorun/start', methods=['POST'])
def autorun_start():
    """Запустить автозапуск"""
    global autorun_state
    data = request.json
    
    tickers = data.get('tickers', [])
    interval_hours = data.get('interval_hours', 1)
    screeners = data.get('screeners', ['long', 'squeeze', 'oversold'])
    
    if not tickers:
        return jsonify({'error': 'No tickers provided'}), 400
    
    if interval_hours not in [1, 2, 3, 4, 5, 6, 12, 24]:
        return jsonify({'error': 'Invalid interval. Allowed: 1, 2, 3, 4, 5, 6, 12, 24 hours'}), 400
    
    with autorun_lock:
        autorun_state['enabled'] = True
        autorun_state['tickers'] = tickers
        autorun_state['interval_hours'] = interval_hours
        autorun_state['screeners'] = screeners
        autorun_state['next_run'] = datetime.now() + timedelta(hours=interval_hours)
    
    log_message(f"🤖 Автозапуск ВКЛЮЧЕН: каждые {interval_hours}ч, {len(tickers)} тикеров, {len(screeners)} скринеров")
    
    return jsonify({
        'success': True,
        'message': f'Autorun enabled with {interval_hours}h interval',
        'next_run': autorun_state['next_run'].isoformat()
    })

@app.route('/api/autorun/stop', methods=['POST'])
def autorun_stop():
    """Остановить автозапуск"""
    global autorun_state
    
    with autorun_lock:
        was_enabled = autorun_state['enabled']
        autorun_state['enabled'] = False
        autorun_state['next_run'] = None
    
    if was_enabled:
        log_message("🛑 Автозапуск ОСТАНОВЛЕН")
    
    return jsonify({
        'success': True,
        'message': 'Autorun stopped',
        'stats': {
            'total_runs': autorun_state['run_count'],
            'total_signals': autorun_state['total_signals_found']
        }
    })

@app.route('/api/autorun/run-now', methods=['POST'])
def autorun_run_now():
    """Запустить немедленно (вне расписания)"""
    global autorun_state
    data = request.json or {}
    
    tickers = data.get('tickers', autorun_state['tickers'])
    screeners = data.get('screeners', autorun_state['screeners'])
    
    if not tickers:
        return jsonify({'error': 'No tickers provided'}), 400
    
    # Добавляем все скринеры в очередь
    job_ids = []
    now = datetime.now()
    
    for screener_type in screeners:
        job_id = f"manual_{screener_type}_{now.strftime('%H%M%S')}"
        with lock:
            screening_state['queue'].append({
                'id': job_id,
                'type': screener_type,
                'tickers': tickers.copy(),
                'added_at': now.isoformat(),
                'is_manual': True
            })
        job_ids.append(job_id)
    
    log_message(f"⚡ Ручной запуск: {len(screeners)} скринеров добавлены в очередь")
    
    return jsonify({
        'success': True,
        'message': f'{len(screeners)} screeners queued',
        'job_ids': job_ids
    })

# Health check endpoint для Render
@app.route("/health")
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat(), "version": "1.0.0"})

@app.route("/api/autorun/history")
def autorun_history():
    """Получить историю автозапуска (из результатов)"""
    auto_results = []
    
    with lock:
        for job_id, result in screening_state['results'].items():
            if job_id.startswith('auto_') or job_id.startswith('manual_'):
                auto_results.append({
                    'job_id': job_id,
                    'type': result.get('type'),
                    'completed_at': result.get('completed_at'),
                    'count': result.get('count', 0),
                    'elapsed_seconds': result.get('elapsed_seconds', 0),
                    'saved_file': result.get('saved_file')
                })
    
    # Сортируем по времени (новые первые)
    auto_results.sort(key=lambda x: x['completed_at'] or '', reverse=True)
    
    return jsonify({
        'history': auto_results[:50],  # Последние 50 запусков
        'total': len(auto_results)
    })

if __name__ == '__main__':
    print(f"🚀 TradeScreener Pro запущен")
    print(f"📁 Результаты сохраняются в: {os.path.abspath('results')}")
    print(f"📊 История арбитража: {os.path.abspath(HISTORY_FILE)}")
    app.run(debug=True, host='0.0.0.0', port=PORT, threaded=True)
