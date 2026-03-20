"""
LongScreener - Скринер для поиска долгосрочных сетапов
Улучшенная версия с детальным анализом
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class LongScreener:
    def __init__(self):
        self.min_price = 1.5
        self.min_cap = 500_000_000
        self.min_volume = 600_000
        self.max_pe = 25
        self.min_growth = 0.15
        self.min_roe = 0.15
        self.max_debt_equity = 0.5
        
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
    
    def find_levels(self, df, window=5):
        """Поиск уровней поддержки/сопротивления"""
        levels = []
        for i in range(window, len(df) - window):
            if df['Low'].iloc[i] == df['Low'].iloc[i-window:i+window+1].min():
                levels.append({'price': df['Low'].iloc[i], 'type': 'support', 'touches': 1})
            if df['High'].iloc[i] == df['High'].iloc[i-window:i+window+1].max():
                levels.append({'price': df['High'].iloc[i], 'type': 'resistance', 'touches': 1})
        
        # Группировка близких уровней
        grouped_levels = []
        for level in levels:
            found = False
            for gl in grouped_levels:
                if abs(gl['price'] - level['price']) / gl['price'] < 0.015:
                    gl['touches'] += 1
                    found = True
                    break
            if not found:
                grouped_levels.append({'price': level['price'], 'type': level['type'], 'touches': level['touches']})
        
        # Сортируем по силе (количеству касаний)
        grouped_levels.sort(key=lambda x: x['touches'], reverse=True)
        return grouped_levels[:5]
    
    def check_earnings_risk(self, stock) -> Dict:
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
    
    def calculate_relative_strength(self, hist: pd.DataFrame) -> Dict:
        """Расчет относительной силы vs SPY"""
        try:
            spy = yf.Ticker("SPY").history(period="90d")
            if spy is None or spy.empty:
                return {'rs_score': 0, 'is_leader': False, 'rs_20d': 0}
            
            current_price = hist['Close'].iloc[-1]
            stock_20d = (current_price / hist['Close'].iloc[-20] - 1) * 100 if len(hist) >= 20 else 0
            spy_20d = (spy['Close'].iloc[-1] / spy['Close'].iloc[-20] - 1) * 100 if len(spy) >= 20 else 0
            
            rs_20d = stock_20d - spy_20d
            
            rs_score = 0
            if rs_20d > 5: rs_score += 15
            elif rs_20d > 0: rs_score += 5
            
            return {
                'rs_20d': round(rs_20d, 2),
                'rs_score': rs_score,
                'is_leader': rs_20d > 3,
                'vs_spy_20d': round(stock_20d - spy_20d, 2)
            }
        except:
            return {'rs_score': 0, 'is_leader': False, 'rs_20d': 0}
    
    def analyze_volume(self, hist: pd.DataFrame) -> Dict:
        """Анализ объема"""
        try:
            current_vol = hist['Volume'].iloc[-1]
            avg_vol_20 = hist['Volume'].tail(20).mean()
            rel_volume = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
            vol_trend = hist['Volume'].tail(5).mean() / avg_vol_20 if avg_vol_20 > 0 else 1.0
            
            vol_score = 0
            if rel_volume > 2.0: vol_score += 20
            elif rel_volume > 1.5: vol_score += 10
            if vol_trend > 1.2: vol_score += 10
            
            return {
                'rel_volume': round(rel_volume, 2),
                'vol_score': vol_score,
                'is_accumulation': rel_volume > 1.5 and hist['Close'].iloc[-1] > hist['Close'].iloc[-5]
            }
        except:
            return {'rel_volume': 1.0, 'vol_score': 0, 'is_accumulation': False}
    
    def calculate_fundamental_score(self, info: Dict, current_price: float) -> tuple:
        """Расчет фундаментального скора"""
        score = 0
        details = {}
        
        # P/E
        pe = info.get('trailingPE') or info.get('forwardPE')
        pe = self.safe_float(pe, None)
        if pe and 0 < pe < self.max_pe:
            pe_score = int((self.max_pe - pe) / self.max_pe * 25)
            score += pe_score
            details['pe'] = round(pe, 2)
        elif pe and pe > 0:
            details['pe'] = round(pe, 2)
        
        # Revenue Growth
        revenue_growth = info.get('revenueGrowth')
        revenue_growth = self.safe_float(revenue_growth, 0)
        if revenue_growth and revenue_growth > self.min_growth:
            growth_score = min(int(revenue_growth / self.min_growth * 20), 25)
            score += growth_score
            details['revenue_growth'] = round(revenue_growth * 100, 1)
        elif revenue_growth:
            details['revenue_growth'] = round(revenue_growth * 100, 1)
        
        # ROE
        roe = info.get('returnOnEquity')
        roe = self.safe_float(roe, 0)
        if roe and roe > self.min_roe:
            score += 20
            details['roe'] = round(roe * 100, 1)
        elif roe:
            details['roe'] = round(roe * 100, 1)
        
        # Debt/Equity
        debt_to_equity = info.get('debtToEquity')
        debt_to_equity = self.safe_float(debt_to_equity, None)
        if debt_to_equity is not None:
            de_ratio = debt_to_equity / 100
            if de_ratio < self.max_debt_equity:
                score += 15
                details['debt_equity'] = round(de_ratio, 2)
            else:
                details['debt_equity'] = round(de_ratio, 2)
        
        # Profit Margin
        profit_margin = info.get('profitMargins')
        profit_margin = self.safe_float(profit_margin, 0)
        if profit_margin and profit_margin > 0.20:
            score += 15
            details['profit_margin'] = round(profit_margin * 100, 1)
        elif profit_margin:
            details['profit_margin'] = round(profit_margin * 100, 1)
        
        # 52W Upside
        fifty_two_week_high = info.get('fiftyTwoWeekHigh')
        fifty_two_week_high = self.safe_float(fifty_two_week_high, None)
        if fifty_two_week_high and current_price > 0:
            upside = (fifty_two_week_high - current_price) / current_price * 100
            if 10 <= upside <= 40:
                score += 10
                details['upside_to_52w_high'] = round(upside, 1)
            else:
                details['upside_to_52w_high'] = round(upside, 1)
        
        return score, details
    
    def calculate_risk_levels(self, hist: pd.DataFrame, tech_details: Dict, current_price: float) -> Dict:
        """Расчет уровней риска"""
        try:
            atr = (hist['High'] - hist['Low']).rolling(14).mean().iloc[-1]
            nearest_support = tech_details.get('nearest_level')
            
            if nearest_support and nearest_support['type'] == 'support':
                stop_loss = nearest_support['price'] * 0.98
                stop_type = "Уровень"
            else:
                stop_loss = current_price - (2 * atr)
                stop_type = "2xATR"
            
            risk_per_share = current_price - stop_loss
            risk_pct = (risk_per_share / current_price) * 100 if current_price > 0 else 0
            
            high_52w = hist['High'].max()
            potential_reward = high_52w - current_price
            rr = potential_reward / risk_per_share if risk_per_share > 0 else 0
            
            return {
                'stop_loss': round(stop_loss, 2),
                'stop_type': stop_type,
                'risk_per_share': round(risk_per_share, 2),
                'risk_pct': round(risk_pct, 2),
                'risk_reward': round(rr, 2),
                'potential_gain_pct': round((potential_reward/current_price)*100, 1)
            }
        except:
            return {
                'stop_loss': current_price * 0.95,
                'stop_type': 'Default',
                'risk_per_share': round(current_price * 0.05, 2),
                'risk_pct': 5.0,
                'risk_reward': 0
            }
    
    def analyze_ticker(self, ticker: str) -> Optional[Dict]:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="180d")
            info = stock.info
            
            if hist.empty or len(hist) < 50:
                return None
                
            current_price = hist['Close'].iloc[-1]
            
            # Базовые фильтры
            if current_price < self.min_price:
                return None
                
            market_cap = info.get('marketCap', 0)
            if market_cap < self.min_cap:
                return None
            
            # Проверка earnings
            earnings = self.check_earnings_risk(stock)
            if earnings.get('skip'):
                return None
            
            # Технический анализ
            ema20 = self.calculate_ema(hist['Close'], 20).iloc[-1]
            ema50 = self.calculate_ema(hist['Close'], 50).iloc[-1]
            ema200 = self.calculate_ema(hist['Close'], 200).iloc[-1] if len(hist) >= 200 else ema50
            
            # Определение тренда
            trend = "neutral"
            trend_score = 0
            
            if current_price > ema20 > ema50 > ema200:
                trend = "strong_uptrend"
                trend_score = 25
            elif current_price > ema50 > ema200:
                trend = "uptrend"
                trend_score = 20
            elif ema20 > current_price > ema50 and current_price > ema200:
                trend = "pullback_to_ema50"
                trend_score = 30
            elif current_price > ema20 and abs(current_price - ema20)/ema20 < 0.02 and current_price > ema50:
                trend = "bouncing_off_ema20"
                trend_score = 25
            elif current_price < ema50 and current_price < ema200:
                trend = "downtrend"
                trend_score = 0
            elif current_price < ema50:
                trend = "correction"
                trend_score = 5
            
            # Уровни
            levels = self.find_levels(hist)
            nearest_level = None
            level_info = ""
            
            if levels:
                nearest = min(levels, key=lambda x: abs(x['price'] - current_price))
                dist_pct = abs(nearest['price'] - current_price) / current_price * 100
                if dist_pct < 5:
                    nearest_level = nearest
                    level_info = f"{nearest['type']} ${nearest['price']:.2f}"
            
            # ATR
            atr = (hist['High'] - hist['Low']).rolling(14).mean().iloc[-1]
            atr_pct = atr / current_price * 100
            
            # Фундаменталы
            fund_score, fund_details = self.calculate_fundamental_score(info, current_price)
            
            # Relative Strength
            rs_data = self.calculate_relative_strength(hist)
            
            # Volume
            vol_data = self.analyze_volume(hist)
            
            # Итоговый скор
            total_score = trend_score + fund_score + rs_data.get('rs_score', 0) + vol_data.get('vol_score', 0)
            
            # Риск-менеджмент
            tech_details = {'trend': {'trend': trend}, 'nearest_level': nearest_level}
            risk = self.calculate_risk_levels(hist, tech_details, current_price)
            
            # Грейд
            if trend == 'downtrend':
                total_score = min(total_score, 65)
                grade = "👀 REVERSAL WATCH" if (trend_score >= 10 and fund_score >= 70) else "❌ DOWNTREND"
            elif trend in ['correction', 'sideways']:
                if total_score >= 85 and rs_data.get('is_leader') and vol_data.get('is_accumulation'):
                    grade = "🥇 STRONG BUY"
                elif total_score >= 75 and fund_score >= 45:
                    grade = "🥈 BUY"
                elif total_score >= 60:
                    grade = "👀 WATCH"
                else:
                    grade = "PASS"
            elif trend in ['uptrend', 'strong_uptrend', 'weak_uptrend']:
                if total_score >= 110 and rs_data.get('is_leader'):
                    grade = "🥇 STRONG BUY"
                elif total_score >= 85:
                    grade = "🥈 BUY"
                elif total_score >= 65:
                    grade = "👀 WATCH"
                else:
                    grade = "PASS"
            elif trend in ['pullback_to_ema50', 'bouncing_off_ema20']:
                total_score += 5
                if total_score >= 95 and rs_data.get('is_leader'):
                    grade = "🥇 PERFECT ENTRY"
                elif total_score >= 80:
                    grade = "🥈 BUY"
                else:
                    grade = "👀 WATCH"
            else:
                grade = "PASS"
            
            return {
                'ticker': ticker,
                'grade': grade,
                'price': round(current_price, 2),
                'score': total_score,
                'trend': trend,
                'ema50': round(ema50, 2),
                'level_info': level_info,
                'pe': fund_details.get('pe'),
                'roe': fund_details.get('roe'),
                'market_cap': round(market_cap/1e9, 2),
                'rs_20d': rs_data.get('rs_20d'),
                'rvol': vol_data.get('rel_volume'),
                'atr_pct': round(atr_pct, 2),
                'stop_loss': risk.get('stop_loss'),
                'risk_reward': risk.get('risk_reward'),
                'potential_gain': risk.get('potential_gain_pct')
            }
            
        except Exception as e:
            return None
    
    def screen_tickers(self, tickers: List[str]) -> List[Dict]:
        results = []
        for ticker in tickers:
            result = self.analyze_ticker(ticker)
            if result and result['grade'] not in ['PASS', '❌ DOWNTREND']:
                results.append(result)
        return sorted(results, key=lambda x: x['score'], reverse=True)
