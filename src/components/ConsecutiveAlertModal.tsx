import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Download, Clock, Globe, Info, TrendingUp, BarChart3 } from 'lucide-react';
import TradingViewChart from './TradingViewChart';
import CoinGeckoChart from './CoinGeckoChart';
import ChartModal from './ChartModal';

interface ConsecutiveAlert {
  id: number;
  symbol: string;
  alert_type: 'consecutive_long';
  price: number;
  consecutive_count: number;
  timestamp: string;
  close_timestamp?: string;
  is_closed: boolean;
  has_imbalance: boolean;
  imbalance_data?: any;
  candle_data?: any;
  message: string;
}

interface ConsecutiveAlertModalProps {
  alert: ConsecutiveAlert;
  onClose: () => void;
}

type ChartType = 'tradingview' | 'coingecko' | 'internal' | null;

const ConsecutiveAlertModal: React.FC<ConsecutiveAlertModalProps> = ({ alert, onClose }) => {
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

  const getStrengthColor = (count: number) => {
    if (count >= 10) return 'text-red-600';
    if (count >= 7) return 'text-orange-600';
    if (count >= 5) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getStrengthText = (count: number) => {
    if (count >= 10) return 'Очень сильный';
    if (count >= 7) return 'Сильный';
    if (count >= 5) return 'Умеренный';
    return 'Слабый';
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
              <BarChart3 className="w-6 h-6 mr-2 text-green-600" />
              {alert.symbol}
            </h2>
            <p className="text-gray-600">
              Последовательные LONG свечи • ${alert.price.toFixed(6)}
            </p>
            <div className="flex items-center space-x-4 mt-2">
              <span className={`text-sm font-medium ${getStrengthColor(alert.consecutive_count)}`}>
                {alert.consecutive_count} свечей подряд • {getStrengthText(alert.consecutive_count)}
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
            <div className="bg-green-50 p-4 rounded-lg">
              <h4 className="font-semibold text-green-900 mb-2">Последовательность</h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>LONG свечей:</span>
                  <span className="font-bold text-green-600">{alert.consecutive_count}</span>
                </div>
                <div className="flex justify-between">
                  <span>Сила сигнала:</span>
                  <span className={getStrengthColor(alert.consecutive_count)}>
                    {getStrengthText(alert.consecutive_count)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Статус:</span>
                  <span className="text-green-600">Закрыт</span>
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
            <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-800">{alert.message}</p>
            </div>
          )}

          {/* Candle Visualization */}
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-semibold text-gray-900 mb-3">Визуализация последовательности</h4>
            <div className="flex items-end space-x-1 justify-center">
              {Array.from({ length: Math.min(alert.consecutive_count, 10) }, (_, i) => (
                <div
                  key={i}
                  className="w-4 h-8 bg-green-500 rounded-sm opacity-80"
                  style={{ height: `${20 + (i * 2)}px` }}
                />
              ))}
              {alert.consecutive_count > 10 && (
                <span className="text-sm text-gray-500 ml-2">+{alert.consecutive_count - 10}</span>
              )}
            </div>
            <p className="text-xs text-gray-500 text-center mt-2">
              Каждый столбец = 1 LONG свеча
            </p>
          </div>
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
                <h3 className="text-lg font-semibold text-gray-900">TradingView с трендовыми зонами</h3>
                <p className="text-gray-600">
                  Профессиональные графики с отметками последовательных движений
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Реальное время</span>
                  <span>✓ Трендовые зоны</span>
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
                  Рыночные данные и трендовый анализ
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Рыночная капитализация</span>
                  <span>✓ Трендовые данные</span>
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
                  График на основе собранных данных с трендовым анализом
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Данные алертов</span>
                  <span>✓ Трендовые зоны</span>
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
              <strong>📈 Трендовый анализ:</strong> Выявление устойчивых направленных движений
            </p>
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-green-600">LONG свечи</span> - восходящее движение
              </div>
              <div>
                <span className="text-orange-600">Последовательность</span> - сила тренда
              </div>
              <div>
                <span className="text-red-600">Сильный сигнал</span> - 10+ свечей подряд
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConsecutiveAlertModal;