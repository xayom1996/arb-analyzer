# arbitrage_analyzer.py - Упрощенный анализатор без базы данных
from typing import List, Dict
from datetime import datetime
import logging
from collections import defaultdict
from data_models import PriceData, ArbitrageOpportunity, NotificationManager

class ArbitrageAnalyzer:
    def __init__(self, config):
        self.config = config
        self.notification_manager = NotificationManager(config.ALERT_COOLDOWN_MINUTES)
        self.logger = logging.getLogger(__name__)
        
        # Статистика для текущей сессии
        self.session_stats = {
            'cycles_completed': 0,
            'total_opportunities_found': 0,
            'alerts_sent': 0,
            'start_time': datetime.now()
        }
    
    def analyze_arbitrage_opportunities(self, price_data: List[PriceData]) -> List[ArbitrageOpportunity]:
        """Анализ возможностей арбитража"""
        opportunities = []
        
        # Группируем цены по символам
        prices_by_symbol = defaultdict(list)
        for price in price_data:
            prices_by_symbol[price.symbol].append(price)
        
        # Анализируем каждый символ
        for symbol, prices in prices_by_symbol.items():
            if len(prices) < 2:  # Нужно минимум 2 биржи
                continue
                
            symbol_opportunities = self._analyze_symbol(symbol, prices)
            opportunities.extend(symbol_opportunities)
        
        # Сортируем по убыванию разности цен
        opportunities.sort(key=lambda x: x.price_difference_percent, reverse=True)
        
        # Обновляем статистику
        self.session_stats['total_opportunities_found'] += len(opportunities)
        
        self.logger.info(f"Найдено {len(opportunities)} возможностей арбитража")
        return opportunities
    
    def _analyze_symbol(self, symbol: str, prices: List[PriceData]) -> List[ArbitrageOpportunity]:
        """Анализ арбитража для конкретного символа"""
        opportunities = []
        
        # Фильтруем цены с достаточным объемом
        valid_prices = [
            p for p in prices 
            if p.volume_24h >= self.config.MIN_VOLUME_USD
        ]
        
        if len(valid_prices) < 2:
            return opportunities
        
        # Сортируем по цене
        valid_prices.sort(key=lambda x: x.price)
        
        min_price_data = valid_prices[0]  # Самая низкая цена (покупка)
        max_price_data = valid_prices[-1]  # Самая высокая цена (продажа)
        
        # Рассчитываем разность в процентах
        price_difference = ((max_price_data.price - min_price_data.price) / min_price_data.price) * 100
        
        # Проверяем превышение порога
        if price_difference >= self.config.PRICE_DIFFERENCE_THRESHOLD:
            # Дополнительные проверки
            if self._is_valid_opportunity(symbol, min_price_data, max_price_data, price_difference):
                opportunity = ArbitrageOpportunity(
                    symbol=symbol,
                    buy_exchange=min_price_data.exchange,
                    sell_exchange=max_price_data.exchange,
                    buy_price=min_price_data.price,
                    sell_price=max_price_data.price,
                    price_difference_percent=price_difference,
                    min_volume_24h=min(min_price_data.volume_24h, max_price_data.volume_24h),
                    timestamp=datetime.now()
                )
                opportunities.append(opportunity)
        
        return opportunities
    
    def _is_valid_opportunity(self, symbol: str, buy_data: PriceData, sell_data: PriceData, 
                            price_difference: float) -> bool:
        """Валидация возможности арбитража"""
        
        # Проверяем что это не одна и та же биржа
        if buy_data.exchange == sell_data.exchange:
            return False
        
        # Проверяем временные метки (данные не старше 5 минут)
        now = datetime.now()
        if (now - buy_data.timestamp).seconds > 300 or (now - sell_data.timestamp).seconds > 300:
            return False
        
        # Проверяем минимальную ликвидность
        if buy_data.volume_24h < self.config.MIN_VOLUME_USD * 1.5 or sell_data.volume_24h < self.config.MIN_VOLUME_USD * 1.5:
            return False
        
        # Проверяем разумность разности (исключаем ошибки в данных)
        if price_difference > 50:
            self.logger.warning(f"Подозрительно большая разность для {symbol}: {price_difference:.2f}%")
            return False
        
        # Проверяем разумность цен
        if buy_data.price <= 0 or sell_data.price <= 0:
            return False
        
        return True
    
    def filter_notifications(self, opportunities: List[ArbitrageOpportunity]) -> List[ArbitrageOpportunity]:
        """Фильтрация уведомлений (избегаем спам)"""
        # Очищаем старые записи
        self.notification_manager.cleanup_old_notifications()
        
        # Фильтруем новые возможности
        new_opportunities = [
            opp for opp in opportunities 
            if self.notification_manager.should_notify(opp)
        ]
        
        # Ограничиваем количество уведомлений за цикл
        limited_opportunities = new_opportunities[:self.config.MAX_ALERTS_PER_CYCLE]
        
        if limited_opportunities:
            self.session_stats['alerts_sent'] += len(limited_opportunities)
        
        return limited_opportunities
    
    def get_market_overview(self, price_data: List[PriceData]) -> Dict[str, any]:
        """Обзор рынка"""
        # Группируем по символам
        symbols_data = defaultdict(list)
        for price in price_data:
            symbols_data[price.symbol].append(price)
        
        total_symbols = len(symbols_data)
        symbols_with_arbitrage = 0
        max_spread = 0
        best_opportunity = None
        exchange_counts = defaultdict(int)
        
        for symbol, prices in symbols_data.items():
            if len(prices) < 2:
                continue
                
            # Подсчитываем биржи
            for price in prices:
                exchange_counts[price.exchange] += 1
            
            # Находим спред
            min_price = min(prices, key=lambda x: x.price)
            max_price = max(prices, key=lambda x: x.price)
            spread = ((max_price.price - min_price.price) / min_price.price) * 100
            
            if spread >= self.config.PRICE_DIFFERENCE_THRESHOLD:
                symbols_with_arbitrage += 1
                
                if spread > max_spread:
                    max_spread = spread
                    best_opportunity = {
                        'symbol': symbol,
                        'buy_exchange': min_price.exchange,
                        'sell_exchange': max_price.exchange,
                        'spread': spread
                    }
        
        return {
            'timestamp': datetime.now(),
            'total_symbols_monitored': total_symbols,
            'symbols_with_arbitrage': symbols_with_arbitrage,
            'arbitrage_percentage': (symbols_with_arbitrage / total_symbols * 100) if total_symbols > 0 else 0,
            'max_spread_found': max_spread,
            'best_opportunity': best_opportunity,
            'exchanges_data_count': dict(exchange_counts),
            'session_stats': self.session_stats.copy(),
            'notification_stats': self.notification_manager.get_stats()
        }
    
    def update_session_stats(self):
        """Обновление статистики сессии"""
        self.session_stats['cycles_completed'] += 1
    
    def get_session_summary(self) -> str:
        """Краткая сводка сессии"""
        runtime = datetime.now() - self.session_stats['start_time']
        hours = runtime.total_seconds() / 3600
        
        return f"""📊 Сводка сессии:
• Время работы: {hours:.1f} часов
• Циклов выполнено: {self.session_stats['cycles_completed']}
• Найдено возможностей: {self.session_stats['total_opportunities_found']}
• Отправлено уведомлений: {self.session_stats['alerts_sent']}
• Среднее за цикл: {self.session_stats['total_opportunities_found'] / max(1, self.session_stats['cycles_completed']):.1f}"""