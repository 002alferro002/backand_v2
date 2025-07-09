from fastapi import APIRouter, HTTPException
from typing import Dict, List
from pydantic import BaseModel
from cryptoscan.backand.core.core_logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/trading", tags=["trading"])


class TradingSettings(BaseModel):
    account_balance: float
    max_risk_per_trade: float
    max_open_trades: int
    default_stop_loss_percentage: float
    default_take_profit_percentage: float
    auto_calculate_quantity: bool


class TradingSettingsUpdate(BaseModel):
    account_balance: float = None
    max_risk_per_trade: float = None
    max_open_trades: int = None
    default_stop_loss_percentage: float = None
    default_take_profit_percentage: float = None
    auto_calculate_quantity: bool = None


class PaperTradeRequest(BaseModel):
    symbol: str
    direction: str  # 'long' or 'short'
    entry_price: float
    stop_loss: float = None
    take_profit: float = None
    quantity: float = None
    risk_amount: float = None
    risk_percentage: float = None
    notes: str = ""
    alert_id: int = None


class PaperTradeResponse(BaseModel):
    id: int
    symbol: str
    trade_type: str
    entry_price: float
    exit_price: float = None
    quantity: float
    stop_loss: float = None
    take_profit: float = None
    risk_amount: float = None
    risk_percentage: float = None
    potential_profit: float = None
    potential_loss: float = None
    actual_profit: float = None
    risk_reward_ratio: float = None
    status: str
    exit_reason: str = None
    notes: str
    alert_id: int = None
    entry_time: str
    exit_time: str = None


def setup_trading_routes(db_queries):
    """Настройка маршрутов для торговли"""
    
    @router.get("/settings", response_model=TradingSettings)
    async def get_trading_settings():
        """Получение торговых настроек"""
        try:
            settings = await db_queries.get_trading_settings()
            return TradingSettings(**settings)
            
        except Exception as e:
            logger.error(f"Ошибка получения торговых настроек: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения настроек: {str(e)}")

    @router.put("/settings")
    async def update_trading_settings(settings: TradingSettingsUpdate):
        """Обновление торговых настроек"""
        try:
            # Фильтруем только заданные поля
            update_data = {k: v for k, v in settings.dict().items() if v is not None}
            
            success = await db_queries.update_trading_settings(update_data)
            
            if success:
                return {"success": True, "message": "Торговые настройки обновлены"}
            else:
                raise HTTPException(status_code=500, detail="Не удалось обновить настройки")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка обновления торговых настроек: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка обновления настроек: {str(e)}")

    @router.get("/paper-trades", response_model=List[PaperTradeResponse])
    async def get_paper_trades(limit: int = 100):
        """Получение бумажных сделок"""
        try:
            trades = await db_queries.get_paper_trades(limit)
            return [PaperTradeResponse(**trade) for trade in trades]
            
        except Exception as e:
            logger.error(f"Ошибка получения бумажных сделок: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения сделок: {str(e)}")

    @router.post("/paper-trades")
    async def create_paper_trade(trade: PaperTradeRequest):
        """Создание бумажной сделки"""
        try:
            # Рассчитываем дополнительные параметры
            trade_data = trade.dict()
            
            # Если не указано количество, рассчитываем на основе риска
            if not trade_data.get('quantity') and trade_data.get('risk_amount') and trade_data.get('stop_loss'):
                risk_per_unit = abs(trade_data['entry_price'] - trade_data['stop_loss'])
                if risk_per_unit > 0:
                    trade_data['quantity'] = trade_data['risk_amount'] / risk_per_unit
            
            # Рассчитываем потенциальную прибыль/убыток
            if trade_data.get('quantity'):
                if trade_data.get('stop_loss'):
                    trade_data['potential_loss'] = abs(trade_data['entry_price'] - trade_data['stop_loss']) * trade_data['quantity']
                
                if trade_data.get('take_profit'):
                    trade_data['potential_profit'] = abs(trade_data['take_profit'] - trade_data['entry_price']) * trade_data['quantity']
                
                # Рассчитываем риск/прибыль
                if trade_data.get('potential_loss') and trade_data.get('potential_profit'):
                    trade_data['risk_reward_ratio'] = trade_data['potential_profit'] / trade_data['potential_loss']
            
            trade_data['status'] = 'planned'
            
            trade_id = await db_queries.save_paper_trade(trade_data)
            
            if trade_id:
                return {"success": True, "id": trade_id, "message": "Бумажная сделка создана"}
            else:
                raise HTTPException(status_code=500, detail="Не удалось создать сделку")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка создания бумажной сделки: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка создания сделки: {str(e)}")

    return router