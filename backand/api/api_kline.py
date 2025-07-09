from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from cryptoscan.backand.core.core_logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/kline", tags=["kline"])


class KlineData(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool
    is_long: bool


class DataIntegrityResponse(BaseModel):
    symbol: str
    total_existing: int
    total_expected: int
    integrity_percentage: float
    missing_count: int


class DataRangeResponse(BaseModel):
    symbol: str
    earliest_time: Optional[int]
    latest_time: Optional[int]
    total_count: int


def setup_kline_routes(db_queries):
    """Настройка маршрутов для kline данных"""
    
    @router.get("/{symbol}/recent", response_model=List[KlineData])
    async def get_recent_candles(
        symbol: str = Path(..., description="Торговый символ"),
        limit: int = Query(100, ge=1, le=1000, description="Количество свечей")
    ):
        """Получение последних свечей для символа"""
        try:
            candles = await db_queries.get_recent_candles(symbol, limit)
            return [KlineData(**candle) for candle in candles]
            
        except Exception as e:
            logger.error(f"Ошибка получения свечей для {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения данных: {str(e)}")

    @router.get("/{symbol}/integrity", response_model=DataIntegrityResponse)
    async def check_data_integrity(
        symbol: str = Path(..., description="Торговый символ"),
        hours: int = Query(1, ge=1, le=168, description="Период в часах для проверки")
    ):
        """Проверка целостности данных для символа"""
        try:
            integrity = await db_queries.check_data_integrity(symbol, hours)
            return DataIntegrityResponse(symbol=symbol, **integrity)
            
        except Exception as e:
            logger.error(f"Ошибка проверки целостности для {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка проверки данных: {str(e)}")

    @router.get("/{symbol}/range", response_model=DataRangeResponse)
    async def get_data_range(symbol: str = Path(..., description="Торговый символ")):
        """Получение временного диапазона данных для символа"""
        try:
            range_data = await db_queries.get_data_time_range(symbol)
            return DataRangeResponse(symbol=symbol, **range_data)
            
        except Exception as e:
            logger.error(f"Ошибка получения диапазона данных для {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения диапазона: {str(e)}")

    @router.get("/{symbol}/volumes")
    async def get_historical_volumes(
        symbol: str = Path(..., description="Торговый символ"),
        hours: int = Query(1, ge=1, le=168, description="Период в часах"),
        offset_minutes: int = Query(0, ge=0, le=1440, description="Смещение в минутах"),
        volume_type: str = Query("long", regex="^(long|short|all)$", description="Тип объемов")
    ):
        """Получение исторических объемов для символа"""
        try:
            volumes = await db_queries.get_historical_long_volumes(
                symbol, hours, offset_minutes, volume_type
            )
            
            # Рассчитываем статистику
            if volumes:
                avg_volume = sum(volumes) / len(volumes)
                max_volume = max(volumes)
                min_volume = min(volumes)
            else:
                avg_volume = max_volume = min_volume = 0
            
            return {
                "symbol": symbol,
                "period_hours": hours,
                "offset_minutes": offset_minutes,
                "volume_type": volume_type,
                "volumes": volumes,
                "count": len(volumes),
                "average_volume": avg_volume,
                "max_volume": max_volume,
                "min_volume": min_volume
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения объемов для {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения объемов: {str(e)}")

    @router.delete("/{symbol}/cleanup")
    async def cleanup_old_data(
        symbol: str = Path(..., description="Торговый символ"),
        retention_hours: int = Query(24, ge=1, le=8760, description="Период хранения в часах")
    ):
        """Очистка старых данных для символа"""
        try:
            deleted_count = await db_queries.cleanup_old_candles(symbol, retention_hours)
            
            return {
                "success": True,
                "symbol": symbol,
                "deleted_count": deleted_count,
                "retention_hours": retention_hours,
                "message": f"Удалено {deleted_count} старых свечей"
            }
            
        except Exception as e:
            logger.error(f"Ошибка очистки данных для {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка очистки данных: {str(e)}")

    @router.post("/{symbol}/save")
    async def save_kline_data(
        symbol: str = Path(..., description="Торговый символ"),
        kline_data: Dict = None
    ):
        """Сохранение kline данных"""
        try:
            if not kline_data:
                raise HTTPException(status_code=400, detail="Данные kline не предоставлены")
            
            # Проверяем обязательные поля
            required_fields = ['start', 'end', 'open', 'high', 'low', 'close', 'volume']
            for field in required_fields:
                if field not in kline_data:
                    raise HTTPException(status_code=400, detail=f"Отсутствует обязательное поле: {field}")
            
            is_closed = kline_data.get('confirm', False)
            await db_queries.save_kline_data(symbol, kline_data, is_closed)
            
            return {
                "success": True,
                "symbol": symbol,
                "is_closed": is_closed,
                "message": "Данные kline сохранены"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка сохранения kline данных для {symbol}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения данных: {str(e)}")

    return router