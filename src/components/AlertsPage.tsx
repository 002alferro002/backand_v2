@@ .. @@
-const AlertsPage: React.FC = () => {
+interface AlertsPageProps {
+  startupData?: any;
+}
+
+const AlertsPage: React.FC<AlertsPageProps> = ({ startupData }) => {
   const [alerts, setAlerts] = useState<any[]>([]);
@@ .. @@
   useEffect(() => {
+    // Инициализируем данными из startup
+    if (startupData?.alerts) {
+      setAlerts(startupData.alerts);
+      setLoading(false);
+      console.log('AlertsPage initialized with startup data:', startupData.alerts.length);
+    } else {
+      loadAlerts();
+    }
-    loadAlerts();
-  }, []);
+  }, [startupData]);