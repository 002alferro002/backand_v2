import aiohttp
from typing import Dict, Optional
from datetime import datetime
from cryptoscan.backand.core.core_logger import get_logger
from cryptoscan.backand.core.core_utils import CoreUtils
from cryptoscan.backand.settings import get_setting

logger = get_logger(__name__)


class TelegramBot:
    """Telegram бот для отправки уведомлений"""
    
    def __init__(self):
        self.bot_token = get_setting('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = get_setting('TELEGRAM_CHAT_ID', '')
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram бот не настроен. Проверьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env")
        else:
            logger.info("Telegram бот инициализирован")

    def _format_timestamp(self, timestamp) -> str:
        """Форматирование timestamp для отображения в UTC"""
        return CoreUtils.format_timestamp(timestamp, '%H:%M:%S UTC')

    async def send_volume_alert(self, alert_data: Dict) -> bool:
        """Отправка алерта по объему в Telegram"""
        if not self.enabled:
            return False

        try:
            symbol = alert_data['symbol']
            price = alert_data['price']
            volume_ratio = alert_data.get('volume_ratio', 0)
            current_volume = alert_data.get('current_volume_usdt', 0)
            average_volume = alert_data.get('average_volume_usdt', 0)
            is_closed = alert_data.get('is_closed', False)
            is_true_signal = alert_data.get('is_true_signal')
            timestamp = alert_data.get('close_timestamp', alert_data['timestamp'])
            
            # Определяем статус и эмодзи
            if is_closed:
                if is_true_signal:
                    emoji = "✅"
                    status = "Истинный сигнал"
                else:
                    emoji = "❌"
                    status = "Ложный сигнал"
            else:
                emoji = "⚡"
                status = "В процессе"
            
            # Форматируем время
            time_str = self._format_timestamp(timestamp)
            
            # Формируем сообщение
            message = f"""
{emoji} <b>АЛЕРТ ПО ОБЪЕМУ</b>

💰 <b>Пара:</b> {symbol}
💵 <b>Цена:</b> ${price:,.8f}
📊 <b>Превышение объема:</b> {volume_ratio}x
📈 <b>Текущий объем:</b> ${current_volume:,.0f}
📉 <b>Средний объем:</b> ${average_volume:,.0f}
🎯 <b>Статус:</b> {status}
🕐 <b>Время:</b> {time_str}

🔗 <a href="https://www.tradingview.com/chart/?symbol=BYBIT:{symbol.replace('USDT', '')}USDT.P&interval=1">Открыть в TradingView</a>

#VolumeAlert #{symbol.replace('USDT', '')}
            """.strip()
            
            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Ошибка отправки алерта по объему в Telegram: {e}")
            return False

    async def send_preliminary_alert(self, alert_data: Dict) -> bool:
        """Отправка предварительного алерта в Telegram"""
        if not self.enabled:
            return False

        try:
            symbol = alert_data['symbol']
            price = alert_data['price']
            volume_ratio = alert_data.get('volume_ratio', 0)
            current_volume = alert_data.get('current_volume_usdt', 0)
            timestamp = alert_data['timestamp']
            
            # Форматируем время
            time_str = self._format_timestamp(timestamp)
            
            message = f"""
⚡ <b>ПРЕДВАРИТЕЛЬНЫЙ СИГНАЛ</b>

💰 <b>Пара:</b> {symbol}
💵 <b>Цена:</b> ${price:,.8f}
📊 <b>Превышение объема:</b> {volume_ratio}x
📈 <b>Объем:</b> ${current_volume:,.0f}
🕐 <b>Время:</b> {time_str}

⏳ <b>Ожидаем закрытия свечи для подтверждения...</b>

🔗 <a href="https://www.tradingview.com/chart/?symbol=BYBIT:{symbol.replace('USDT', '')}USDT.P&interval=1">Открыть в TradingView</a>

#PreliminaryAlert #{symbol.replace('USDT', '')}
            """.strip()
            
            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Ошибка отправки предварительного алерта в Telegram: {e}")
            return False

    async def send_final_alert(self, alert_data: Dict) -> bool:
        """Отправка финального алерта в Telegram"""
        if not self.enabled:
            return False

        try:
            symbol = alert_data['symbol']
            price = alert_data['price']
            volume_ratio = alert_data.get('volume_ratio', 0)
            is_true_signal = alert_data.get('is_true_signal', False)
            timestamp = alert_data.get('close_timestamp', alert_data['timestamp'])
            preliminary_timestamp = alert_data.get('preliminary_timestamp')
            
            # Определяем статус и эмодзи
            if is_true_signal:
                emoji = "✅"
                status = "Истинный LONG"
            else:
                emoji = "❌"
                status = "Ложный сигнал (SHORT)"
            
            # Форматируем время
            time_str = self._format_timestamp(timestamp)
            preliminary_time_str = self._format_timestamp(preliminary_timestamp) if preliminary_timestamp else "N/A"
            
            message = f"""
{emoji} <b>ФИНАЛЬНЫЙ СИГНАЛ</b>

💰 <b>Пара:</b> {symbol}
💵 <b>Цена закрытия:</b> ${price:,.8f}
📊 <b>Превышение объема:</b> {volume_ratio}x
🎯 <b>Результат:</b> {status}
🕐 <b>Предварительный:</b> {preliminary_time_str}
🕐 <b>Закрытие:</b> {time_str}

🔗 <a href="https://www.tradingview.com/chart/?symbol=BYBIT:{symbol.replace('USDT', '')}USDT.P&interval=1">Открыть в TradingView</a>

#FinalAlert #{symbol.replace('USDT', '')}
            """.strip()
            
            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Ошибка отправки финального алерта в Telegram: {e}")
            return False

    async def send_consecutive_alert(self, alert_data: Dict) -> bool:
        """Отправка алерта по подряд идущим свечам в Telegram"""
        if not self.enabled:
            return False

        try:
            symbol = alert_data['symbol']
            price = alert_data['price']
            consecutive_count = alert_data.get('consecutive_count', 0)
            timestamp = alert_data.get('close_timestamp', alert_data['timestamp'])
            
            # Форматируем время
            time_str = self._format_timestamp(timestamp)
            
            # Определяем эмодзи в зависимости от количества
            if consecutive_count >= 10:
                emoji = "🚀"
            elif consecutive_count >= 7:
                emoji = "🔼"
            else:
                emoji = "📈"
            
            message = f"""
{emoji} <b>АЛЕРТ ПО ПОДРЯД ИДУЩИМ СВЕЧАМ</b>

💰 <b>Пара:</b> {symbol}
💵 <b>Цена:</b> ${price:,.8f}
🕯️ <b>Подряд LONG свечей:</b> {consecutive_count}
🕐 <b>Время закрытия:</b> {time_str}

🔗 <a href="https://www.tradingview.com/chart/?symbol=BYBIT:{symbol.replace('USDT', '')}USDT.P&interval=1">Открыть в TradingView</a>

#ConsecutiveAlert #{symbol.replace('USDT', '')}
            """.strip()
            
            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Ошибка отправки алерта подряд идущих свечей в Telegram: {e}")
            return False

    async def send_priority_alert(self, alert_data: Dict) -> bool:
        """Отправка приоритетного алерта в Telegram"""
        if not self.enabled:
            return False

        try:
            symbol = alert_data['symbol']
            price = alert_data['price']
            consecutive_count = alert_data.get('consecutive_count', 0)
            volume_ratio = alert_data.get('volume_ratio')
            current_volume = alert_data.get('current_volume_usdt')
            timestamp = alert_data.get('close_timestamp', alert_data['timestamp'])
            has_imbalance = alert_data.get('has_imbalance', False)
            
            # Форматируем время
            time_str = self._format_timestamp(timestamp)
            
            message = f"""
⭐ <b>ПРИОРИТЕТНЫЙ СИГНАЛ</b>

💰 <b>Пара:</b> {symbol}
💵 <b>Цена:</b> ${price:,.8f}
🕯️ <b>LONG свечей подряд:</b> {consecutive_count}
            """.strip()
            
            # Добавляем информацию об объеме, если есть
            if volume_ratio and current_volume:
                message += f"""
📊 <b>Превышение объема:</b> {volume_ratio}x
📈 <b>Объем:</b> ${current_volume:,.0f}
                """.strip()
            
            # Добавляем информацию об имбалансе
            imbalance_text = " + имбаланс" if has_imbalance else ""
            
            message += f"""

🎯 <b>Комбинированный сигнал:</b> Подряд идущие LONG свечи + всплеск объема{imbalance_text}
🕐 <b>Время:</b> {time_str}

🔗 <a href="https://www.tradingview.com/chart/?symbol=BYBIT:{symbol.replace('USDT', '')}USDT.P&interval=1">Открыть в TradingView</a>

#PriorityAlert #{symbol.replace('USDT', '')}
            """.strip()
            
            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Ошибка отправки приоритетного алерта в Telegram: {e}")
            return False

    async def send_system_message(self, message: str) -> bool:
        """Отправка системного сообщения"""
        if not self.enabled:
            return False

        try:
            formatted_message = f"🤖 <b>Система:</b> {message}"
            return await self._send_message(formatted_message)

        except Exception as e:
            logger.error(f"Ошибка отправки системного сообщения: {e}")
            return False

    async def send_chart_screenshot(self, symbol: str, chart_data: bytes) -> bool:
        """Отправка скриншота графика в Telegram"""
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            
            data = aiohttp.FormData()
            data.add_field('chat_id', self.chat_id)
            data.add_field('caption', f"📊 График {symbol}")
            data.add_field('photo', chart_data, filename=f'{symbol}_chart.png', content_type='image/png')

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        logger.info(f"Скриншот графика отправлен в Telegram для {symbol}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"Ошибка отправки скриншота в Telegram: {response.status} - {response_text}")
                        return False

        except Exception as e:
            logger.error(f"Ошибка отправки скриншота графика в Telegram: {e}")
            return False

    async def _send_message(self, message: str) -> bool:
        """Внутренний метод для отправки сообщения"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        logger.info(f"Сообщение отправлено в Telegram")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"Ошибка отправки в Telegram: {response.status} - {response_text}")
                        return False

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
            return False

    def update_settings(self, bot_token: str = None, chat_id: str = None):
        """Обновление настроек бота"""
        if bot_token:
            self.bot_token = bot_token
        if chat_id:
            self.chat_id = chat_id
        
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if self.enabled:
            logger.info("✅ Настройки Telegram бота обновлены")
        else:
            logger.warning("⚠️ Telegram бот отключен - не все настройки заданы")

    def get_status(self) -> Dict:
        """Получение статуса бота"""
        return {
            'enabled': self.enabled,
            'has_token': bool(self.bot_token),
            'has_chat_id': bool(self.chat_id)
        }