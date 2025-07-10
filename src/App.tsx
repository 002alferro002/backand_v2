@@ .. @@
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
+import StartupLoader from './components/StartupLoader';
import Dashboard from './components/Dashboard';
@@ .. @@
function App() {
+  const [startupData, setStartupData] = useState<any>(null);
+
+  const handleDataLoaded = (data: any) => {
+    setStartupData(data);
+    console.log('Startup data loaded in App:', data);
+  };

   return (
     <Router>
-      <div className="min-h-screen bg-gray-50">
-        <Routes>
-          <Route path="/" element={<Dashboard />} />
-          <Route path="/settings" element={<Settings />} />
-          <Route path="/alerts" element={<AlertsPage />} />
-          <Route path="/trading" element={<TradingPage />} />
-          <Route path="/social" element={<SocialPage />} />
-        </Routes>
-      </div>
+      <StartupLoader onDataLoaded={handleDataLoaded}>
+        <div className="min-h-screen bg-gray-50">
+          <Routes>
+            <Route path="/" element={<Dashboard startupData={startupData} />} />
+            <Route path="/settings" element={<Settings />} />
+            <Route path="/alerts" element={<AlertsPage startupData={startupData} />} />
+            <Route path="/trading" element={<TradingPage />} />
+            <Route path="/social" element={<SocialPage />} />
+          </Routes>
+        </div>
+      </StartupLoader>
     </Router>
   );
 }