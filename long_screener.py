"""
ArbitrageMonitor - Мониторинг арбитража ES vs SPX
Улучшенная версия с корректной обработкой данных yfinance
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class ArbitrageMonitor:
    def __init__(self):
        self.data = {}
        
    def get_current_basis(self):
        """Расчет базиса ES vs SPX с улучшенной обработкой данных"""
        try:
            # Загрузка данных
            es = yf.download("ES=F", period="3d", interval="30m", progress=False)
            spx = yf.download("^GSPC", period="3d", interval="30m", progress=False)
            vix = yf.download("^VIX", period="1d", progress=False)
            spy = yf.download("SPY", period="3d", interval="30m", progress=False)
            
            # Обработка мультииндекса колонок
            if isinstance(es.columns, pd.MultiIndex):
                es.columns = [' '.join(col).strip() if col[1] not in ['nan', 'NaN'] else col[0] 
                              for col in es.columns.values]
            if isinstance(spx.columns, pd.MultiIndex):
                spx.columns = [' '.join(col).strip() if col[1] not in ['nan', 'NaN'] else col[0] 
                               for col in spx.columns.values]
            if isinstance(vix.columns, pd.MultiIndex):
                vix.columns = [' '.join(col).strip() if col[1] not in ['nan', 'NaN'] else col[0] 
                               for col in vix.columns.values]
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = [' '.join(col).strip() if col[1] not in ['nan', 'NaN'] else col[0] 
                               for col in spy.columns.values]
            
            # Переименовываем колонки
            col_map_es = {}
            for col in es.columns:
                if 'datetime' in col.lower() or 'date' in col.lower():
                    col_map_es[col] = 'Date'
                elif 'close' in col.lower():
                    col_map_es[col] = 'Close'
                elif 'volume' in col.lower():
                    col_map_es[col] = 'Volume'
            es = es.rename(columns=col_map_es)
            
            col_map_spx = {}
            for col in spx.columns:
                if 'datetime' in col.lower() or 'date' in col.lower():
                    col_map_spx[col] = 'Date'
                elif 'close' in col.lower():
                    col_map_spx[col] = 'Close'
            spx = spx.rename(columns=col_map_spx)
            
            col_map_vix = {}
            for col in vix.columns:
                if 'close' in col.lower():
                    col_map_vix[col] = 'Close'
            vix = vix.rename(columns=col_map_vix)
            
            col_map_spy = {}
            for col in spy.columns:
                if 'datetime' in col.lower() or 'date' in col.lower():
                    col_map_spy[col] = 'Date'
                elif 'close' in col.lower():
                    col_map_spy[col] = 'Close'
                elif 'volume' in col.lower():
                    col_map_spy[col] = 'Volume'
            spy = spy.rename(columns=col_map_spy)
            
            if es.empty or spx.empty:
                return {'error': 'No data'}
            
            current_es = es['Close'].iloc[-1]
            current_spx = spx['Close'].iloc[-1]
            current_vix = vix['Close'].iloc[-1] if not vix.empty else 20
            
            # Расчет базиса
            basis = ((current_es - current_spx) / current_spx) * 100
            
            # Z-Score за 5 дней
            basis_history = []
            for i in range(min(20, len(es))):
                try:
                    b = ((es['Close'].iloc[i] - spx['Close'].iloc[i]) / spx['Close'].iloc[i]) * 100
                    basis_history.append(b)
                except:
                    continue
            
            if basis_history:
                basis_mean = np.mean(basis_history)
                basis_std = np.std(basis_history) if np.std(basis_history) > 0 else 1
                z_score = (basis - basis_mean) / basis_std
            else:
                z_score = 0
            
            # Определение сигнала
            signal = "NEUTRAL"
            if z_score < -1.5:
                signal = "BEARISH (Discount)"
            elif z_score > 1.5:
                signal = "BULLISH (Premium)"
            elif z_score < -0.5:
                signal = "SLIGHT_BEAR"
            elif z_score > 0.5:
                signal = "SLIGHT_BULL"
            
            # Расчет объема SPY
            spy_vol_ratio = 1.0
            if not spy.empty and len(spy) > 20:
                current_vol = spy['Volume'].iloc[-1]
                avg_vol = spy['Volume'].tail(20).mean()
                spy_vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
            
            return {
                'es_price': round(current_es, 2),
                'spx_price': round(current_spx, 2),
                'basis_pct': round(basis, 3),
                'z_score': round(z_score, 2),
                'vix': round(current_vix, 2),
                'spy_volume_ratio': round(spy_vol_ratio, 1),
                'signal': signal,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
        except Exception as e:
            return {'error': str(e), 'basis_pct': 0, 'signal': 'ERROR'}
