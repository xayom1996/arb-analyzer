# data_models.py - Простые модели данных без базы данных
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

@dataclass
class PriceData:
    symbol: str
    exchange: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    timestamp: datetime
    
    def __str__(self):
        return f"{self.symbol} на {self.exchange}: ${self.price:.6f} (${self.volume_24h:,.0f})"

@dataclass
class ArbitrageOpportunity:
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    price_difference_percent: float
    min_volume_24h: float
    timestamp: datetime
    
    def profit_estimation(self, trade_amount_usd: float = 1000) -> Dict[str, float]:
        """Быстрый расчет потенциальной прибыли"""
        coins_to_buy = trade_amount_usd / self.buy_price
        sell_revenue = coins_to_buy * self.sell_price
        gross_profit = sell_revenue - trade_amount_usd
        estimated_fees = trade_amount_usd * 0.002  # 0.2% комиссия
        net_profit = gross_profit - estimated_fees
        roi_percentage = (net_profit / trade_amount_usd) * 100
        
        return {
            'trade_amount': trade_amount_usd,
            'coins_quantity': coins_to_buy,
            'gross_profit': gross_profit,
            'estimated_fees': estimated_fees,
            'net_profit': net_profit,
            'roi_percentage': roi_percentage
        }
    
    def __str__(self):
        return f"{self.symbol}: {self.price_difference_percent:.2f}% ({self.buy_exchange} → {self.sell_exchange})"

# Простой менеджер уведомлений в памяти
class NotificationManager:
    def __init__(self, cooldown_minutes: int = 30):
        self.last_notifications: Dict[str, datetime] = {}
        self.cooldown_minutes = cooldown_minutes
    
    def should_notify(self, opportunity: ArbitrageOpportunity) -> bool:
        """Проверяет нужно ли отправлять уведомление"""
        key = f"{opportunity.symbol}_{opportunity.buy_exchange}_{opportunity.sell_exchange}"
        last_time = self.last_notifications.get(key)
        
        if last_time is None:
            self.last_notifications[key] = datetime.now()
            return True
        
        # Проверяем прошло ли достаточно времени
        time_diff = (datetime.now() - last_time).total_seconds() / 60
        if time_diff >= self.cooldown_minutes:
            self.last_notifications[key] = datetime.now()
            return True
        
        return False
    
    def cleanup_old_notifications(self):
        """Очищает старые записи"""
        cutoff_time = datetime.now()
        keys_to_remove = []
        
        for key, timestamp in self.last_notifications.items():
            time_diff = (cutoff_time - timestamp).total_seconds() / 3600  # часы
            if time_diff > 4:  # Удаляем записи старше 4 часов
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.last_notifications[key]
    
    def get_stats(self) -> Dict[str, int]:
        """Получение статистики уведомлений"""
        return {
            'active_cooldowns': len(self.last_notifications),
            'cooldown_minutes': self.cooldown_minutes
        }