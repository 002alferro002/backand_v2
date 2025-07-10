import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Download, Clock, Globe, Info, Star, Zap } from 'lucide-react';
import TradingViewChart from './TradingViewChart';
import CoinGeckoChart from './CoinGeckoChart';
import ChartModal from './ChartModal';

interface PriorityAlert {
  id: number;
  symbol: string;
  alert_type: 'priority';
  price: number;
  consecutive_count: number;
  volume_ratio?: number;
  current_volume_usdt?: number;
  average_volume_usdt?: number;
  timestamp: string;
  close_timestamp?: string;
  is_closed: boolean;
  has_imbalance: boolean;
  imbalance_data?: any;
  candle_data?: any;
  message: string;
}

interface PriorityAlertModalProps {
  alert: PriorityAlert;
  onClose: () => void;
}

type ChartType = 'tradingview' | 'coingecko' | 'internal' | null;

const PriorityAlertModal: React.FC<PriorityAlertModalProps> = ({ alert, onClose }) => {
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

  const getPriorityLevel = () => {
    let score = 0;
    
    // Очки за последовательность
    if (alert.consecutive_count >= 10) score += 3;
    else if (alert.consecutive_count >= 7) score += 2;
    else if (alert.consecutive_count >= 5) score += 1;
    
    // Очки за объем
    if (alert.volume_ratio) {
      if (alert.volume_ratio >= 5) score += 3;
      else if (alert.volume_ratio >= 3) score += 2;
      else if (alert.volume_ratio >= 2) score += 1;
    }
    
    // Очки за имбаланс
    if (alert.has_imbalance) score += 2;
    
    if (score >= 7) return { level: 'Критический', color: 'text-red-600', bg: 'bg-red-50' };
    if (score >= 5) return { level: 'Высокий', color: 'text-orange-600', bg: 'bg-orange-50' };
    if (score >= 3) return { level: 'Средний', color: 'text-yellow-600', bg: 'bg-yellow-50' };
    return { level: 'Низкий', color: 'text-green-600', bg: 'bg-green-50' };
  };

  const priorityInfo = getPriorityLevel();

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
              <Star className="w-6 h-6 mr-2 text-yellow-500" />
              {alert.symbol}
            </h2>
            <p className="text-gray-600">
              Приоритетный сигнал • ${alert.price.toFixed(6)}
            </p>
            <div className="flex items-center space-x-4 mt-2">
              <span className={`text-sm font-medium px-2 py-1 rounded ${priorityInfo.bg} ${priorityInfo.color}`}>
                Приоритет: {priorityInfo.level}
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
            <div className="bg-yellow-50 p-4 rounded-lg">
              <h4 className="font-semibold text-yellow-900 mb-2 flex items-center">
                <Zap className="w-4 h-4 mr-1" />
                Комбинированный сигнал
              </h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>LONG свечей:</span>
                  <span className="font-bold text-yellow-600">{alert.consecutive_count}</span>
                </div>
                {alert.volume_ratio && (
                  <div className="flex justify-between">
                    <span>Объем:</span>
                    <span className="font-bold text-yellow-600">{alert.volume_ratio}x</span>
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

            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-semibold text-gray-900 mb-2">Детали</h4>
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
                {alert.current_volume_usdt && (
                  <div className="flex justify-between">
                    <span>Объем USDT:</span>
                    <span>${alert.current_volume_usdt.toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {alert.message && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">{alert.message}</p>
            </div>
          )}

          {/* Priority Score Breakdown */}
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-semibold text-gray-900 mb-3">Расчет приоритета</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Последовательность ({alert.consecutive_count} свечей):</span>
                <span className="font-medium">
                  {alert.consecutive_count >= 10 ? '★★★' : 
                   alert.consecutive_count >= 7 ? '★★☆' : 
                   alert.consecutive_count >= 5 ? '★☆☆' : '☆☆☆'}
                </span>
              </div>
              {alert.volume_ratio && (
                <div className="flex justify-between">
                  <span>Объем ({alert.volume_ratio}x):</span>
                  <span className="font-medium">
                    {alert.volume_ratio >= 5 ? '★★★' : 
                     alert.volume_ratio >= 3 ? '★★☆' : 
                     alert.volume_ratio >= 2 ? '★☆☆' : '☆☆☆'}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Smart Money имбаланс:</span>
                <span className="font-medium">
                  {alert.has_imbalance ? '★★☆' : '☆☆☆'}
                </span>
              </div>
            </div>
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
                <h3 className="text-lg font-semibold text-gray-900">TradingView с приоритетными зонами</h3>
                <p className="text-gray-600">
                  Профессиональные графики с отметками всех сигналов
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Реальное время</span>
                  <span>✓ Все типы зон</span>
                  <span>✓ Приоритетные сигналы</span>
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
                  Рыночные данные и комплексный анализ
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Рыночная капитализация</span>
                  <span>✓ Комплексные данные</span>
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
                  График на основе собранных данных с комплексным анализом
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Данные алертов</span>
                  <span>✓ Все типы зон</span>
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
              <strong>⭐ Приоритетный анализ:</strong> Комбинация нескольких сильных сигналов
            </p>
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-yellow-600">Комбинированный</span> - несколько сигналов
              </div>
              <div>
                <span className="text-orange-600">Высокий приоритет</span> - сильные сигналы
              </div>
              <div>
                <span className="text-red-600">Критический</span> - максимальная сила
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PriorityAlertModal;