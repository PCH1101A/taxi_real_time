import React from 'react';
import { useFleetStore } from '../../store/useFleetStore';
import { Map, Activity, BarChart3 } from 'lucide-react';

const TABS = [
  { id: 0 as const, label: '3D Fleet Command Map', icon: Map, badge: 'Live 60 FPS' },
  { id: 1 as const, label: 'Live Telemetry', icon: Activity, badge: 'Kafka Stream' },
  { id: 2 as const, label: 'Fleet Analytics', icon: BarChart3, badge: 'Deep Intelligence' },
];

export const TabNav: React.FC = () => {
  const activeTab = useFleetStore((s) => s.activeTab);
  const setActiveTab = useFleetStore((s) => s.setActiveTab);

  return (
    <nav
      className="glass-panel"
      style={{
        margin: '8px 12px 0 12px',
        padding: '4px',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        height: '46px',
        zIndex: 40,
      }}
    >
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              borderRadius: '8px',
              border: isActive ? '1px solid rgba(0, 245, 255, 0.4)' : '1px solid transparent',
              background: isActive
                ? 'linear-gradient(180deg, rgba(0, 245, 255, 0.15) 0%, rgba(10, 22, 40, 0.8) 100%)'
                : 'transparent',
              color: isActive ? '#00F5FF' : '#94A3B8',
              cursor: 'pointer',
              transition: 'all 0.18s ease',
              fontWeight: isActive ? 700 : 500,
              fontSize: '13px',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.color = '#F1F5F9';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.color = '#94A3B8';
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            <Icon size={16} color={isActive ? '#00F5FF' : '#94A3B8'} />
            <span>{tab.label}</span>
            <span
              style={{
                fontSize: '10px',
                padding: '1px 5px',
                borderRadius: '4px',
                background: isActive ? 'rgba(0, 245, 255, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                color: isActive ? '#00F5FF' : '#64748B',
                fontWeight: 600,
              }}
            >
              {tab.badge}
            </span>
          </button>
        );
      })}
    </nav>
  );
};
