"""
OversoldScreener - Скринер для поиска перепроданных акций с потенциалом отскока
Улучшенная версия с фундаментальным анализом
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class OversoldScreener:
    def __init__(self):
        self.min_price = 2.0
        self.min_cap = 300_000_000
        self.min_volume = 400_000
        
        # Пороги для отскока
        self.min_drop_5d = 7.0
        self.min_drop_1d = 3.0
        self.max_rsi = 35
        self.min_bounce_target = 7.0
        
        # Фундаментальные пороги
        self.max_pe = 30
        self.max_peg = 2.0
        self.min_roe = 0.08
        self.max_debt_equity = 1.0
        
        # Веса
        self.weight_technical = 60
        self.weight_fundamental = 40
        
    def safe_float(self, value, default=0):
        try:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value.replace(',', ''))
            return default
        except:
            return default
    
    def calculate_ema(self, prices, span):
        return prices.ewm(span=span, adjust=False).mean()
    
    def calculate_rsi(self, prices, period=14):
        """Исправленная версия RSI"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        loss = loss.replace(0, np.nan)
        rs = gain / loss
        rs = rs.fillna(100)
        
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def find_support_resistance(self, df, window=5):
        """Поиск уровней поддержки/сопротивления"""
        if len(df) < 20:
            return []
        
        levels = []
        for i in range(window, len(df) - window):
            if df['Low'].iloc[i] == df['Low'].iloc[i-window:i+window+1].min():
                levels.append({'price': df['Low'].iloc[i], 'type': 'support', 'date': df.index[i]})
        
        for i in range(window, len(df) - window):
            if df['High'].iloc[i] == df['High'].iloc[i-window:i+window+1].max():
                levels.append({'price': df['High'].iloc[i], 'type': 'resistance', 'date': df.index[i]})
        
        grouped_levels = []
        for level in levels:
            found = False
            for gl in grouped_levels:
                if abs(gl['price'] - level['price']) / gl['price'] < 0.015:
                    gl['touches'] += 1
                    gl['dates'].append(level['date'])
                    found = True
                    break
            if not found:
                grouped_levels.append({'price': level['price'], 'type': level['type'], 'touches': 1, 'dates': [level['date']]})
        
        strong_levels = [l for l in grouped_levels if l['touches'] >= 2]
        strong_levels.sort(key=lambda x: x['touches'], reverse=True)
        return strong_levels[:3]
    
    def check_bullish_divergence(self, df):
        """Проверка бычьей дивергенции"""
        if len(df) < 20:
            return {'has_divergence': False, 'strength': 0}
        
        closes = df['Close'].tail(20)
        rsi = self.calculate_rsi(closes).tail(20)
        
        price_lows = []
        rsi_lows = []
        
        for i in range(5, len(closes)-5):
            if closes.iloc[i] == min(closes.iloc[i-5:i+6]):
                price_lows.append({'idx': i, 'price': closes.iloc[i]})
            if rsi.iloc[i] == min(rsi.iloc[i-5:i+6]) and not pd.isna(rsi.iloc[i]):
                rsi_lows.append({'idx': i, 'rsi': rsi.iloc[i]})
        
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            p1, p2 = price_lows[-2], price_lows[-1]
            r1, r2 = rsi_lows[-2], rsi_lows[-1]
            
            if p2['price'] < p1['price'] and r2['rsi'] > r1['rsi']:
                strength = min(100, int((r2['rsi'] - r1['rsi']) * 10))
                return {
                    'has_divergence': True,
                    'strength': strength,
                    'type': 'bullish',
                    'description': f"Цена: {p2['price']:.2f} < {p1['price']:.2f}, RSI: {r2['rsi']:.1f} > {r1['rsi']:.1f}"
                }
        
        return {'has_divergence': False, 'strength': 0}
    
    def check_hammer_candle(self, df):
        """Проверка паттерна 'молот'"""
        if len(df) < 2:
            return {'is_hammer': False}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        body = abs(last['Close'] - last['Open'])
        lower_shadow = min(last['Open'], last['Close']) - last['Low']
        upper_shadow = last['High'] - max(last['Open'], last['Close'])
        
        if body > 0 and lower_shadow > body * 2 and upper_shadow < body * 0.5:
            if last['Close'] > last['Open']:
                strength = min(100, int(lower_shadow / body * 20))
                return {
                    'is_hammer': True,
                    'strength': strength,
                    'type': 'bullish_hammer',
                    'description': f"Тело: {body:.2f}, Тень: {lower_shadow:.2f}"
                }
        
        return {'is_hammer': False}
    
    def check_engulfing_pattern(self, df):
        """Проверка паттерна 'бычье поглощение'"""
        if len(df) < 2:
            return {'is_engulfing': False}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        if prev['Close'] < prev['Open'] and last['Close'] > last['Open']:
            if last['Open'] < prev['Close'] and last['Close'] > prev['Open']:
                vol_ratio = last['Volume'] / prev['Volume'] if prev['Volume'] > 0 else 1
                strength = min(100, int(vol_ratio * 50))
                
                return {
                    'is_engulfing': True,
                    'strength': strength,
                    'type': 'bullish_engulfing',
                    'description': f"Объем: {vol_ratio:.1f}x"
                }
        
        return {'is_engulfing': False}
    
    def calculate_bounce_potential(self, df, current_price):
        """Расчет потенциала отскока"""
        if len(df) < 20:
            return {'target_price': None, 'potential_%': 0, 'confidence': 0}
        
        highs = df['High'].tail(50)
        resistance_levels = []
        
        for i in range(5, len(highs)-5):
            if highs.iloc[i] == max(highs.iloc[i-5:i+6]):
                if highs.iloc[i] > current_price:
                    resistance_levels.append(highs.iloc[i])
        
        if resistance_levels:
            nearest_resistance = min(resistance_levels)
        else:
            ema50 = self.calculate_ema(df['Close'], 50).iloc[-1]
            nearest_resistance = max(ema50, current_price * 1.05)
        
        potential = (nearest_resistance - current_price) / current_price * 100
        
        confidence = 0
        atr = (df['High'] - df['Low']).tail(14).mean()
        atr_pct = atr / current_price * 100
        
        if potential <= atr_pct * 2:
            confidence = 80
        elif potential <= atr_pct * 3:
            confidence = 60
        elif potential <= atr_pct * 4:
            confidence = 40
        else:
            confidence = 20
        
        return {
            'target_price': round(nearest_resistance, 2),
            'potential_%': round(potential, 1),
            'confidence': confidence,
            'resistance_type': 'level' if resistance_levels else 'ema50'
        }
    
    def check_drop_recent(self, df):
        """Проверка недавнего падения"""
        if len(df) < 10:
            return {'is_dropping': False, 'drop_5d': 0, 'drop_1d': 0}
        
        current = df['Close'].iloc[-1]
        close_5d_ago = df['Close'].iloc[-6] if len(df) >= 6 else current
        close_1d_ago = df['Close'].iloc[-2]
        
        drop_5d = (close_5d_ago - current) / close_5d_ago * 100
        drop_1d = (close_1d_ago - current) / close_1d_ago * 100
        
        return {
            'drop_5d': round(drop_5d, 1),
            'drop_1d': round(drop_1d, 1),
            'is_dropping': drop_5d > 0,
            'oversold_5d': drop_5d >= self.min_drop_5d,
            'oversold_1d': drop_1d >= self.min_drop_1d
        }
    
    def calculate_fundamental_score(self, info, current_price):
        """Расчет фундаментального скора"""
        score = 0
        details = {}
        
        # P/E
        pe = info.get('trailingPE') or info.get('forwardPE')
        pe = self.safe_float(pe, None)
        if pe and 0 < pe < self.max_pe:
            if pe < 15:
                pe_score = 30
                pe_grade = "Отлично"
            elif pe < 25:
                pe_score = 20
                pe_grade = "Хорошо"
            else:
                pe_score = 10
                pe_grade = "Приемлемо"
            
            score += pe_score
            details['pe'] = round(pe, 2)
            details['pe_score'] = pe_score
            details['pe_grade'] = pe_grade
        else:
            details['pe'] = None
            details['pe_score'] = 0
        
        # PEG
        pe_for_peg = info.get('trailingPE')
        growth = info.get('earningsGrowth') or info.get('revenueGrowth')
        
        if pe_for_peg and pe_for_peg > 0 and growth and growth > 0:
            peg = pe_for_peg / (growth * 100)
            if peg < 1.0:
                peg_score = 25
                peg_grade = "Недооценена"
            elif peg < 1.5:
                peg_score = 15
                peg_grade = "Справедливо"
            elif peg < self.max_peg:
                peg_score = 5
                peg_grade = "Дороговато"
            else:
                peg_score = 0
                peg_grade = "Переоценена"
            
            score += peg_score
            details['peg'] = round(peg, 2)
            details['peg_score'] = peg_score
            details['peg_grade'] = peg_grade
        else:
            details['peg'] = None
            details['peg_score'] = 0
        
        # ROE
        roe = info.get('returnOnEquity')
        roe = self.safe_float(roe, 0)
        if roe and roe > 0:
            if roe > 0.25:
                roe_score = 25
                roe_grade = "Превосходно"
            elif roe > 0.15:
                roe_score = 20
                roe_grade = "Отлично"
            elif roe > self.min_roe:
                roe_score = 15
                roe_grade = "Хорошо"
            else:
                roe_score = 5
                roe_grade = "Слабо"
            
            score += roe_score
            details['roe'] = round(roe * 100, 1)
            details['roe_score'] = roe_score
            details['roe_grade'] = roe_grade
        else:
            details['roe'] = None
            details['roe_score'] = 0
        
        # Debt/Equity
        debt_to_equity = info.get('debtToEquity')
        debt_to_equity = self.safe_float(debt_to_equity, None)
        if debt_to_equity is not None:
            de_ratio = debt_to_equity / 100
            if de_ratio < 0.3:
                de_score = 20
                de_grade = "Очень низкий"
            elif de_ratio < 0.6:
                de_score = 15
                de_grade = "Низкий"
            elif de_ratio < self.max_debt_equity:
                de_score = 10
                de_grade = "Умеренный"
            else:
                de_score = 0
                de_grade = "Высокий"
            
            score += de_score
            details['debt_equity'] = round(de_ratio, 2)
            details['de_score'] = de_score
            details['de_grade'] = de_grade
        else:
            details['debt_equity'] = None
            details['de_score'] = 0
        
        # Profit Margin
        margin = info.get('profitMargins')
        margin = self.safe_float(margin, 0)
        if margin and margin > 0:
            if margin > 0.20:
                margin_score = 10
            elif margin > 0.10:
                margin_score = 5
            else:
                margin_score = 2
            
            score += margin_score
            details['profit_margin'] = round(margin * 100, 1)
            details['margin_score'] = margin_score
        else:
            details['profit_margin'] = None
            details['margin_score'] = 0
        
        normalized_score = min(100, int(score * 100 / 110))
        details['fundamental_score'] = normalized_score
        details['fundamental_raw'] = score
        
        return normalized_score, details
    
    def calculate_risk_levels(self, hist, nearest_support, current_price):
        """Расчет уровней риска"""
        try:
            atr = (hist['High'] - hist['Low']).tail(14).mean()
            
            if nearest_support and nearest_support['type'] == 'support':
                stop_loss = nearest_support['price'] * 0.98
                stop_type = "Поддержка"
            else:
                stop_loss = current_price - (1.5 * atr)
                stop_type = "1.5xATR"
            
            risk_per_share = current_price - stop_loss
            risk_pct = (risk_per_share / current_price) * 100 if current_price > 0 else 0
            
            return {
                'stop_loss': round(stop_loss, 2),
                'stop_type': stop_type,
                'risk_per_share': round(risk_per_share, 2),
                'risk_pct': round(risk_pct, 2)
            }
        except:
            return {
                'stop_loss': current_price * 0.95,
                'stop_type': 'Default',
                'risk_per_share': round(current_price * 0.05, 2),
                'risk_pct': 5.0
            }
    
    def check_earnings_risk(self, stock):
        """Проверка риска отчетности"""
        try:
            calendar = stock.calendar
            if calendar is not None and not calendar.empty:
                next_earnings = pd.to_datetime(calendar.index[0])
                days_to_earnings = (next_earnings - datetime.now()).days
                if 0 <= days_to_earnings <= 3:
                    return {'risk': 'HIGH', 'days': days_to_earnings, 'skip': True}
                elif 4 <= days_to_earnings <= 7:
                    return {'risk': 'MEDIUM', 'days': days_to_earnings, 'skip': False}
            return {'risk': 'LOW', 'days': 999, 'skip': False}
        except:
            return {'risk': 'UNKNOWN', 'days': 999, 'skip': False}
    
    def analyze_volume(self, hist):
        """Анализ объема"""
        try:
            current_vol = hist['Volume'].iloc[-1]
            avg_vol_20 = hist['Volume'].tail(20).mean()
            rel_volume = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
            
            selling_on_drop = False
            if len(hist) > 5:
                if hist['Close'].iloc[-5] > hist['Close'].iloc[-1]:
                    max_vol_drop = hist['Volume'].tail(5).max()
                    if max_vol_drop > avg_vol_20 * 1.5:
                        selling_on_drop = True
            
            vol_score = 0
            if rel_volume > 1.5:
                vol_score += 15
            if selling_on_drop:
                vol_score += 10
            
            return {
                'rel_volume': round(rel_volume, 2),
                'vol_score': vol_score,
                'selling_on_drop': selling_on_drop,
                'is_accumulation': rel_volume > 1.2 and hist['Close'].iloc[-1] > hist['Close'].iloc[-2]
            }
        except:
            return {'rel_volume': 1.0, 'vol_score': 0, 'selling_on_drop': False, 'is_accumulation': False}
    
    def analyze_ticker(self, ticker: str) -> Optional[Dict]:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="90d")
            info = stock.info
            
            if hist.empty or len(hist) < 20:
                return None
            
            current_price = hist['Close'].iloc[-1]
            
            # Базовые фильтры
            if current_price < self.min_price:
                return None
            
            market_cap = info.get('marketCap', 0)
            market_cap = self.safe_float(market_cap, 0)
            if market_cap < self.min_cap:
                return None
            
            volume = info.get('averageVolume', 0)
            volume = self.safe_float(volume, 0)
            dollar_volume = volume * current_price
            if dollar_volume < self.min_volume:
                return None
            
            # Проверка earnings
            earnings = self.check_earnings_risk(stock)
            if earnings.get('skip'):
                return None
            
            # ===== ТЕХНИЧЕСКИЙ АНАЛИЗ =====
            tech_score = 0
            tech_details = {}
            
            # Падение
            drop = self.check_drop_recent(hist)
            tech_details.update(drop)
            
            if drop['oversold_5d']:
                tech_score += 30
            elif drop['drop_5d'] > 0:
                tech_score += 10
            
            if drop['oversold_1d']:
                tech_score += 20
            elif drop['drop_1d'] > 0:
                tech_score += 5
            
            # RSI
            rsi = self.calculate_rsi(hist['Close']).iloc[-1]
            tech_details['rsi'] = round(rsi, 1)
            
            if not pd.isna(rsi):
                if rsi < 25:
                    tech_score += 35
                elif rsi < self.max_rsi:
                    tech_score += 25
                elif rsi < 45:
                    tech_score += 10
            
            # Уровни поддержки
            levels = self.find_support_resistance(hist)
            nearest_support = None
            
            if levels:
                supports = [l for l in levels if l['type'] == 'support' and l['price'] < current_price]
                if supports:
                    nearest_support = min(supports, key=lambda x: abs(x['price'] - current_price))
                    dist_to_support = (current_price - nearest_support['price']) / current_price * 100
                    
                    tech_details['support_price'] = nearest_support['price']
                    tech_details['support_touches'] = nearest_support['touches']
                    tech_details['dist_to_support'] = round(dist_to_support, 1)
                    
                    if dist_to_support < 3.0 and nearest_support['touches'] >= 3:
                        tech_score += 35
                    elif dist_to_support < 5.0 and nearest_support['touches'] >= 2:
                        tech_score += 25
                    elif dist_to_support < 7.0:
                        tech_score += 10
            
            # Дивергенция
            divergence = self.check_bullish_divergence(hist)
            tech_details['has_divergence'] = divergence['has_divergence']
            
            if divergence['has_divergence']:
                tech_score += divergence['strength']
            
            # Паттерны
            hammer = self.check_hammer_candle(hist)
            engulfing = self.check_engulfing_pattern(hist)
            
            if hammer['is_hammer']:
                tech_score += hammer['strength']
            
            if engulfing['is_engulfing']:
                tech_score += engulfing['strength']
            
            # Потенциал отскока
            bounce = self.calculate_bounce_potential(hist, current_price)
            tech_details['target_price'] = bounce['target_price']
            tech_details['potential_%'] = bounce['potential_%']
            tech_details['bounce_confidence'] = bounce['confidence']
            
            if bounce['potential_%'] >= self.min_bounce_target:
                tech_score += min(30, int(bounce['confidence'] / 3))
            
            # Объем
            vol = self.analyze_volume(hist)
            tech_details['rel_volume'] = vol['rel_volume']
            
            if vol['selling_on_drop']:
                tech_score += vol['vol_score']
            
            # ===== ФУНДАМЕНТАЛЬНЫЙ АНАЛИЗ =====
            fund_score, fund_details = self.calculate_fundamental_score(info, current_price)
            
            # ===== ИТОГОВАЯ ОЦЕНКА =====
            total_score = int(tech_score * (self.weight_technical/100) + fund_score * (self.weight_fundamental/100))
            
            # Риск-менеджмент
            risk = self.calculate_risk_levels(hist, nearest_support, current_price)
            
            # R/R
            potential = tech_details.get('potential_%', 0)
            if risk['risk_pct'] > 0 and potential > 0:
                rr_ratio = potential / risk['risk_pct']
            else:
                rr_ratio = 0
            
            # Грейд
            if total_score >= 85 and potential >= self.min_bounce_target and fund_score >= 70:
                grade = "🚀 PERFECT FUNDAMENTAL BOUNCE"
            elif total_score >= 75 and potential >= self.min_bounce_target and fund_score >= 60:
                grade = "✅ STRONG FUNDAMENTAL BOUNCE"
            elif total_score >= 70 and potential >= self.min_bounce_target:
                grade = "📈 TECHNICAL BOUNCE"
            elif total_score >= 65:
                grade = "👀 WATCH"
            elif total_score >= 50 and tech_details.get('drop_5d', 0) >= 5:
                grade = "📉 OVERSOLD ONLY"
            else:
                grade = "PASS"
            
            return {
                'ticker': ticker,
                'grade': grade,
                'price': round(current_price, 2),
                'score': total_score,
                'tech_score': tech_score,
                'fund_score': fund_score,
                'drop_5d': tech_details.get('drop_5d'),
                'drop_1d': tech_details.get('drop_1d'),
                'rsi': tech_details.get('rsi'),
                'target_price': tech_details.get('target_price'),
                'potential': tech_details.get('potential_%'),
                'confidence': tech_details.get('bounce_confidence'),
                'support_price': tech_details.get('support_price'),
                'support_touches': tech_details.get('support_touches'),
                'has_divergence': tech_details.get('has_divergence'),
                'rel_volume': tech_details.get('rel_volume'),
                'pe': fund_details.get('pe'),
                'peg': fund_details.get('peg'),
                'roe': fund_details.get('roe'),
                'debt_equity': fund_details.get('debt_equity'),
                'profit_margin': fund_details.get('profit_margin'),
                'stop_loss': risk.get('stop_loss'),
                'risk_pct': risk.get('risk_pct'),
                'risk_reward': round(rr_ratio, 2)
            }
            
        except Exception as e:
            return None
    
    def screen_tickers(self, tickers: List[str]) -> List[Dict]:
        results = []
        for ticker in tickers:
            result = self.analyze_ticker(ticker)
            if result and result['grade'] != "PASS":
                results.append(result)
        return sorted(results, key=lambda x: x['score'], reverse=True)
