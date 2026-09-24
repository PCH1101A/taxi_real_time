import React, { useState, useEffect } from 'react';
import { useFleetStore } from '../../store/useFleetStore';
import { Activity, Radio, Cpu, Clock } from 'lucide-react';
import { formatNumber } from '../../lib/colorScales';

export const TopBar: React.FC = () => {
  const wsStatus = useFleetStore((s) => s.wsStatus);
  const kpis = useFleetStore((s) => s.kpis);
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString('en-US', {
          timeZone: 'America/New_York',
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="glass-panel" style={{ height: '56px', margin: '8px 12px 0 12px', padding: '0 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', zIndex: 50 }}>
      {/* Brand & Mission Status */}
      <div className="flex items-center gap-3">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '34px', height: '34px', borderRadius: '8px', background: 'rgba(0, 245, 255, 0.1)', border: '1px solid rgba(0, 245, 255, 0.3)' }}>
          <Radio size={20} className="text-cyan" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontWeight: 800, letterSpacing: '0.05em', fontSize: '15px' }} className="text-cyan">
              NYC FLEET COMMAND
            </span>
            <span style={{ fontSize: '10px', background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8', padding: '2px 6px', borderRadius: '4px', border: '1px solid rgba(56, 189, 248, 0.3)', fontWeight: 600 }}>
              MISSION CONTROL
            </span>
          </div>
          <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '1px' }}>
            Apache Flink Real-Time Telemetry & Spatial Intelligence
          </div>
        </div>
      </div>

      {/* Center KPIs & Engine status */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Cpu size={15} className="text-sky" />
          <span style={{ fontSize: '12px', color: '#94A3B8' }}>Engine:</span>
          <span className="font-mono text-cyan" style={{ fontSize: '12px', fontWeight: 600 }}>
            {kpis.engine || 'Flink 1.18.1'}
          </span>
        </div>

        <div style={{ width: '1px', height: '20px', background: 'rgba(56, 189, 248, 0.2)' }} />

        <div className="flex items-center gap-2">
          <Activity size={15} className="text-yellow" />
          <span style={{ fontSize: '12px', color: '#94A3B8' }}>Events:</span>
          <span className="font-mono text-yellow" style={{ fontSize: '13px', fontWeight: 700 }}>
            {formatNumber(kpis.total_events_processed)}
          </span>
        </div>

        <div style={{ width: '1px', height: '20px', background: 'rgba(56, 189, 248, 0.2)' }} />

        <div className="flex items-center gap-2">
          <span style={{ fontSize: '12px', color: '#94A3B8' }}>Active Fleet:</span>
          <span className="font-mono text-green" style={{ fontSize: '14px', fontWeight: 800 }}>
            {formatNumber(kpis.total_active_vehicles)}
          </span>
        </div>
      </div>

      {/* Right Clock & WS Connection status */}
      <div className="flex items-center gap-4">
        {/* NYC Time */}
        <div className="flex items-center gap-2" style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(56, 189, 248, 0.15)' }}>
          <Clock size={13} className="text-cyan" />
          <span style={{ fontSize: '11px', color: '#94A3B8' }}>NYC EDT:</span>
          <span className="font-mono text-cyan" style={{ fontSize: '12px', fontWeight: 700 }}>
            {timeStr || '--:--:--'}
          </span>
        </div>

        {/* Status Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            borderRadius: '9999px',
            background:
              wsStatus === 'CONNECTED'
                ? 'rgba(34, 197, 94, 0.12)'
                : wsStatus === 'CONNECTING'
                ? 'rgba(245, 158, 11, 0.12)'
                : 'rgba(244, 63, 94, 0.12)',
            border: `1px solid ${
              wsStatus === 'CONNECTED'
                ? 'rgba(34, 197, 94, 0.4)'
                : wsStatus === 'CONNECTING'
                ? 'rgba(245, 158, 11, 0.4)'
                : 'rgba(244, 63, 94, 0.4)'
            }`,
          }}
        >
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor:
                wsStatus === 'CONNECTED' ? '#22C55E' : wsStatus === 'CONNECTING' ? '#F59E0B' : '#F43F5E',
              boxShadow: wsStatus === 'CONNECTED' ? '0 0 8px #22C55E' : 'none',
            }}
          />
          <span
            style={{
              fontSize: '11px',
              fontWeight: 700,
              color: wsStatus === 'CONNECTED' ? '#22C55E' : wsStatus === 'CONNECTING' ? '#F59E0B' : '#F43F5E',
              letterSpacing: '0.04em',
            }}
          >
            {wsStatus}
          </span>
        </div>
      </div>
    </header>
  );
};
