from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Dict, Optional
from pydantic import BaseModel
from cryptoscan.backand.core.core_logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertResponse(BaseModel):
    id: int
    symbol: str
    alert_type: str
    price: float
    volume_ratio: Optional[float] = None
    current_volume_usdt: Optional[int] = None
    average_volume_usdt: Optional[int] = None
    consecutive_count: Optional[int] = None
    alert_timestamp_ms: int
    close_timestamp_ms: Optional[int] = None
    is_closed: bool
    is_true_signal: Optional[bool] = None
    has_imbalance: bool
    imbalance_data: Optional[Dict] = None
    candle_data: Optional[Dict] = None
    order_book_snapshot: Optional[Dict] = None
    message: str
    status: str
    created_at: str


class AlertUpdateRequest(BaseModel):
    status: Optional[str] = None
    is_true_signal: Optional[bool] = None


class AlertsListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    page: int
    limit: int


class AlertsStatsResponse(BaseModel):
    total_alerts: int
    volume_alerts: int
    consecutive_alerts: int
    priority_alerts: int
    true_signals: int
    false_signals: int
    alerts_with_imbalance: int
    accuracy_percentage: float
    avg_volume_ratio: Optional[float] = None


def setup_alerts_routes(db_queries):
    """Настройка маршрутов для алертов"""
    
    @router.get("/", response_model=AlertsListResponse)
    async def get_alerts(
        page: int = Query(1, ge=1, description="Номер страницы"),
        limit: int = Query(50, ge=1, le=1000, description="Количество алертов на странице"),
        symbol: Optional[str] = Query(None, description="Фильтр по символу"),
        alert_type: Optional[str] = Query(None, description="Фильтр по типу алерта"),
        status: Optional[str] = Query(None, description="Фильтр по статусу")
    ):
        """Получение списка алертов с фильтрацией и пагинацией"""
        try:
            offset = (page - 1) * limit
            alerts = await db_queries.get_alerts(
                limit=limit, 
                offset=offset, 
                symbol=symbol, 
                alert_type=alert_type, 
                status=status
            )
            
            # Получаем общее количество для пагинации
            total_query_params = []
            if symbol:
                total_query_params.append(f"symbol = '{symbol}'")
            if alert_type:
                total_query_params.append(f"alert_type = '{alert_type}'")
            if status:
                total_query_params.append(f"status = '{status}'")
            
            where_clause = "WHERE " + " AND ".join(total_query_params) if total_query_params else ""
            total_query = f"SELECT COUNT(*) as count FROM alerts {where_clause}"
            
            total_result = await db_queries.db_connection.execute_query(total_query)
            total = total_result[0]['count'] if total_result else 0
            
            return AlertsListResponse(
                alerts=alerts,
                total=total,
                page=page,
                limit=limit
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения алертов: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения алертов: {str(e)}")

    @router.get("/{alert_id}", response_model=AlertResponse)
    async def get_alert(alert_id: int = Path(..., description="ID алерта")):
        """Получение алерта по ID"""
        try:
            alert = await db_queries.get_alert_by_id(alert_id)
            if not alert:
                raise HTTPException(status_code=404, detail="Алерт не найден")
            
            return AlertResponse(**alert)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка получения алерта {alert_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения алерта: {str(e)}")

    @router.put("/{alert_id}")
    async def update_alert(
        alert_id: int = Path(..., description="ID алерта"),
        update_data: AlertUpdateRequest = None
    ):
        """Обновление алерта"""
        try:
            success = await db_queries.update_alert_status(
                alert_id, 
                update_data.status if update_data and update_data.status else None,
                update_data.is_true_signal if update_data else None
            )
            
            if not success:
                raise HTTPException(status_code=404, detail="Алерт не найден или не обновлен")
            
            return {"success": True, "message": "Алерт обновлен"}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка обновления алерта {alert_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка обновления алерта: {str(e)}")

    @router.delete("/{alert_id}")
    async def delete_alert(alert_id: int = Path(..., description="ID алерта")):
        """Удаление алерта"""
        try:
            success = await db_queries.delete_alert(alert_id)
            if not success:
                raise HTTPException(status_code=404, detail="Алерт не найден")
            
            return {"success": True, "message": "Алерт удален"}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка удаления алерта {alert_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка удаления алерта: {str(e)}")

    @router.get("/stats/summary", response_model=AlertsStatsResponse)
    async def get_alerts_statistics(
        days: int = Query(7, ge=1, le=365, description="Количество дней для статистики")
    ):
        """Получение статистики алертов"""
        try:
            stats = await db_queries.get_alerts_statistics(days)
            return AlertsStatsResponse(**stats)
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики алертов: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

    return router