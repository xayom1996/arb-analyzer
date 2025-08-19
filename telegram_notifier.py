# telegram_notifier.py - Упрощенный Telegram уведомитель без базы данных
import asyncio
import httpx
from typing import List
from datetime import datetime
import logging
from data_models import ArbitrageOpportunity
import os
import json

class TelegramNotifier:
    def __init__(self, config):
        self.config = config
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.client = None
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self):
        """Инициализация Telegram клиента"""
        try:
            self.client = httpx.AsyncClient(timeout=30.0)
            
            # Проверяем токен бота
            response = await self.client.get(f"{self.base_url}/getMe")
            if response.status_code == 200:
                bot_info = response.json()
                bot_name = bot_info['result']['first_name']
                self.logger.info(f"✅ Telegram бот подключен: {bot_name}")
            else:
                raise Exception(f"Неверный токен бота: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Ошибка инициализации Telegram: {e}")
            raise
    
    async def get_all_chat_ids(self) -> List[int]:
        try:
            # Проверяем токен бота
            response = await self.client.get(f"{self.base_url}/getUpdates")
            if response.status_code == 200:
                updates_info = response.json()
                print(f"{self.base_url}/getUpdates")
                print(updates_info)
                results = updates_info['result']
                chat_ids = {}
                for result in results:
                	self.logger.info(f"getUpdate result: {result}")
                	if result['message']:
                		chat_ids.add(result['chat']['id'])
                self.logger.info(f"✅ chat_ids: {chat_ids}")
                return list(chat_ids)
            else:
            	raise Exception(f"Неверный токен бота: {response.text}")
            	
        except Exception as e:
            self.logger.error(f"Ошибка инициализации Telegram: {e}")
            raise
                    
    async def load_users(self) -> List:
        """Загрузка пользователей из файла"""
        try:
            if os.path.exists("users.json"):
                with open("users.json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                users = data.get('users', [])
                    
                self.logger.info(f"Загружено {len(users)} пользователей")
                
                return users
            else:
                self.logger.info("Файл пользователей не найден, создается новый")
                return []
                
        except Exception as e:
            self.logger.error(f"Ошибка загрузки пользователей: {e}")
            raise
    
    async def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Отправка сообщения в Telegram"""
        try:
            response = await self.client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }
            )
            
            if response.status_code == 200:
                return True
            else:
                self.logger.error(f"Ошибка отправки сообщения: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка отправки в Telegram: {e}")
            return False
    
    async def send_arbitrage_alerts(self, opportunities: List[ArbitrageOpportunity]):
        """Отправка уведомлений о возможностях арбитража"""
        if not opportunities:
            return
            
        try:
            for i, opportunity in enumerate(opportunities):
                profit_calc = opportunity.profit_estimation()
                
                x = int(opportunity.price_difference_percent // 1.95)
                signal_icons = "🚨" * x

                # Создаем красивое уведомление
                alert_message = f"""
{signal_icons} <b>АРБИТРАЖ {opportunity.price_difference_percent:.2f}%</b>

💎 <b>Монета:</b> {opportunity.symbol}
💰 <b>Спред:</b> <b>{opportunity.price_difference_percent:.2f}%</b>

📈 <b>КУПИТЬ:</b>
🏛️ Биржа: <b>{opportunity.buy_exchange}</b>
💵 Цена: <code>${opportunity.buy_price:.8f}</code>

📉 <b>ПРОДАТЬ:</b>
🏛️ Биржа: <b>{opportunity.sell_exchange}</b>
💵 Цена: <code>${opportunity.sell_price:.8f}</code>

📊 <b>Данные:</b>
📈 Объем 24ч: <code>${opportunity.min_volume_24h:,.0f}</code>
⏰ Время: <code>{opportunity.timestamp.strftime('%H:%M:%S')}</code>
                """.strip()
                
                success = await self.send_message(alert_message)
                
                if success:
                    self.logger.info(f"✅ Уведомление отправлено: {opportunity.symbol}")
                else:
                    self.logger.error(f"❌ Не удалось отправить уведомление: {opportunity.symbol}")
                
                # Пауза между сообщениями (избегаем лимиты)
                if i < len(opportunities) - 1:
                    await asyncio.sleep(2)
                
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомлений об арбитраже: {e}")
    
    async def send_system_message(self, message: str):
        """Отправка системных уведомлений"""
        try:
            system_message = f"🤖 <b>Система ArbitrageBot</b>\n\n{message}"
            await self.send_message(system_message)
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки системного сообщения: {e}")
    
    async def send_startup_message(self):
        """Отправка сообщения о запуске"""
        startup_message = f"""
🚀 <b>ArbitrageBot запущен!</b>

⚙️ <b>Настройки:</b>
• Порог спреда: <b>{self.config.PRICE_DIFFERENCE_THRESHOLD}%</b>
• Минимальный объем: <b>${self.config.MIN_VOLUME_USD:,}</b>
• Интервал обновления: <b>{self.config.UPDATE_INTERVAL} сек</b>
• Максимум уведомлений за цикл: <b>{self.config.MAX_ALERTS_PER_CYCLE}</b>
• Cooldown между уведомлениями: <b>{self.config.ALERT_COOLDOWN_MINUTES} мин</b>

🏛️ <b>Мониторимые биржи:</b>
{', '.join(self.config.EXCHANGES)}

📊 <b>Статус:</b> ✅ Активно мониторю рынок!

🔔 Вы будете получать уведомления только о новых возможностях арбитража.
        """.strip()
        
        await self.send_message(startup_message)
    
    async def send_market_summary(self, market_overview: dict):
        """Отправка сводки рынка"""
        try:
            best_opp = market_overview.get('best_opportunity')
            session_stats = market_overview.get('session_stats', {})
            
            summary_message = f"""
📊 <b>Сводка рынка</b>

📈 <b>Анализ:</b>
• Символов мониторится: <b>{market_overview['total_symbols_monitored']}</b>
• С арбитражем: <b>{market_overview['symbols_with_arbitrage']}</b>
• Процент: <b>{market_overview['arbitrage_percentage']:.1f}%</b>
• Максимальный спред: <b>{market_overview['max_spread_found']:.2f}%</b>

🎯 <b>Лучшая возможность:</b>
{f"• {best_opp['symbol']}: {best_opp['spread']:.2f}%" if best_opp else "• Не найдена"}

📊 <b>Статистика сессии:</b>
• Циклов выполнено: <b>{session_stats.get('cycles_completed', 0)}</b>
• Возможностей найдено: <b>{session_stats.get('total_opportunities_found', 0)}</b>
• Уведомлений отправлено: <b>{session_stats.get('alerts_sent', 0)}</b>

⏰ <b>Время:</b> {market_overview['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            await self.send_message(summary_message)
            
        except Exception as e:
            self.logger.error(f"Ошибка отправки сводки рынка: {e}")
    
    async def close(self):
        """Закрытие Telegram клиента"""
        if self.client:
            await self.client.aclose()
            self.logger.info("✅ Telegram клиент закрыт")
