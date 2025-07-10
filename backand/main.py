import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Импорты модулей системы
from cryptoscan.backand.core.core_logger import get_logger
from cryptoscan.backand.database.database_manager import DatabaseManager
from cryptoscan.backand.alert.alert_manager import AlertManager
from cryptoscan.backand.bybit.bybit_websocket import BybitWebSocketManager
from cryptoscan.backand.filter.filter_price import PriceFilter
from cryptoscan.backand.telegram.telegram_bot import TelegramBot
from cryptoscan.backand.times.times_manager import TimeManager
from cryptoscan.backand.websocket.websocket_manager import ConnectionManager
from cryptoscan.backand.settings import (
    get_setting, 
    start_settings_monitor, 
    stop_settings_monitor,
    set_main_event_loop,
    register_settings_callback
)

# Импорты API роутеров
from cryptoscan.backand.api.api_alerts import setup_alerts_routes
from cryptoscan.backand.api.api_favorites import setup_favorites_routes
from cryptoscan.backand.api.api_kline import setup_kline_routes
from cryptoscan.backand.api.api_trading import setup_trading_routes
from cryptoscan.backand.api.api_watchlist import setup_watchlist_routes
from cryptoscan.backand.api.api_startup import setup_startup_routes

logger = get_logger(__name__)

# Глобальные переменные для компонентов системы
database_manager = None
alert_manager = None
bybit_websocket = None
price_filter = None
telegram_bot = None
time_manager = None
connection_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("🚀 Запуск CryptoScan...")
    
    try:
        # Устанавливаем ссылку на главный event loop
        set_main_event_loop(asyncio.get_event_loop())
        
        # Инициализация компонентов
        await initialize_components()
        
        # Запуск мониторинга настроек
        start_settings_monitor()
        
        logger.info("✅ CryptoScan успешно запущен")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска приложения: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 Остановка CryptoScan...")
        
        try:
            await shutdown_components()
            stop_settings_monitor()
            logger.info("✅ CryptoScan успешно остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки приложения: {e}")


async def initialize_components():
    """Инициализация всех компонентов системы"""
    global database_manager, alert_manager, bybit_websocket, price_filter
    global telegram_bot, time_manager, connection_manager
    
    try:
        # 1. Инициализация базы данных
        logger.info("📊 Инициализация базы данных...")
        database_manager = DatabaseManager()
        await database_manager.initialize()
        
        # 2. Инициализация менеджера времени
        logger.info("⏰ Инициализация синхронизации времени...")
        time_manager = TimeManager()
        await time_manager.start()
        
        # 3. Инициализация WebSocket менеджера
        logger.info("🔌 Инициализация WebSocket менеджера...")
        connection_manager = ConnectionManager()
        
        # 4. Инициализация Telegram бота
        logger.info("📱 Инициализация Telegram бота...")
        telegram_bot = TelegramBot()
        
        # 5. Инициализация менеджера алертов
        logger.info("🚨 Инициализация менеджера алертов...")
        alert_manager = AlertManager(
            db_queries=database_manager.db_queries,
            telegram_bot=telegram_bot,
            connection_manager=connection_manager,
            time_manager=time_manager
        )
        
        # 6. Инициализация фильтра цен
        logger.info("💰 Инициализация фильтра цен...")
        price_filter = PriceFilter(database_manager)
        
        # 7. Инициализация Bybit WebSocket
        logger.info("📡 Инициализация Bybit WebSocket...")
        bybit_websocket = BybitWebSocketManager(alert_manager, connection_manager)
        
        # 8. Настройка callback для обновления торговых пар
        price_filter.set_pairs_updated_callback(handle_pairs_updated)
        
        # 9. Регистрация callback для обновления настроек
        register_settings_callback(handle_settings_update)
        
        # 10. Запуск фоновых задач
        await start_background_tasks()
        
        logger.info("✅ Все компоненты инициализированы")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации компонентов: {e}")
        raise


async def start_background_tasks():
    """Запуск фоновых задач"""
    try:
        # Запуск фильтра цен
        asyncio.create_task(price_filter.start())
        
        # Запуск Bybit WebSocket
        asyncio.create_task(start_bybit_websocket())
        
        # Запуск периодической очистки данных
        asyncio.create_task(periodic_cleanup())
        
        logger.info("✅ Фоновые задачи запущены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска фоновых задач: {e}")


async def start_bybit_websocket():
    """Запуск Bybit WebSocket с обработкой ошибок"""
    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            # Получаем список торговых пар
            watchlist = await database_manager.get_watchlist()
            
            if watchlist:
                # Обновляем список пар в WebSocket менеджере
                bybit_websocket.update_trading_pairs(set(watchlist), set())
                
                # Запускаем WebSocket
                bybit_websocket.is_running = True
                await bybit_websocket.connect()
            else:
                logger.warning("⚠️ Watchlist пуст, WebSocket не запущен")
                break
                
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Bybit WebSocket (попытка {attempt + 1}): {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"🔄 Повторная попытка через {retry_delay} секунд...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Экспоненциальная задержка
            else:
                logger.error("❌ Превышено максимальное количество попыток запуска WebSocket")


async def periodic_cleanup():
    """Периодическая очистка старых данных"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            
            if alert_manager:
                await alert_manager.cleanup_old_data()
                
            logger.info("🧹 Периодическая очистка данных выполнена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка периодической очистки: {e}")
            await asyncio.sleep(300)  # Повторить через 5 минут при ошибке


async def handle_pairs_updated(new_pairs: set, removed_pairs: set):
    """Обработка обновления списка торговых пар"""
    try:
        if bybit_websocket and bybit_websocket.is_running:
            # Обновляем список пар в WebSocket
            bybit_websocket.update_trading_pairs(new_pairs, removed_pairs)
            
            # Подписываемся на новые пары
            if new_pairs:
                await bybit_websocket.subscribe_to_new_pairs(new_pairs)
                logger.info(f"📡 Подписка на {len(new_pairs)} новых пар")
            
            # Отписываемся от удаленных пар
            if removed_pairs:
                await bybit_websocket.unsubscribe_from_pairs(removed_pairs)
                logger.info(f"📡 Отписка от {len(removed_pairs)} пар")
                
    except Exception as e:
        logger.error(f"❌ Ошибка обновления торговых пар: {e}")


async def handle_settings_update(new_settings: dict):
    """Обработка обновления настроек"""
    try:
        # Обновляем настройки в компонентах
        if alert_manager:
            alert_manager.update_settings(new_settings)
            
        if price_filter:
            price_filter.update_settings(new_settings)
            
        if telegram_bot:
            telegram_bot.update_settings(
                new_settings.get('TELEGRAM_BOT_TOKEN'),
                new_settings.get('TELEGRAM_CHAT_ID')
            )
            
        logger.info("⚙️ Настройки обновлены во всех компонентах")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления настроек: {e}")


async def shutdown_components():
    """Остановка всех компонентов"""
    global database_manager, alert_manager, bybit_websocket, price_filter
    global telegram_bot, time_manager, connection_manager
    
    try:
        # Останавливаем WebSocket
        if bybit_websocket:
            await bybit_websocket.close()
            
        # Останавливаем фильтр цен
        if price_filter:
            await price_filter.stop()
            
        # Останавливаем менеджер времени
        if time_manager:
            await time_manager.stop()
            
        # Закрываем базу данных
        if database_manager:
            await database_manager.close()
            
        logger.info("✅ Все компоненты остановлены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка остановки компонентов: {e}")


# Создание FastAPI приложения
app = FastAPI(
    title="CryptoScan API",
    description="API для анализа объемов криптовалют",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API роуты
@app.get("/api/stats")
async def get_stats():
    """Получение статистики системы"""
    try:
        stats = {
            "status": "running",
            "components": {
                "database": database_manager.is_initialized() if database_manager else False,
                "websocket": bybit_websocket.websocket_connected if bybit_websocket else False,
                "alerts": alert_manager is not None,
                "price_filter": price_filter is not None,
                "telegram": telegram_bot.enabled if telegram_bot else False,
                "time_sync": time_manager.is_time_synced() if time_manager else False
            }
        }
        
        if connection_manager:
            stats["websocket_connections"] = connection_manager.get_connection_count()
            
        if bybit_websocket:
            stats["bybit_connection"] = bybit_websocket.get_connection_stats()
            
        return stats
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/api/time")
async def get_time_info():
    """Получение информации о времени"""
    try:
        if time_manager:
            return time_manager.get_time_info()
        else:
            return {
                "error": "TimeManager не инициализирован",
                "status": "not_available"
            }
    except Exception as e:
        logger.error(f"Ошибка получения информации о времени: {e}")
        return {"error": str(e), "status": "error"}


@app.get("/api/settings")
async def get_settings():
    """Получение текущих настроек"""
    try:
        settings = {}
        
        if alert_manager:
            settings["volume_analyzer"] = alert_manager.get_settings()
            
        if price_filter:
            settings["price_filter"] = price_filter.get_settings()
            
        if time_manager:
            settings["time_sync"] = time_manager.get_sync_status()
            
        if telegram_bot:
            settings["telegram"] = telegram_bot.get_status()
            
        return settings
        
    except Exception as e:
        logger.error(f"Ошибка получения настроек: {e}")
        return {"error": str(e)}


@app.post("/api/settings")
async def update_settings(new_settings: dict):
    """Обновление настроек"""
    try:
        from cryptoscan.backand.settings import update_multiple_settings
        
        success, errors = update_multiple_settings(new_settings)
        
        if success:
            return {"success": True, "message": "Настройки обновлены"}
        else:
            return {"success": False, "errors": errors}
            
    except Exception as e:
        logger.error(f"Ошибка обновления настроек: {e}")
        return {"success": False, "error": str(e)}


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для real-time обновлений"""
    if not connection_manager:
        await websocket.close(code=1000, reason="Connection manager not available")
        return
        
    await connection_manager.connect(websocket)
    
    try:
        while True:
            # Получаем сообщения от клиента
            message = await websocket.receive_text()
            await connection_manager.handle_client_message(websocket, message)
            
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
        connection_manager.disconnect(websocket)


# Подключение API роутеров после инициализации компонентов
@app.on_event("startup")
async def setup_routes():
    """Настройка API роутеров после инициализации"""
    try:
        # Ждем инициализации компонентов
        await asyncio.sleep(1)
        
        if database_manager and database_manager.db_queries:
            # Подключаем роуты
            app.include_router(setup_alerts_routes(database_manager.db_queries))
            app.include_router(setup_favorites_routes(database_manager.db_queries))
            app.include_router(setup_kline_routes(database_manager.db_queries))
            app.include_router(setup_trading_routes(database_manager.db_queries))
            app.include_router(setup_watchlist_routes(database_manager.db_queries))
            app.include_router(setup_startup_routes(
                database_manager.db_queries, 
                alert_manager, 
                price_filter
            ))
            
            logger.info("✅ API роуты подключены")
        else:
            logger.error("❌ Не удалось подключить API роуты - компоненты не инициализированы")
            
    except Exception as e:
        logger.error(f"❌ Ошибка настройки API роутеров: {e}")


# Статические файлы (для фронтенда)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_root():
    """Главная страница"""
    try:
        return FileResponse("static/index.html")
    except Exception:
        return {"message": "CryptoScan API", "status": "running"}


if __name__ == "__main__":
    # Настройки сервера
    host = get_setting('SERVER_HOST', '0.0.0.0')
    port = int(get_setting('SERVER_PORT', 8000))
    
    logger.info(f"🚀 Запуск сервера на {host}:{port}")
    
    # Запуск сервера
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )