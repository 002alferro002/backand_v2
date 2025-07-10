import React from 'react';
import { Loader2, Database, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import { useStartupData } from '../hooks/useStartupData';

interface StartupLoaderProps {
  onDataLoaded: (data: any) => void;
  children: React.ReactNode;
}

const StartupLoader: React.FC<StartupLoaderProps> = ({ onDataLoaded, children }) => {
  const { data, loading, error, reload } = useStartupData();

  React.useEffect(() => {
    if (data && !loading) {
      onDataLoaded(data);
    }
  }, [data, loading, onDataLoaded]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Загрузка CryptoScan
            </h2>
            <p className="text-gray-600 mb-6">
              Инициализация системы и загрузка данных...
            </p>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                <div className="flex items-center">
                  <Database className="w-5 h-5 text-blue-600 mr-2" />
                  <span className="text-sm text-blue-900">Подключение к базе данных</span>
                </div>
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              
              <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                <div className="flex items-center">
                  <AlertTriangle className="w-5 h-5 text-yellow-600 mr-2" />
                  <span className="text-sm text-yellow-900">Загрузка алертов</span>
                </div>
                <Loader2 className="w-5 h-5 text-yellow-600 animate-spin" />
              </div>
              
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <RefreshCw className="w-5 h-5 text-gray-600 mr-2" />
                  <span className="text-sm text-gray-900">Проверка целостности данных</span>
                </div>
                <Loader2 className="w-5 h-5 text-gray-600 animate-spin" />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <AlertTriangle className="w-12 h-12 text-red-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Ошибка загрузки
            </h2>
            <p className="text-gray-600 mb-6">
              Не удалось загрузить данные при запуске
            </p>
            
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-red-800">{error}</p>
            </div>
            
            <button
              onClick={reload}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Повторить загрузку
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <AlertTriangle className="w-12 h-12 text-yellow-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Нет данных
            </h2>
            <p className="text-gray-600 mb-6">
              Данные не были загружены
            </p>
            
            <button
              onClick={reload}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Загрузить данные
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

export default StartupLoader;