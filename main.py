# main.py - Упрощенное основное приложение без баз данных
import aiohttp
from aiohttp import web, web_runner
import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import List
import os
from dotenv import load_dotenv
from simple_config import SimpleConfig
from data_models import PriceData, ArbitrageOpportunity
from arbitrage_analyzer import ArbitrageAnalyzer
from exchange_manager import ExchangeManager
from telegram_notifier import TelegramNotifier


class ArbitrageBotSystem:
    def __init__(self):
        self.config = SimpleConfig()
        self.exchange_manager = None
        self.arbitrage_analyzer = None
        self.telegram_notifier = None
        self.is_running = False
        self.logger = self._setup_logging()

    def _setup_logging(self):
        """Настройка логирования"""
        # Создаем директорию для логов
        # os.makedirs('logs', exist_ok=True)

        # logging.basicConfig(
        #     level=getattr(logging, self.config.LOG_LEVEL),
        #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        #     handlers=[
        #         logging.FileHandler(f'logs/{self.config.LOG_FILE}'),
        #         logging.StreamHandler(sys.stdout)
        #     ]
        # )
        return logging.getLogger(__name__)

    async def initialize(self):
        """Инициализация всех компонентов системы"""
        self.logger.info(
            "🚀 Запуск системы ArbitrageBot (упрощенная версия)...")

        try:
            # Проверка обязательных настроек
            if not self.config.TELEGRAM_BOT_TOKEN:
                raise Exception("TELEGRAM_BOT_TOKEN не задан")
            if not self.config.TELEGRAM_CHAT_ID:
                raise Exception("TELEGRAM_CHAT_ID не задан")

            # Инициализация менеджера бирж
            self.exchange_manager = ExchangeManager(self.config)

            # Инициализация анализатора арбитража
            self.arbitrage_analyzer = ArbitrageAnalyzer(self.config)
            self.logger.info("✅ Анализатор арбитража инициализирован")

            # Инициализация Telegram уведомителя
            self.telegram_notifier = TelegramNotifier(self.config)
            await self.telegram_notifier.initialize()
            self.logger.info("✅ Telegram уведомитель инициализирован")

            # Отправляем уведомление о запуске
            await self.telegram_notifier.send_system_message("🚀 ArbitrageBot запущен и начинает мониторинг!")

            self.logger.info("🎉 Все компоненты инициализированы успешно!")

        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации: {e}")
            raise

    async def get_monitoring_symbols(self) -> List[str]:
        """Получение списка символов для мониторинга"""
        try:
            # Получаем популярные символы на основе объема торгов
            symbols = await self.exchange_manager.fetch_popular_symbols(limit=400)

            if not symbols:
                self.logger.warning(
                    "Не удалось получить символы, используем базовый список")
                # Базовый список популярных альткоинов
                symbols = [
                    'AVAX/USDT', 'POL/USDT', 'LINK/USDT', 'ATOM/USDT', 'NEAR/USDT',
                    'FTM/USDT', 'ONE/USDT', 'ALGO/USDT', 'VET/USDT', 'ENJ/USDT',
                    'SAND/USDT', 'MANA/USDT', 'AXS/USDT', 'GALA/USDT', 'CHZ/USDT',
                    'FIL/USDT', 'XTZ/USDT', 'EGLD/USDT', 'FLOW/USDT', 'ICP/USDT'
                ]

            self.logger.info(f"Мониторим {len(symbols)} символов")
            return symbols

        except Exception as e:
            self.logger.error(f"Ошибка получения символов: {e}")
            return []

    async def monitoring_cycle(self):
        """Основной цикл мониторинга"""
        cycle_count = 0

        while self.is_running:
            try:
                cycle_start = datetime.now()
                cycle_count += 1

                self.logger.info(f"🔄 Цикл мониторинга #{cycle_count} начат...")

                await self.exchange_manager.initialize_exchanges()
                self.logger.info("✅ Биржи load markets успешны")

                # Получаем символы для мониторинга
                symbols = await self.get_monitoring_symbols()
                if not symbols:
                    await asyncio.sleep(60)
                    continue

                # Получаем данные с бирж
                self.logger.info("📊 Сбор данных с бирж...")
                await self.exchange_manager.fetch_all_tickers(symbols, self.telegram_notifier, self.arbitrage_analyzer)

                # Обновляем статистику
                self.arbitrage_analyzer.update_session_stats()

                # Рассчитываем время выполнения
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                self.logger.info(
                    f"⏱️ Цикл #{cycle_count} завершен за {cycle_duration:.2f} сек")

                # Ждем до следующего цикла
                sleep_time = max(
                    0, self.config.UPDATE_INTERVAL - cycle_duration)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except KeyboardInterrupt:
                self.logger.info("Получен сигнал остановки")
                break

            except Exception as e:
                self.logger.error(f"❌ Ошибка в цикле мониторинга: {e}")
                await self.telegram_notifier.send_system_message(f"⚠️ Ошибка мониторинга: {str(e)[:100]}...")
                await asyncio.sleep(30)  # Пауза при ошибке

    async def run(self):
        """Запуск основного цикла"""
        try:
            await self.initialize()

            self.is_running = True

            # Запускаем мониторинг
            await self.monitoring_cycle()

        except KeyboardInterrupt:
            self.logger.info("Получен сигнал остановки от пользователя")
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
            if self.telegram_notifier:
                await self.telegram_notifier.send_system_message(f"🚨 Критическая ошибка: {str(e)[:100]}...")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы"""
        self.logger.info("🛑 Завершение работы системы...")
        self.is_running = False

        try:
            if self.telegram_notifier:
                session_summary = self.arbitrage_analyzer.get_session_summary()
                await self.telegram_notifier.send_system_message(f"🛑 Система завершает работу\n\n{session_summary}")
                await self.telegram_notifier.close()

            if self.exchange_manager:
                await self.exchange_manager.close_all_exchanges()

            self.logger.info("✅ Система корректно завершена")

        except Exception as e:
            self.logger.error(f"Ошибка при завершении: {e}")


# Простой HTTP сервер для health check


class HealthServer:
    def __init__(self, port: int = 8000):
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.site = None

    async def health_handler(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'arbitrage-bot'
        })

    async def start(self):
        """Запуск health check сервера"""
        self.app.router.add_get('/health', self.health_handler)
        self.runner = web_runner.AppRunner(self.app)
        await self.runner.setup()
        self.site = web_runner.TCPSite(self.runner, '0.0.0.0', self.port)
        await self.site.start()

    async def stop(self):
        """Остановка health check сервера"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()


async def main():
    """Главная функция"""
    # Создаем систему
    bot_system = ArbitrageBotSystem()

    # Создаем health check сервер
    health_server = HealthServer()

    # Обработка сигналов остановки
    def signal_handler(signum, frame):
        bot_system.is_running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Запускаем health check сервер
        await health_server.start()
        bot_system.logger.info("✅ Health check сервер запущен на порту 8000")

        # Запускаем основную систему
        await bot_system.run()

    finally:
        # Останавливаем health check сервер
        await health_server.stop()

if __name__ == "__main__":
    # Проверяем наличие обязательных переменных окружения
    load_dotenv()
    required_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(
            f"❌ Не заданы обязательные переменные окружения: {', '.join(missing_vars)}")
        print("\nПример настройки:")
        print("export TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("export TELEGRAM_CHAT_ID='your_chat_id'")
        print("\nИли создайте .env файл с этими переменными")
        sys.exit(1)

    # Запускаем систему
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 ArbitrageBot остановлен")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)
