import asyncio
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any, Set, Union

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

# Импорты наших модулей
from settings import get_setting, register_settings_callback, start_settings_monitor, stop_settings_monitor
from settings import (
    get_setting, register_settings_callback, start_settings_monitor, stop_settings_monitor,
    get_settings_schema, get_settings_by_category, reset_settings_to_default,
    export_settings, import_settings, update_multiple_settings, ENV_FILE_PATH
)
from core.core_logger import get_logger
from database.database_connection import DatabaseConnection
from database.database_tables import DatabaseTables
from database.database_queries import DatabaseQueries
from alert.alert_manager import AlertManager
from bybit.bybit_websocket import BybitWebSocketManager
from bybit.bybit_rest_api import BybitRestAPI
from filter.filter_price import PriceFilter
from telegram.telegram_bot import TelegramBot
from times.times_manager import TimeManager
from cryptoscan.backand.websocket.websocket_manager import ConnectionManager

logger = get_logger(__name__)

# Глобальные переменные
db_connection = None
db_queries = None
alert_manager = None
bybit_websocket = None
bybit_api = None
price_filter = None
telegram_bot = None
time_manager = None
connection_manager = None


# Модели данных для API
class SettingsUpdate(BaseModel):
    settings: Dict[str, Any]


class PaperTradeCreate(BaseModel):
    symbol: str
    alert_id: Optional[int] = None
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    quantity: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None
    position_value: Optional[float] = None
    potential_loss: Optional[float] = None
    potential_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    status: str = 'planned'
    notes: Optional[str] = None


class RealTradeCreate(BaseModel):
    symbol: str
    alert_id: Optional[int] = None
    side: str  # 'BUY' or 'SELL'
    direction: str  # 'LONG' or 'SHORT'
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: int = 1
    margin_type: str = 'isolated'
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None


# Функция для обновления настроек во всех компонентах
async def update_all_components_settings(new_settings: Dict):
    """Обновление настроек во всех компонентах системы"""
    try:
        logger.info("🔄 Обновление настроек во всех компонентах...")

        # Обновляем настройки в alert_manager
        if alert_manager:
            alert_manager.update_settings(new_settings)

        # Обновляем настройки в price_filter
        if price_filter:
            price_filter.update_settings(new_settings)

        # Обновляем настройки в telegram_bot
        if telegram_bot:
            telegram_token = new_settings.get('TELEGRAM_BOT_TOKEN')
            telegram_chat = new_settings.get('TELEGRAM_CHAT_ID')
            if telegram_token or telegram_chat:
                telegram_bot.update_settings(telegram_token, telegram_chat)

        # Уведомляем клиентов об обновлении настроек
        if connection_manager:
            await connection_manager.broadcast_json({
                "type": "settings_updated",
                "message": "Настройки обновлены из .env файла",
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
            })

        logger.info("✅ Настройки успешно обновлены во всех компонентах")

    except Exception as e:
        logger.error(f"❌ Ошибка обновления настроек в компонентах: {e}")


class WatchlistAdd(BaseModel):
    symbol: str


class WatchlistUpdate(BaseModel):
    id: int
    symbol: str
    is_active: bool


class FavoriteAdd(BaseModel):
    symbol: str
    notes: Optional[str] = None
    color: Optional[str] = '#FFD700'


class FavoriteUpdate(BaseModel):
    notes: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


class FavoriteReorder(BaseModel):
    symbol_order: List[str]


class PaperTradeCreate(BaseModel):
    symbol: str
    trade_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None
    notes: Optional[str] = None
    alert_id: Optional[int] = None


class PaperTradeClose(BaseModel):
    exit_price: float
    exit_reason: Optional[str] = 'MANUAL'


class TradingSettingsUpdate(BaseModel):
    account_balance: Optional[float] = None
    max_risk_per_trade: Optional[float] = None
    max_open_trades: Optional[int] = None
    default_stop_loss_percentage: Optional[float] = None
    default_take_profit_percentage: Optional[float] = None
    auto_calculate_quantity: Optional[bool] = None


class SettingsSchema(BaseModel):
    """Модель для получения схемы настроек"""
    pass


class SettingsImport(BaseModel):
    """Модель для импорта настроек"""
    settings: Dict[str, Any]


class SettingsReset(BaseModel):
    """Модель для сброса настроек"""
    confirm: bool = False


class SettingsUpdate(BaseModel):
    settings: Dict[str, Any]


class RiskCalculatorRequest(BaseModel):
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None
    account_balance: Optional[float] = None
    trade_type: str = 'LONG'


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_connection, db_queries, alert_manager, bybit_websocket, bybit_api
    global price_filter, telegram_bot, time_manager, connection_manager

    try:
        logger.info("🚀 Запуск системы анализа объемов...")

        # КРИТИЧЕСКИ ВАЖНО: Создаем .env файл в первую очередь
        from settings import create_env_file, load_settings
        create_env_file()  # Создаем файл настроек если его нет
        initial_settings = load_settings()  # Загружаем настройки
        logger.info("✅ Файл настроек создан/загружен")

        # Инициализация менеджера WebSocket соединений
        connection_manager = ConnectionManager()

        # Инициализация синхронизации времени
        time_manager = TimeManager()
        await time_manager.start()
        logger.info("⏰ Синхронизация времени запущена")

        # Инициализация базы данных с обработкой ошибок
        db_connection = None
        db_queries = None
        db_initialized = False
        
        try:
            db_connection = DatabaseConnection()
            await db_connection.initialize()

            # Создание таблиц
            db_tables = DatabaseTables(db_connection)
            await db_tables.create_all_tables()

            # Инициализация запросов к БД
            db_queries = DatabaseQueries(db_connection)
            db_initialized = True
            logger.info("✅ База данных инициализирована")
            
        except Exception as db_error:
            logger.error(f"❌ Ошибка инициализации базы данных: {db_error}")
            logger.warning("⚠️ Система продолжит работу без базы данных")
            logger.warning("⚠️ Некоторые функции будут недоступны")
            
            # Уведомляем через WebSocket о проблеме с БД
            if connection_manager:
                await connection_manager.send_system_notification(
                    "database_error",
                    {
                        "message": "Ошибка подключения к базе данных",
                        "error": str(db_error),
                        "impact": "Система работает в ограниченном режиме"
                    }
                )

        # Инициализация Telegram бота
        telegram_bot = TelegramBot()

        # Инициализация менеджера алертов (работает и без БД)
        alert_manager = AlertManager(db_queries, telegram_bot, connection_manager, time_manager)

        # Инициализация Bybit API
        bybit_api = BybitRestAPI()
        await bybit_api.start()

        # Инициализация фильтра цен (работает и без БД)
        price_filter = PriceFilter(db_queries)

        # Инициализация WebSocket менеджера Bybit
        bybit_websocket = BybitWebSocketManager(alert_manager, connection_manager)

        # Настраиваем callback для обновления пар
        async def on_pairs_updated(new_pairs, removed_pairs):
            """Callback для обновления пар в bybit_websocket"""
            if bybit_websocket:
                bybit_websocket.update_trading_pairs(new_pairs, removed_pairs)
                if new_pairs:
                    await bybit_websocket.subscribe_to_new_pairs(new_pairs)
                if removed_pairs:
                    await bybit_websocket.unsubscribe_from_pairs(removed_pairs)

        price_filter.set_pairs_updated_callback(on_pairs_updated)

        # Запуск всех сервисов
        logger.info("🔄 Запуск сервисов...")

        # Получаем начальный watchlist (только если БД доступна)
        if db_initialized and db_queries:
            try:
                initial_watchlist = await db_queries.get_watchlist()
                if initial_watchlist:
                    # Устанавливаем торговые пары в WebSocket менеджер
                    bybit_websocket.trading_pairs = set(initial_watchlist)
                    logger.info(f"📋 Установлен начальный watchlist: {len(initial_watchlist)} пар")
                else:
                    logger.info("📋 Watchlist пуст")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки watchlist: {e}")
        else:
            logger.warning("⚠️ Watchlist недоступен - база данных не инициализирована")

        # Запускаем фильтр цен
        if get_setting('WATCHLIST_AUTO_UPDATE', True):
            if db_initialized:
                asyncio.create_task(price_filter.start())
            else:
                logger.warning("⚠️ Автообновление watchlist отключено - база данных недоступна")
        else:
            logger.info("🔍 Автоматическое обновление watchlist отключено")

        # Запускаем WebSocket клиент
        bybit_websocket.is_running = True
        asyncio.create_task(bybit_websocket_loop())

        # Запускаем загрузчик исторических данных только если БД доступна
        if db_initialized:
            asyncio.create_task(historical_data_loader())
        else:
            logger.warning("⚠️ Загрузчик исторических данных отключен - база данных недоступна")

        # Запуск периодической очистки данных
        asyncio.create_task(periodic_cleanup())

        # Запуск периодической очистки WebSocket соединений
        asyncio.create_task(connection_manager.start_periodic_cleanup())

        # Регистрируем callback для обновления настроек
        register_settings_callback(update_all_components_settings)

        # Запускаем мониторинг изменений .env файла
        start_settings_monitor()

        if db_initialized:
            logger.info("✅ Система успешно запущена в полном режиме!")
        else:
            logger.warning("⚠️ Система запущена в ограниченном режиме (без базы данных)")
            logger.info("💡 Настройте подключение к базе данных в .env файле и перезапустите")

    except Exception as e:
        logger.error(f"❌ Ошибка запуска системы: {e}")
        logger.error("❌ Система не может быть запущена")
        # Не прерываем запуск - позволяем системе работать для настройки
        pass

    yield

    # Shutdown
    logger.info("🛑 Остановка системы...")

    # Останавливаем мониторинг настроек
    stop_settings_monitor()

    if time_manager:
        await time_manager.stop()
    if bybit_websocket:
        bybit_websocket.is_running = False
        await bybit_websocket.close()
    if bybit_api:
        await bybit_api.stop()
    if price_filter:
        await price_filter.stop()
    if db_connection:
        db_connection.close()


async def bybit_websocket_loop():
    """Цикл WebSocket соединения с переподключениями"""
    while bybit_websocket.is_running:
        try:
            await bybit_websocket.connect()
            # Если дошли сюда, соединение было успешным
            bybit_websocket.reconnect_attempts = 0

        except Exception as e:
            logger.error(f"❌ WebSocket ошибка: {e}")

            if bybit_websocket.is_running:
                bybit_websocket.reconnect_attempts += 1

                if bybit_websocket.reconnect_attempts <= bybit_websocket.max_reconnect_attempts:
                    delay = min(bybit_websocket.reconnect_delay * bybit_websocket.reconnect_attempts, 60)
                    logger.info(f"🔄 Переподключение через {delay} секунд... "
                                f"(попытка {bybit_websocket.reconnect_attempts}/{bybit_websocket.max_reconnect_attempts})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Превышено максимальное количество попыток переподключения")
                    bybit_websocket.is_running = False
                    break


async def historical_data_loader():
    """Периодическая загрузка исторических данных"""
    while True:
        try:
            # Проверяем доступность компонентов
            if not db_queries:
                logger.warning("⚠️ Загрузчик исторических данных: база данных недоступна")
                await asyncio.sleep(300)  # Ждем 5 минут и проверяем снова
                continue
                
            if not bybit_api:
                logger.warning("⚠️ Загрузчик исторических данных: Bybit API недоступен")
                await asyncio.sleep(300)
                continue
                
            if db_queries and bybit_api:
                # Получаем текущий watchlist
                try:
                    watchlist = await db_queries.get_watchlist()
                except Exception as e:
                    logger.error(f"❌ Ошибка получения watchlist: {e}")
                    await asyncio.sleep(300)
                    continue

                for symbol in watchlist:
                    try:
                        # Проверяем целостность данных
                        analysis_hours = get_setting('ANALYSIS_HOURS', 1)
                        offset_minutes = get_setting('OFFSET_MINUTES', 0)

                        # Рассчитываем период загрузки
                        total_hours = analysis_hours + (offset_minutes / 60)

                        integrity = await db_queries.check_data_integrity(symbol, int(total_hours * 60))  # в минутах

                        # Если целостность данных менее 90%, загружаем недостающие данные
                        if integrity['integrity_percentage'] < 90:
                            logger.info(
                                f"📊 Загрузка исторических данных для {symbol} (целостность: {integrity['integrity_percentage']:.1f}%)")

                            # Рассчитываем диапазон загрузки
                            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                            end_time_ms = current_time_ms - (offset_minutes * 60 * 1000)
                            start_time_ms = end_time_ms - (int(total_hours * 60) * 60 * 1000)

                            # Загружаем данные пакетами
                            batch_size_hours = 24  # 24 часа за раз
                            current_start = start_time_ms

                            while current_start < end_time_ms:
                                current_end = min(current_start + (batch_size_hours * 60 * 60 * 1000), end_time_ms)

                                try:
                                    klines = await bybit_api.get_kline_data(symbol, current_start, current_end)

                                    for kline in klines:
                                        # Сохраняем как закрытую свечу
                                        kline_data = {
                                            'start': kline['timestamp'],
                                            'end': kline['timestamp'] + 60000,  # +1 минута
                                            'open': kline['open'],
                                            'high': kline['high'],
                                            'low': kline['low'],
                                            'close': kline['close'],
                                            'volume': kline['volume']
                                        }

                                        await db_queries.save_historical_kline_data(symbol, kline_data)

                                    logger.debug(f"📊 Загружено {len(klines)} свечей для {symbol}")

                                except Exception as e:
                                    logger.error(
                                        f"❌ Ошибка загрузки данных для {symbol} в диапазоне {current_start}-{current_end}: {e}")

                                current_start = current_end
                                await asyncio.sleep(0.1)  # Небольшая задержка между запросами

                        await asyncio.sleep(0.5)  # Задержка между символами

                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки исторических данных для {symbol}: {e}")
                        continue

            # Проверяем каждые 30 минут
            await asyncio.sleep(1800)

        except Exception as e:
            logger.error(f"❌ Ошибка загрузчика исторических данных: {e}")
            await asyncio.sleep(300)  # Повторить через 5 минут при ошибке


async def periodic_cleanup():
    """Периодическая очистка старых данных"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            
            if alert_manager:
                await alert_manager.cleanup_old_data()
                
            if db_queries:
                retention_hours = get_setting('DATA_RETENTION_HOURS', 2)
                # Здесь можно добавить очистку старых данных через db_queries
            else:
                logger.debug("🧹 Очистка БД пропущена - база данных недоступна")
                
            logger.info("🧹 Периодическая очистка данных выполнена")
        except Exception as e:
            logger.error(f"❌ Ошибка периодической очистки: {e}")


app = FastAPI(title="Trading Volume Analyzer", lifespan=lifespan)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            # Ожидаем сообщения от клиента
            data = await websocket.receive_text()
            await connection_manager.handle_client_message(websocket, data)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket ошибка: {e}")
        connection_manager.disconnect(websocket)


# API endpoints
@app.get("/api/stats")
async def get_stats():
    """Получить статистику системы"""
    try:
        if not db_queries:
            return {"error": "Database not initialized"}

        # Получаем статистику из базы данных
        watchlist = await db_queries.get_watchlist()
        # alerts_data = await db_queries.get_all_alerts(limit=1000)  # Будет реализовано
        # favorites = await db_queries.get_favorites()  # Будет реализовано
        # trading_stats = await db_queries.get_trading_statistics()  # Будет реализовано

        # Информация о синхронизации времени
        time_sync_info = {}
        if time_manager:
            time_sync_info = time_manager.get_sync_status()

        # Статистика подписок
        subscription_stats = {}
        if bybit_websocket:
            subscription_stats = bybit_websocket.get_connection_stats()

        return {
            "pairs_count": len(watchlist),
            "favorites_count": 0,  # Временно
            "alerts_count": 0,  # Временно
            "volume_alerts_count": 0,  # Временно
            "consecutive_alerts_count": 0,  # Временно
            "priority_alerts_count": 0,  # Временно
            "trading_stats": {},  # Временно
            "subscription_stats": subscription_stats,
            "last_update": datetime.now(timezone.utc).isoformat(),
            "system_status": "running",
            "time_sync": time_sync_info
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {"error": str(e)}


@app.get("/api/time")
async def get_time_info():
    """Получить информацию о времени биржи"""
    try:
        if time_manager:
            return time_manager.get_time_info()
        else:
            # Fallback на локальное UTC время
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            return {
                "is_synced": False,
                "serverTime": current_time_ms,
                "local_time": datetime.now(timezone.utc).isoformat(),
                "utc_time": datetime.now(timezone.utc).isoformat(),
                "time_offset_ms": 0,
                "status": "not_synced"
            }
    except Exception as e:
        logger.error(f"Ошибка получения информации о времени: {e}")
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return {
            "is_synced": False,
            "serverTime": current_time_ms,
            "local_time": datetime.now(timezone.utc).isoformat(),
            "utc_time": datetime.now(timezone.utc).isoformat(),
            "time_offset_ms": 0,
            "status": "error",
            "error": str(e)
        }


@app.get("/api/watchlist")
async def get_watchlist():
    """Получить список торговых пар"""
    try:
        if not db_queries:
            return {
                "error": "База данных недоступна",
                "pairs": [],
                "message": "Настройте подключение к базе данных в настройках"
            }
            
        pairs = await db_queries.get_watchlist_details()
        return {"pairs": pairs}
    except Exception as e:
        logger.error(f"Ошибка получения watchlist: {e}")
        return {
            "error": str(e),
            "pairs": [],
            "message": "Ошибка получения данных из базы"
        }


@app.post("/api/watchlist")
async def add_to_watchlist(item: WatchlistAdd):
    """Добавить торговую пару в watchlist"""
    try:
        if not db_queries:
            return {
                "status": "error",
                "message": "База данных недоступна. Настройте подключение в настройках."
            }
            
        await db_queries.add_to_watchlist(item.symbol)

        # Добавляем пару в WebSocket менеджер
        if bybit_websocket:
            bybit_websocket.trading_pairs.add(item.symbol)
            await bybit_websocket.subscribe_to_new_pairs({item.symbol})

        # Уведомляем клиентов об обновлении
        await connection_manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "added",
            "symbol": item.symbol
        })

        return {"status": "success", "symbol": item.symbol}
    except Exception as e:
        logger.error(f"Ошибка добавления в watchlist: {e}")
        return {
            "status": "error",
            "message": f"Ошибка добавления в watchlist: {str(e)}"
        }


@app.get("/api/chart-data/{symbol}")
async def get_chart_data(symbol: str, interval: str = "1m", hours: int = 24):
    """Получить данные для графика"""
    try:
        # Заглушка для данных графика
        return {"chart_data": []}
    except Exception as e:
        logger.error(f"Ошибка получения данных графика: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/favorites")
async def get_favorites():
    """Получить список избранных пар"""
    try:
        # Заглушка для избранного
        return {"favorites": []}
    except Exception as e:
        logger.error(f"Ошибка получения избранного: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/favorites")
async def add_to_favorites(item: FavoriteAdd):
    """Добавить пару в избранное"""
    try:
        # Заглушка для добавления в избранное
        return {"status": "success", "symbol": item.symbol}
    except Exception as e:
        logger.error(f"Ошибка добавления в избранное: {e}")
        return {"status": "error", "message": str(e)}


@app.delete("/api/favorites/{symbol}")
async def remove_from_favorites(symbol: str):
    """Удалить пару из избранного"""
    try:
        # Заглушка для удаления из избранного
        return {"status": "success", "symbol": symbol}
    except Exception as e:
        logger.error(f"Ошибка удаления из избранного: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/alerts/all")
async def get_all_alerts():
    """Получить все алерты"""
    try:
        # Заглушка для алертов
        return {
            "volume_alerts": [],
            "consecutive_alerts": [],
            "priority_alerts": []
        }
    except Exception as e:
        logger.error(f"Ошибка получения алертов: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/alerts/symbol/{symbol}")
async def get_symbol_alerts(symbol: str, hours: int = 24):
    """Получить алерты для конкретного символа"""
    try:
        # Заглушка для алертов по символу
        return {"alerts": []}
    except Exception as e:
        logger.error(f"Ошибка получения алертов для {symbol}: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/settings")
async def get_settings():
    """Получить текущие настройки системы"""
    try:
        # Получаем настройки, сгруппированные по категориям
        settings_by_category = get_settings_by_category()

        # Информация о синхронизации времени
        time_sync_info = {}
        if time_manager:
            time_sync_info = time_manager.get_sync_status()

        # Информация о состоянии системы
        system_status = {
            "database_available": db_queries is not None,
            "database_connection": db_connection is not None,
            "alert_manager_active": alert_manager is not None,
            "websocket_active": bybit_websocket is not None and bybit_websocket.is_running,
            "price_filter_active": price_filter is not None,
            "telegram_bot_enabled": telegram_bot is not None and telegram_bot.enabled
        }

        return {
            "categories": settings_by_category,
            "time_sync": time_sync_info,
            "system_status": system_status,
            "system_info": {
                "config_file": str(ENV_FILE_PATH) if ENV_FILE_PATH.exists() else "Файл не создан",
                "config_exists": ENV_FILE_PATH.exists(),
                "last_modified": datetime.fromtimestamp(ENV_FILE_PATH.stat().st_mtime).isoformat() if ENV_FILE_PATH.exists() else None
            }
        }

    except Exception as e:
        logger.error(f"Ошибка получения настроек: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/paper-trades")
async def create_paper_trade(trade: PaperTradeCreate):
    """Создание бумажной сделки"""
    try:
        if not db_queries:
            return {
                "status": "error", 
                "message": "База данных недоступна. Настройте подключение в настройках."
            }

        # Сохраняем бумажную сделку в базу данных
        trade_id = await db_queries.save_paper_trade(trade.dict())

        return {
            "status": "success",
            "trade_id": trade_id,
            "message": "Бумажная сделка создана"
        }
    except Exception as e:
        logger.error(f"Ошибка создания бумажной сделки: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/trading/execute-trade")
async def execute_real_trade(trade: RealTradeCreate):
    """Выполнение реальной сделки"""
    try:
        # Проверяем настройки API
        api_key = get_setting('BYBIT_API_KEY', '')
        api_secret = get_setting('BYBIT_API_SECRET', '')

        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API ключи не настроены")

        # Здесь должна быть логика выполнения реальной сделки через Bybit API
        # Пока возвращаем заглушку
        return {
            "status": "success",
            "order_id": "mock_order_123",
            "message": "Сделка выполнена (demo режим)"
        }
    except Exception as e:
        logger.error(f"Ошибка выполнения реальной сделки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/test-connection")
async def test_trading_connection(credentials: dict):
    """Тестирование подключения к торговому API"""
    try:
        api_key = credentials.get('api_key')
        api_secret = credentials.get('api_secret')

        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API ключи не предоставлены")

        # Здесь должна быть проверка подключения к Bybit API
        # Пока возвращаем заглушку
        return {
            "success": True,
            "balance": 10000.0,
            "message": "Подключение успешно (demo режим)"
        }
    except Exception as e:
        logger.error(f"Ошибка тестирования подключения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings/schema")
async def get_settings_schema_endpoint():
    """Получить схему настроек с описаниями и типами"""
    try:
        schema = get_settings_schema()
        return {"schema": schema}
    except Exception as e:
        logger.error(f"Ошибка получения схемы настроек: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
async def update_settings(settings_update: SettingsUpdate):
    """Обновить настройки анализатора"""
    try:
        settings = settings_update.settings
        
        # Преобразуем вложенные настройки в плоский формат
        flat_settings = {}
        for key, value in settings.items():
            # Если это прямой ключ настройки (уже в правильном формате)
            flat_settings[key] = value
        
        # Обновляем все настройки одним вызовом
        success, errors = update_multiple_settings(flat_settings)
        
        if not success:
            return {
                "status": "error", 
                "message": "Ошибка сохранения настроек", 
                "errors": errors
            }

        # Обновляем настройки во всех компонентах системы
        await update_all_components_settings(flat_settings)

        # Уведомляем клиентов об успешном обновлении
        await connection_manager.broadcast_json({
            "type": "settings_updated",
            "status": "success",
            "data": settings,
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "message": "Настройки успешно обновлены и сохранены",
            "system_restart_required": False  # Настройки применяются автоматически
        })
        
        logger.info("✅ Настройки успешно обновлены через API")
        return {
            "status": "success", 
            "updated_count": len(flat_settings),
            "message": "Настройки успешно обновлены и сохранены",
            "applied_immediately": True
        }
        
    except Exception as e:
        logger.error(f"Ошибка обновления настроек: {e}")
        
        # Уведомляем клиентов об ошибке
        if connection_manager:
            await connection_manager.broadcast_json({
                "type": "settings_update_error",
                "error": str(e),
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
            })
        
        return {
            "status": "error", 
            "message": f"Ошибка обновления настроек: {str(e)}", 
            "detail": str(e)
        }


@app.post("/api/settings/reset")
async def reset_settings(reset_data: SettingsReset):
    """Сброс настроек к значениям по умолчанию"""
    try:
        if not reset_data.confirm:
            return {
                "status": "error",
                "message": "Требуется подтверждение для сброса настроек"
            }
        
        success = reset_settings_to_default()
        
        if success:
            # Обновляем настройки во всех компонентах
            from settings import load_settings
            new_settings = load_settings()
            await update_all_components_settings(new_settings)
            
            if connection_manager:
                await connection_manager.broadcast_json({
                    "type": "settings_reset",
                    "status": "success",
                    "message": "Настройки сброшены к значениям по умолчанию",
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
                })
            
            return {
                "status": "success",
                "message": "Настройки успешно сброшены к значениям по умолчанию"
            }
        else:
            return {
                "status": "error",
                "message": "Ошибка сброса настроек"
            }
            
    except Exception as e:
        logger.error(f"Ошибка сброса настроек: {e}")
        return {
            "status": "error",
            "message": f"Ошибка сброса настроек: {str(e)}"
        }


@app.get("/api/settings/export")
async def export_settings_endpoint():
    """Экспорт текущих настроек"""
    try:
        settings = export_settings()
        return {
            "status": "success",
            "settings": settings,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(settings)
        }
    except Exception as e:
        logger.error(f"Ошибка экспорта настроек: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/import")
async def import_settings_endpoint(import_data: SettingsImport):
    """Импорт настроек"""
    try:
        success, errors = import_settings(import_data.settings)
        
        if success:
            # Обновляем настройки во всех компонентах
            await update_all_components_settings(import_data.settings)
            
            if connection_manager:
                await connection_manager.broadcast_json({
                    "type": "settings_imported",
                    "status": "success",
                    "count": len(import_data.settings),
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
                })
            
            return {
                "status": "success",
                "imported_count": len(import_data.settings),
                "message": "Настройки успешно импортированы"
            }
        else:
            return {
                "status": "error",
                "message": "Ошибка импорта настроек",
                "errors": errors
            }
            
    except Exception as e:
        logger.error(f"Ошибка импорта настроек: {e}")
        return {
            "status": "error",
            "message": f"Ошибка импорта настроек: {str(e)}"
        }


@app.post("/api/settings/reload")
async def reload_settings_endpoint():
    """Принудительная перезагрузка настроек из .env файла"""
    try:
        from settings import reload_settings, load_settings
        await reload_settings()
        
        # Обновляем настройки во всех компонентах
        new_settings = load_settings()
        await update_all_components_settings(new_settings)

        return {"status": "success", "message": "Настройки перезагружены из .env файла"}
    except Exception as e:
        logger.error(f"Ошибка перезагрузки настроек: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Удалить торговую пару из watchlist"""
    try:
        if not db_queries:
            return {
                "status": "error",
                "message": "База данных недоступна. Настройте подключение в настройках."
            }
            
        await db_queries.remove_from_watchlist(symbol)

        # Удаляем пару из WebSocket менеджера
        if bybit_websocket:
            bybit_websocket.trading_pairs.discard(symbol)
            await bybit_websocket.unsubscribe_from_pairs({symbol})

        # Уведомляем клиентов об обновлении
        await connection_manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "removed",
            "symbol": symbol
        })

        return {"status": "success", "symbol": symbol}
    except Exception as e:
        logger.error(f"Ошибка удаления из watchlist: {e}")
        return {
            "status": "error",
            "message": f"Ошибка удаления из watchlist: {str(e)}"
        }


# Проверяем существование директории dist перед монтированием
if os.path.exists("dist"):
    if os.path.exists("dist/assets"):
        app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")


    @app.get("/vite.svg")
    async def get_vite_svg():
        if os.path.exists("dist/vite.svg"):
            return FileResponse("dist/vite.svg")
        raise HTTPException(status_code=404, detail="File not found")


    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Обслуживание SPA для всех маршрутов"""
        if os.path.exists("dist/index.html"):
            return FileResponse("dist/index.html")
        raise HTTPException(status_code=404, detail="SPA not built")
else:
    @app.get("/")
    async def root():
        return {"message": "Frontend not built. Run 'npm run build' first."}

if __name__ == "__main__":
    # Настройки сервера из переменных окружения
    host = get_setting('SERVER_HOST', '0.0.0.0')
    port = get_setting('SERVER_PORT', 8000)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )