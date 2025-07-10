import json
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
            # Безопасное преобразование параметров в числа с обработкой дробных значений
            try:
                hours_int = max(1, int(round(float(hours)))) if hours is not None else 1
            except (ValueError, TypeError):
                hours_int = 1
                logger.warning(f"Некорректное значение hours: {hours}, используется значение по умолчанию: 1")
            
            try:
                offset_minutes_int = max(0, int(round(float(offset_minutes)))) if offset_minutes is not None else 0
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
            expected_count = max(1, hours * 60)  # Минимум 1 свеча

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
            expected_count = max(1, (end_time_ms - start_time_ms) // 60000)  # Минимум 1 свеча

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

    async def get_latest_closed_candle_time(self, symbol: str) -> Optional[int]:
        """Получение времени последней закрытой свечи для символа"""
        try:
            query = """
            SELECT MAX(start_time) as latest_time
            FROM kline_data 
            WHERE symbol = %s AND is_closed = true
            """
            result = await self.db_connection.execute_query(query, (symbol,))
            
            if result and result[0]['latest_time']:
                return result[0]['latest_time']
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения времени последней свечи для {symbol}: {e}")
            return None

    async def calculate_required_data_range(self, analysis_hours: int, offset_minutes: int) -> Dict:
        """Расчет требуемого диапазона данных от последней закрытой свечи"""
        try:
            # Текущее время
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Время последней закрытой минутной свечи (округляем вниз до минуты)
            last_closed_minute = (current_time_ms // 60000) * 60000
            
            # Применяем смещение
            offset_ms = offset_minutes * 60 * 1000
            end_time_ms = last_closed_minute - offset_ms
            
            # Рассчитываем начало периода
            analysis_duration_ms = analysis_hours * 60 * 60 * 1000
            start_time_ms = end_time_ms - analysis_duration_ms
            
            # Ожидаемое количество свечей (минутные интервалы)
            expected_candles = analysis_hours * 60
            
            return {
                'start_time_ms': start_time_ms,
                'end_time_ms': end_time_ms,
                'last_closed_minute': last_closed_minute,
                'expected_candles': expected_candles,
                'analysis_hours': analysis_hours,
                'offset_minutes': offset_minutes
            }
            
        except Exception as e:
            logger.error(f"Ошибка расчета требуемого диапазона данных: {e}")
            return {}

    async def check_startup_data_integrity(self, symbol: str, analysis_hours: int, offset_minutes: int) -> Dict:
        """Проверка целостности данных при запуске для символа"""
        try:
            # Рассчитываем требуемый диапазон
            required_range = await self.calculate_required_data_range(analysis_hours, offset_minutes)
            if not required_range:
                return {'symbol': symbol, 'status': 'error', 'error': 'Failed to calculate range'}
            
            start_time_ms = required_range['start_time_ms']
            end_time_ms = required_range['end_time_ms']
            expected_candles = required_range['expected_candles']
            
            # Получаем текущее состояние данных
            current_range = await self.get_data_time_range(symbol)
            
            # Проверяем целостность в требуемом диапазоне
            integrity = await self.check_data_integrity_range(symbol, start_time_ms, end_time_ms)
            
            result = {
                'symbol': symbol,
                'required_start': start_time_ms,
                'required_end': end_time_ms,
                'expected_candles': expected_candles,
                'current_candles': integrity['total_existing'],
                'missing_candles': integrity['missing_count'],
                'integrity_percentage': integrity['integrity_percentage'],
                'current_earliest': current_range['earliest_time'],
                'current_latest': current_range['latest_time'],
                'current_total': current_range['total_count'],
                'actions_needed': []
            }
            
            # Определяем необходимые действия
            
            # 1. Удаление старых данных (раньше требуемого начала)
            if current_range['earliest_time'] and current_range['earliest_time'] < start_time_ms:
                old_data_count = await self.db_connection.execute_query(
                    "SELECT COUNT(*) as count FROM kline_data WHERE symbol = %s AND start_time < %s AND is_closed = true",
                    (symbol, start_time_ms)
                )
                if old_data_count and old_data_count[0]['count'] > 0:
                    result['actions_needed'].append({
                        'action': 'delete_old_data',
                        'count': old_data_count[0]['count'],
                        'before_time': start_time_ms
                    })
            
            # 2. Удаление будущих данных (позже требуемого конца)
            if current_range['latest_time'] and current_range['latest_time'] > end_time_ms:
                future_data_count = await self.db_connection.execute_query(
                    "SELECT COUNT(*) as count FROM kline_data WHERE symbol = %s AND start_time > %s AND is_closed = true",
                    (symbol, end_time_ms)
                )
                if future_data_count and future_data_count[0]['count'] > 0:
                    result['actions_needed'].append({
                        'action': 'delete_future_data',
                        'count': future_data_count[0]['count'],
                        'after_time': end_time_ms
                    })
            
            # 3. Загрузка недостающих данных
            if integrity['missing_count'] > 0:
                result['actions_needed'].append({
                    'action': 'load_missing_data',
                    'count': integrity['missing_count'],
                    'start_time': start_time_ms,
                    'end_time': end_time_ms
                })
            
            # Определяем статус
            if not result['actions_needed']:
                result['status'] = 'ok'
            elif integrity['integrity_percentage'] >= 95:
                result['status'] = 'minor_issues'
            else:
                result['status'] = 'needs_correction'
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка проверки целостности данных при запуске для {symbol}: {e}")
            return {
                'symbol': symbol,
                'status': 'error',
                'error': str(e),
                'actions_needed': []
            }

    async def execute_startup_data_corrections(self, symbol: str, actions: List[Dict]) -> Dict:
        """Выполнение корректировок данных при запуске"""
        try:
            result = {
                'symbol': symbol,
                'actions_executed': [],
                'total_deleted': 0,
                'total_loaded': 0
            }
            
            for action in actions:
                action_type = action['action']
                
                if action_type == 'delete_old_data':
                    deleted = await self.cleanup_old_candles_before_time(symbol, action['before_time'])
                    result['actions_executed'].append(f"deleted_old: {deleted}")
                    result['total_deleted'] += deleted
                    logger.info(f"🧹 Удалено {deleted} старых свечей для {symbol}")
                
                elif action_type == 'delete_future_data':
                    deleted = await self.cleanup_future_candles_after_time(symbol, action['after_time'])
                    result['actions_executed'].append(f"deleted_future: {deleted}")
                    result['total_deleted'] += deleted
                    logger.info(f"🧹 Удалено {deleted} будущих свечей для {symbol}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка выполнения корректировок для {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'actions_executed': []
            }

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
            # Безопасное преобразование параметров с обработкой дробных значений
            try:
                analysis_hours = max(1, int(round(float(analysis_hours)))) if analysis_hours is not None else 1
            except (ValueError, TypeError):
                logger.warning(f"Некорректное значение analysis_hours: {analysis_hours}, используется 1")
                analysis_hours = 1
            
            try:
                offset_minutes = max(0, int(round(float(offset_minutes)))) if offset_minutes is not None else 0
            except (ValueError, TypeError):
                logger.warning(f"Некорректное значение offset_minutes: {offset_minutes}, используется 0")
                offset_minutes = 0
            
            # Рассчитываем требуемый диапазон времени
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            offset_ms = offset_minutes * 60 * 1000
            end_time_ms = current_time_ms - offset_ms
            start_time_ms = end_time_ms - (analysis_hours * 60 * 60 * 1000)
            
            # Получаем текущий диапазон данных
            current_range = await self.get_data_time_range(symbol)
            
            result = {
                'symbol': symbol,
                'analysis_hours': analysis_hours,
                'offset_minutes': offset_minutes,
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
    # Методы для работы с алертами
    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных"""
        try:
            logger.info(f"💾 Попытка сохранения алерта: {alert_data['symbol']} - {alert_data['alert_type']}")
            
            query = """
            INSERT INTO alerts (
                symbol, alert_type, price, volume_ratio, current_volume_usdt, 
                average_volume_usdt, consecutive_count, alert_timestamp_ms, 
                close_timestamp_ms, is_closed, is_true_signal, has_imbalance,
                imbalance_data, candle_data, order_book_snapshot, message, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            result = await self.db_connection.execute_command_with_return(query, (
                alert_data['symbol'],
                alert_data['alert_type'],
                alert_data['price'],
                alert_data.get('volume_ratio'),
                alert_data.get('current_volume_usdt'),
                alert_data.get('average_volume_usdt'),
                alert_data.get('consecutive_count'),
                alert_data['timestamp'],
                alert_data.get('close_timestamp'),
                alert_data.get('is_closed', False),
                alert_data.get('is_true_signal'),
                alert_data.get('has_imbalance', False),
                json.dumps(alert_data.get('imbalance_data')) if alert_data.get('imbalance_data') else None,
                json.dumps(alert_data.get('candle_data')) if alert_data.get('candle_data') else None,
                json.dumps(alert_data.get('order_book_snapshot')) if alert_data.get('order_book_snapshot') else None,
                alert_data.get('message', ''),
                alert_data.get('status', 'active')
            ))
            
            if result and 'id' in result:
                logger.info(f"✅ Алерт успешно сохранен в БД с ID: {result['id']}")
                return result['id']
            else:
                logger.error(f"❌ Не удалось получить ID сохраненного алерта")
                return None
            
        except Exception as e:
            logger.error(f"Ошибка сохранения алерта: {e}")
            logger.error(f"Данные алерта: {alert_data}")
            raise DatabaseException(f"Ошибка сохранения алерта: {e}")

    async def get_alerts(self, limit: int = 100, offset: int = 0, symbol: str = None, 
                        alert_type: str = None, status: str = None) -> List[Dict]:
        """Получение алертов с фильтрацией"""
        try:
            conditions = []
            params = []
            
            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)
            
            if alert_type:
                conditions.append("alert_type = %s")
                params.append(alert_type)
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
            SELECT * FROM alerts
            {where_clause}
            ORDER BY alert_timestamp_ms DESC
            LIMIT %s OFFSET %s
            """
            
            params.extend([limit, offset])
            result = await self.db_connection.execute_query(query, tuple(params))
            
            alerts = []
            for row in result:
                alert = dict(row)
                # Парсим JSON поля
                if alert.get('imbalance_data'):
                    alert['imbalance_data'] = json.loads(alert['imbalance_data'])
                if alert.get('candle_data'):
                    alert['candle_data'] = json.loads(alert['candle_data'])
                if alert.get('order_book_snapshot'):
                    alert['order_book_snapshot'] = json.loads(alert['order_book_snapshot'])
                
                # Добавляем поле timestamp для совместимости с фронтендом
                if alert.get('alert_timestamp_ms'):
                    alert['timestamp'] = datetime.fromtimestamp(
                        alert['alert_timestamp_ms'] / 1000, tz=timezone.utc
                    ).isoformat()
                
                if alert.get('close_timestamp_ms'):
                    alert['close_timestamp'] = datetime.fromtimestamp(
                        alert['close_timestamp_ms'] / 1000, tz=timezone.utc
                    ).isoformat()
                
                alerts.append(alert)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Ошибка получения алертов: {e}")
            return []

    async def get_alert_by_id(self, alert_id: int) -> Optional[Dict]:
        """Получение алерта по ID"""
        try:
            query = "SELECT * FROM alerts WHERE id = %s"
            result = await self.db_connection.execute_query(query, (alert_id,))
            
            if result:
                alert = dict(result[0])
                # Парсим JSON поля
                if alert['imbalance_data']:
                    alert['imbalance_data'] = json.loads(alert['imbalance_data'])
                if alert['candle_data']:
                    alert['candle_data'] = json.loads(alert['candle_data'])
                if alert['order_book_snapshot']:
                    alert['order_book_snapshot'] = json.loads(alert['order_book_snapshot'])
                return alert
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения алерта {alert_id}: {e}")
            return None

    async def update_alert_status(self, alert_id: int, status: str, is_true_signal: bool = None) -> bool:
        """Обновление статуса алерта"""
        try:
            if is_true_signal is not None:
                query = "UPDATE alerts SET status = %s, is_true_signal = %s WHERE id = %s"
                params = (status, is_true_signal, alert_id)
            else:
                query = "UPDATE alerts SET status = %s WHERE id = %s"
                params = (status, alert_id)
            
            rows_affected = await self.db_connection.execute_command(query, params)
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса алерта {alert_id}: {e}")
            return False

    async def delete_alert(self, alert_id: int) -> bool:
        """Удаление алерта"""
        try:
            query = "DELETE FROM alerts WHERE id = %s"
            rows_affected = await self.db_connection.execute_command(query, (alert_id,))
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Ошибка удаления алерта {alert_id}: {e}")
            return False

    async def get_alerts_statistics(self, days: int = 7) -> Dict:
        """Получение статистики алертов"""
        try:
            cutoff_time = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
            
            query = """
            SELECT 
                COUNT(*) as total_alerts,
                COUNT(CASE WHEN alert_type = 'volume_spike' THEN 1 END) as volume_alerts,
                COUNT(CASE WHEN alert_type = 'consecutive_long' THEN 1 END) as consecutive_alerts,
                COUNT(CASE WHEN alert_type = 'priority' THEN 1 END) as priority_alerts,
                COUNT(CASE WHEN is_true_signal = true THEN 1 END) as true_signals,
                COUNT(CASE WHEN is_true_signal = false THEN 1 END) as false_signals,
                COUNT(CASE WHEN has_imbalance = true THEN 1 END) as alerts_with_imbalance,
                AVG(volume_ratio) as avg_volume_ratio
            FROM alerts 
            WHERE alert_timestamp_ms >= %s
            """
            
            result = await self.db_connection.execute_query(query, (cutoff_time,))
            
            if result:
                stats = dict(result[0])
                # Рассчитываем процент точности
                total_closed = (stats['true_signals'] or 0) + (stats['false_signals'] or 0)
                if total_closed > 0:
                    stats['accuracy_percentage'] = round((stats['true_signals'] or 0) / total_closed * 100, 2)
                else:
                    stats['accuracy_percentage'] = 0
                
                return stats
            
            return {}
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики алертов: {e}")
            return {}

    # Методы для работы с избранными парами
    async def get_favorites(self) -> List[Dict]:
        """Получение избранных пар"""
        try:
            query = "SELECT * FROM favorites ORDER BY sort_order, symbol"
            result = await self.db_connection.execute_query(query)
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Ошибка получения избранных: {e}")
            return []

    async def add_to_favorites(self, symbol: str, notes: str = '', color: str = '#FFD700', sort_order: int = 0) -> int:
        """Добавление в избранное"""
        try:
            query = """
            INSERT INTO favorites (symbol, notes, color, sort_order)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                notes = EXCLUDED.notes,
                color = EXCLUDED.color,
                sort_order = EXCLUDED.sort_order,
                updated_at = NOW()
            RETURNING id
            """
            
            result = await self.db_connection.execute_command_with_return(
                query, (symbol, notes, color, sort_order)
            )
            return result['id'] if result else None
            
        except Exception as e:
            logger.error(f"Ошибка добавления в избранное {symbol}: {e}")
            raise DatabaseException(f"Ошибка добавления в избранное: {e}")

    async def remove_from_favorites(self, favorite_id: int = None, symbol: str = None) -> bool:
        """Удаление из избранного"""
        try:
            if favorite_id:
                query = "DELETE FROM favorites WHERE id = %s"
                params = (favorite_id,)
            elif symbol:
                query = "DELETE FROM favorites WHERE symbol = %s"
                params = (symbol,)
            else:
                raise ValueError("Необходимо указать favorite_id или symbol")
            
            rows_affected = await self.db_connection.execute_command(query, params)
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Ошибка удаления из избранного: {e}")
            return False

    async def update_favorite(self, favorite_id: int, symbol: str = None, notes: str = None, 
                             color: str = None, sort_order: int = None) -> bool:
        """Обновление избранного"""
        try:
            updates = []
            params = []
            
            if symbol is not None:
                updates.append("symbol = %s")
                params.append(symbol)
            if notes is not None:
                updates.append("notes = %s")
                params.append(notes)
            if color is not None:
                updates.append("color = %s")
                params.append(color)
            if sort_order is not None:
                updates.append("sort_order = %s")
                params.append(sort_order)
            
            if not updates:
                return False
            
            updates.append("updated_at = NOW()")
            params.append(favorite_id)
            
            query = f"UPDATE favorites SET {', '.join(updates)} WHERE id = %s"
            rows_affected = await self.db_connection.execute_command(query, tuple(params))
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Ошибка обновления избранного {favorite_id}: {e}")
            return False

    # Методы для работы с торговыми настройками
    async def get_trading_settings(self) -> Dict:
        """Получение торговых настроек"""
        try:
            query = "SELECT * FROM trading_settings ORDER BY id DESC LIMIT 1"
            result = await self.db_connection.execute_query(query)
            
            if result:
                return dict(result[0])
            
            # Возвращаем настройки по умолчанию
            return {
                'account_balance': 10000.0,
                'max_risk_per_trade': 2.0,
                'max_open_trades': 5,
                'default_stop_loss_percentage': 2.0,
                'default_take_profit_percentage': 4.0,
                'auto_calculate_quantity': True
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения торговых настроек: {e}")
            return {}

    async def update_trading_settings(self, settings: Dict) -> bool:
        """Обновление торговых настроек"""
        try:
            # Проверяем, есть ли уже настройки
            existing = await self.get_trading_settings()
            
            if existing and 'id' in existing:
                # Обновляем существующие
                updates = []
                params = []
                
                for key, value in settings.items():
                    if key != 'id':
                        updates.append(f"{key} = %s")
                        params.append(value)
                
                if updates:
                    updates.append("updated_at = NOW()")
                    params.append(existing['id'])
                    
                    query = f"UPDATE trading_settings SET {', '.join(updates)} WHERE id = %s"
                    rows_affected = await self.db_connection.execute_command(query, tuple(params))
                    return rows_affected > 0
            else:
                # Создаем новые
                query = """
                INSERT INTO trading_settings (
                    account_balance, max_risk_per_trade, max_open_trades,
                    default_stop_loss_percentage, default_take_profit_percentage,
                    auto_calculate_quantity
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                await self.db_connection.execute_command(query, (
                    settings.get('account_balance', 10000.0),
                    settings.get('max_risk_per_trade', 2.0),
                    settings.get('max_open_trades', 5),
                    settings.get('default_stop_loss_percentage', 2.0),
                    settings.get('default_take_profit_percentage', 4.0),
                    settings.get('auto_calculate_quantity', True)
                ))
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка обновления торговых настроек: {e}")
            return False