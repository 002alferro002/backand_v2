from typing import List, Dict, Optional, Any
from datetime import datetime, timezone, timedelta
from cryptoscan.backand.core.core_logger import get_logger
from cryptoscan.backand.core.core_exceptions import DatabaseException

logger = get_logger(__name__)


class DatabaseQueries:
    """Класс для выполнения запросов к базе данных"""

    def __init__(self, db_connection):
        self.db_connection = db_connection

    # Методы для работы с watchlist
    async def get_watchlist(self) -> List[str]:
        """Получение списка символов из watchlist"""
        try:
            query = "SELECT symbol FROM watchlist WHERE is_active = true ORDER BY symbol"
            result = await self.db_connection.execute_query(query)
            return [row['symbol'] for row in result]
        except Exception as e:
            logger.error(f"Ошибка получения watchlist: {e}")
            return []

    async def save_paper_trade(self, trade_data: Dict) -> int:
        """Сохранение бумажной сделки"""
        try:
            query = """
            INSERT INTO paper_trades (
                symbol, alert_id, direction, entry_price, stop_loss, take_profit,
                quantity, risk_amount, risk_percentage, position_value,
                potential_loss, potential_profit, risk_reward_ratio, status, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """

            result = await self.db_connection.execute_command_with_return(query, (
                trade_data['symbol'],
                trade_data.get('alert_id'),
                trade_data['direction'],
                trade_data['entry_price'],
                trade_data.get('stop_loss'),
                trade_data.get('take_profit'),
                trade_data.get('quantity'),
                trade_data.get('risk_amount'),
                trade_data.get('risk_percentage'),
                trade_data.get('position_value'),
                trade_data.get('potential_loss'),
                trade_data.get('potential_profit'),
                trade_data.get('risk_reward_ratio'),
                trade_data.get('status', 'planned'),
                trade_data.get('notes')
            ))

            return result['id'] if result else None

        except Exception as e:
            logger.error(f"Ошибка сохранения бумажной сделки: {e}")
            raise DatabaseException(f"Ошибка сохранения бумажной сделки: {e}")

    async def get_paper_trades(self, limit: int = 100) -> List[Dict]:
        """Получение бумажных сделок"""
        try:
            query = """
            SELECT * FROM paper_trades
            ORDER BY entry_time DESC
            LIMIT %s
            """
            result = await self.db_connection.execute_query(query, (limit,))
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Ошибка получения бумажных сделок: {e}")
            return []

    async def get_watchlist_details(self) -> List[Dict]:
        """Получение детальной информации о watchlist"""
        try:
            query = """
            SELECT id, symbol, price_drop, current_price, historical_price, 
                   is_active, added_at, updated_at
            FROM watchlist 
            ORDER BY symbol
            """
            result = await self.db_connection.execute_query(query)
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Ошибка получения деталей watchlist: {e}")
            return []

    async def add_to_watchlist(self, symbol: str, price_drop: float = 0,
                               current_price: float = 0, historical_price: float = 0):
        """Добавление символа в watchlist"""
        try:
            query = """
            INSERT INTO watchlist (symbol, price_drop, current_price, historical_price)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                price_drop = EXCLUDED.price_drop,
                current_price = EXCLUDED.current_price,
                historical_price = EXCLUDED.historical_price,
                is_active = true,
                updated_at = NOW()
            """
            await self.db_connection.execute_command(
                query, (symbol, price_drop, current_price, historical_price)
            )
            logger.info(f"✅ Символ {symbol} добавлен в watchlist")
        except Exception as e:
            logger.error(f"Ошибка добавления {symbol} в watchlist: {e}")
            raise DatabaseException(f"Ошибка добавления в watchlist: {e}")

    async def remove_from_watchlist(self, symbol: str = None, item_id: int = None):
        """Удаление символа из watchlist"""
        try:
            if item_id:
                query = "DELETE FROM watchlist WHERE id = %s"
                params = (item_id,)
            elif symbol:
                query = "DELETE FROM watchlist WHERE symbol = %s"
                params = (symbol,)
            else:
                raise ValueError("Необходимо указать symbol или item_id")

            await self.db_connection.execute_command(query, params)
            logger.info(f"✅ Элемент удален из watchlist")
        except Exception as e:
            logger.error(f"Ошибка удаления из watchlist: {e}")
            raise DatabaseException(f"Ошибка удаления из watchlist: {e}")

    async def update_watchlist_item(self, item_id: int, symbol: str, is_active: bool):
        """Обновление элемента watchlist"""
        try:
            query = """
            UPDATE watchlist 
            SET symbol = %s, is_active = %s, updated_at = NOW()
            WHERE id = %s
            """
            await self.db_connection.execute_command(query, (symbol, is_active, item_id))
            logger.info(f"✅ Элемент watchlist обновлен")
        except Exception as e:
            logger.error(f"Ошибка обновления watchlist: {e}")
            raise DatabaseException(f"Ошибка обновления watchlist: {e}")

    # Методы для работы с kline данными
    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение kline данных"""
        try:
            is_long = float(kline_data['close']) > float(kline_data['open'])

            query = """
            INSERT INTO kline_data (
                symbol, start_time, end_time, open_price, high_price, 
                low_price, close_price, volume, is_closed, is_long
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, start_time) DO UPDATE SET
                end_time = EXCLUDED.end_time,
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume,
                is_closed = EXCLUDED.is_closed,
                is_long = EXCLUDED.is_long
            """

            await self.db_connection.execute_command(query, (
                symbol, kline_data['start'], kline_data['end'],
                kline_data['open'], kline_data['high'], kline_data['low'],
                kline_data['close'], kline_data['volume'], is_closed, is_long
            ))

        except Exception as e:
            logger.error(f"Ошибка сохранения kline данных для {symbol}: {e}")
            raise DatabaseException(f"Ошибка сохранения kline данных: {e}")

    async def save_historical_kline_data(self, symbol: str, kline_data: Dict):
        """Сохранение исторических kline данных"""
        await self.save_kline_data(symbol, kline_data, is_closed=True)

    async def get_recent_candles(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Получение последних свечей"""
        try:
            query = """
            SELECT start_time as timestamp, open_price as open, high_price as high,
                   low_price as low, close_price as close, volume, is_closed, is_long
            FROM kline_data
            WHERE symbol = %s AND is_closed = true
            ORDER BY start_time DESC
            LIMIT %s
            """
            result = await self.db_connection.execute_query(query, (symbol, limit))

            # Преобразуем в нужный формат
            candles = []
            for row in reversed(result):  # Возвращаем в хронологическом порядке
                candles.append({
                    'timestamp': row['timestamp'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'is_long': row['is_long'],
                    'is_closed': row['is_closed']
                })

            return candles

        except Exception as e:
            logger.error(f"Ошибка получения свечей для {symbol}: {e}")
            return []

    async def get_historical_long_volumes(self, symbol: str, hours: int,
                                          offset_minutes: int = 0, volume_type: str = 'long') -> List[float]:
        """Получение исторических объемов LONG свечей"""
        try:
            # Безопасное преобразование параметров в числа
            try:
                hours_int = int(float(hours)) if hours is not None else 1
            except (ValueError, TypeError):
                hours_int = 1
                logger.warning(f"Некорректное значение hours: {hours}, используется значение по умолчанию: 1")
            
            try:
                offset_minutes_int = int(float(offset_minutes)) if offset_minutes is not None else 0
            except (ValueError, TypeError):
                offset_minutes_int = 0
                logger.warning(f"Некорректное значение offset_minutes: {offset_minutes}, используется значение по умолчанию: 0")

            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            offset_ms = offset_minutes_int * 60 * 1000
            start_time_ms = current_time_ms - (hours_int * 60 * 60 * 1000) - offset_ms
            end_time_ms = current_time_ms - offset_ms

            if volume_type.lower() == 'long':
                condition = "AND is_long = true"
            elif volume_type.lower() == 'short':
                condition = "AND is_long = false"
            else:
                condition = ""  # ALL - все свечи

            query = f"""
            SELECT volume, close_price
            FROM kline_data
            WHERE symbol = %s 
            AND start_time >= %s 
            AND start_time < %s 
            AND is_closed = true
            {condition}
            ORDER BY start_time
            """

            result = await self.db_connection.execute_query(query, (symbol, start_time_ms, end_time_ms))

            # Рассчитываем объем в USDT
            volumes = []
            for row in result:
                # Безопасное преобразование в float
                volume = float(row['volume']) if row['volume'] is not None else 0.0
                close_price = float(row['close_price']) if row['close_price'] is not None else 0.0
                volume_usdt = volume * close_price
                volumes.append(volume_usdt)

            return volumes

        except Exception as e:
            logger.error(f"Ошибка получения исторических объемов для {symbol}: {e}")
            logger.error(f"Параметры: hours={hours} (type: {type(hours)}), offset_minutes={offset_minutes} (type: {type(offset_minutes)})")
            return []

    async def check_candle_exists(self, symbol: str, timestamp: int) -> bool:
        """Проверка существования свечи"""
        try:
            query = "SELECT 1 FROM kline_data WHERE symbol = %s AND start_time = %s"
            result = await self.db_connection.execute_query(query, (symbol, timestamp))
            return len(result) > 0
        except Exception as e:
            logger.error(f"Ошибка проверки существования свечи: {e}")
            return False

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Проверка целостности данных"""
        try:
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            start_time_ms = current_time_ms - (hours * 60 * 60 * 1000)

            # Подсчитываем существующие свечи
            query = """
            SELECT COUNT(*) as existing_count
            FROM kline_data
            WHERE symbol = %s 
            AND start_time >= %s 
            AND start_time < %s
            AND is_closed = true
            """

            result = await self.db_connection.execute_query(query, (symbol, start_time_ms, current_time_ms))
            existing_count = result[0]['existing_count']

            # Ожидаемое количество свечей (минутные интервалы)
            expected_count = hours * 60

            integrity_percentage = (existing_count / expected_count * 100) if expected_count > 0 else 0

            return {
                'total_existing': existing_count,
                'total_expected': expected_count,
                'integrity_percentage': integrity_percentage,
                'missing_count': max(0, expected_count - existing_count)
            }

        except Exception as e:
            logger.error(f"Ошибка проверки целостности данных для {symbol}: {e}")
            return {
                'total_existing': 0,
                'total_expected': hours * 60,
                'integrity_percentage': 0,
                'missing_count': hours * 60
            }

    async def check_data_integrity_range(self, symbol: str, start_time_ms: int, end_time_ms: int) -> Dict:
        """Проверка целостности данных в диапазоне"""
        try:
            query = """
            SELECT COUNT(*) as existing_count
            FROM kline_data
            WHERE symbol = %s 
            AND start_time >= %s 
            AND start_time < %s
            AND is_closed = true
            """

            result = await self.db_connection.execute_query(query, (symbol, start_time_ms, end_time_ms))
            existing_count = result[0]['existing_count']

            # Ожидаемое количество свечей в диапазоне
            expected_count = (end_time_ms - start_time_ms) // 60000

            integrity_percentage = (existing_count / expected_count * 100) if expected_count > 0 else 0

            return {
                'total_existing': existing_count,
                'total_expected': expected_count,
                'integrity_percentage': integrity_percentage,
                'missing_count': max(0, expected_count - existing_count)
            }

        except Exception as e:
            logger.error(f"Ошибка проверки целостности данных в диапазоне для {symbol}: {e}")
            return {
                'total_existing': 0,
                'total_expected': 0,
                'integrity_percentage': 0,
                'missing_count': 0
            }

    async def cleanup_old_candles(self, symbol: str, retention_hours: int):
        """Очистка старых свечей"""
        try:
            cutoff_time = int(datetime.now(timezone.utc).timestamp() * 1000) - (retention_hours * 60 * 60 * 1000)

            query = "DELETE FROM kline_data WHERE symbol = %s AND start_time < %s"
            deleted_count = await self.db_connection.execute_command(query, (symbol, cutoff_time))

            if deleted_count > 0:
                logger.debug(f"🧹 Удалено {deleted_count} старых свечей для {symbol}")

            return deleted_count

        except Exception as e:
            logger.error(f"Ошибка очистки старых свечей для {symbol}: {e}")
            return 0

    async def cleanup_old_candles_before_time(self, symbol: str, cutoff_time_ms: int) -> int:
        """Очистка свечей до указанного времени"""
        try:
            query = "DELETE FROM kline_data WHERE symbol = %s AND start_time < %s"
            deleted_count = await self.db_connection.execute_command(query, (symbol, cutoff_time_ms))
            return deleted_count
        except Exception as e:
            logger.error(f"Ошибка очистки свечей до времени для {symbol}: {e}")
            return 0

    async def cleanup_future_candles_after_time(self, symbol: str, cutoff_time_ms: int) -> int:
        """Очистка будущих свечей после указанного времени"""
        try:
            query = "DELETE FROM kline_data WHERE symbol = %s AND start_time >= %s"
            deleted_count = await self.db_connection.execute_command(query, (symbol, cutoff_time_ms))
            return deleted_count
        except Exception as e:
            logger.error(f"Ошибка очистки будущих свечей для {symbol}: {e}")
            return 0

    async def get_data_time_range(self, symbol: str) -> Dict:
        """Получение временного диапазона данных для символа"""
        try:
            query = """
            SELECT 
                MIN(start_time) as earliest_time,
                MAX(start_time) as latest_time,
                COUNT(*) as total_count
            FROM kline_data 
            WHERE symbol = %s AND is_closed = true
            """
            result = await self.db_connection.execute_query(query, (symbol,))
            
            if result and result[0]['total_count'] > 0:
                return {
                    'earliest_time': result[0]['earliest_time'],
                    'latest_time': result[0]['latest_time'],
                    'total_count': result[0]['total_count']
                }
            else:
                return {
                    'earliest_time': None,
                    'latest_time': None,
                    'total_count': 0
                }
        except Exception as e:
            logger.error(f"Ошибка получения временного диапазона для {symbol}: {e}")
            return {'earliest_time': None, 'latest_time': None, 'total_count': 0}

    async def adjust_data_for_new_settings(self, symbol: str, analysis_hours: int, offset_minutes: int) -> Dict:
        """Корректировка данных под новые настройки анализа"""
        try:
            # Рассчитываем требуемый диапазон времени
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            offset_ms = offset_minutes * 60 * 1000
            end_time_ms = current_time_ms - offset_ms
            start_time_ms = end_time_ms - (analysis_hours * 60 * 60 * 1000)
            
            # Получаем текущий диапазон данных
            current_range = await self.get_data_time_range(symbol)
            
            result = {
                'symbol': symbol,
                'required_start': start_time_ms,
                'required_end': end_time_ms,
                'current_earliest': current_range['earliest_time'],
                'current_latest': current_range['latest_time'],
                'current_count': current_range['total_count'],
                'actions_taken': []
            }
            
            # Если нет данных, возвращаем информацию для загрузки
            if current_range['total_count'] == 0:
                result['actions_taken'].append('no_data_found')
                return result
            
            # Удаляем данные старше требуемого начала
            if current_range['earliest_time'] and current_range['earliest_time'] < start_time_ms:
                deleted_old = await self.cleanup_old_candles_before_time(symbol, start_time_ms)
                if deleted_old > 0:
                    result['actions_taken'].append(f'deleted_old_data: {deleted_old} candles')
                    logger.info(f"🧹 Удалено {deleted_old} старых свечей для {symbol}")
            
            # Удаляем данные новее требуемого конца
            if current_range['latest_time'] and current_range['latest_time'] > end_time_ms:
                deleted_future = await self.cleanup_future_candles_after_time(symbol, end_time_ms)
                if deleted_future > 0:
                    result['actions_taken'].append(f'deleted_future_data: {deleted_future} candles')
                    logger.info(f"🧹 Удалено {deleted_future} будущих свечей для {symbol}")
            
            # Проверяем целостность данных после очистки
            integrity = await self.check_data_integrity_range(symbol, start_time_ms, end_time_ms)
            result['final_integrity'] = integrity
            
            if integrity['integrity_percentage'] < 95:
                result['actions_taken'].append(f'needs_loading: {integrity["missing_count"]} candles')
                logger.info(f"📊 Требуется загрузка {integrity['missing_count']} свечей для {symbol}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка корректировки данных для {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'actions_taken': ['error']
            }