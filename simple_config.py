# simple_config.py - Исправленная конфигурация без ошибок dataclass
import os
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class SimpleConfig:
    # Telegram (ОБЯЗАТЕЛЬНО)
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: os.getenv('TELEGRAM_BOT_TOKEN', ''))
    TELEGRAM_CHAT_ID: str = field(default_factory=lambda: os.getenv('TELEGRAM_CHAT_ID', ''))
    
    # Настройки арбитража
    PRICE_DIFFERENCE_THRESHOLD: float = field(default_factory=lambda: float(os.getenv('PRICE_THRESHOLD', '10.0')))
    MIN_VOLUME_USD: float = field(default_factory=lambda: float(os.getenv('MIN_VOLUME', '50000')))
    UPDATE_INTERVAL: int = field(default_factory=lambda: int(os.getenv('UPDATE_INTERVAL', '60')))
    
    # Биржи для мониторинга
    EXCHANGES: List[str] = field(default_factory=lambda: [
        'binance', 'bybit', 
        'okx', 'kucoin', 'gateio', 'mexc', 'bitget'
    ])
    
    # API ключи бирж (опционально для лучших лимитов)
    EXCHANGE_CREDENTIALS: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        'binance': {
            'apiKey': os.getenv('BINANCE_API_KEY', ''),
            'secret': os.getenv('BINANCE_SECRET', ''),
        },
        'okx': {
            'apiKey': os.getenv('OKX_API_KEY', ''),
            'secret': os.getenv('OKX_SECRET', ''),
            'password': os.getenv('OKX_PASSPHRASE', ''),
        },
        'bybit': {
            'apiKey': os.getenv('BYBIT_API_KEY', ''),
            'secret': os.getenv('BYBIT_SECRET', ''),
        },
        'kucoin': {
            'apiKey': os.getenv('KUCOIN_API_KEY', ''),
            'secret': os.getenv('KUCOIN_SECRET', ''),
            'password': os.getenv('KUCOIN_PASSPHRASE', ''),
        },
        'gateio': {
            'apiKey': os.getenv('GATEIO_API_KEY', ''),
            'secret': os.getenv('GATEIO_SECRET', ''),
        },
        'mexc': {
            'apiKey': os.getenv('MEXC_API_KEY', ''),
            'secret': os.getenv('MEXC_SECRET', ''),
        },
        'htx': {
            'apiKey': os.getenv('HTX_API_KEY', ''),
            'secret': os.getenv('HTX_SECRET', ''),
        },
        'bitget': {
            'apiKey': os.getenv('BITGET_API_KEY', ''),
            'secret': os.getenv('BITGET_SECRET', ''),
            'password': os.getenv('BITGET_PASSPHRASE', ''),
        }
    })
    
    # Исключения из мониторинга (топ монеты и стейблкоины)
    EXCLUDED_SYMBOLS: List[str] = field(default_factory=lambda: [
        'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'XRP', 'ADA', 'SOL', 
        'DOGE', 'MATIC', 'DOT', 'AVAX', 'SHIB', 'LTC', 'UNI',
        'BUSD', 'DAI', 'TUSD', 'USDD', 'FRAX'
    ])
    
    # Настройки уведомлений
    MAX_ALERTS_PER_CYCLE: int = field(default_factory=lambda: int(os.getenv('MAX_ALERTS', '5')))
    ALERT_COOLDOWN_MINUTES: int = field(default_factory=lambda: int(os.getenv('ALERT_COOLDOWN', '30')))
    
    # Логирование
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))
    LOG_FILE: str = field(default_factory=lambda: os.getenv('LOG_FILE', 'arbitrage.log'))