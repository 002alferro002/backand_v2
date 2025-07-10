from cryptoscan.backand.core.core_logger import get_logger
from cryptoscan.backand.core.core_exceptions import DatabaseException
from cryptoscan.backand.database.database_connection import DatabaseConnection
from cryptoscan.backand.database.database_tables import DatabaseTables
from cryptoscan.backand.database.database_queries import DatabaseQueries

logger = get_logger(__name__)


class DatabaseManager:
    """Главный менеджер базы данных"""
    
    def __init__(self):
        self.db_connection = None
        self.db_tables = None
        self.db_queries = None
        self._is_initialized = False
    
    async def initialize(self):
        """Инициализация всех компонентов базы данных"""
        if self._is_initialized:
            return
        
        try:
            # Инициализация подключения
            self.db_connection = DatabaseConnection()
            await self.db_connection.initialize()
            
            # Инициализация таблиц
            self.db_tables = DatabaseTables(self.db_connection)
            
            # Инициализация запросов
            self.db_queries = DatabaseQueries(self.db_connection)
            
            # Создание таблиц
            await self.db_tables.create_all_tables()
            
            self._is_initialized = True
            logger.info("✅ DatabaseManager инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации DatabaseManager: {e}")
            raise DatabaseException(f"Ошибка инициализации базы данных: {e}")
    
    async def close(self):
        """Закрытие всех подключений"""
        if self.db_connection:
            self.db_connection.close()
        self._is_initialized = False
        logger.info("🔌 DatabaseManager закрыт")
    
    def is_initialized(self) -> bool:
        """Проверка инициализации"""
        return self._is_initialized
    
    async def get_watchlist(self):
        """Получение watchlist"""
        if not self._is_initialized:
            raise DatabaseException("DatabaseManager не инициализирован")
        return await self.db_queries.get_watchlist()
    
    async def add_to_watchlist(self, symbol: str, price_drop: float = 0, 
                              current_price: float = 0, historical_price: float = 0):
        """Добавление в watchlist"""
        if not self._is_initialized:
            raise DatabaseException("DatabaseManager не инициализирован")
        return await self.db_queries.add_to_watchlist(symbol, price_drop, current_price, historical_price)
    
    async def remove_from_watchlist(self, symbol: str = None, item_id: int = None):
        """Удаление из watchlist"""
        if not self._is_initialized:
            raise DatabaseException("DatabaseManager не инициализирован")
        return await self.db_queries.remove_from_watchlist(symbol, item_id)