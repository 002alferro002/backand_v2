import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Download, Clock, Globe, Info, TrendingUp, Volume2 } from 'lucide-react';
import TradingViewChart from './TradingViewChart';
import CoinGeckoChart from './CoinGeckoChart';
import ChartModal from './ChartModal';

interface VolumeAlert {
  id: number;
  symbol: string;
  alert_type: 'volume_spike' | 'preliminary_volume_spike' | 'final_volume_spike';
  price: number;
  volume_ratio: number;
  current_volume_usdt: number;
  average_volume_usdt: number;
  timestamp: string;
  close_timestamp?: string;
  is_closed: boolean;
  is_true_signal?: boolean;
  has_imbalance: boolean;
  imbalance_data?: any;
  candle_data?: any;
  message: string;
}

interface VolumeAlertModalProps {
  alert: VolumeAlert;
  onClose: () => void;
}

type ChartType = 'tradingview' | 'coingecko' | 'internal' | null;

const VolumeAlertModal: React.FC<VolumeAlertModalProps> = ({ alert, onClose }) => {
  const [selectedChart, setSelectedChart] = useState<ChartType>(null);
  const [relatedAlerts, setRelatedAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRelatedAlerts();
  }, [alert.symbol]);

  const loadRelatedAlerts = async () => {
    try {
      setLoading(true);

      // Загружаем алерты для данного символа за последние 24 часа
      const response = await fetch(`/api/alerts?symbol=${alert.symbol}&limit=50`);
      if (response.ok) {
        const data = await response.json();
        
        // Фильтруем по времени (последние 24 часа)
        const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
        const recentAlerts = data.alerts.filter((a: any) => {
          const alertTime = a.alert_timestamp_ms || new Date(a.timestamp).getTime();
          return alertTime > oneDayAgo;
        });

        setRelatedAlerts(recentAlerts);
      }
    } catch (error) {
      console.error('Ошибка загрузки связанных алертов:', error);
    } finally {
      setLoading(false);
    }
  };

  const getAlertTypeDisplay = (type: string) => {
    switch (type) {
      case 'volume_spike':
        return 'Всплеск объема';
      case 'preliminary_volume_spike':
        return 'Предварительный сигнал';
      case 'final_volume_spike':
        return 'Финальный сигнал';
      default:
        return type;
    }
  };

  const getStatusColor = () => {
    if (!alert.is_closed) return 'text-yellow-600';
    if (alert.is_true_signal) return 'text-green-600';
    return 'text-red-600';
  };

  const getStatusText = () => {
    if (!alert.is_closed) return 'В процессе';
    if (alert.is_true_signal) return 'Истинный сигнал';
    return 'Ложный сигнал';
  };

  if (selectedChart === 'tradingview') {
    return (
      <TradingViewChart
        symbol={alert.symbol}
        alertPrice={alert.price}
        alertTime={alert.close_timestamp || alert.timestamp}
        alerts={[alert, ...relatedAlerts]}
        onClose={onClose}
      />
    );
  }

  if (selectedChart === 'coingecko') {
    return (
      <CoinGeckoChart
        symbol={alert.symbol}
        onClose={onClose}
      />
    );
  }

  if (selectedChart === 'internal') {
    return (
      <ChartModal
        alert={alert}
        onClose={onClose}
      />
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 flex items-center">
              <Volume2 className="w-6 h-6 mr-2 text-blue-600" />
              {alert.symbol}
            </h2>
            <p className="text-gray-600">
              {getAlertTypeDisplay(alert.alert_type)} • ${alert.price.toFixed(6)}
            </p>
            <div className="flex items-center space-x-4 mt-2">
              <span className={`text-sm font-medium ${getStatusColor()}`}>
                {getStatusText()}
              </span>
              <span className="text-sm text-gray-500">
                {loading ? 'Загрузка...' : `${relatedAlerts.length} связанных алертов`}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Alert Details */}
        <div className="p-6 border-b border-gray-200">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <h4 className="font-semibold text-blue-900 mb-2">Объем</h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Превышение:</span>
                  <span className="font-bold text-blue-600">{alert.volume_ratio}x</span>
                </div>
                <div className="flex justify-between">
                  <span>Текущий:</span>
                  <span>${alert.current_volume_usdt.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Средний:</span>
                  <span>${alert.average_volume_usdt.toLocaleString()}</span>
                </div>
              </div>
            </div>

            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-semibold text-gray-900 mb-2">Время</h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Создан:</span>
                  <span>{new Date(alert.timestamp).toLocaleTimeString()}</span>
                </div>
                {alert.close_timestamp && (
                  <div className="flex justify-between">
                    <span>Закрыт:</span>
                    <span>{new Date(alert.close_timestamp).toLocaleTimeString()}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Имбаланс:</span>
                  <span className={alert.has_imbalance ? 'text-green-600' : 'text-gray-400'}>
                    {alert.has_imbalance ? 'Да' : 'Нет'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {alert.message && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">{alert.message}</p>
            </div>
          )}
        </div>

        {/* Chart Options */}
        <div className="p-6 space-y-4">
          {/* TradingView */}
          <button
            onClick={() => setSelectedChart('tradingview')}
            className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center group-hover:bg-blue-200">
                <Globe className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">TradingView с объемными зонами</h3>
                <p className="text-gray-600">
                  Профессиональные графики с отметками объемных всплесков
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Реальное время</span>
                  <span>✓ Объемные зоны</span>
                  <span>✓ Все сигналы программы</span>
                </div>
              </div>
              <div className="text-green-600 font-semibold">Рекомендуется</div>
            </div>
          </button>

          {/* CoinGecko */}
          <button
            onClick={() => setSelectedChart('coingecko')}
            className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-green-500 hover:bg-green-50 transition-all group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center group-hover:bg-green-200">
                <ExternalLink className="w-6 h-6 text-green-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">CoinGecko</h3>
                <p className="text-gray-600">
                  Рыночные данные и объемы торгов
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Рыночная капитализация</span>
                  <span>✓ Объемы торгов</span>
                  <span>✓ Исторические данные</span>
                </div>
              </div>
            </div>
          </button>

          {/* Internal Chart */}
          <button
            onClick={() => setSelectedChart('internal')}
            className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center group-hover:bg-purple-200">
                <Info className="w-6 h-6 text-purple-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">Внутренний график</h3>
                <p className="text-gray-600">
                  График на основе собранных данных с объемным анализом
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Данные алертов</span>
                  <span>✓ Объемные зоны</span>
                  <span>✓ Детальный анализ</span>
                </div>
              </div>
            </div>
          </button>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="text-sm text-gray-600">
            <p className="mb-2">
              <strong>📊 Объемный анализ:</strong> Выявление аномальной торговой активности
            </p>
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-blue-600">Всплеск объема</span> - превышение среднего объема
              </div>
              <div>
                <span className="text-yellow-600">Предварительный</span> - сигнал в процессе
              </div>
              <div>
                <span className="text-green-600">Финальный</span> - подтвержденный сигнал
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VolumeAlertModal;