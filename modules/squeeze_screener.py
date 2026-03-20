"""
SqueezeScreener - Скринер для поиска Short Squeeze сетапов
Улучшенная версия с анализом уровней, пробоев и ретестов
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class SqueezeScreener:
    def __init__(self):
        self.min_price = 3.0
        self.max_price = 100.0
        self.min_volume = 500000
        self.max_market_cap = 15e9
        self.min_adx = 20
        self.min_price_change_3d = 2
        self.max_price_change_3d = 30
        
        # Веса для скора
        self.score_trend_strength = 25
        self.score_momentum = 20
        self.score_rvol = 15
        self.score_technical = 15
        self.score_risk_reward = 15
        self.score_volatility = 10
        self.score_level_bounce = 25
        self.score_level_breakout = 30
        self.score_level_retest = 20
        
    def safe_float(self, value, default=0.0):
        try:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value.replace(',', '').replace('%', ''))
            return default
        except:
            return default
    
    def find_key_levels(self, df, lookback=90):
        """Поиск сильных уровней"""
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        hist = df.tail(lookback)
        
        # Свинг-хаи и свинг-лои
        swing_highs = []
        swing_lows = []
        window = 10
        
        for i in range(window, len(hist) - window):
            if hist['High'].iloc[i] == max(hist['High'].iloc[i-window:i+window+1]):
                swing_highs.append({
                    'price': hist['High'].iloc[i],
                    'strength': 1 + (hist['Volume'].iloc[i] / hist['Volume'].mean())
                })
            
            if hist['Low'].iloc[i] == min(hist['Low'].iloc[i-window:i+window+1]):
                swing_lows.append({
                    'price': hist['Low'].iloc[i],
                    'strength': 1 + (hist['Volume'].iloc[i] / hist['Volume'].mean())
                })
        
        # Области высокого объема
        price_bins = {}
        bin_size = (hist['High'].max() - hist['Low'].min()) / 50
        
        for i in range(len(hist)):
            price = (hist['High'].iloc[i] + hist['Low'].iloc[i]) / 2
            vol = hist['Volume'].iloc[i]
            bin_idx = int((price - hist['Low'].min()) / bin_size) if bin_size > 0 else 0
            
            if bin_idx not in price_bins:
                price_bins[bin_idx] = {'volume': 0, 'price_level': price}
            price_bins[bin_idx]['volume'] += vol
        
        high_volume_levels = []
        if price_bins:
            sorted_bins = sorted(price_bins.values(), key=lambda x: x['volume'], reverse=True)[:5]
            high_volume_levels = [b['price_level'] for b in sorted_bins]
        
        return {
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'high_volume_levels': high_volume_levels
        }
    
    def check_level_interaction(self, df, levels):
        """Проверка взаимодействия цены с уровнями"""
        current_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        today_open = df['Open'].iloc[-1]
        today_low = df['Low'].iloc[-1]
        today_high = df['High'].iloc[-1]
        volume = df['Volume'].iloc[-1]
        avg_volume = df['Volume'].tail(20).mean()
        
        results = {
            'support_bounce': False,
            'resistance_break': False,
            'retest': False,
            'level_type': None,
            'level_price': None,
            'description': '',
            'strength': 0
        }
        
        # Проверка поддержки (отбой)
        for swing_low in levels['swing_lows']:
            level_price = swing_low['price']
            distance = abs(current_price - level_price) / level_price * 100
            
            if distance < 1.5 and today_low <= level_price * 1.01 and current_price > level_price:
                was_below = prev_close < level_price or today_open < level_price
                
                results['support_bounce'] = True
                results['level_type'] = 'Support'
                results['level_price'] = level_price
                results['retest'] = was_below
                results['strength'] = swing_low['strength']
                results['description'] = f"Отбой от поддержки ${level_price:.2f}"
                
                if was_below:
                    results['description'] += " (ретест)"
                
                if volume > avg_volume * 1.5:
                    results['strength'] += 1
                    results['description'] += " с объемом"
                
                return results
        
        # Проверка сопротивления (пробой)
        for swing_high in levels['swing_highs']:
            level_price = swing_high['price']
            distance = abs(current_price - level_price) / level_price * 100
            
            if distance < 2.0 and current_price > level_price and prev_close <= level_price:
                results['resistance_break'] = True
                results['level_type'] = 'Resistance'
                results['level_price'] = level_price
                results['retest'] = False
                results['strength'] = swing_high['strength']
                results['description'] = f"Пробой сопротивления ${level_price:.2f}"
                
                if volume > avg_volume * 1.5:
                    results['strength'] += 1
                    results['description'] += " с объемом"
                
                return results
        
        return results
    
    def calculate_vwap(self, df):
        """Расчет VWAP"""
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        return (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    def calculate_momentum_strength(self, df):
        """Расчет силы моментума"""
        close = df['Close']
        volume = df['Volume']
        
        sma_5 = close.rolling(5).mean()
        sma_20 = close.rolling(20).mean()
        
        trend_up = sma_5.iloc[-1] > sma_20.iloc[-1]
        
        price_change_3d = (close.iloc[-1] - close.iloc[-4]) / close.iloc[-4] * 100 if len(close) > 4 else 0
        volume_trend = volume.tail(3).mean() > volume.tail(10).mean() * 1.2 if len(volume) > 10 else False
        
        # ADX
        high, low = df['High'], df['Low']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        up_move = high - high.shift()
        down_move = low.shift() - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        atr_period = 14
        plus_di = 100 * (pd.Series(plus_dm).rolling(atr_period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(atr_period).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(atr_period).mean()
        
        adx_value = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
        
        return {
            'trend_up': trend_up,
            'price_change_3d': round(price_change_3d, 2),
            'volume_trend': volume_trend,
            'adx': round(adx_value, 2),
            'trend_strength': 'Strong' if adx_value > 25 else 'Weak' if adx_value < 20 else 'Moderate'
        }
    
    def calculate_support_resistance(self, df):
        """Расчет уровней поддержки/сопротивления"""
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        window = 5
        resistance_levels = []
        support_levels = []
        
        for i in range(window, len(high) - window):
            if high.iloc[i] == max(high.iloc[i-window:i+window+1]):
                resistance_levels.append(high.iloc[i])
            if low.iloc[i] == min(low.iloc[i-window:i+window+1]):
                support_levels.append(low.iloc[i])
        
        current_price = close.iloc[-1]
        nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.05)
        nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.95)
        
        return {
            'nearest_resistance': round(nearest_resistance, 2),
            'nearest_support': round(nearest_support, 2),
            'resistance_distance_%': round((nearest_resistance - current_price) / current_price * 100, 2),
            'support_distance_%': round((current_price - nearest_support) / current_price * 100, 2),
            'risk_reward_ratio': round((nearest_resistance - current_price) / (current_price - nearest_support), 2) if current_price > nearest_support else 0
        }
    
    def identify_market_structure(self, df):
        """Определение рыночной структуры"""
        recent = df.tail(20)
        
        higher_highs = 0
        higher_lows = 0
        lower_highs = 0
        lower_lows = 0
        
        for i in range(1, len(recent)):
            if recent['High'].iloc[i] > recent['High'].iloc[i-1]:
                higher_highs += 1
            if recent['Low'].iloc[i] > recent['Low'].iloc[i-1]:
                higher_lows += 1
            if recent['High'].iloc[i] < recent['High'].iloc[i-1]:
                lower_highs += 1
            if recent['Low'].iloc[i] < recent['Low'].iloc[i-1]:
                lower_lows += 1
        
        if higher_highs > lower_highs and higher_lows > lower_lows:
            trend = "UPTREND"
            structure = "HH/HL"
        elif lower_highs > higher_highs and lower_lows > higher_lows:
            trend = "DOWNTREND"
            structure = "LH/LL"
        else:
            trend = "RANGING"
            structure = "CHOP"
        
        return {
            'trend': trend,
            'structure': structure,
            'hh_hl_ratio': higher_highs / max(higher_lows, 1),
            'recent_strength': (higher_highs + higher_lows) - (lower_highs + lower_lows)
        }
    
    def analyze_ticker(self, ticker: str) -> Optional[Dict]:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="90d")
            info = stock.info
            
            if hist.empty or len(hist) < 30:
                return None
            
            current_price = hist['Close'].iloc[-1]
            volume = hist['Volume'].iloc[-1]
            market_cap = self.safe_float(info.get('marketCap', 0))
            
            # Базовые фильтры
            if not (self.min_price <= current_price <= self.max_price):
                return None
            
            if market_cap > self.max_market_cap or market_cap == 0:
                return None
            
            if volume < self.min_volume:
                return None
            
            # Моментум
            momentum = self.calculate_momentum_strength(hist)
            
            if momentum['adx'] < self.min_adx and momentum['price_change_3d'] < self.min_price_change_3d:
                return None
            
            if momentum['price_change_3d'] > self.max_price_change_3d:
                return None
            
            # Relative Volume
            avg_vol = hist['Volume'].tail(20).mean()
            rvol = volume / avg_vol if avg_vol > 0 else 1.0
            
            # Уровни
            levels = self.find_key_levels(hist)
            level_interaction = self.check_level_interaction(hist, levels)
            
            # Рыночная структура
            market_structure = self.identify_market_structure(hist)
            
            # ATR
            atr = (hist['High'] - hist['Low']).tail(14).mean()
            atr_pct = (atr / current_price) * 100
            
            # VWAP
            vwap = self.calculate_vwap(hist.tail(20)).iloc[-1]
            above_vwap = current_price > vwap
            
            # Уровни R/R
            sr_levels = self.calculate_support_resistance(hist)
            
            # ===== РАСЧЕТ СКОРА =====
            score = 0
            signals = []
            
            # RVOL
            if rvol > 5:
                score += self.score_rvol
                signals.append(f"🔥 Экстремальный объем {rvol:.1f}x")
            elif rvol > 3:
                score += int(self.score_rvol * 0.8)
                signals.append(f"📈 Высокий объем {rvol:.1f}x")
            elif rvol > 2:
                score += int(self.score_rvol * 0.5)
                signals.append(f"📊 Объем выше среднего {rvol:.1f}x")
            
            # Gap
            today_open = hist['Open'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            gap_pct = (today_open - prev_close) / prev_close * 100
            
            if gap_pct > 10:
                score += 15
                signals.append(f"🚨 Gap up +{gap_pct:.1f}%")
            elif gap_pct > 5:
                score += 9
                signals.append(f"⬆️ Gap up +{gap_pct:.1f}%")
            
            # Пробой
            if current_price > sr_levels['nearest_resistance'] * 0.99 and rvol > 1.5:
                score += self.score_technical
                signals.append(f"💥 Пробой уровня ${sr_levels['nearest_resistance']:.2f}")
            
            # Сжатие волатильности
            bb_width = (hist['High'].tail(10).max() - hist['Low'].tail(10).min()) / hist['Close'].tail(10).mean() * 100
            if bb_width < 8 and rvol > 2:
                score += 10
                signals.append("🎯 Сжатие + пробой")
            
            # Моментум
            closes = hist['Close'].tail(5)
            returns = closes.pct_change().dropna()
            
            if len(returns) >= 3:
                if all(r > 0 for r in returns.tail(3)) and returns.iloc[-1] > returns.iloc[-2]:
                    score += self.score_momentum
                    signals.append("🚀 Ускоряющийся рост")
                
                daily_change = (current_price - prev_close) / prev_close * 100
                if daily_change > 10:
                    score += 10
                    signals.append(f"⚡ Сильный день +{daily_change:.1f}%")
                elif daily_change > 5:
                    score += 5
                    signals.append(f"📈 Рост +{daily_change:.1f}%")
            
            # Market Cap
            if market_cap > 0:
                if market_cap < 500e6:
                    score += 10
                    cap_category = 'Micro'
                    signals.append("🎲 Micro-cap")
                elif market_cap < 2e9:
                    score += 7
                    cap_category = 'Small'
                    signals.append("🎯 Small-cap")
                else:
                    cap_category = 'Mid+'
            
            # Волатильность
            if 3 < atr_pct < 12:
                score += self.score_volatility
            elif atr_pct > 15:
                score -= 10
                signals.append("⚠️ Слишком волатильно")
            
            # VWAP
            if above_vwap and rvol > 2:
                signals.append(f"✅ Выше VWAP")
                score += 5
            
            # Уровни
            if level_interaction['support_bounce']:
                score += self.score_level_bounce
                signals.append(f"🛡️ {level_interaction['description']}")
                
                if level_interaction['strength'] > 1.5:
                    score += 10
                    signals.append("💪 Сильный уровень")
                
                if level_interaction['retest']:
                    score += self.score_level_retest
                    signals.append("🔄 Ретест")
            
            if level_interaction['resistance_break']:
                score += self.score_level_breakout
                signals.append(f"🚀 {level_interaction['description']}")
                
                if level_interaction['strength'] > 1.5:
                    score += 10
                    signals.append("📊 Пробой с объемом")
                
                if level_interaction['retest']:
                    score += self.score_level_retest
                    signals.append("🎯 Ретест пробитого")
            
            # Рыночная структура
            if market_structure['trend'] == 'UPTREND':
                score += 10
                signals.append(f"📈 {market_structure['structure']}")
            elif market_structure['trend'] == 'DOWNTREND':
                score -= 15
                signals.append("📉 Нисходящая структура")
            
            # R/R
            if sr_levels['risk_reward_ratio'] > 3:
                score += self.score_risk_reward
                signals.append(f"💰 R/R: {sr_levels['risk_reward_ratio']:.1f}")
            elif sr_levels['risk_reward_ratio'] > 2:
                score += int(self.score_risk_reward * 0.8)
                signals.append(f"⚖️ R/R: {sr_levels['risk_reward_ratio']:.1f}")
            
            # ADX
            if momentum['adx'] > 25:
                score += self.score_trend_strength
                signals.append(f"💪 ADX: {momentum['adx']:.1f}")
            
            # ===== ОПРЕДЕЛЕНИЕ ГРЕЙДА =====
            if level_interaction.get('level_type') == 'Resistance (Retest)':
                grade = "🔄 RETEST SETUP"
            elif level_interaction.get('resistance_break') and not level_interaction.get('retest'):
                grade = "🚀 BREAKOUT"
            elif level_interaction.get('support_bounce'):
                grade = "🛡️ SUPPORT BOUNCE"
            elif score >= 80 and rvol > 3:
                grade = "🚨 SQUEEZE ALERT"
            elif score >= 60:
                grade = "⚡ PRE-SQUEEZE"
            elif score >= 40:
                grade = "👀 EARLY SETUP"
            elif score < 20 and rvol > 5:
                grade = "☠️ HIGH RISK"
            else:
                grade = "PASS"
            
            # Стоп-лосс
            stop_loss = current_price * (1 - atr_pct/100 * 2)
            target_price = sr_levels['nearest_resistance']
            
            return {
                'ticker': ticker,
                'grade': grade,
                'price': round(current_price, 2),
                'score': score,
                'rvol': round(rvol, 1),
                'change_3d': momentum['price_change_3d'],
                'breakout': level_interaction.get('resistance_break', False),
                'level_price': round(level_interaction.get('level_price'), 2) if level_interaction.get('level_price') else None,
                'atr': round(atr_pct, 1),
                'level_info': level_interaction.get('description', ''),
                'market_trend': market_structure['trend'],
                'adx': momentum['adx'],
                'nearest_resistance': sr_levels['nearest_resistance'],
                'nearest_support': sr_levels['nearest_support'],
                'risk_reward': sr_levels['risk_reward_ratio'],
                'stop_loss': round(stop_loss, 2),
                'target_price': round(target_price, 2),
                'potential': round((target_price - current_price) / current_price * 100, 1),
                'signals': " | ".join(signals[:3])
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
