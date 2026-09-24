import React, { useState } from 'react';
import { Flame, ChevronUp, ChevronDown, Target } from 'lucide-react';
import { useFleetStore } from '../../store/useFleetStore';
import { Zone } from '../../lib/types';

interface DemandSurgePanelProps {
  onFlyToZone: (zone: Zone) => void;
}

export const DemandSurgePanel: React.FC<DemandSurgePanelProps> = ({ onFlyToZone }) => {
  const [collapsed, setCollapsed] = useState(false);
  const topZones = useFleetStore((s) => s.topZones);

  // Take top 4-5 high demand zones
  const surgeZones = topZones.slice(0, 4);

  if (surgeZones.length === 0) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: '16px',
        left: '16px',
        zIndex: 25,
        width: '280px',
        background: 'rgba(10, 22, 40, 0.88)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(56, 189, 248, 0.22)',
        borderRadius: '10px',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.55)',
        overflow: 'hidden',
        pointerEvents: 'auto',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          borderBottom: collapsed ? 'none' : '1px solid rgba(56, 189, 248, 0.12)',
          background: 'rgba(15, 23, 42, 0.6)',
          cursor: 'pointer',
        }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Flame size={15} style={{ color: '#F43F5E' }} />
          <span
            style={{
              fontSize: '11px',
              fontWeight: 800,
              color: '#F1F5F9',
              letterSpacing: '0.06em',
            }}
          >
            DEMAND SURGE HOTSPOTS
          </span>
        </div>
        <button
          style={{
            background: 'transparent',
            border: 'none',
            color: '#94A3B8',
            cursor: 'pointer',
            padding: '2px',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>

      {/* Content */}
      {!collapsed && (
        <div style={{ padding: '8px 12px 10px 12px' }}>
          {/* Table Header */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '9.5px',
              fontWeight: 700,
              color: '#64748B',
              letterSpacing: '0.04em',
              paddingBottom: '6px',
              borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
              marginBottom: '6px',
            }}
          >
            <span>TOP HIGH-DEMAND ZONES</span>
            <span>EST. SURGE</span>
          </div>

          {/* Zone list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {surgeZones.map((z, idx) => {
              const tripCount = z.vehicle_count || Math.max(12, 45 - idx * 8);
              // Calculate representative surge multiplier (e.g. 4.5x, 3.8x)
              const estSurge = (Math.max(2.0, Math.min(4.8, (tripCount / 10) * 1.2))).toFixed(1) + 'x';

              return (
                <div
                  key={z.zone_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '5px 6px',
                    borderRadius: '6px',
                    background: 'rgba(255, 255, 255, 0.02)',
                    transition: 'background 0.2s',
                  }}
                  className="hover:bg-slate-800/40"
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 800,
                        color: idx === 0 ? '#F43F5E' : '#38BDF8',
                        width: '16px',
                      }}
                    >
                      #{idx + 1}
                    </span>
                    <div>
                      <div
                        style={{
                          fontSize: '11.5px',
                          fontWeight: 700,
                          color: '#F1F5F9',
                          lineHeight: 1.2,
                        }}
                      >
                        {z.zone_name}
                      </div>
                      <div style={{ fontSize: '9.5px', color: '#94A3B8', marginTop: '2px' }}>
                        {z.borough} • {tripCount} trips
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontWeight: 800,
                        color: '#F43F5E',
                      }}
                    >
                      {estSurge}
                    </span>
                    <button
                      onClick={() => onFlyToZone(z)}
                      title={`Fly camera to ${z.zone_name}`}
                      style={{
                        background: 'rgba(56, 189, 248, 0.1)',
                        border: '1px solid rgba(56, 189, 248, 0.25)',
                        borderRadius: '4px',
                        padding: '3px',
                        color: '#38BDF8',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Target size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
