import { useState, useEffect } from 'react';

interface StartupData {
  alerts: any[];
  watchlist: string[];
  favorites: any[];
  settings: any;
  trading_settings: any;
  data_integrity: any;
}

interface UseStartupDataReturn {
  data: StartupData | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export const useStartupData = (): UseStartupDataReturn => {
  const [data, setData] = useState<StartupData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Загружаем данные напрямую из основных API эндпоинтов
      const [alertsResponse, watchlistResponse, favoritesResponse, settingsResponse] = await Promise.all([
        fetch('/api/alerts/all'),
        fetch('/api/watchlist'),
        fetch('/api/favorites'),
        fetch('/api/settings')
      ]);

      const alerts = alertsResponse.ok ? await alertsResponse.json() : { volume_alerts: [], consecutive_alerts: [], priority_alerts: [] };
      const watchlist = watchlistResponse.ok ? await watchlistResponse.json() : { pairs: [] };
      const favorites = favoritesResponse.ok ? await favoritesResponse.json() : { favorites: [] };
      const settings = settingsResponse.ok ? await settingsResponse.json() : {};

      const startupData = {
        alerts: [
          ...(alerts.volume_alerts || []),
          ...(alerts.consecutive_alerts || []),
          ...(alerts.priority_alerts || [])
        ],
        watchlist: watchlist.pairs?.map((p: any) => p.symbol) || [],
        favorites: favorites.favorites || [],
        settings: settings,
        trading_settings: {},
        data_integrity: {}
      };

      setData(startupData);
      
      console.log('Данные при запуске загружены:', {
        alerts: startupData.alerts?.length || 0,
        watchlist: startupData.watchlist?.length || 0,
        favorites: startupData.favorites?.length || 0,
        settings: Object.keys(startupData.settings || {}).length
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(errorMessage);
      console.error('Ошибка загрузки данных при запуске:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadDataOld = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/startup/data');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const startupData = await response.json();
      setData(startupData);
      
      console.log('Данные при запуске загружены:', {
        alerts: startupData.alerts?.length || 0,
        watchlist: startupData.watchlist?.length || 0,
        favorites: startupData.favorites?.length || 0,
        settings: Object.keys(startupData.settings || {}).length,
        data_integrity: Object.keys(startupData.data_integrity || {}).length
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(errorMessage);
      console.error('Ошибка загрузки данных при запуске:', err);
    } finally {
      setLoading(false);
    }
  };

  const reload = async () => {
    try {
      setError(null);
      
      // Сначала запрашиваем перезагрузку на сервере
      const reloadResponse = await fetch('/api/startup/data/reload', {
        method: 'POST'
      });
      
      if (reloadResponse.ok) {
        const reloadData = await reloadResponse.json();
        setData(reloadData.data);
      } else {
        // Если перезагрузка не удалась, просто загружаем данные заново
        await loadData();
      }
    } catch (err) {
      console.error('Ошибка перезагрузки данных:', err);
      // При ошибке перезагрузки пробуем обычную загрузку
      await loadData();
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return {
    data,
    loading,
    error,
    reload
  };
};

export default useStartupData;