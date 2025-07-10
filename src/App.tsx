import React, { useState, useEffect, useRef } from 'react';
import {
  TrendingUp,
  BarChart3,
  Star,
  List,
  Wifi,
  Settings,
  ExternalLink,
  Brain,
  RefreshCw,
  Clock,
  WifiOff,
  Activity,
  Zap,
  Heart,
  HeartOff
} from 'lucide-react';
import ChartSelector from './components/ChartSelector';
import WatchlistModal from './components/WatchlistModal';
import FavoritesModal from './components/FavoritesModal';
import StreamDataModal from './components/StreamDataModal';
import SettingsModal from './components/SettingsModal';
import StartupLoader from './components/StartupLoader';
import VolumeAlertModal from './components/VolumeAlertModal';
import ConsecutiveAlertModal from './components/ConsecutiveAlertModal';
import PriorityAlertModal from './components/PriorityAlertModal';
import { TimeZoneProvider } from './contexts/TimeZoneContext';
import { formatTime } from './utils/timeUtils';

interface Alert {
  id: number;
  symbol: string;
  alert_type: string;
  price: number;
  timestamp: string;
  close_timestamp?: string;
  message: string;
  volume_ratio?: number;
  current_volume_usdt?: number;
  consecutive_count?: number;
  has_imbalance?: boolean;
  imbalance_data?: {
    type: string;
    direction: string;
    strength: number;
    top?: number;
    bottom?: number;
  };
  is_closed: boolean;
  is_true_signal?: boolean;
  preliminary_alert?: {
    timestamp: string;
    volume_ratio: number;
  };
}

interface SmartMoneyAlert {
  id: number;
  symbol: string;
  type: string;
  direction: string;
  strength: number;
  price: number;
  timestamp: string;
  top?: number;
  bottom?: number;
  related_alert_id?: number;
}

interface WatchlistItem {
  id: number;
  symbol: string;
  is_active: boolean;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
  favorite_added_at?: string;
  notes?: string;
  color?: string;
  price_drop_percentage?: number;
  current_price?: number;
}

interface StreamData {
  symbol: string;
  price: number;
  volume: number;
  volume_usdt: number;
  is_long: boolean;
  timestamp: string;
  is_closed: boolean;
}

interface Settings {
  volume_analyzer?: {
    notification_enabled: boolean;
  };
  time_sync?: TimeSync;
}

interface TimeSync {
  is_synced: boolean;
  server_time: string;
  local_time: string;
  offset_ms: number;
}

const App: React.FC = () => {
  // Состояние загрузки данных при запуске
  const [startupData, setStartupData] = useState<any>(null);
  const [isStartupComplete, setIsStartupComplete] = useState(false);

  const [activeTab, setActiveTab] = useState<'volume' | 'consecutive' | 'priority' | 'watchlist' | 'favorites' | 'stream' | 'smart_money'>('volume');
  const [volumeAlerts, setVolumeAlerts] = useState<Alert[]>([]);
  const [consecutiveAlerts, setConsecutiveAlerts] = useState<Alert[]>([]);
  const [priorityAlerts, setPriorityAlerts] = useState<Alert[]>([]);
  const [smartMoneyAlerts, setSmartMoneyAlerts] = useState<SmartMoneyAlert[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [favorites, setFavorites] = useState<WatchlistItem[]>([]);
  const [streamData, setStreamData] = useState<StreamData[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [selectedSmartMoneyAlert, setSelectedSmartMoneyAlert] = useState<SmartMoneyAlert | null>(null);
  const [showWatchlistModal, setShowWatchlistModal] = useState(false);
  const [showFavoritesModal, setShowFavoritesModal] = useState(false);
  const [showStreamModal, setShowStreamModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [appInitialized, setAppInitialized] = useState(false);
  const [currentTime, setCurrentTime] = useState<Date>(new Date());
  const [timeSync, setTimeSync] = useState<TimeSync | null>(null);
  const [lastDataUpdate, setLastDataUpdate] = useState<Date | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [dataActivity, setDataActivity] = useState<'active' | 'idle' | 'error'>('idle');
  const [connectionInfo, setConnectionInfo] = useState<{
    subscribedCount: number;
    failedCount: number;
    subscribedPairs: string[];
  }>({ subscribedCount: 0, failedCount: 0, subscribedPairs: [] });

  // Refs для WebSocket и интервалов
  const wsRef = useRef<WebSocket | null>(null);
  const timeIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const syncIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const dataRefreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const activityTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Инициализация происходит только после загрузки startup данных
    if (appInitialized && startupData) {
      initializeApp();
    }
  }, [appInitialized, startupData]);

  const handleStartupDataLoaded = (data: any) => {
    console.log('Startup data loaded:', data);
    setStartupData(data);
    
    // Инициализируем состояние из startup данных
    if (data.alerts) {
      // Разделяем алерты по типам
      const volumeAlerts = data.alerts.filter((a: any) => 
        a.alert_type === 'volume_spike' || a.alert_type === 'preliminary_volume_spike' || a.alert_type === 'final_volume_spike'
      );
      const consecutiveAlerts = data.alerts.filter((a: any) => a.alert_type === 'consecutive_long');
      const priorityAlerts = data.alerts.filter((a: any) => a.alert_type === 'priority');
      
      setVolumeAlerts(volumeAlerts.sort((a: any, b: any) =>
        new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
      ));
      setConsecutiveAlerts(consecutiveAlerts.sort((a: any, b: any) =>
        new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
      ));
      setPriorityAlerts(priorityAlerts.sort((a: any, b: any) =>
        new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
      ));
      
      // Создаем Smart Money алерты из алертов с имбалансом
      const smartMoneyAlerts = data.alerts
        .filter((a: any) => a.has_imbalance && a.imbalance_data)
        .map((a: any) => ({
          id: Date.now() + Math.random(),
          symbol: a.symbol,
          type: a.imbalance_data.type,
          direction: a.imbalance_data.direction,
          strength: a.imbalance_data.strength,
          price: a.price,
          timestamp: a.timestamp,
          top: a.imbalance_data.top,
          bottom: a.imbalance_data.bottom,
          related_alert_id: a.id
        }));
      setSmartMoneyAlerts(smartMoneyAlerts);
    }
    
    if (data.watchlist) {
      setWatchlist(data.watchlist.map((symbol: string) => ({
        id: Date.now() + Math.random(),
        symbol,
        is_active: true,
        is_favorite: false
      })));
    }
    
    if (data.favorites) {
      setFavorites(data.favorites);
    }
    
    if (data.settings) {
      setSettings(data.settings);
    }
    
    setAppInitialized(true);
  };

  const initializeApp = () => {
    connectWebSocket();
    requestNotificationPermission();

    // Обновляем время каждую секунду
    timeIntervalRef.current = setInterval(() => {
      updateCurrentTime();
    }, 1000);

    // Загружаем информацию о синхронизации времени каждые 30 секунд
    syncIntervalRef.current = setInterval(loadTimeSync, 30000);
    loadTimeSync();

    // Периодически обновляем данные (каждые 30 секунд)
    dataRefreshIntervalRef.current = setInterval(() => {
      refreshData();
    }, 30000);
  };

  // Cleanup effect
  useEffect(() => {
    return () => {
      if (timeIntervalRef.current) {
        clearInterval(timeIntervalRef.current);
      }
      if (syncIntervalRef.current) {
        clearInterval(syncIntervalRef.current);
      }
      if (dataRefreshIntervalRef.current) {
        clearInterval(dataRefreshIntervalRef.current);
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (activityTimeoutRef.current) {
        clearTimeout(activityTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const updateCurrentTime = () => {
    setCurrentTime(new Date());
  };

  const updateDataActivity = (status: 'active' | 'idle' | 'error') => {
    setDataActivity(status);

    // Сбрасываем таймер активности
    if (activityTimeoutRef.current) {
      clearTimeout(activityTimeoutRef.current);
    }

    // Если статус активный, через 3 секунды переводим в idle
    if (status === 'active') {
      activityTimeoutRef.current = setTimeout(() => {
        setDataActivity('idle');
      }, 3000);
    }
  };

  const loadTimeSync = async () => {
    try {
      const response = await fetch('/api/time');
      if (response.ok) {
        const timeSyncData = await response.json();
        setTimeSync(timeSyncData);
      }
    } catch (error) {
      console.error('Ошибка загрузки информации о времени:', error);
    }
  };

  const refreshData = async () => {
    try {
      updateDataActivity('active');

      // Обновляем алерты
      const alertsResponse = await fetch('/api/alerts/all');
      if (alertsResponse.ok) {
        const alertsData = await alertsResponse.json();

        // Обновляем алерты с сортировкой
        setVolumeAlerts((alertsData.volume_alerts || []).sort((a: Alert, b: Alert) =>
          new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
        ));
        setConsecutiveAlerts((alertsData.consecutive_alerts || []).sort((a: Alert, b: Alert) =>
          new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
        ));
        setPriorityAlerts((alertsData.priority_alerts || []).sort((a: Alert, b: Alert) =>
          new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
        ));

        console.log('Данные обновлены:', {
          volume: alertsData.volume_alerts?.length || 0,
          consecutive: alertsData.consecutive_alerts?.length || 0,
          priority: alertsData.priority_alerts?.length || 0
        });
      }

      // Обновляем watchlist
      const watchlistResponse = await fetch('/api/watchlist');
      if (watchlistResponse.ok) {
        const watchlistData = await watchlistResponse.json();
        const sortedWatchlist = (watchlistData.pairs || []).sort((a: WatchlistItem, b: WatchlistItem) => {
          // Сначала избранные
          if (a.is_favorite && !b.is_favorite) return -1;
          if (!a.is_favorite && b.is_favorite) return 1;

          // Затем по проценту падения
          if (a.price_drop_percentage && b.price_drop_percentage) {
            if (a.price_drop_percentage !== b.price_drop_percentage) {
              return b.price_drop_percentage - a.price_drop_percentage;
            }
          }
          return a.symbol.localeCompare(b.symbol);
        });
        setWatchlist(sortedWatchlist);
      }

      // Обновляем избранное
      const favoritesResponse = await fetch('/api/favorites');
      if (favoritesResponse.ok) {
        const favoritesData = await favoritesResponse.json();
        setFavorites(favoritesData.favorites || []);
      }

    } catch (error) {
      console.error('Ошибка обновления данных:', error);
      updateDataActivity('error');
    }
  };

  const requestNotificationPermission = async () => {
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission();
    }
  };

  const showNotification = (alert: Alert) => {
    if (!settings?.volume_analyzer?.notification_enabled) return;
    if ('Notification' in window && Notification.permission === 'granted') {
      const title = `Алерт: ${alert.symbol}`;
      const body = alert.message;
      const notification = new Notification(title, {
        body,
        icon: '/favicon.ico',
        tag: `alert-${alert.id}`
      });

      notification.onclick = () => {
        window.focus();
        setSelectedAlert(alert);
        notification.close();
      };

      setTimeout(() => notification.close(), 10000);
    }
  };

  const connectWebSocket = () => {
    // Закрываем существующее соединение, если есть
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log('🔗 Подключение к WebSocket:', wsUrl);
    setConnectionStatus('connecting');

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus('connected');
      setReconnectAttempts(0);
      updateDataActivity('active');
      console.log('✅ WebSocket подключен');

      // Отправляем ping для поддержания соединения
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        } else {
          clearInterval(pingInterval);
        }
      }, 30000); // Ping каждые 30 секунд
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastDataUpdate(new Date());
        updateDataActivity('active');
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Ошибка парсинга WebSocket сообщения:', error);
        updateDataActivity('error');
      }
    };

    ws.onclose = (event) => {
      console.log('❌ WebSocket отключен:', event.code, event.reason);
      setConnectionStatus('disconnected');
      updateDataActivity('error');

      // Автоматическое переподключение с экспоненциальной задержкой
      if (wsRef.current === ws) { // Проверяем, что это текущее соединение
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000); // Максимум 30 секунд
        console.log(`🔄 Переподключение через ${delay}мс (попытка ${reconnectAttempts + 1})`);

        reconnectTimeoutRef.current = setTimeout(() => {
          setReconnectAttempts(prev => prev + 1);
          connectWebSocket();
        }, delay);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket ошибка:', error);
      setConnectionStatus('disconnected');
      updateDataActivity('error');
    };
  };

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'pong':
        // Ответ на ping - ничего не делаем
        break;

      case 'new_alert':
      case 'alert_updated':
        const alert = data.alert;

        // Показываем уведомление только для новых алертов
        if (data.type === 'new_alert') {
          showNotification(alert);
        }

        // Обновляем алерты без дублирования
        if (alert.alert_type === 'volume_spike') {
          setVolumeAlerts(prev => {
            const existing = prev.find(a => a.id === alert.id);
            if (existing) {
              // Обновляем существующий алерт
              const updated = prev.map(a => a.id === alert.id ? alert : a);
              return updated.sort((a, b) =>
                new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
              );
            }
            // Добавляем новый алерт
            const newList = [alert, ...prev].slice(0, 100);
            return newList.sort((a, b) =>
              new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
            );
          });
        } else if (alert.alert_type === 'consecutive_long') {
          setConsecutiveAlerts(prev => {
            const existing = prev.find(a => a.id === alert.id);
            if (existing) {
              const updated = prev.map(a => a.id === alert.id ? alert : a);
              return updated.sort((a, b) =>
                new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
              );
            }
            const newList = [alert, ...prev].slice(0, 100);
            return newList.sort((a, b) =>
              new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
            );
          });
        } else if (alert.alert_type === 'priority') {
          setPriorityAlerts(prev => {
            const existing = prev.find(a => a.id === alert.id);
            if (existing) {
              const updated = prev.map(a => a.id === alert.id ? alert : a);
              return updated.sort((a, b) =>
                new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
              );
            }
            const newList = [alert, ...prev].slice(0, 100);
            return newList.sort((a, b) =>
              new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
            );
          });
        }

        // Если есть имбаланс, добавляем в Smart Money алерты
        if (alert.has_imbalance && alert.imbalance_data) {
          const smartMoneyAlert: SmartMoneyAlert = {
            id: Date.now(),
            symbol: alert.symbol,
            type: alert.imbalance_data.type,
            direction: alert.imbalance_data.direction,
            strength: alert.imbalance_data.strength,
            price: alert.price,
            timestamp: alert.timestamp,
            top: alert.imbalance_data.top,
            bottom: alert.imbalance_data.bottom,
            related_alert_id: alert.id
          };
          setSmartMoneyAlerts(prev => [smartMoneyAlert, ...prev].slice(0, 50));
        }
        break;

      case 'kline_update':
        // Обновляем потоковые данные для ВСЕХ символов
        const streamItem: StreamData = {
          symbol: data.symbol,
          price: parseFloat(data.data.close),
          volume: parseFloat(data.data.volume),
          volume_usdt: parseFloat(data.data.volume) * parseFloat(data.data.close),
          is_long: parseFloat(data.data.close) > parseFloat(data.data.open),
          timestamp: data.timestamp,
          is_closed: data.is_closed || false
        };

        setStreamData(prev => {
          // Обновляем или добавляем данные для символа
          const filtered = prev.filter(item => item.symbol !== data.symbol);
          const newData = [streamItem, ...filtered].slice(0, 2000); // Увеличиваем лимит до 2000
          return newData;
        });
        break;

      case 'connection_status':
        setConnectionStatus(data.status === 'connected' ? 'connected' : 'disconnected');

        // Обновляем информацию о подключении
        if (data.subscribed_count !== undefined) {
          setConnectionInfo({
            subscribedCount: data.subscribed_count || 0,
            failedCount: data.failed_count || 0,
            subscribedPairs: data.subscribed_pairs || []
          });
        }

        console.log('📊 Статус подключения:', {
          status: data.status,
          subscribedCount: data.subscribed_count,
          failedCount: data.failed_count,
          totalPairs: data.pairs_count
        });
        break;

      case 'watchlist_updated':
      case 'favorites_updated':
        // Обновляем watchlist и избранное при изменениях
        refreshData();
        break;

      case 'consecutive_update':
        // Обновление счетчика последовательных свечей
        console.log(`Обновление последовательности для ${data.symbol}: ${data.count} свечей`);
        break;

      case 'alerts_cleared':
        // Очистка алертов
        if (data.alert_type === 'volume_spike') {
          setVolumeAlerts([]);
        } else if (data.alert_type === 'consecutive_long') {
          setConsecutiveAlerts([]);
        } else if (data.alert_type === 'priority') {
          setPriorityAlerts([]);
        }
        break;

      default:
        console.log('❓ Неизвестный тип сообщения WebSocket:', data.type);
    }
  };

  const loadWatchlist = async () => {
    try {
      const response = await fetch('/api/watchlist');
      if (response.ok) {
        const data = await response.json();
        // Сортируем по избранному, проценту падения и алфавиту
        const sortedWatchlist = (data.pairs || []).sort((a: WatchlistItem, b: WatchlistItem) => {
          // Сначала избранные
          if (a.is_favorite && !b.is_favorite) return -1;
          if (!a.is_favorite && b.is_favorite) return 1;

          // Затем по проценту падения
          if (a.price_drop_percentage && b.price_drop_percentage) {
            if (a.price_drop_percentage !== b.price_drop_percentage) {
              return b.price_drop_percentage - a.price_drop_percentage;
            }
          }
          return a.symbol.localeCompare(b.symbol);
        });
        setWatchlist(sortedWatchlist);
      }
    } catch (error) {
      console.error('Ошибка загрузки watchlist:', error);
    }
  };

  const loadFavorites = async () => {
    try {
      const response = await fetch('/api/favorites');
      if (response.ok) {
        const data = await response.json();
        setFavorites(data.favorites || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки избранного:', error);
    }
  };

  const toggleFavorite = async (symbol: string, isFavorite: boolean) => {
    try {
      if (isFavorite) {
        // Удаляем из избранного
        const response = await fetch(`/api/favorites/${symbol}`, {
          method: 'DELETE'
        });
        if (response.ok) {
          await refreshData();
        }
      } else {
        // Добавляем в избранное
        const response = await fetch('/api/favorites', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ symbol }),
        });
        if (response.ok) {
          await refreshData();
        }
      }
    } catch (error) {
      console.error('Ошибка переключения избранного:', error);
    }
  };

  const clearAlerts = async (alertType: string) => {
    try {
      const response = await fetch(`/api/alerts/clear/${alertType}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        if (alertType === 'volume_spike') {
          setVolumeAlerts([]);
        } else if (alertType === 'consecutive_long') {
          setConsecutiveAlerts([]);
        } else if (alertType === 'priority') {
          setPriorityAlerts([]);
        }
      }
    } catch (error) {
      console.error('Ошибка очистки алертов:', error);
    }
  };

  const openTradingView = (symbol: string) => {
    const cleanSymbol = symbol.replace('USDT', '');
    const url = `https://www.tradingview.com/chart/?symbol=BYBIT:${cleanSymbol}USDT.P&interval=1`;
    window.open(url, '_blank');
  };

  const handleSettingsSave = (newSettings: Settings) => {
    setSettings(newSettings);
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1000000) {
      return `$${(volume / 1000000).toFixed(1)}M`;
    } else if (volume >= 1000) {
      return `$${(volume / 1000).toFixed(1)}K`;
    }
    return `$${volume.toFixed(0)}`;
  };

  const getAlertStatusBadge = (alert: Alert) => {
    if (!alert.is_closed) {
      return <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full">В процессе</span>;
    }

    if (alert.is_true_signal === true) {
      return <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">Истинный</span>;
    } else if (alert.is_true_signal === false) {
      return <span className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded-full">Ложный</span>;
    }

    return <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded-full">Неизвестно</span>;
  };

  const getTimeSyncStatus = () => {
    if (!timeSync) return { color: 'text-gray-500', text: 'Нет данных', icon: '⚪' };

    if (!timeSync.is_synced) {
      return { color: 'text-yellow-500', text: 'Не синхронизировано', icon: '🟡' };
    }

    return { color: 'text-green-500', text: 'Синхронизировано', icon: '🟢' };
  };

  const formatLocalTime = (date: Date) => {
    return date.toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const formatLocalDate = (date: Date) => {
    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    });
  };

  const getTimezoneInfo = () => {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const offset = new Date().getTimezoneOffset();
    const offsetHours = Math.abs(Math.floor(offset / 60));
    const offsetMinutes = Math.abs(offset % 60);
    const offsetSign = offset <= 0 ? '+' : '-';

    return {
      timezone,
      offsetString: `UTC${offsetSign}${offsetHours.toString().padStart(2, '0')}:${offsetMinutes.toString().padStart(2, '0')}`
    };
  };

  const getConnectionStatusIcon = () => {
    switch (connectionStatus) {
      case 'connected':
        return <Wifi className="w-5 h-5 text-green-500" />;
      case 'connecting':
        return <RefreshCw className="w-5 h-5 text-yellow-500 animate-spin" />;
      case 'disconnected':
        return <WifiOff className="w-5 h-5 text-red-500" />;
      default:
        return <WifiOff className="w-5 h-5 text-gray-500" />;
    }
  };

  const getConnectionStatusText = () => {
    switch (connectionStatus) {
      case 'connected':
        return `Подключено (${connectionInfo.subscribedCount}/${watchlist.length})`;
      case 'connecting':
        return 'Подключение...';
      case 'disconnected':
        return reconnectAttempts > 0 ? `Переподключение (${reconnectAttempts})` : 'Отключено';
      default:
        return 'Неизвестно';
    }
  };

  const renderAlertModal = () => {
    if (!selectedAlert) return null;

    // Определяем тип алерта и показываем соответствующий модал
    if (selectedAlert.alert_type === 'volume_spike' || 
        selectedAlert.alert_type === 'preliminary_volume_spike' || 
        selectedAlert.alert_type === 'final_volume_spike') {
      return (
        <VolumeAlertModal
          alert={selectedAlert as any}
          onClose={() => setSelectedAlert(null)}
        />
      );
    }

    if (selectedAlert.alert_type === 'consecutive_long') {
      return (
        <ConsecutiveAlertModal
          alert={selectedAlert as any}
          onClose={() => setSelectedAlert(null)}
        />
      );
    }

    if (selectedAlert.alert_type === 'priority') {
      return (
        <PriorityAlertModal
          alert={selectedAlert as any}
          onClose={() => setSelectedAlert(null)}
        />
      );
    }

    // Fallback на обычный ChartSelector
    return (
      <ChartSelector
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />
    );
  };

  const getDataActivityIcon = () => {
    switch (dataActivity) {
      case 'active':
        return <Zap className="w-4 h-4 text-green-500 animate-pulse" />;
      case 'error':
        return <Activity className="w-4 h-4 text-red-500" />;
      case 'idle':
      default:
        return <Activity className="w-4 h-4 text-gray-400" />;
    }
  };

  const getDataActivityText = () => {
    switch (dataActivity) {
      case 'active':
        return 'Получение данных';
      case 'error':
        return 'Ошибка данных';
      case 'idle':
      default:
        return 'Ожидание';
    }
  };

  // Функция для определения типа алерта и открытия соответствующего модального окна
  const openAlertModal = (alert: Alert) => {
    if (alert.alert_type === 'volume_spike' || alert.alert_type === 'preliminary_volume_spike' || alert.alert_type === 'final_volume_spike') {
      // Используем VolumeAlertModal для объемных алертов
      setSelectedAlert(alert);
    } else if (alert.alert_type === 'consecutive_long') {
      // Используем ConsecutiveAlertModal для последовательных алертов
      setSelectedAlert(alert);
    } else if (alert.alert_type === 'priority') {
      // Используем PriorityAlertModal для приоритетных алертов
      setSelectedAlert(alert);
    } else {
      // Fallback на ChartSelector
      setSelectedAlert(alert);
    }
  };

  const renderAlertCard = (alert: Alert) => (
    <div
      key={alert.id}
      className="bg-white rounded-lg shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow cursor-pointer w-full"
      onClick={() => openAlertModal(alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-lg text-gray-900">{alert.symbol}</span>
          {alert.has_imbalance && (
            <span className="text-orange-500 text-sm">⚠️ Имбаланс</span>
          )}
          {getAlertStatusBadge(alert)}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              openTradingView(alert.symbol);
            }}
            className="text-blue-600 hover:text-blue-800 p-1"
            title="Открыть в TradingView"
          >
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-600">Цена:</span>
          <div className="font-mono text-gray-900">${alert.price.toFixed(8)}</div>
        </div>

        {alert.volume_ratio && (
          <div>
            <span className="text-gray-600">Превышение:</span>
            <div className="font-semibold text-orange-600">{alert.volume_ratio}x</div>
          </div>
        )}

        {alert.current_volume_usdt && (
          <div>
            <span className="text-gray-600">Объем:</span>
            <div className="text-gray-900">{formatVolume(alert.current_volume_usdt)}</div>
          </div>
        )}

        {alert.consecutive_count && (
          <div>
            <span className="text-gray-600">LONG свечей:</span>
            <div className="font-semibold text-green-600">{alert.consecutive_count}</div>
          </div>
        )}
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200">
        <div className="text-xs text-gray-500">
          <div>Время закрытия: {formatTime(alert.close_timestamp || alert.timestamp, 'local')}</div>
          {alert.preliminary_alert && (
            <div>Предварительный: {formatTime(alert.preliminary_alert.timestamp, 'local')}</div>
          )}
        </div>
      </div>
    </div>
  );

  const renderSmartMoneyCard = (alert: SmartMoneyAlert) => (
    <div
      key={alert.id}
      className="bg-white rounded-lg shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow cursor-pointer w-full"
      onClick={() => setSelectedSmartMoneyAlert(alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-lg text-gray-900">{alert.symbol}</span>
          <span className={`px-2 py-1 text-xs rounded-full ${
            alert.direction === 'bullish' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            {alert.direction === 'bullish' ? 'Бычий' : 'Медвежий'}
          </span>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            openTradingView(alert.symbol);
          }}
          className="text-blue-600 hover:text-blue-800 p-1"
          title="Открыть в TradingView"
        >
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-600">Тип:</span>
          <div className="font-semibold text-gray-900">
            {alert.type === 'fair_value_gap' && 'Fair Value Gap'}
            {alert.type === 'order_block' && 'Order Block'}
            {alert.type === 'breaker_block' && 'Breaker Block'}
          </div>
        </div>

        <div>
          <span className="text-gray-600">Сила:</span>
          <div className="font-semibold text-purple-600">{alert.strength.toFixed(2)}%</div>
        </div>

        <div>
          <span className="text-gray-600">Цена:</span>
          <div className="font-mono text-gray-900">${alert.price.toFixed(8)}</div>
        </div>

        <div>
          <span className="text-gray-600">Время:</span>
          <div className="text-gray-900">{formatTime(alert.timestamp, 'local')}</div>
        </div>
      </div>

      {alert.top && alert.bottom && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4  text-xs text-gray-500">
            <div>Верх: ${alert.top.toFixed(6)}</div>
            <div>Низ: ${alert.bottom.toFixed(6)}</div>
          </div>
        </div>
      )}
    </div>
  );

  const renderWatchlistCard = (item: WatchlistItem) => (
    <div key={item.id} className="bg-white rounded-lg shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow w-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className={`w-3 h-3 rounded-full ${item.is_active ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="font-bold text-lg text-gray-900">{item.symbol}</span>
          {item.is_favorite && (
            <span className="text-yellow-500">
              <Star className="w-4 h-4 fill-yellow-500" />
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleFavorite(item.symbol, item.is_favorite);
            }}
            className={`p-1 rounded-full ${
              item.is_favorite
                ? 'text-yellow-500 hover:text-yellow-600'
                : 'text-gray-400 hover:text-yellow-500'
            }`}
            title={item.is_favorite ? "Удалить из избранного" : "Добавить в избранное"}
          >
            {item.is_favorite ? (
              <Heart className="w-5 h-5 fill-yellow-500" />
            ) : (
              <Heart className="w-5 h-5" />
            )}
          </button>

          <button
            onClick={() => openTradingView(item.symbol)}
            className="text-blue-600 hover:text-blue-800 p-1"
            title="Открыть в TradingView"
          >
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>

      {item.price_drop_percentage && (
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-600">Падение цены:</span>
            <div className="font-semibold text-red-600">{item.price_drop_percentage.toFixed(2)}%</div>
          </div>

          {item.current_price && (
            <div>
              <span className="text-gray-600">Текущая цена:</span>
              <div className="font-mono text-gray-900">${item.current_price.toFixed(8)}</div>
            </div>
          )}
        </div>
      )}

      {item.notes && (
        <div className="mt-2 text-sm text-gray-600 bg-gray-50 p-2 rounded">
          {item.notes}
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
        Обновлено: {formatTime(item.updated_at, 'local')}
      </div>
    </div>
  );

  const renderFavoriteCard = (item: WatchlistItem) => (
    <div
      key={item.id}
      className="bg-white rounded-lg shadow-md border-l-4 p-4 hover:shadow-lg transition-shadow w-full"
      style={{ borderLeftColor: item.color || '#FFD700' }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className={`w-3 h-3 rounded-full ${item.is_active ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="font-bold text-lg text-gray-900">{item.symbol}</span>
          <span className="text-yellow-500">
            <Star className="w-4 h-4 fill-yellow-500" />
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleFavorite(item.symbol, true);
            }}
            className="text-yellow-500 hover:text-yellow-600 p-1"
            title="Удалить из избранного"
          >
            <HeartOff className="w-5 h-5" />
          </button>

          <button
            onClick={() => openTradingView(item.symbol)}
            className="text-blue-600 hover:text-blue-800 p-1"
            title="Открыть в TradingView"
          >
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        {item.price_drop_percentage && (
          <div>
            <span className="text-gray-600">Падение цены:</span>
            <div className="font-semibold text-red-600">{item.price_drop_percentage.toFixed(2)}%</div>
          </div>
        )}

        {item.current_price && (
          <div>
            <span className="text-gray-600">Текущая цена:</span>
            <div className="font-mono text-gray-900">${item.current_price.toFixed(8)}</div>
          </div>
        )}
      </div>

      {item.notes && (
        <div className="mt-2 text-sm text-gray-600 bg-gray-50 p-2 rounded">
          {item.notes}
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500 flex justify-between">
        <span>Добавлено: {formatTime(item.favorite_added_at || item.created_at, 'local')}</span>
        <span>Обновлено: {formatTime(item.updated_at, 'local')}</span>
      </div>
    </div>
  );

  const timeSyncStatus = getTimeSyncStatus();
  const timezoneInfo = getTimezoneInfo();

  return (
    <TimeZoneProvider>
      <StartupLoader onDataLoaded={handleStartupDataLoaded}>
        {!appInitialized ? (
          <div className="min-h-screen bg-gray-50 flex items-center justify-center">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
              <p className="text-gray-600">Инициализация приложения...</p>
            </div>
          </div>
        ) : (
          <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center space-x-4">
                <h1 className="text-xl font-bold text-gray-900">Анализатор Объемов</h1>
                <div className="flex items-center space-x-3">
                  {getConnectionStatusIcon()}
                  <span className="text-sm text-gray-600">
                    {getConnectionStatusText()}
                  </span>
                  {/* Индикатор активности данных */}
                  <div className="flex items-center space-x-1">
                    {getDataActivityIcon()}
                    <span className="text-xs text-gray-500">
                      {getDataActivityText()}
                    </span>
                  </div>
                  {lastDataUpdate && (
                    <span className="text-xs text-gray-400">
                      • {formatLocalTime(lastDataUpdate)}
                    </span>
                  )}
                  {connectionInfo.subscribedCount > 0 && (
                    <span className="text-xs text-gray-400">
                      • Подписано: {connectionInfo.subscribedCount}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-6">
                {/* Динамические часы в локальном часовом поясе */}
                <div className="flex items-center space-x-3 bg-gray-100 rounded-lg px-4 py-2">
                  <Clock className="w-5 h-5 text-gray-600" />
                  <div className="text-center">
                    <div className="text-lg font-mono font-bold text-gray-900">
                      {formatLocalTime(currentTime)}
                    </div>
                    <div className="text-xs text-gray-500">
                      {formatLocalDate(currentTime)}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 text-center">
                    <div className={timeSyncStatus.color}>
                      {timeSyncStatus.icon} {timezoneInfo.offsetString}
                    </div>
                    <div className="text-xs">
                      {timezoneInfo.timezone.split('/').pop()}
                    </div>
                    <div className="text-xs">
                      Синх: {timeSyncStatus.text}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => setShowSettings(true)}
                  className="text-gray-600 hover:text-gray-900 p-2 rounded-lg hover:bg-gray-100 transition-colors"
                  title="Настройки"
                >
                  <Settings className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Navigation Tabs */}
        <nav className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex space-x-8">
              {[
                { id: 'volume', label: 'Алерты по объему', icon: TrendingUp, count: volumeAlerts.length },
                { id: 'consecutive', label: 'LONG последовательности', icon: BarChart3, count: consecutiveAlerts.length },
                { id: 'priority', label: 'Приоритетные', icon: Star, count: priorityAlerts.length },
                { id: 'smart_money', label: 'Smart Money', icon: Brain, count: smartMoneyAlerts.length },
                { id: 'favorites', label: 'Избранное', icon: Heart, count: favorites.length },
                { id: 'watchlist', label: 'Торговые пары', icon: List, count: watchlist.length },
                { id: 'stream', label: 'Потоковые данные', icon: Wifi, count: streamData.length }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  {tab.count > 0 && (
                    <span className="bg-gray-100 text-gray-900 py-0.5 px-2 rounded-full text-xs">
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Volume Alerts */}
          {activeTab === 'volume' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Алерты по объему</h2>
                <button
                  onClick={() => clearAlerts('volume_spike')}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {volumeAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <TrendingUp className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет алертов по объему</p>
                  </div>
                ) : (
                  volumeAlerts.map(renderAlertCard)
                )}
              </div>
            </div>
          )}

          {/* Consecutive Alerts */}
          {activeTab === 'consecutive' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">LONG последовательности</h2>
                <button
                  onClick={() => clearAlerts('consecutive_long')}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {consecutiveAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <BarChart3 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет алертов по последовательностям</p>
                  </div>
                ) : (
                  consecutiveAlerts.map(renderAlertCard)
                )}
              </div>
            </div>
          )}

          {/* Priority Alerts */}
          {activeTab === 'priority' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Приоритетные алерты</h2>
                <button
                  onClick={() => clearAlerts('priority')}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {priorityAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <Star className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет приоритетных алертов</p>
                  </div>
                ) : (
                  priorityAlerts.map(renderAlertCard)
                )}
              </div>
            </div>
          )}

          {/* Smart Money Alerts */}
          {activeTab === 'smart_money' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Smart Money Concepts</h2>
                <button
                  onClick={() => setSmartMoneyAlerts([])}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {smartMoneyAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <Brain className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет сигналов Smart Money</p>
                  </div>
                ) : (
                  smartMoneyAlerts.map(renderSmartMoneyCard)
                )}
              </div>
            </div>
          )}

          {/* Favorites */}
          {activeTab === 'favorites' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Избранные торговые пары</h2>
                <button
                  onClick={() => setShowFavoritesModal(true)}
                  className="bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Управление избранным
                </button>
              </div>

              <div className="space-y-4">
                {favorites.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <Heart className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет избранных торговых пар</p>
                    <p className="mt-2 text-sm">Добавьте пары в избранное, нажав на иконку сердечка в списке торговых пар</p>
                  </div>
                ) : (
                  favorites.map(renderFavoriteCard)
                )}
              </div>
            </div>
          )}

          {/* Watchlist */}
          {activeTab === 'watchlist' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Список торговых пар</h2>
                <button
                  onClick={() => setShowWatchlistModal(true)}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Управление
                </button>
              </div>

              <div className="space-y-4">
                {watchlist.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <List className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет торговых пар в списке</p>
                  </div>
                ) : (
                  watchlist.map(renderWatchlistCard)
                )}
              </div>
            </div>
          )}

          {/* Stream Data */}
          {activeTab === 'stream' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Потоковые данные</h2>
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-gray-600">
                    Обновлений: {streamData.length} / Пар в watchlist: {watchlist.length} / Подписано: {connectionInfo.subscribedCount}
                  </span>
                  <button
                    onClick={() => connectWebSocket()}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                    disabled={connectionStatus === 'connecting'}
                  >
                    {connectionStatus === 'connecting' ? 'Подключение...' : 'Переподключить'}
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                {streamData.slice(0, 200).map((item, index) => (
                  <div key={`${item.symbol}-${index}`} className="bg-white rounded-lg shadow-md border border-gray-200 p-4 w-full">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <div className={`w-4 h-4 rounded-full ${
                          item.is_long ? 'bg-green-500' : 'bg-red-500'
                        }`}></div>

                        <div>
                          <span className="font-semibold text-gray-900 text-lg">{item.symbol}</span>
                          <div className="flex items-center space-x-2 text-sm">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              item.is_long ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {item.is_long ? 'LONG' : 'SHORT'}
                            </span>
                            {item.is_closed && (
                              <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">Закрыта</span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-xl font-bold text-gray-900">
                          ${item.price.toFixed(8)}
                        </div>
                        <div className="text-sm text-gray-600">
                          Vol: {formatVolume(item.volume_usdt)}
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <div className="text-right text-sm text-gray-500">
                          <div>{formatTime(item.timestamp, 'local', { includeDate: false, includeSeconds: true })}</div>
                          <div className="text-xs">
                            {formatVolume(item.volume)} {item.symbol.replace('USDT', '')}
                          </div>
                        </div>

                        <button
                          onClick={() => openTradingView(item.symbol)}
                          className="text-blue-600 hover:text-blue-800 p-1"
                          title="Открыть в TradingView"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Modals */}
        {renderAlertModal()}

        {selectedSmartMoneyAlert && (
          <ChartSelector
            alert={{
              id: selectedSmartMoneyAlert.id,
              symbol: selectedSmartMoneyAlert.symbol,
              alert_type: 'smart_money',
              price: selectedSmartMoneyAlert.price,
              timestamp: selectedSmartMoneyAlert.timestamp,
              close_timestamp: selectedSmartMoneyAlert.timestamp,
              has_imbalance: true,
              imbalance_data: {
                type: selectedSmartMoneyAlert.type,
                direction: selectedSmartMoneyAlert.direction,
                strength: selectedSmartMoneyAlert.strength,
                top: selectedSmartMoneyAlert.top,
                bottom: selectedSmartMoneyAlert.bottom
              },
              is_closed: true,
              message: `Smart Money: ${selectedSmartMoneyAlert.type}`
            }}
            onClose={() => setSelectedSmartMoneyAlert(null)}
          />
        )}

        {showWatchlistModal && (
          <WatchlistModal
            watchlist={watchlist}
            onClose={() => setShowWatchlistModal(false)}
            onUpdate={loadWatchlist}
            onToggleFavorite={toggleFavorite}
          />
        )}

        {showFavoritesModal && (
          <FavoritesModal
            favorites={favorites}
            onClose={() => setShowFavoritesModal(false)}
            onUpdate={loadFavorites}
          />
        )}

        {showStreamModal && (
          <StreamDataModal
            streamData={streamData}
            connectionStatus={connectionStatus}
            onClose={() => setShowStreamModal(false)}
          />
        )}

        {showSettings && (
          <SettingsModal
            settings={settings}
            onClose={() => setShowSettings(false)}
            onSave={handleSettingsSave}
          />
        )}
      </div>
        )}
      </StartupLoader>
    </TimeZoneProvider>
  );
};

export default App;