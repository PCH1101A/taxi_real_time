import React from 'react';
import { useFleetStore } from '../../store/useFleetStore';
import { FLEET_COLORS, formatCurrency } from '../../lib/colorScales';

export const LiveFeedTable: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);
  const setSelectedTripId = useFleetStore((s) => s.setSelectedTripId);
  const setActiveTab = useFleetStore((s) => s.setActiveTab);

  const topVehicles = vehicles.slice(0, 25);

  const handleRowClick = (tripId: string) => {
    setSelectedTripId(tripId);
    setActiveTab(0); // Switch to map tab to track
  };

  return (
    <div className="glass-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', height: '320px' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '12px' }}>
        <div className="flex items-center gap-2">
          <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            MICRO-BATCH TELEMETRY FEED (TOP ACTIVE TRIPS)
          </span>
          <span style={{ fontSize: '10px', background: 'rgba(0, 245, 255, 0.1)', color: '#00F5FF', padding: '2px 6px', borderRadius: '4px', border: '1px solid rgba(0, 245, 255, 0.25)', fontWeight: 600 }}>
            LIVE REFRESH 2s
          </span>
        </div>
        <span style={{ fontSize: '11px', color: '#94A3B8' }}>
          Showing 25 / {vehicles.length} units &middot; Click row to inspect on 3D map
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(56, 189, 248, 0.2)', color: '#94A3B8' }}>
              <th style={{ padding: '6px 8px' }}>TRIP ID</th>
              <th style={{ padding: '6px 8px' }}>FLEET</th>
              <th style={{ padding: '6px 8px' }}>PICKUP HUB</th>
              <th style={{ padding: '6px 8px' }}>DROPOFF HUB</th>
              <th style={{ padding: '6px 8px' }}>SPEED</th>
              <th style={{ padding: '6px 8px' }}>FARE</th>
              <th style={{ padding: '6px 8px' }}>PROGRESS</th>
            </tr>
          </thead>
          <tbody>
            {topVehicles.map((v) => {
              const fleet = FLEET_COLORS[v.dataset_source];
              return (
                <tr
                  key={v.trip_id}
                  onClick={() => handleRowClick(v.trip_id)}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(0, 245, 255, 0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <td className="font-mono" style={{ padding: '8px', fontWeight: 700, color: '#00F5FF' }}>
                    {v.trip_id}
                  </td>
                  <td style={{ padding: '8px' }}>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: 'rgba(255, 255, 255, 0.06)',
                        color: fleet?.hex,
                        fontWeight: 700,
                        fontSize: '10px',
                      }}
                    >
                      {v.dataset_source}
                    </span>
                  </td>
                  <td style={{ padding: '8px', color: '#E2E8F0' }}>
                    {v.zone_name} <span style={{ color: '#64748B' }}>({v.borough})</span>
                  </td>
                  <td style={{ padding: '8px', color: '#94A3B8' }}>
                    {v.dropoff_zone_name || 'In-transit'}
                  </td>
                  <td className="font-mono text-yellow" style={{ padding: '8px' }}>
                    {v.speed_mph.toFixed(1)} mph
                  </td>
                  <td className="font-mono text-green" style={{ padding: '8px' }}>
                    {formatCurrency(v.fare_amount)}
                  </td>
                  <td style={{ padding: '8px', minWidth: '100px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ flex: 1, height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div
                          style={{
                            height: '100%',
                            width: `${Math.round(v.progress_ratio * 100)}%`,
                            background: '#00F5FF',
                          }}
                        />
                      </div>
                      <span className="font-mono text-cyan" style={{ fontSize: '10px' }}>
                        {Math.round(v.progress_ratio * 100)}%
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
