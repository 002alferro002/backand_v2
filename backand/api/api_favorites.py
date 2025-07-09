from fastapi import APIRouter, HTTPException, Path
from typing import List
from pydantic import BaseModel
from cryptoscan.backand.core.core_logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


class FavoriteItem(BaseModel):
    id: int
    symbol: str
    notes: str
    color: str
    sort_order: int
    created_at: str
    updated_at: str


class FavoriteAddRequest(BaseModel):
    symbol: str
    notes: str = ""
    color: str = "#FFD700"
    sort_order: int = 0


class FavoriteUpdateRequest(BaseModel):
    symbol: str = None
    notes: str = None
    color: str = None
    sort_order: int = None


def setup_favorites_routes(db_queries):
    """Настройка маршрутов для избранных пар"""
    
    @router.get("/", response_model=List[FavoriteItem])
    async def get_favorites():
        """Получение списка избранных пар"""
        try:
            favorites = await db_queries.get_favorites()
            return [FavoriteItem(**item) for item in favorites]
            
        except Exception as e:
            logger.error(f"Ошибка получения избранных: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения избранных: {str(e)}")

    @router.post("/")
    async def add_to_favorites(item: FavoriteAddRequest):
        """Добавление пары в избранное"""
        try:
            favorite_id = await db_queries.add_to_favorites(
                symbol=item.symbol,
                notes=item.notes,
                color=item.color,
                sort_order=item.sort_order
            )
            
            if favorite_id:
                return {"success": True, "id": favorite_id, "message": f"Пара {item.symbol} добавлена в избранное"}
            else:
                raise HTTPException(status_code=500, detail="Не удалось добавить в избранное")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка добавления в избранное: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка добавления в избранное: {str(e)}")

    @router.put("/{favorite_id}")
    async def update_favorite(
        favorite_id: int = Path(..., description="ID избранной пары"),
        update_data: FavoriteUpdateRequest = None
    ):
        """Обновление избранной пары"""
        try:
            success = await db_queries.update_favorite(
                favorite_id=favorite_id,
                symbol=update_data.symbol if update_data else None,
                notes=update_data.notes if update_data else None,
                color=update_data.color if update_data else None,
                sort_order=update_data.sort_order if update_data else None
            )
            
            if success:
                return {"success": True, "message": "Избранная пара обновлена"}
            else:
                raise HTTPException(status_code=404, detail="Избранная пара не найдена")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка обновления избранной пары: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")

    @router.delete("/{favorite_id}")
    async def remove_from_favorites(favorite_id: int = Path(..., description="ID избранной пары")):
        """Удаление пары из избранного"""
        try:
            success = await db_queries.remove_from_favorites(favorite_id=favorite_id)
            
            if success:
                return {"success": True, "message": "Пара удалена из избранного"}
            else:
                raise HTTPException(status_code=404, detail="Избранная пара не найдена")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка удаления из избранного: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка удаления: {str(e)}")

    @router.delete("/symbol/{symbol}")
    async def remove_symbol_from_favorites(symbol: str = Path(..., description="Символ для удаления")):
        """Удаление символа из избранного"""
        try:
            success = await db_queries.remove_from_favorites(symbol=symbol)
            
            if success:
                return {"success": True, "message": f"Символ {symbol} удален из избранного"}
            else:
                raise HTTPException(status_code=404, detail="Символ не найден в избранном")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка удаления символа из избранного: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка удаления символа: {str(e)}")

    return router