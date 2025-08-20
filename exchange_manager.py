import ccxt
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import logging
from data_models import PriceData
from telegram_notifier import TelegramNotifier
from arbitrage_analyzer import ArbitrageAnalyzer

class ExchangeManager:
    def __init__(self, config):
        self.config = config
        self.exchanges = {}
        self.logger = logging.getLogger(__name__)
        
    async def initialize_exchanges(self):
        semaphore = asyncio.Semaphore(8)  # Максимум 8 одновременных запросов
        tasks = []

        for exchange_name in self.config.EXCHANGES:
            exchange_class = getattr(ccxt, exchange_name)
            credentials = self.config.EXCHANGE_CREDENTIALS.get(exchange_name, {})
            print(credentials)
            
            exchange = exchange_class({
                **credentials,
                'enableRateLimit': True,
                'timeout': 30000,
            })

            print(exchange_name)

            self.exchanges[exchange_name] = exchange

        for exchange_name in self.exchanges.keys():
            exchange = self.exchanges.get(exchange_name)
            task = self.load_markets(exchange_name)
            tasks.append(task)
        
        async def limited_fetch(task):
            async with semaphore:
                try:
                    return await task
                except Exception as e:
                    self.logger.error(f"Ошибка инициализации биржи {task}: {e}")
        
        results = await asyncio.gather(*[limited_fetch(task) for task in tasks], 
                                    return_exceptions=True)

        # print(len(results))

        # """Инициализация всех бирж"""
        # for exchange_name in self.config.EXCHANGES:
        #     try:
        #         exchange_class = getattr(ccxt, exchange_name)
        #         credentials = self.config.EXCHANGE_CREDENTIALS.get(exchange_name, {})
                
        #         exchange = exchange_class({
        #             **credentials,
        #             'enableRateLimit': True,
        #             'timeout': 30000,
        #         })
                
        #         # Проверка подключения с правильной обработкой sync/async
        #         if hasattr(exchange, 'fetch_currencies'):
        #             try:
        #                 if asyncio.iscoroutinefunction(exchange.fetch_currencies):
        #                     await exchange.fetch_currencies()
        #                 else:
        #                     # Запускаем синхронный метод в отдельном потоке
        #                     loop = asyncio.get_event_loop()
        #                     await loop.run_in_executor(None, exchange.fetch_currencies)
                        
        #                 self.exchanges[exchange_name] = exchange
        #                 self.logger.info(f"Биржа {exchange_name} инициализирована успешно")
        #             except Exception as load_error:
        #                 self.logger.warning(f"Не удалось загрузить рынки для {exchange_name}: {load_error}")
        #                 # Продолжаем без загрузки рынков
                
        #     except Exception as e:
        #         self.logger.error(f"Ошибка инициализации биржи {exchange_name}: {e}")
                
        # self.logger.info(f"Инициализировано {len(self.exchanges)} бирж")
    
    async def load_markets(self, exchange_name: str) -> dict:
        """Получение данных load_markets с биржи"""
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return None
            
            # Проверяем есть ли метод load_markets
            if not hasattr(exchange, 'load_markets'):
                return None
                
            # Определяем синхронный или асинхронный метод
            if asyncio.iscoroutinefunction(exchange.load_markets):
                data = await exchange.load_markets()
            else:
                print(exchange_name)
                # Запускаем синхронный метод в отдельном потоке
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, exchange.load_markets) 
            
            return data
            
        except Exception as e:
            self.logger.warning(f"Ошибка получения тикера {symbol} с {exchange_name}: {e}")
            return None
    
    async def get_all_symbols(self) -> List[str]:
        """Получение списка всех символов доступных на биржах"""
        all_symbols = set()
        
        for exchange_name, exchange in self.exchanges.items():
            try:
                markets = exchange.markets
                self.logger.error(f"{exchange.name}: {markets}")
                for symbol in markets:
                    if self._is_valid_symbol(symbol, markets[symbol]):
                        all_symbols.add(symbol)
                        
            except Exception as e:
                self.logger.error(f"Ошибка получения символов с {exchange_name}: {e}")
        
        # Исключаем топ монеты и стейблкоины
        filtered_symbols = [
            symbol for symbol in all_symbols 
            if not any(excluded in symbol for excluded in self.config.EXCLUDED_SYMBOLS)
        ]
        
        self.logger.info(f"Найдено {len(filtered_symbols)} символов для мониторинга")
        return sorted(filtered_symbols)
    
    def _is_valid_symbol(self, symbol: str, market: dict) -> bool:
        """Проверка валидности символа для торговли"""
        try:
            # Проверяем что это спот торговля
            if market.get('type') != 'spot':
                return False
                
            # Проверяем что торговля активна
            if not market.get('active', False):
                return False
                
            # Проверяем что это не фьючерс или опцион
            if any(keyword in symbol.upper() 
                   for keyword in ['PERP', 'SWAP', 'FUTURE', '-', 'USDT-', 'BUSD-']):
                return False
                
            # Проверяем базовую валюту (исключаем фиатные пары)
            quote = market.get('quote', '').upper()
            if quote not in ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']:
                return False
            
            if 'USDT' not in symbol:
            	return False
            
            if 'USD' in symbol.split('/')[0]:
                return False
                
            return True
            
        except Exception:
            return False


    async def get_currency_networks(self, exchange_name: str, currency: str, price: float) -> str:
        exchange = self.exchanges.get(exchange_name)
        networks = ''
        if not exchange:
            return None 
        
        currency_info = exchange.currency(currency)

        if currency_info and 'networks' in currency_info:
            for network, data in currency_info['networks'].items():
                if data['active'] == True:
                    networks += f"\n{network}"
                    if data['fee'] != None:
                        networks += f", Комиссия: {round(data['fee'] * price, 2)} USDT\n"
                # networks += f"Withdraw Enabled: {data['withdraw']}\n"
                # networks += f"Deposit Enabled: {data['deposit']}\n"
        
        if networks == '':
            networks = 'Пусто'
            
        return networks
            
    async def fetch_ticker_data(self, exchange_name: str, symbol: str) -> Optional[PriceData]:
        """Получение данных тикера с биржи"""
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return None
                
            
            # Проверяем есть ли метод fetch_ticker
            if not hasattr(exchange, 'fetch_ticker'):
                return None
                
            # Определяем синхронный или асинхронный метод
            if asyncio.iscoroutinefunction(exchange.fetch_ticker):
                ticker = await exchange.fetch_ticker(symbol)
            else:
                # Запускаем синхронный метод в отдельном потоке
                loop = asyncio.get_event_loop()
                ticker = await loop.run_in_executor(None, exchange.fetch_ticker, symbol) 
            
            # self.logger.info(f"Данные с тикера {symbol} {exchange_name} {ticker}")
            
            # Проверяем минимальный объем торгов
            volume_usd = ticker.get('quoteVolume', 0) or 0
            if volume_usd < self.config.MIN_VOLUME_USD:
                return None
                
            return PriceData(
                symbol=symbol,
                exchange=exchange_name,
                price=ticker['last'],
                bid=ticker['bid'],
                ask=ticker['ask'],
                volume_24h=volume_usd,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.warning(f"Ошибка получения тикера {symbol} с {exchange_name}: {e}")
            return None
    
    async def fetch_all_tickers(self, symbols: List[str], telegram_notifier: TelegramNotifier, arbitrage_analyzer: ArbitrageAnalyzer):
        """Получение всех тикеров со всех бирж"""
        
        # Создаем задачи для параллельного выполнения
        for symbol in symbols:
            tasks = []
            all_price_data = []
             # Выполняем все запросы параллельно с ограничением
            semaphore = asyncio.Semaphore(8)  # Максимум 8 одновременных запросов

            for exchange_name in self.exchanges.keys():
                task = self.fetch_ticker_data(exchange_name, symbol)
                tasks.append(task)
            
            async def limited_fetch(task):
                async with semaphore:
                    return await task
            
            results = await asyncio.gather(*[limited_fetch(task) for task in tasks], 
                                        return_exceptions=True)
            
            # Фильтруем успешные результаты
            for result in results:
                if isinstance(result, PriceData):
                    all_price_data.append(result)
            
            opportunities = arbitrage_analyzer.analyze_arbitrage_opportunities(
                    all_price_data)
            
            for opp in opportunities: 
                opp.buy_exchange_networks = await self.get_currency_networks(opp.buy_exchange, opp.symbol.split('/')[0], opp.buy_price)
                opp.sell_exchange_networks = await self.get_currency_networks(opp.sell_exchange, opp.symbol.split('/')[0], opp.sell_price)

            self.logger.info(f"Найдено {len(opportunities)} возможностей для {symbol}")

            await telegram_notifier.send_arbitrage_alerts(opportunities)

        return
    
    async def fetch_popular_symbols(self, limit: int = 200) -> List[str]:
        """Получение популярных символов на основе объема торгов"""
        symbol_volumes = {}
        
        # Получаем данные с Binance как основной биржи
        try:
            binance = self.exchanges.get('binance')
            if binance:
            	if asyncio.iscoroutinefunction(binance.fetch_tickers):
            		tickers = await binance.fetch_tickers()
            	else:
                	# Запускаем синхронный метод в отдельном потоке
                	loop = asyncio.get_event_loop()
                	tickers = await loop.run_in_executor(None, binance.fetch_tickers)
				
            	for symbol, ticker in tickers.items():
            		if self._is_valid_symbol(symbol, binance.markets.get(symbol, {})):
            			volume_usd = ticker.get('quoteVolume', 0) or 0
            			if volume_usd >= self.config.MIN_VOLUME_USD:
            				symbol_volumes[symbol] = volume_usd
                            
        except Exception as e:
            self.logger.error(f"Ошибка получения популярных символов: {e}")
        
        # Сортируем по объему и берем топ
        sorted_symbols = sorted(symbol_volumes.items(), key=lambda x: x[1], reverse=True)
        popular_symbols = [symbol for symbol, _ in sorted_symbols[:limit]]
        
        # Исключаем топ монеты
        filtered_symbols = [
            symbol for symbol in popular_symbols 
            if not any(excluded in symbol.split('/')[0] for excluded in self.config.EXCLUDED_SYMBOLS)
        ]
        
        self.logger.info(f"Найдено {len(filtered_symbols)} популярных символов")
        return filtered_symbols
    
    async def close_all_exchanges(self):
        """Закрытие всех подключений к биржам"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close()
                self.logger.info(f"Закрыто подключение к {exchange_name}")
            except Exception as e:
                self.logger.error(f"Ошибка закрытия {exchange_name}: {e}")
    
    def get_exchange_names(self) -> List[str]:
        """Получение списка подключенных бирж"""
        return list(self.exchanges.keys())