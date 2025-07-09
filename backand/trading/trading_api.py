import logging
import time
import hmac
import hashlib
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from cryptoscan.backand.core.core_logger import get_logger
from cryptoscan.backand.core.core_exceptions import TradingException
from cryptoscan.backand.settings import get_setting

logger = get_logger(__name__)


class BybitTradingAPI:
    """Класс для работы с API Bybit для реальной торговли"""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or get_setting('BYBIT_API_KEY', '')
        self.api_secret = api_secret or get_setting('BYBIT_API_SECRET', '')
        self.base_url = "https://api.bybit.com"
        self.recv_window = 5000  # Окно приема запроса в миллисекундах
        
        self.is_configured = bool(self.api_key and self.api_secret)
        
        if not self.is_configured:
            logger.warning("API ключи Bybit не настроены. Реальная торговля недоступна.")
    
    def _generate_signature(self, params: Dict) -> str:
        """Генерация подписи для запроса"""
        param_str = ''
        
        # Текущее время в миллисекундах
        timestamp = int(time.time() * 1000)
        
        # Добавляем обязательные параметры
        params['api_key'] = self.api_key
        params['timestamp'] = timestamp
        params['recv_window'] = self.recv_window
        
        # Сортируем параметры по ключу
        sorted_params = dict(sorted(params.items()))
        
        # Формируем строку параметров
        for key, value in sorted_params.items():
            param_str += f"{key}={value}&"
        
        param_str = param_str[:-1]  # Удаляем последний &
        
        # Создаем подпись
        signature = hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(param_str, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Выполнение запроса к API"""
        if not self.is_configured:
            raise TradingException("API ключи не настроены")
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-TIMESTAMP': str(int(time.time() * 1000)),
            'X-BAPI-RECV-WINDOW': str(self.recv_window)
        }
        
        try:
            # Для GET запросов параметры идут в URL
            if method == 'GET':
                if not params:
                    params = {}
                signature = self._generate_signature(params)
                headers['X-BAPI-SIGN'] = signature
                response = requests.get(url, headers=headers, params=params, timeout=30)
            
            # Для POST запросов параметры идут в теле
            elif method == 'POST':
                if not data:
                    data = {}
                signature = self._generate_signature(data)
                headers['X-BAPI-SIGN'] = signature
                response = requests.post(url, headers=headers, json=data, timeout=30)
            
            # Для DELETE запросов
            elif method == 'DELETE':
                if not params:
                    params = {}
                signature = self._generate_signature(params)
                headers['X-BAPI-SIGN'] = signature
                response = requests.delete(url, headers=headers, params=params, timeout=30)
            
            else:
                raise TradingException(f"Неподдерживаемый метод: {method}")
            
            # Проверяем ответ
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API ошибка: {response.status_code} - {response.text}")
                raise TradingException(f"API ошибка: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сетевого запроса: {e}")
            raise TradingException(f"Ошибка сетевого запроса: {e}")
    
    def get_account_info(self) -> Dict:
        """Получение информации об аккаунте"""
        try:
            endpoint = "/v5/account/wallet-balance"
            params = {
                "accountType": "UNIFIED"
            }
            
            response = self._make_request('GET', endpoint, params)
            
            if response.get('retCode') == 0 and response.get('result'):
                account_data = response['result']['list'][0]
                
                # Извлекаем нужные данные
                total_equity = float(account_data.get('totalEquity', 0))
                available_balance = float(account_data.get('availableBalance', 0))
                used_margin = float(account_data.get('totalMarginUsed', 0))
                unrealized_pnl = float(account_data.get('totalPnl', 0))
                
                # Получаем информацию о позициях
                positions = self.get_positions()
                open_positions_count = len(positions.get('positions', []))
                
                return {
                    "balance": total_equity,
                    "available_balance": available_balance,
                    "used_margin": used_margin,
                    "unrealized_pnl": unrealized_pnl,
                    "open_positions": open_positions_count
                }
            else:
                error_msg = response.get('retMsg', 'Неизвестная ошибка')
                logger.error(f"Ошибка получения информации об аккаунте: {error_msg}")
                raise TradingException(error_msg)
                
        except Exception as e:
            logger.error(f"Ошибка получения информации об аккаунте: {e}")
            raise TradingException(f"Ошибка получения информации об аккаунте: {e}")
    
    def get_positions(self, symbol: str = None) -> Dict:
        """Получение открытых позиций"""
        try:
            endpoint = "/v5/position/list"
            params = {
                "category": "linear"
            }
            
            if symbol:
                params["symbol"] = symbol
            
            response = self._make_request('GET', endpoint, params)
            
            if response.get('retCode') == 0:
                positions_data = response['result']['list']
                
                # Фильтруем только открытые позиции
                open_positions = []
                for position in positions_data:
                    size = float(position.get('size', 0))
                    if size > 0:
                        open_positions.append({
                            "symbol": position.get('symbol'),
                            "side": position.get('side'),
                            "size": size,
                            "entry_price": float(position.get('avgPrice', 0)),
                            "position_value": float(position.get('positionValue', 0)),
                            "leverage": float(position.get('leverage', 1)),
                            "unrealized_pnl": float(position.get('unrealisedPnl', 0)),
                            "stop_loss": float(position.get('stopLoss', 0)) if position.get('stopLoss') else None,
                            "take_profit": float(position.get('takeProfit', 0)) if position.get('takeProfit') else None,
                            "created_time": position.get('createdTime'),
                            "updated_time": position.get('updatedTime')
                        })
                
                return {"positions": open_positions}
            else:
                error_msg = response.get('retMsg', 'Неизвестная ошибка')
                logger.error(f"Ошибка получения позиций: {error_msg}")
                raise TradingException(error_msg)
                
        except Exception as e:
            logger.error(f"Ошибка получения позиций: {e}")
            raise TradingException(f"Ошибка получения позиций: {e}")
    
    def place_order(self, symbol: str, side: str, order_type: str, qty: float, 
                   price: Optional[float] = None, stop_loss: Optional[float] = None, 
                   take_profit: Optional[float] = None, leverage: int = 1, 
                   margin_type: str = "isolated") -> Dict:
        """Размещение ордера"""
        try:
            # Устанавливаем кредитное плечо и тип маржи
            self.set_leverage(symbol, leverage, margin_type)
            
            endpoint = "/v5/order/create"
            data = {
                "category": "linear",
                "symbol": symbol,
                "side": side,  # Buy или Sell
                "orderType": order_type,  # Limit или Market
                "qty": str(qty)
            }
            
            # Для лимитных ордеров нужна цена
            if order_type.lower() == "limit" and price:
                data["price"] = str(price)
            
            # Добавляем стоп-лосс и тейк-профит, если указаны
            if stop_loss:
                data["stopLoss"] = str(stop_loss)
            
            if take_profit:
                data["takeProfit"] = str(take_profit)
            
            # Добавляем дополнительные параметры
            data["timeInForce"] = "GTC"  # Good Till Cancel
            data["positionIdx"] = 0  # One-Way Mode
            
            response = self._make_request('POST', endpoint, data=data)
            
            if response.get('retCode') == 0:
                order_data = response['result']
                return {
                    "order_id": order_data.get('orderId'),
                    "symbol": order_data.get('symbol'),
                    "side": order_data.get('side'),
                    "order_type": order_data.get('orderType'),
                    "price": order_data.get('price'),
                    "qty": order_data.get('qty'),
                    "status": order_data.get('orderStatus'),
                    "created_time": order_data.get('createdTime')
                }
            else:
                error_msg = response.get('retMsg', 'Неизвестная ошибка')
                logger.error(f"Ошибка размещения ордера: {error_msg}")
                raise TradingException(error_msg)
                
        except Exception as e:
            logger.error(f"Ошибка размещения ордера: {e}")
            raise TradingException(f"Ошибка размещения ордера: {e}")
    
    def set_leverage(self, symbol: str, leverage: int, margin_type: str = "isolated") -> Dict:
        """Установка кредитного плеча и типа маржи"""
        try:
            endpoint = "/v5/position/set-leverage"
            data = {
                "category": "linear",
                "symbol": symbol,
                "buyLeverage": str(leverage),
                "sellLeverage": str(leverage)
            }
            
            response = self._make_request('POST', endpoint, data=data)
            
            # Устанавливаем тип маржи
            margin_endpoint = "/v5/position/switch-isolated"
            margin_data = {
                "category": "linear",
                "symbol": symbol,
                "tradeMode": 1 if margin_type.lower() == "isolated" else 0,
                "buyLeverage": str(leverage),
                "sellLeverage": str(leverage)
            }
            
            margin_response = self._make_request('POST', margin_endpoint, data=margin_data)
            
            if response.get('retCode') == 0 and margin_response.get('retCode') == 0:
                return {"success": True, "leverage": leverage, "margin_type": margin_type}
            else:
                error_msg = response.get('retMsg', '') or margin_response.get('retMsg', 'Неизвестная ошибка')
                logger.error(f"Ошибка установки плеча или типа маржи: {error_msg}")
                raise TradingException(error_msg)
                
        except Exception as e:
            logger.error(f"Ошибка установки плеча или типа маржи: {e}")
            raise TradingException(f"Ошибка установки плеча или типа маржи: {e}")
    
    def close_position(self, symbol: str, side: str) -> Dict:
        """Закрытие позиции"""
        try:
            # Получаем текущую позицию
            position = self.get_positions(symbol)
            
            positions = position.get('positions', [])
            if not positions:
                raise TradingException(f"Нет открытой позиции для {symbol}")
            
            # Находим позицию для закрытия
            position_to_close = None
            for pos in positions:
                if pos['symbol'] == symbol:
                    position_to_close = pos
                    break
            
            if not position_to_close:
                raise TradingException(f"Нет открытой позиции для {symbol}")
            
            # Определяем сторону для закрытия (противоположную текущей позиции)
            close_side = "Sell" if position_to_close['side'] == "Buy" else "Buy"
            
            # Размещаем рыночный ордер для закрытия позиции
            return self.place_order(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=position_to_close['size']
            )
            
        except Exception as e:
            logger.error(f"Ошибка закрытия позиции: {e}")
            raise TradingException(f"Ошибка закрытия позиции: {e}")
    
    def test_connection(self) -> Dict:
        """Проверка подключения к API"""
        try:
            account_info = self.get_account_info()
            
            return {
                "success": True,
                "balance": account_info["balance"],
                "available_balance": account_info["available_balance"]
            }
        except Exception as e:
            logger.error(f"Ошибка проверки подключения к API: {e}")
            return {"success": False, "error": str(e)}