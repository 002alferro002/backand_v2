import os
import threading
import asyncio
from pathlib import Path
from typing import Dict, Any, Callable, List
from datetime import datetime

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
_reload_lock = threading.Lock()

# Настройки по умолчанию
DEFAULT_SETTINGS = {
    # Настройки сервера
    'SERVER_HOST': '0.0.0.0',
    'SERVER_PORT': '8000',

    # Настройки базы данных
    'DATABASE_URL': 'postgresql://user:password@localhost:5432/cryptoscan',
    'DB_HOST': 'localhost',
    'DB_PORT': '5432',
    'DB_NAME': 'cryptoscan',
    'DB_USER': 'user',
    'DB_PASSWORD': 'password',

    # Настройки анализа объемов
    'ANALYSIS_HOURS': '1',
    'OFFSET_MINUTES': '0',
    'VOLUME_MULTIPLIER': '2.0',
    'MIN_VOLUME_USDT': '1000',
    'CONSECUTIVE_LONG_COUNT': '5',
    'ALERT_GROUPING_MINUTES': '5',
    'DATA_RETENTION_HOURS': '2',
    'UPDATE_INTERVAL_SECONDS': '1',
    'PAIRS_CHECK_INTERVAL_MINUTES': '30',
    'PRICE_CHECK_INTERVAL_MINUTES': '5',

    # Настройки фильтра цен
    'PRICE_HISTORY_DAYS': '30',
    'PRICE_DROP_PERCENTAGE': '10.0',
    'WATCHLIST_AUTO_UPDATE': 'True',

    # Настройки Telegram
    'TELEGRAM_BOT_TOKEN': '',
    'TELEGRAM_CHAT_ID': '',

    # Настройки Bybit API
    'BYBIT_API_KEY': '',
    'BYBIT_API_SECRET': '',

    # Настройки логирования
    'LOG_LEVEL': 'INFO',
    'LOG_FILE': 'cryptoscan.log',

    # Настройки WebSocket
    'WS_PING_INTERVAL': '20',
    'WS_PING_TIMEOUT': '10',
    'WS_CLOSE_TIMEOUT': '10',
    'WS_MAX_SIZE': '10000000',

    # Настройки синхронизации времени
    'TIME_SYNC_INTERVAL': '300',
    'TIME_SERVER_SYNC_INTERVAL': '3600',

    # Настройки имбаланса
    'MIN_GAP_PERCENTAGE': '0.1',
    'MIN_STRENGTH': '0.5',
    'FAIR_VALUE_GAP_ENABLED': 'True',
    'ORDER_BLOCK_ENABLED': 'True',
    'BREAKER_BLOCK_ENABLED': 'True',

    # Настройки стакана
    'ORDERBOOK_ENABLED': 'False',
    'ORDERBOOK_SNAPSHOT_ON_ALERT': 'False',

    # Настройки алертов
    'VOLUME_ALERTS_ENABLED': 'True',
    'CONSECUTIVE_ALERTS_ENABLED': 'True',
    'PRIORITY_ALERTS_ENABLED': 'True',
    'IMBALANCE_ENABLED': 'True',
    'NOTIFICATION_ENABLED': 'True',
    'VOLUME_TYPE': 'long',

    # Настройки социальных сетей
    'SOCIAL_SENTIMENT_ENABLED': 'False',
    'SOCIAL_ANALYSIS_PERIOD_HOURS': '72',
    'SOCIAL_MIN_MENTIONS_FOR_RATING': '3',
    'SOCIAL_CACHE_DURATION_MINUTES': '30',
}

# Схема настроек с описаниями и типами
SETTINGS_SCHEMA = {
    'server': {
        'title': 'Настройки сервера',
        'description': 'Конфигурация веб-сервера',
        'settings': {
            'SERVER_HOST': {
                'type': 'string',
                'default': '0.0.0.0',
                'description': 'IP адрес для привязки сервера',
                'validation': 'ip_address'
            },
            'SERVER_PORT': {
                'type': 'integer',
                'default': 8000,
                'description': 'Порт для веб-сервера',
                'validation': 'port_range'
            }
        }
    },
    'database': {
        'title': 'База данных',
        'description': 'Настройки подключения к PostgreSQL',
        'settings': {
            'DATABASE_URL': {
                'type': 'string',
                'default': 'postgresql://user:password@localhost:5432/cryptoscan',
                'description': 'URL подключения к базе данных',
                'validation': 'database_url'
            },
            'DB_HOST': {
                'type': 'string',
                'default': 'localhost',
                'description': 'Хост базы данных'
            },
            'DB_PORT': {
                'type': 'integer',
                'default': 5432,
                'description': 'Порт базы данных'
            },
            'DB_NAME': {
                'type': 'string',
                'default': 'cryptoscan',
                'description': 'Имя базы данных'
            },
            'DB_USER': {
                'type': 'string',
                'default': 'user',
                'description': 'Пользователь базы данных'
            },
            'DB_PASSWORD': {
                'type': 'password',
                'default': 'password',
                'description': 'Пароль базы данных'
            }
        }
    },
    'volume_analysis': {
        'title': 'Анализ объемов',
        'description': 'Настройки анализа торговых объемов',
        'settings': {
            'ANALYSIS_HOURS': {
                'type': 'integer',
                'default': 1,
                'description': 'Период анализа в часах',
                'min': 1,
                'max': 24
            },
            'OFFSET_MINUTES': {
                'type': 'integer',
                'default': 0,
                'description': 'Смещение в минутах от текущего времени',
                'min': 0,
                'max': 60
            },
            'VOLUME_MULTIPLIER': {
                'type': 'float',
                'default': 2.0,
                'description': 'Множитель превышения объема',
                'min': 1.1,
                'max': 10.0
            },
            'MIN_VOLUME_USDT': {
                'type': 'integer',
                'default': 1000,
                'description': 'Минимальный объем в USDT',
                'min': 100,
                'max': 100000
            },
            'CONSECUTIVE_LONG_COUNT': {
                'type': 'integer',
                'default': 5,
                'description': 'Количество подряд идущих LONG свечей',
                'min': 3,
                'max': 20
            }
        }
    },
    'alerts': {
        'title': 'Алерты',
        'description': 'Настройки системы уведомлений',
        'settings': {
            'VOLUME_ALERTS_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Включить алерты по объему'
            },
            'CONSECUTIVE_ALERTS_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Включить алерты по последовательности'
            },
            'PRIORITY_ALERTS_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Включить приоритетные алерты'
            },
            'ALERT_GROUPING_MINUTES': {
                'type': 'integer',
                'default': 5,
                'description': 'Группировка алертов в минутах',
                'min': 1,
                'max': 60
            },
            'NOTIFICATION_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Включить уведомления'
            }
        }
    },
    'telegram': {
        'title': 'Telegram',
        'description': 'Настройки Telegram бота',
        'settings': {
            'TELEGRAM_BOT_TOKEN': {
                'type': 'password',
                'default': '',
                'description': 'Токен Telegram бота'
            },
            'TELEGRAM_CHAT_ID': {
                'type': 'string',
                'default': '',
                'description': 'ID чата для уведомлений'
            }
        }
    },
    'bybit': {
        'title': 'Bybit API',
        'description': 'Настройки API биржи Bybit',
        'settings': {
            'BYBIT_API_KEY': {
                'type': 'password',
                'default': '',
                'description': 'API ключ Bybit'
            },
            'BYBIT_API_SECRET': {
                'type': 'password',
                'default': '',
                'description': 'Секретный ключ Bybit'
            }
        }
    },
    'imbalance': {
        'title': 'Анализ имбалансов',
        'description': 'Настройки Smart Money анализа',
        'settings': {
            'IMBALANCE_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Включить анализ имбалансов'
            },
            'FAIR_VALUE_GAP_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Анализ Fair Value Gap'
            },
            'ORDER_BLOCK_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Анализ Order Block'
            },
            'BREAKER_BLOCK_ENABLED': {
                'type': 'boolean',
                'default': True,
                'description': 'Анализ Breaker Block'
            },
            'MIN_GAP_PERCENTAGE': {
                'type': 'float',
                'default': 0.1,
                'description': 'Минимальный процент гэпа',
                'min': 0.01,
                'max': 5.0
            },
            'MIN_STRENGTH': {
                'type': 'float',
                'default': 0.5,
                'description': 'Минимальная сила сигнала',
                'min': 0.1,
                'max': 10.0
            }
        }
    },
    'watchlist': {
        'title': 'Watchlist',
        'description': 'Настройки списка отслеживания',
        'settings': {
            'WATCHLIST_AUTO_UPDATE': {
                'type': 'boolean',
                'default': True,
                'description': 'Автоматическое обновление watchlist'
            },
            'PRICE_HISTORY_DAYS': {
                'type': 'integer',
                'default': 30,
                'description': 'Период истории цен в днях',
                'min': 1,
                'max': 365
            },
            'PRICE_DROP_PERCENTAGE': {
                'type': 'float',
                'default': 10.0,
                'description': 'Процент падения цены для добавления в watchlist',
                'min': 1.0,
                'max': 90.0
            },
            'PAIRS_CHECK_INTERVAL_MINUTES': {
                'type': 'integer',
                'default': 30,
                'description': 'Интервал проверки пар в минутах',
                'min': 5,
                'max': 1440
            }
        }
    }
}


def _safe_reload_in_thread():
    """Безопасная перезагрузка настроек в отдельном потоке"""
    def reload_thread():
        try:
            with _reload_lock:
                # Очищаем кэш
                global _settings_cache
                _settings_cache = {}
                
                # Загружаем новые настройки
                new_settings = load_settings()
                
                # Уведомляем все зарегистрированные компоненты
                for callback in _settings_callbacks:
                    try:
                        # Проверяем, есть ли активный event loop
                        try:
                            loop = asyncio.get_running_loop()
                            if loop and not loop.is_closed():
                                # Если есть активный loop, планируем выполнение
                                asyncio.run_coroutine_threadsafe(callback(new_settings), loop)
                            else:
                                # Если нет активного loop, пропускаем асинхронный callback
                                print(f"⚠️ Пропущен callback - нет активного event loop")
                        except RuntimeError:
                            # Нет активного event loop - пропускаем асинхронные callbacks
                            if not asyncio.iscoroutinefunction(callback):
                                callback(new_settings)
                            else:
                                print(f"⚠️ Пропущен асинхронный callback - нет активного event loop")
                                
                    except Exception as e:
                        print(f"❌ Ошибка обновления настроек в компоненте: {e}")
                
                print(f"✅ Настройки перезагружены из .env файла")
                
        except Exception as e:
            print(f"❌ Ошибка перезагрузки настроек: {e}")
    
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=reload_thread, daemon=True)
    thread.start()


class SettingsFileHandler(FileSystemEventHandler):
    """Обработчик изменений файла настроек"""

    def on_modified(self, event):
        if event.is_directory:
            return

        if event.src_path == str(ENV_FILE_PATH):
            # Используем безопасную перезагрузку в отдельном потоке
            _safe_reload_in_thread()


def create_env_file():
    """Создание .env файла с настройками по умолчанию"""
    if ENV_FILE_PATH.exists():
        return

    try:
        # Создаем директорию если её нет
        ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("# Настройки CryptoScan\n")
            f.write("# Этот файл создан автоматически. Измените значения по необходимости.\n\n")

            # Группируем настройки по категориям
            categories = {
                'Сервер': ['SERVER_HOST', 'SERVER_PORT'],
                'База данных': ['DATABASE_URL', 'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD'],
                'Анализ объемов': ['ANALYSIS_HOURS', 'OFFSET_MINUTES', 'VOLUME_MULTIPLIER', 'MIN_VOLUME_USDT',
                                   'CONSECUTIVE_LONG_COUNT', 'ALERT_GROUPING_MINUTES', 'DATA_RETENTION_HOURS',
                                   'UPDATE_INTERVAL_SECONDS', 'PAIRS_CHECK_INTERVAL_MINUTES'],
                'Фильтр цен': ['PRICE_CHECK_INTERVAL_MINUTES', 'PRICE_HISTORY_DAYS', 'PRICE_DROP_PERCENTAGE'],
                'Watchlist': ['WATCHLIST_AUTO_UPDATE'],
                'Telegram': ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'],
                'Bybit API': ['BYBIT_API_KEY', 'BYBIT_API_SECRET'],
                'Логирование': ['LOG_LEVEL', 'LOG_FILE'],
                'WebSocket': ['WS_PING_INTERVAL', 'WS_PING_TIMEOUT', 'WS_CLOSE_TIMEOUT', 'WS_MAX_SIZE'],
                'Синхронизация времени': ['TIME_SYNC_INTERVAL', 'TIME_SERVER_SYNC_INTERVAL'],
                'Имбаланс': ['MIN_GAP_PERCENTAGE', 'MIN_STRENGTH', 'FAIR_VALUE_GAP_ENABLED',
                             'ORDER_BLOCK_ENABLED', 'BREAKER_BLOCK_ENABLED'],
                'Стакан': ['ORDERBOOK_ENABLED', 'ORDERBOOK_SNAPSHOT_ON_ALERT'],
                'Алерты': ['VOLUME_ALERTS_ENABLED', 'CONSECUTIVE_ALERTS_ENABLED', 'PRIORITY_ALERTS_ENABLED',
                           'IMBALANCE_ENABLED', 'NOTIFICATION_ENABLED', 'VOLUME_TYPE'],
                'Социальные сети': ['SOCIAL_SENTIMENT_ENABLED', 'SOCIAL_ANALYSIS_PERIOD_HOURS',
                                    'SOCIAL_MIN_MENTIONS_FOR_RATING', 'SOCIAL_CACHE_DURATION_MINUTES']
            }

            for category, keys in categories.items():
                f.write(f"# {category}\n")
                for key in keys:
                    if key in DEFAULT_SETTINGS:
                        f.write(f"{key}={DEFAULT_SETTINGS[key]}\n")
                f.write("\n")
        
        print(f"✅ Создан файл настроек: {ENV_FILE_PATH}")
        
    except Exception as e:
        print(f"❌ Ошибка создания файла настроек: {e}")


def load_settings() -> Dict[str, Any]:
    """Загрузка настроек из .env файла или создание файла с настройками по умолчанию"""
    global _settings_cache, _last_modified

    try:
        # Проверяем, изменился ли файл
        if ENV_FILE_PATH.exists():
            current_modified = ENV_FILE_PATH.stat().st_mtime
            if current_modified == _last_modified and _settings_cache:
                return _settings_cache
            _last_modified = current_modified
        else:
            # Создаем файл если его нет
            create_env_file()
    except Exception as e:
        print(f"❌ Ошибка проверки файла настроек: {e}")

    # Загружаем настройки из .env файла
    settings = {}

    try:
        if ENV_FILE_PATH.exists():
            with open(ENV_FILE_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        settings[key.strip()] = value.strip()
    except Exception as e:
        print(f"❌ Ошибка чтения .env файла: {e}")

    # Дополняем недостающие настройки значениями по умолчанию
    for key, default_value in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = default_value

    _settings_cache = settings
    return settings


async def reload_settings():
    """Асинхронная перезагрузка настроек"""
    try:
        # Небольшая задержка для завершения записи файла
        await asyncio.sleep(0.1)

        with _reload_lock:
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
                    print(f"❌ Ошибка обновления настроек в компоненте: {e}")

            print(f"✅ Настройки перезагружены из .env файла")

    except Exception as e:
        print(f"❌ Ошибка перезагрузки настроек: {e}")


def register_settings_callback(callback: Callable):
    """Регистрация callback для уведомления об изменении настроек"""
    _settings_callbacks.append(callback)


def unregister_settings_callback(callback: Callable):
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
        try:
            _file_observer.stop()
            _file_observer.join(timeout=5.0)  # Добавляем timeout
            _file_observer = None
            print("🛑 Мониторинг изменений .env файла остановлен")
        except Exception as e:
            print(f"❌ Ошибка остановки мониторинга настроек: {e}")


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


def update_setting(key: str, value: Any):
    """Обновление настройки в .env файле"""
    global _settings_cache, _last_modified

    try:
        # Преобразуем значение в строку, обрабатывая булевы значения
        if isinstance(value, bool):
            str_value = 'True' if value else 'False'
        else:
            str_value = str(value)

        settings = load_settings()
        settings[key] = str_value

        # Обновляем кэш
        _settings_cache[key] = str_value

        # Перезаписываем .env файл
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("# Настройки CryptoScan\n")
            f.write(f"# Обновлено автоматически: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for setting_key, setting_value in settings.items():
                if not setting_key.startswith('#'):
                    f.write(f"{setting_key}={setting_value}\n")

        print(f"⚙️ Настройка {key} обновлена на {str_value}")

        # Принудительно очищаем кэш для следующего чтения
        _last_modified = 0
        _settings_cache = {}

    except Exception as e:
        print(f"❌ Ошибка обновления настройки {key}: {e}")


def update_multiple_settings(settings_dict: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Обновление нескольких настроек одновременно"""
    errors = []
    
    try:
        current_settings = load_settings()
        
        # Обновляем настройки
        for key, value in settings_dict.items():
            try:
                if isinstance(value, bool):
                    str_value = 'True' if value else 'False'
                else:
                    str_value = str(value)
                current_settings[key] = str_value
            except Exception as e:
                errors.append(f"Ошибка обновления {key}: {e}")
        
        # Сохраняем все настройки в файл
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("# Настройки CryptoScan\n")
            f.write(f"# Обновлено автоматически: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for key, value in current_settings.items():
                if not key.startswith('#'):
                    f.write(f"{key}={value}\n")
        
        # Очищаем кэш
        global _settings_cache, _last_modified
        _settings_cache = {}
        _last_modified = 0
        
        print(f"⚙️ Обновлено {len(settings_dict)} настроек")
        return len(errors) == 0, errors
        
    except Exception as e:
        errors.append(f"Общая ошибка сохранения: {e}")
        return False, errors


def get_settings_schema() -> Dict:
    """Получить схему настроек с описаниями и типами"""
    return SETTINGS_SCHEMA


def get_settings_by_category() -> Dict:
    """Получить настройки, сгруппированные по категориям"""
    current_settings = load_settings()
    categorized = {}
    
    for category_key, category_info in SETTINGS_SCHEMA.items():
        categorized[category_key] = {
            'title': category_info['title'],
            'description': category_info['description'],
            'settings': {}
        }
        
        for setting_key, setting_info in category_info['settings'].items():
            current_value = current_settings.get(setting_key, setting_info['default'])
            
            # Преобразуем значение в правильный тип
            if setting_info['type'] == 'boolean':
                if isinstance(current_value, str):
                    current_value = current_value.lower() == 'true'
            elif setting_info['type'] == 'integer':
                try:
                    current_value = int(current_value)
                except (ValueError, TypeError):
                    current_value = setting_info['default']
            elif setting_info['type'] == 'float':
                try:
                    current_value = float(current_value)
                except (ValueError, TypeError):
                    current_value = setting_info['default']
            
            categorized[category_key]['settings'][setting_key] = {
                **setting_info,
                'current_value': current_value
            }
    
    return categorized


def reset_settings_to_default() -> bool:
    """Сброс всех настроек к значениям по умолчанию"""
    try:
        with open(ENV_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write("# Настройки CryptoScan\n")
            f.write(f"# Сброшено к значениям по умолчанию: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for key, value in DEFAULT_SETTINGS.items():
                f.write(f"{key}={value}\n")
        
        # Очищаем кэш
        global _settings_cache, _last_modified
        _settings_cache = {}
        _last_modified = 0
        
        print("✅ Настройки сброшены к значениям по умолчанию")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка сброса настроек: {e}")
        return False


def export_settings() -> Dict[str, Any]:
    """Экспорт текущих настроек"""
    return load_settings()


def import_settings(settings_dict: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Импорт настроек из словаря"""
    return update_multiple_settings(settings_dict)


# Инициализация настроек при импорте модуля
try:
    create_env_file()
    SETTINGS = load_settings()
except Exception as e:
    print(f"❌ Ошибка инициализации настроек: {e}")
    SETTINGS = DEFAULT_SETTINGS.copy()