import React, { useMemo } from 'react';
import { useFleetStore } from '../../store/useFleetStore';

export const TerritoryBar: React.FC = () => {
  const territoryCounts = useFleetStore((s) => s.territoryCounts);

  const stats = useMemo(() => {
    const y = territoryCounts.YELLOW || 0;
    const g = territoryCounts.GREEN || 0;
    const f = territoryCounts.FHVHV || 0;
    const total = y + g + f || 1;

    return {
      yellowCount: y,
      greenCount: g,
      fhvhvCount: f,
      yellowPct: ((y / total) * 100).toFixed(1),
      greenPct: ((g / total) * 100).toFixed(1),
      fhvhvPct: ((f / total) * 100).toFixed(1),
      totalCaptured: y + g + f,
    };
  }, [territoryCounts]);

  return (
    <div
      className="glass-card"
      style={{
        padding: '12px 16px',
        marginBottom: '10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            ZONE TERRITORY DOMINANCE BATTLEFIELD
          </span>
          <span style={{ fontSize: '10px', background: 'rgba(0, 245, 255, 0.1)', color: '#00F5FF', padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>
            {stats.totalCaptured} CONTESTED ZONES
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <span style={{ color: '#FACC15' }}>Yellow: {stats.yellowCount} ({stats.yellowPct}%)</span>
          <span style={{ color: '#22C55E' }}>Green: {stats.greenCount} ({stats.greenPct}%)</span>
          <span style={{ color: '#A855F7' }}>FHVHV: {stats.fhvhvCount} ({stats.fhvhvPct}%)</span>
        </div>
      </div>

      {/* Tri-color Segmented Bar */}
      <div style={{ height: '8px', width: '100%', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${stats.yellowPct}%`, background: '#FACC15', transition: 'width 0.5s ease' }} />
        <div style={{ width: `${stats.greenPct}%`, background: '#22C55E', transition: 'width 0.5s ease' }} />
        <div style={{ width: `${stats.fhvhvPct}%`, background: '#A855F7', transition: 'width 0.5s ease' }} />
      </div>
    </div>
  );
};
