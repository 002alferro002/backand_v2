import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncio
import time
from datetime import datetime
import logging

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("⚠️ Watchdog не установлен. Автоматическое обновление настроек недоступно.")
    print("Установите: pip install watchdog")

# Базовый путь проекта
BASE_DIR = Path(__file__).parent

# Путь к .env файлу
ENV_FILE_PATH = BASE_DIR / '.env'

# Глобальные переменные для системы обновления настроек
_settings_cache = {}
_last_modified = 0
_settings_callbacks = []
_file_observer = None

# Настройки по умолчанию с описаниями и категориями
DEFAULT_SETTINGS = {
    # Настройки сервера
    'SERVER_HOST': {
        'value': '0.0.0.0',
        'type': 'string',
        'category': 'Сервер',
        'description': 'IP адрес для привязки сервера'
    },
    'SERVER_PORT': {
        'value': '8000',
        'type': 'integer',
        'category': 'Сервер',
        'description': 'Порт для HTTP сервера'
    },

    # Настройки базы данных
    'DATABASE_URL': {
        'value': 'postgresql://user:password@localhost:5432/cryptoscan',
        'type': 'string',
        'category': 'База данных',
        'description': 'URL подключения к PostgreSQL'
    },
    'DB_HOST': {
        'value': 'localhost',
        'type': 'string',
        'category': 'База данных',
        'description': 'Хост базы данных'
    },
    'DB_PORT': {
        'value': '5432',
        'type': 'integer',
        'category': 'База данных',
        'description': 'Порт базы данных'
    },
    'DB_NAME': {
        'value': 'cryptoscan',
        'type': 'string',
        'category': 'База данных',
        'description': 'Имя базы данных'
    },
    'DB_USER': {
        'value': 'user',
        'type': 'string',
        'category': 'База данных',
        'description': 'Пользователь базы данных'
    },
    'DB_PASSWORD': {
        'value': 'password',
        'type': 'string',
        'category': 'База данных',
        'description': 'Пароль базы данных'
    },

    # Настройки анализа объемов
    'ANALYSIS_HOURS': {
        'value': '1',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Количество часов для анализа исторических данных'
    },
    'OFFSET_MINUTES': {
        'value': '0',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Смещение в минутах от текущего времени'
    },
    'VOLUME_MULTIPLIER': {
        'value': '2.0',
        'type': 'float',
        'category': 'Анализ объемов',
        'description': 'Множитель превышения объема для алерта'
    },
    'MIN_VOLUME_USDT': {
        'value': '1000',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Минимальный объем в USDT для алерта'
    },
    'CONSECUTIVE_LONG_COUNT': {
        'value': '5',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Количество подряд идущих LONG свечей для алерта'
    },
    'ALERT_GROUPING_MINUTES': {
        'value': '5',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Интервал группировки алертов в минутах'
    },
    'DATA_RETENTION_HOURS': {
        'value': '2',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Время хранения данных в часах'
    },
    'UPDATE_INTERVAL_SECONDS': {
        'value': '1',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Интервал обновления данных в секундах'
    },
    'PAIRS_CHECK_INTERVAL_MINUTES': {
        'value': '30',
        'type': 'integer',
        'category': 'Анализ объемов',
        'description': 'Интервал проверки торговых пар в минутах'
    },

    # Настройки фильтра цен
    'PRICE_HISTORY_DAYS': {
        'value': '30',
        'type': 'integer',
        'category': 'Фильтр цен',
        'description': 'Количество дней для анализа исторических цен'
    },
    'PRICE_DROP_PERCENTAGE': {
        'value': '10.0',
        'type': 'float',
        'category': 'Фильтр цен',
        'description': 'Процент падения цены для добавления в watchlist'
    },
    'WATCHLIST_AUTO_UPDATE': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Фильтр цен',
        'description': 'Автоматическое обновление watchlist'
    },

    # Настройки Telegram
    'TELEGRAM_BOT_TOKEN': {
        'value': '',
        'type': 'string',
        'category': 'Telegram',
        'description': 'Токен Telegram бота для уведомлений'
    },
    'TELEGRAM_CHAT_ID': {
        'value': '',
        'type': 'string',
        'category': 'Telegram',
        'description': 'ID чата для отправки уведомлений'
    },

    # Настройки Bybit API
    'BYBIT_API_KEY': {
        'value': '',
        'type': 'string',
        'category': 'Bybit API',
        'description': 'API ключ для торговли на Bybit'
    },
    'BYBIT_API_SECRET': {
        'value': '',
        'type': 'string',
        'category': 'Bybit API',
        'description': 'Секретный ключ для торговли на Bybit'
    },

    # Настройки логирования
    'LOG_LEVEL': {
        'value': 'INFO',
        'type': 'select',
        'category': 'Логирование',
        'description': 'Уровень логирования',
        'options': ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    },
    'LOG_FILE': {
        'value': 'cryptoscan.log',
        'type': 'string',
        'category': 'Логирование',
        'description': 'Файл для записи логов'
    },

    # Настройки WebSocket
    'WS_PING_INTERVAL': {
        'value': '20',
        'type': 'integer',
        'category': 'WebSocket',
        'description': 'Интервал ping в секундах'
    },
    'WS_PING_TIMEOUT': {
        'value': '10',
        'type': 'integer',
        'category': 'WebSocket',
        'description': 'Таймаут ping в секундах'
    },
    'WS_CLOSE_TIMEOUT': {
        'value': '10',
        'type': 'integer',
        'category': 'WebSocket',
        'description': 'Таймаут закрытия соединения в секундах'
    },
    'WS_MAX_SIZE': {
        'value': '10000000',
        'type': 'integer',
        'category': 'WebSocket',
        'description': 'Максимальный размер сообщения в байтах'
    },

    # Настройки синхронизации времени
    'TIME_SYNC_INTERVAL': {
        'value': '300',
        'type': 'integer',
        'category': 'Синхронизация времени',
        'description': 'Интервал синхронизации с биржей в секундах'
    },
    'TIME_SERVER_SYNC_INTERVAL': {
        'value': '3600',
        'type': 'integer',
        'category': 'Синхронизация времени',
        'description': 'Интервал синхронизации с серверами времени в секундах'
    },

    # Настройки имбаланса
    'MIN_GAP_PERCENTAGE': {
        'value': '0.1',
        'type': 'float',
        'category': 'Имбаланс',
        'description': 'Минимальный процент гэпа для анализа'
    },
    'MIN_STRENGTH': {
        'value': '0.5',
        'type': 'float',
        'category': 'Имбаланс',
        'description': 'Минимальная сила сигнала имбаланса'
    },
    'FAIR_VALUE_GAP_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Имбаланс',
        'description': 'Включить анализ Fair Value Gap'
    },
    'ORDER_BLOCK_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Имбаланс',
        'description': 'Включить анализ Order Block'
    },
    'BREAKER_BLOCK_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Имбаланс',
        'description': 'Включить анализ Breaker Block'
    },

    # Настройки стакана
    'ORDERBOOK_ENABLED': {
        'value': 'False',
        'type': 'boolean',
        'category': 'Стакан',
        'description': 'Включить получение данных стакана'
    },
    'ORDERBOOK_SNAPSHOT_ON_ALERT': {
        'value': 'False',
        'type': 'boolean',
        'category': 'Стакан',
        'description': 'Делать снимок стакана при алерте'
    },

    # Настройки алертов
    'VOLUME_ALERTS_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Алерты',
        'description': 'Включить алерты по объему'
    },
    'CONSECUTIVE_ALERTS_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Алерты',
        'description': 'Включить алерты по подряд идущим свечам'
    },
    'PRIORITY_ALERTS_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Алерты',
        'description': 'Включить приоритетные алерты'
    },
    'IMBALANCE_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Алерты',
        'description': 'Включить анализ имбалансов в алертах'
    },
    'NOTIFICATION_ENABLED': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Алерты',
        'description': 'Включить уведомления'
    },
    'VOLUME_TYPE': {
        'value': 'long',
        'type': 'select',
        'category': 'Алерты',
        'description': 'Тип объема для анализа',
        'options': ['long', 'short', 'all']
    },

    # Настройки торговли
    'ACCOUNT_BALANCE': {
        'value': '10000',
        'type': 'float',
        'category': 'Торговля',
        'description': 'Баланс аккаунта для расчетов'
    },
    'MAX_RISK_PER_TRADE': {
        'value': '2.0',
        'type': 'float',
        'category': 'Торговля',
        'description': 'Максимальный риск на сделку в процентах'
    },
    'MAX_OPEN_TRADES': {
        'value': '5',
        'type': 'integer',
        'category': 'Торговля',
        'description': 'Максимальное количество открытых сделок'
    },
    'DEFAULT_STOP_LOSS_PERCENTAGE': {
        'value': '2.0',
        'type': 'float',
        'category': 'Торговля',
        'description': 'Стоп-лосс по умолчанию в процентах'
    },
    'DEFAULT_TAKE_PROFIT_PERCENTAGE': {
        'value': '6.0',
        'type': 'float',
        'category': 'Торговля',
        'description': 'Тейк-профит по умолчанию в процентах'
    },
    'AUTO_CALCULATE_QUANTITY': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Торговля',
        'description': 'Автоматический расчет размера позиции'
    },
    'ENABLE_REAL_TRADING': {
        'value': 'False',
        'type': 'boolean',
        'category': 'Торговля',
        'description': 'Включить реальную торговлю'
    },
    'DEFAULT_LEVERAGE': {
        'value': '1',
        'type': 'integer',
        'category': 'Торговля',
        'description': 'Кредитное плечо по умолчанию'
    },
    'DEFAULT_MARGIN_TYPE': {
        'value': 'isolated',
        'type': 'select',
        'category': 'Торговля',
        'description': 'Тип маржи по умолчанию',
        'options': ['isolated', 'cross']
    },
    'CONFIRM_TRADES': {
        'value': 'True',
        'type': 'boolean',
        'category': 'Торговля',
        'description': 'Подтверждение перед выполнением сделок'
    },

    # Настройки социальных сетей
    'SOCIAL_SENTIMENT_ENABLED': {
        'value': 'False',
        'type': 'boolean',
        'category': 'Социальные сети',
        'description': 'Включить анализ социальных настроений'
    },
    'SOCIAL_ANALYSIS_PERIOD_HOURS': {
        'value': '72',
        'type': 'integer',
        'category': 'Социальные сети',
        'description': 'Период анализа социальных данных в часах'
    },
    'SOCIAL_MIN_MENTIONS_FOR_RATING': {
        'value': '3',
        'type': 'integer',
        'category': 'Социальные сети',
        'description': 'Минимальное количество упоминаний для рейтинга'
    },
    'SOCIAL_CACHE_DURATION_MINUTES': {
        'value': '30',
        'type': 'integer',
        'category': 'Социальные сети',
        'description': 'Время кэширования социальных данных в минутах'
    },
}


class SettingsFileHandler(FileSystemEventHandler):
    """Обработчик изменений файла настроек"""

    def on_modified(self, event):
        if event.is_directory:
            return

        if event.src_path == str(ENV_FILE_PATH):
            asyncio.create_task(reload_settings())


def create_env_file():
    """Создание .env файла с настройками по умолчанию"""
    # Всегда создаем файл если его нет, независимо от других ошибок
    try:
        if ENV_FILE_PATH.exists():
            return

        # Создаем директорию если её нет
        ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("# Настройки CryptoScan\n")
            f.write("# Этот файл создан автоматически. Измените значения по необходимости.\n")
            f.write(f"# Создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Группируем настройки по категориям
            categories = {}
            for key, config in DEFAULT_SETTINGS.items():
                category = config['category']
                if category not in categories:
                    categories[category] = []
                categories[category].append(key)

            for category, keys in categories.items():
                f.write(f"# {category}\n")
                for key in keys:
                    config = DEFAULT_SETTINGS[key]
                    f.write(f"# {config['description']}\n")
                    f.write(f"{key}={config['value']}\n")
                f.write("\n")

        print(f"✅ Создан файл настроек: {ENV_FILE_PATH}")
        
    except Exception as e:
        print(f"❌ Ошибка создания файла настроек: {e}")
        # Не прерываем выполнение - система должна работать

def load_settings() -> Dict[str, Any]:
    """Загрузка настроек из .env файла или создание файла с настройками по умолчанию"""
    global _settings_cache, _last_modified

    # Проверяем, изменился ли файл
    try:
        current_modified = ENV_FILE_PATH.stat().st_mtime
        if current_modified == _last_modified and _settings_cache:
            return _settings_cache
        _last_modified = current_modified
    except FileNotFoundError:
        pass

    # Создаем .env файл если его нет
    if not ENV_FILE_PATH.exists():
        create_env_file()

    # Загружаем настройки из .env файла
    settings = {}

    try:
        with open(ENV_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    settings[key.strip()] = value.strip()
    except Exception as e:
        print(f"Ошибка чтения .env файла: {e}")
        # Возвращаем значения по умолчанию
        return {key: config['value'] for key, config in DEFAULT_SETTINGS.items()}

    # Дополняем недостающие настройки значениями по умолчанию
    for key, config in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = config['value']

    _settings_cache = settings
    return settings


async def reload_settings():
    """Асинхронная перезагрузка настроек"""
    try:
        # Небольшая задержка для завершения записи файла
        await asyncio.sleep(0.1)

        # Очищаем кэш
        global _settings_cache
        _settings_cache = {}

        # Загружаем новые настройки
        new_settings = load_settings()

        # Уведомляем все зарегистрированные компоненты
        for callback in _settings_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(new_settings)
                else:
                    callback(new_settings)
            except Exception as e:
                print(f"Ошибка обновления настроек в компоненте: {e}")

        print(f"✅ Настройки перезагружены из .env файла")

    except Exception as e:
        print(f"❌ Ошибка перезагрузки настроек: {e}")


def register_settings_callback(callback):
    """Регистрация callback для уведомления об изменении настроек"""
    _settings_callbacks.append(callback)


def unregister_settings_callback(callback):
    """Отмена регистрации callback"""
    if callback in _settings_callbacks:
        _settings_callbacks.remove(callback)


def start_settings_monitor():
    """Запуск мониторинга изменений файла настроек"""
    global _file_observer

    if not WATCHDOG_AVAILABLE:
        print("⚠️ Мониторинг настроек недоступен - watchdog не установлен")
        return

    try:
        if _file_observer is None:
            event_handler = SettingsFileHandler()
            _file_observer = Observer()
            _file_observer.schedule(event_handler, str(BASE_DIR), recursive=False)
            _file_observer.start()
            print("🔍 Мониторинг изменений .env файла запущен")
    except Exception as e:
        print(f"❌ Ошибка запуска мониторинга настроек: {e}")


def stop_settings_monitor():
    """Остановка мониторинга изменений файла настроек"""
    global _file_observer

    if not WATCHDOG_AVAILABLE:
        return

    if _file_observer:
        _file_observer.stop()
        _file_observer.join()
        _file_observer = None
        print("🛑 Мониторинг изменений .env файла остановлен")


def get_setting(key: str, default: Any = None) -> Any:
    """Получение значения настройки"""
    settings = load_settings()
    value = settings.get(key, default)

    # Преобразование строковых значений в нужные типы
    if isinstance(value, str):
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            return value

    return value


def get_settings_schema() -> Dict[str, Any]:
    """Получение схемы настроек с описаниями и типами"""
    return DEFAULT_SETTINGS


def get_settings_by_category() -> Dict[str, List[Dict]]:
    """Получение настроек, сгруппированных по категориям"""
    current_settings = load_settings()
    categories = {}
    
    for key, config in DEFAULT_SETTINGS.items():
        category = config['category']
        if category not in categories:
            categories[category] = []
        
        setting_info = {
            'key': key,
            'value': current_settings.get(key, config['value']),
            'default_value': config['value'],
            'type': config['type'],
            'description': config['description']
        }
        
        if 'options' in config:
            setting_info['options'] = config['options']
        
        categories[category].append(setting_info)
    
    return categories


def validate_setting_value(key: str, value: Any) -> tuple[bool, str, Any]:
    """Валидация значения настройки"""
    if key not in DEFAULT_SETTINGS:
        return False, f"Неизвестная настройка: {key}", None
    
    config = DEFAULT_SETTINGS[key]
    setting_type = config['type']
    
    try:
        if setting_type == 'boolean':
            if isinstance(value, bool):
                validated_value = value
            elif isinstance(value, str):
                validated_value = value.lower() in ('true', '1', 'yes', 'on')
            else:
                validated_value = bool(value)
        
        elif setting_type == 'integer':
            validated_value = int(float(value))
        
        elif setting_type == 'float':
            validated_value = float(value)
        
        elif setting_type == 'string':
            validated_value = str(value)
        
        elif setting_type == 'select':
            str_value = str(value)
            if 'options' in config and str_value not in config['options']:
                return False, f"Недопустимое значение для {key}. Допустимые: {config['options']}", None
            validated_value = str_value
        
        else:
            validated_value = str(value)
        
        return True, "", validated_value
    
    except (ValueError, TypeError) as e:
        return False, f"Ошибка преобразования значения для {key}: {e}", None


def update_setting(key: str, value: Any) -> bool:
    """Обновление настройки в .env файле"""
    global _settings_cache
    
    try:
        logger = logging.getLogger(__name__)
    except:
        logger = None

    # Валидируем значение
    is_valid, error_msg, validated_value = validate_setting_value(key, value)
    if not is_valid:
        if logger:
            logger.error(f"❌ {error_msg}")
        return False

    # Преобразуем значение в строку для записи в файл
    if isinstance(validated_value, bool):
        str_value = 'True' if validated_value else 'False'
    else:
        str_value = str(validated_value)

    settings = load_settings()
    settings[key] = str_value

    # Обновляем кэш
    _settings_cache[key] = str_value

    if logger:
        logger.info(f"⚙️ Настройка {key} обновлена на {str_value}")

    # Перезаписываем .env файл
    try:
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("# Настройки CryptoScan\n")
            f.write(f"# Обновлено автоматически: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Группируем по категориям для красивого вывода
            categories = {}
            for setting_key, setting_value in settings.items():
                if setting_key in DEFAULT_SETTINGS:
                    category = DEFAULT_SETTINGS[setting_key]['category']
                    if category not in categories:
                        categories[category] = []
                    categories[category].append((setting_key, setting_value))
                else:
                    # Неизвестные настройки добавляем в конец
                    if 'Прочее' not in categories:
                        categories['Прочее'] = []
                    categories['Прочее'].append((setting_key, setting_value))

            for category, items in categories.items():
                f.write(f"# {category}\n")
                for setting_key, setting_value in items:
                    if setting_key in DEFAULT_SETTINGS:
                        f.write(f"# {DEFAULT_SETTINGS[setting_key]['description']}\n")
                    f.write(f"{setting_key}={setting_value}\n")
                f.write("\n")

        # Принудительно очищаем кэш для следующего чтения
        global _last_modified
        _last_modified = 0
        _settings_cache = {}

        # Уведомляем о необходимости перезагрузки настроек
        asyncio.create_task(reload_settings())
        
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"❌ Ошибка записи настройки в файл: {e}")
        return False


def update_multiple_settings(settings_dict: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Обновление нескольких настроек одновременно"""
    global _settings_cache
    
    try:
        logger = logging.getLogger(__name__)
    except:
        logger = None
    
    # Валидируем все настройки перед записью
    validated_settings = {}
    errors = []
    
    for key, value in settings_dict.items():
        is_valid, error_msg, validated_value = validate_setting_value(key, value)
        if is_valid:
            if isinstance(validated_value, bool):
                str_value = 'True' if validated_value else 'False'
            else:
                str_value = str(validated_value)
            validated_settings[key] = str_value
        else:
            errors.append(error_msg)
    
    if errors:
        return False, errors
    
    # Загружаем текущие настройки
    current_settings = load_settings()
    
    # Обновляем настройки
    for key, str_value in validated_settings.items():
        current_settings[key] = str_value
        _settings_cache[key] = str_value

        if logger:
            logger.info(f"⚙️ Настройка {key} обновлена на {str_value}")
    
    # Перезаписываем .env файл одним разом
    try:
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("# Настройки CryptoScan\n")
            f.write(f"# Обновлено автоматически: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Группируем по категориям
            categories = {}
            for setting_key, setting_value in current_settings.items():
                if setting_key in DEFAULT_SETTINGS:
                    category = DEFAULT_SETTINGS[setting_key]['category']
                    if category not in categories:
                        categories[category] = []
                    categories[category].append((setting_key, setting_value))
                else:
                    if 'Прочее' not in categories:
                        categories['Прочее'] = []
                    categories['Прочее'].append((setting_key, setting_value))

            for category, items in categories.items():
                f.write(f"# {category}\n")
                for setting_key, setting_value in items:
                    if setting_key in DEFAULT_SETTINGS:
                        f.write(f"# {DEFAULT_SETTINGS[setting_key]['description']}\n")
                    f.write(f"{setting_key}={setting_value}\n")
                f.write("\n")
        
        # Принудительно очищаем кэш
        global _last_modified
        _last_modified = 0
        _settings_cache = {}
        
        # Уведомляем о необходимости перезагрузки настроек
        asyncio.create_task(reload_settings())
        
        return True, []
        
    except Exception as e:
        error_msg = f"Ошибка записи настроек в файл: {e}"
        if logger:
            logger.error(f"❌ {error_msg}")
        return False, [error_msg]


def reset_settings_to_default() -> bool:
    """Сброс всех настроек к значениям по умолчанию"""
    try:
        # Удаляем существующий файл
        if ENV_FILE_PATH.exists():
            ENV_FILE_PATH.unlink()
        
        # Очищаем кэш
        global _settings_cache, _last_modified
        _settings_cache = {}
        _last_modified = 0
        
        # Создаем новый файл с настройками по умолчанию
        create_env_file()
        
        # Уведомляем о перезагрузке
        asyncio.create_task(reload_settings())
        
        return True
        
    except Exception as e:
        try:
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Ошибка сброса настроек: {e}")
        except:
            print(f"❌ Ошибка сброса настроек: {e}")
        return False


def export_settings() -> Dict[str, Any]:
    """Экспорт текущих настроек"""
    return load_settings()


def import_settings(settings_dict: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Импорт настроек из словаря"""
    return update_multiple_settings(settings_dict)


# Инициализация настроек при импорте модуля
SETTINGS = load_settings()