from fastapi import APIRouter, HTTPException, Path
from typing import List, Dict
from pydantic import BaseModel
from cryptoscan.backand.core.core_logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    id: int
    symbol: str
    price_drop: float
    current_price: float
    historical_price: float
    is_active: bool
    added_at: str
    updated_at: str


class WatchlistAddRequest(BaseModel):
    symbol: str
    price_drop: float = 0
    current_price: float = 0
    historical_price: float = 0


class WatchlistUpdateRequest(BaseModel):
    symbol: str
    is_active: bool


def setup_watchlist_routes(db_queries):
    """Настройка маршрутов для watchlist"""
    
    @router.get("/", response_model=List[WatchlistItem])
    async def get_watchlist():
        """Получение полного списка watchlist"""
        try:
            watchlist = await db_queries.get_watchlist_details()
            return [WatchlistItem(**item) for item in watchlist]
            
        except Exception as e:
            logger.error(f"Ошибка получения watchlist: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения watchlist: {str(e)}")

    @router.get("/symbols")
    async def get_watchlist_symbols():
        """Получение только символов из watchlist"""
        try:
            symbols = await db_queries.get_watchlist()
            return {"symbols": symbols}
            
        except Exception as e:
            logger.error(f"Ошибка получения символов watchlist: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения символов: {str(e)}")

    @router.post("/")
    async def add_to_watchlist(item: WatchlistAddRequest):
        """Добавление символа в watchlist"""
        try:
            await db_queries.add_to_watchlist(
                symbol=item.symbol,
                price_drop=item.price_drop,
                current_price=item.current_price,
                historical_price=item.historical_price
            )
            
            return {"success": True, "message": f"Символ {item.symbol} добавлен в watchlist"}
            
        except Exception as e:
            logger.error(f"Ошибка добавления в watchlist: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка добавления в watchlist: {str(e)}")

    @router.put("/{item_id}")
    async def update_watchlist_item(
        item_id: int = Path(..., description="ID элемента watchlist"),
        update_data: WatchlistUpdateRequest = None
    ):
        """Обновление элемента watchlist"""
        try:
            await db_queries.update_watchlist_item(
                item_id=item_id,
                symbol=update_data.symbol,
                is_active=update_data.is_active
            )
            
            return {"success": True, "message": "Элемент watchlist обновлен"}
            
        except Exception as e:
            logger.error(f"Ошибка обновления watchlist: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка обновления watchlist: {str(e)}")

    @router.delete("/{item_id}")
    async def remove_from_watchlist(item_id: int = Path(..., description="ID элемента watchlist")):
        """Удаление элемента из watchlist"""
        try:
            await db_queries.remove_from_watchlist(item_id=item_id)
            return {"success": True, "message": "Элемент удален из watchlist"}
            
        except Exception as e:
            logger.error(f"Ошибка удаления из watchlist: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка удаления из watchlist: {str(e)}")

    @router.delete("/symbol/{symbol}")
    async def remove_symbol_from_watchlist(symbol: str = Path(..., description="Символ для удаления")):
        """Удаление символа из watchlist"""
        try:
            await db_queries.remove_from_watchlist(symbol=symbol)
            return {"success": True, "message": f"Символ {symbol} удален из watchlist"}
            
        except Exception as e:
            logger.error(f"Ошибка удаления символа из watchlist: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка удаления символа: {str(e)}")

    return router