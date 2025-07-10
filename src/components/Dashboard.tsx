interface DashboardProps {
  startupData?: any;
}

const Dashboard: React.FC<DashboardProps> = ({ startupData }) => {
  const [alerts, setAlerts] = useState<any[]>([]);
  useEffect(() => {
    // Инициализируем данными из startup
    if (startupData) {
      setAlerts(startupData.alerts || []);
      setWatchlist(startupData.watchlist || []);
      console.log('Dashboard initialized with startup data:', {
        alerts: startupData.alerts?.length || 0,
        watchlist: startupData.watchlist?.length || 0
      });
    }

    // Подключение к WebSocket
  }, [startupData]);
}