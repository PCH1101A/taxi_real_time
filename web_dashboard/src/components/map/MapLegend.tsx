import React from 'react';
import { useFleetStore } from '../../store/useFleetStore';

export const MapLegend: React.FC = () => {
  const colorMode = useFleetStore((s) => s.colorMode);
  const layerToggles = useFleetStore((s) => s.layerToggles);

  return (
    <div
      className="glass-panel"
      style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        zIndex: 25,
        pointerEvents: 'auto',
        fontSize: '11px',
      }}
    >
      <div style={{ fontWeight: 700, color: '#94A3B8', letterSpacing: '0.04em' }}>
        MAP LEGEND ({colorMode})
      </div>

      {colorMode === 'TAXI_TYPE' && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#FACC15' }} />
            <span>Yellow Cab</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#22C55E' }} />
            <span>Green Boro Taxi</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#A855F7' }} />
            <span>FHVHV (Uber / Lyft)</span>
          </div>
        </div>
      )}

      {colorMode === 'SPEED' && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#EF4444' }} />
            <span>Heavy Congestion (&lt; 10 mph)</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#F59E0B' }} />
            <span>Moderate (10 - 22 mph)</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38BDF8' }} />
            <span>Cruising (22 - 35 mph)</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#00F5FF' }} />
            <span>Expressway (35+ mph)</span>
          </div>
        </div>
      )}

      {colorMode === 'FARE' && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#22C55E' }} />
            <span>Economy (&lt; $15)</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38BDF8' }} />
            <span>Standard ($15 - $35)</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#F59E0B' }} />
            <span>Surge ($35 - $60)</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#EC4899' }} />
            <span>Airport / Long Haul (&gt; $60)</span>
          </div>
        </div>
      )}

      {colorMode === 'EFFICIENCY' && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#22C55E' }} />
            <span>High Efficiency Route (&ge; 85%)</span>
          </div>
          <div className="flex items-center gap-2">
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#F59E0B' }} />
            <span>Moderate Detour (&lt; 85%)</span>
          </div>
        </div>
      )}

      {layerToggles.demandHeatmap && (
        <div className="flex flex-col gap-1" style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '6px' }}>
          <div className="flex items-center justify-between" style={{ fontSize: '10px', color: '#94A3B8' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#F43F5E' }} />
              Demand Heatmap
            </span>
            <span style={{ fontSize: '9px', color: '#64748B' }}>Normal ── Critical Surge</span>
          </div>
          <div
            style={{
              height: '5px',
              borderRadius: '3px',
              background: 'linear-gradient(to right, #00F5FF, #FACC15, #F97316, #F43F5E)',
            }}
          />
        </div>
      )}

      {layerToggles.airports && (
        <div className="flex items-center gap-2" style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '6px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', border: '2px solid #0EA5E9' }} />
          <span>Major Airport (JFK / LGA / EWR)</span>
        </div>
      )}

      {layerToggles.busiest && (
        <div className="flex items-center gap-2">
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', border: '2px solid #F43F5E', background: 'rgba(244,63,94,0.3)' }} />
          <span>Top Hotspots & Beacons</span>
        </div>
      )}
    </div>
  );
};
