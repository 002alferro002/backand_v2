from fastapi import APIRouter, HTTPException
from typing import Dict, List
from pydantic import BaseModel
from cryptoscan.backand.core.core_logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/startup", tags=["startup"])


class StartupDataResponse(BaseModel):
    alerts: List[Dict]
    watchlist: List[str]
    favorites: List[Dict]
    settings: Dict
    trading_settings: Dict
    data_integrity: Dict


def setup_startup_routes(db_queries, alert_manager, price_filter):
    """Настройка маршрутов для загрузки данных при запуске"""
    
    @router.get("/data", response_model=StartupDataResponse)
    async def get_startup_data():
        """Получение всех данных для инициализации приложения"""
        try:
            # Загружаем алерты (последние 100)
            alerts = await db_queries.get_alerts(limit=100)
            
            # Загружаем watchlist
            watchlist = await db_queries.get_watchlist()
            
            # Загружаем избранные пары
            favorites = await db_queries.get_favorites()
            
            # Загружаем торговые настройки
            trading_settings = await db_queries.get_trading_settings()
            
            # Получаем настройки системы
            settings = {}
            if alert_manager:
                settings.update(alert_manager.get_settings())
            if price_filter:
                settings.update(price_filter.get_settings())
            
            # Проверяем целостность данных для watchlist
            data_integrity = {}
            for symbol in watchlist[:5]:  # Проверяем первые 5 символов
                try:
                    integrity = await db_queries.check_data_integrity(symbol, 1)
                    data_integrity[symbol] = integrity
                except Exception as e:
                    logger.error(f"Ошибка проверки целостности для {symbol}: {e}")
                    data_integrity[symbol] = {
                        'total_existing': 0,
                        'total_expected': 60,
                        'integrity_percentage': 0,
                        'missing_count': 60
                    }
            
            return StartupDataResponse(
                alerts=alerts,
                watchlist=watchlist,
                favorites=favorites,
                settings=settings,
                trading_settings=trading_settings,
                data_integrity=data_integrity
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения данных при запуске: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения данных: {str(e)}")

    @router.get("/alerts/recent")
    async def get_recent_alerts(limit: int = 50):
        """Получение последних алертов"""
        try:
            alerts = await db_queries.get_alerts(limit=limit)
            return {"alerts": alerts, "count": len(alerts)}
            
        except Exception as e:
            logger.error(f"Ошибка получения последних алертов: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения алертов: {str(e)}")

    @router.get("/watchlist/status")
    async def get_watchlist_status():
        """Получение статуса watchlist с проверкой данных"""
        try:
            watchlist = await db_queries.get_watchlist()
            watchlist_details = await db_queries.get_watchlist_details()
            
            # Проверяем целостность данных для каждого символа
            status_data = []
            for symbol in watchlist:
                try:
                    integrity = await db_queries.check_data_integrity(symbol, 1)
                    data_range = await db_queries.get_data_time_range(symbol)
                    
                    status_data.append({
                        'symbol': symbol,
                        'integrity_percentage': integrity['integrity_percentage'],
                        'total_candles': data_range['total_count'],
                        'missing_count': integrity['missing_count'],
                        'status': 'ok' if integrity['integrity_percentage'] > 95 else 'needs_data'
                    })
                except Exception as e:
                    logger.error(f"Ошибка проверки статуса для {symbol}: {e}")
                    status_data.append({
                        'symbol': symbol,
                        'integrity_percentage': 0,
                        'total_candles': 0,
                        'missing_count': 60,
                        'status': 'error',
                        'error': str(e)
                    })
            
            return {
                "watchlist": watchlist,
                "watchlist_details": watchlist_details,
                "status_data": status_data,
                "total_symbols": len(watchlist)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса watchlist: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")

    @router.post("/data/reload")
    async def reload_startup_data():
        """Перезагрузка данных при запуске"""
        try:
            # Перезагружаем watchlist
            if price_filter:
                await price_filter.update_watchlist()
            
            # Получаем обновленные данные
            startup_data = await get_startup_data()
            
            return {
                "success": True,
                "message": "Данные перезагружены",
                "data": startup_data
            }
            
        except Exception as e:
            logger.error(f"Ошибка перезагрузки данных: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка перезагрузки: {str(e)}")

    return router