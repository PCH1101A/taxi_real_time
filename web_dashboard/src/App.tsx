import React from 'react';
import { useFleetStore } from './store/useFleetStore';
import { useFleetWS } from './hooks/useFleetWS';
import { useKpiWS } from './hooks/useKpiWS';
import { TopBar } from './components/layout/TopBar';
import { TabNav } from './components/layout/TabNav';
import { Sidebar } from './components/layout/Sidebar';
import { FleetMap } from './components/map/FleetMap';
import { TelemetryTab } from './components/views/TelemetryTab';
import { AnalyticsTab } from './components/views/AnalyticsTab';

export const App: React.FC = () => {
  // Start WebSocket pipelines
  useFleetWS();
  useKpiWS();

  const activeTab = useFleetStore((s) => s.activeTab);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100vw',
        height: '100vh',
        backgroundColor: '#020B18',
        color: '#F1F5F9',
        overflow: 'hidden',
      }}
    >
      {/* Ops Header */}
      <TopBar />

      {/* 3 Tabs Navigation Bar */}
      <TabNav />

      {/* Main Mission View Area */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {activeTab === 0 && (
          <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
            <Sidebar />
            <div style={{ flex: 1, position: 'relative', height: '100%', margin: '8px 12px 8px 12px', borderRadius: '12px', overflow: 'hidden' }}>
              <FleetMap />
            </div>
          </div>
        )}

        {activeTab === 1 && <TelemetryTab />}

        {activeTab === 2 && <AnalyticsTab />}
      </main>
    </div>
  );
};

export default App;
