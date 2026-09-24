import React from 'react';
import { useFleetStore } from '../../store/useFleetStore';
import { FleetType } from '../../lib/types';
import { Filter, Layers, Palette, Compass, MapPin } from 'lucide-react';

const BOROUGHS = ['ALL', 'Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island'];

const FLEET_TYPES: { type: FleetType; label: string; color: string }[] = [
  { type: 'YELLOW', label: 'Yellow Cab', color: '#FACC15' },
  { type: 'GREEN', label: 'Green Boro', color: '#22C55E' },
  { type: 'FHVHV', label: 'FHVHV (Uber/Lyft)', color: '#A855F7' },
];

export const Sidebar: React.FC = () => {
  const selectedBorough = useFleetStore((s) => s.selectedBorough);
  const setSelectedBorough = useFleetStore((s) => s.setSelectedBorough);

  const allowedSources = useFleetStore((s) => s.allowedSources);
  const toggleFleetType = useFleetStore((s) => s.toggleFleetType);

  const colorMode = useFleetStore((s) => s.colorMode);
  const setColorMode = useFleetStore((s) => s.setColorMode);

  const mapTheme = useFleetStore((s) => s.mapTheme);
  const setMapTheme = useFleetStore((s) => s.setMapTheme);

  const layerToggles = useFleetStore((s) => s.layerToggles);
  const toggleLayer = useFleetStore((s) => s.toggleLayer);

  return (
    <aside
      className="glass-panel"
      style={{
        width: '280px',
        margin: '8px 0 8px 12px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        overflowY: 'auto',
        zIndex: 30,
      }}
    >
      {/* Title */}
      <div className="flex items-center gap-2" style={{ borderBottom: '1px solid rgba(56, 189, 248, 0.15)', paddingBottom: '10px' }}>
        <Filter size={16} className="text-cyan" />
        <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.04em' }}>
          CONTROL TELEMETRY
        </span>
      </div>

      {/* Borough Filter */}
      <div className="flex flex-col gap-2">
        <label style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <MapPin size={13} className="text-sky" />
          BOROUGH REGION
        </label>
        <select
          value={selectedBorough}
          onChange={(e) => setSelectedBorough(e.target.value)}
          style={{
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            color: '#F1F5F9',
            padding: '8px 10px',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          {BOROUGHS.map((b) => (
            <option key={b} value={b} style={{ background: '#0A1628', color: '#F1F5F9' }}>
              {b === 'ALL' ? '🌐 All Boroughs (Full NYC)' : b}
            </option>
          ))}
        </select>
      </div>

      {/* Fleet Type Selector */}
      <div className="flex flex-col gap-2">
        <label style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={13} className="text-yellow" />
          FLEET CLASSIFICATION
        </label>
        <div className="flex flex-col gap-2">
          {FLEET_TYPES.map(({ type, label, color }) => {
            const isChecked = allowedSources.includes(type);
            return (
              <button
                key={type}
                type="button"
                onClick={() => toggleFleetType(type)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '7px 10px',
                  borderRadius: '6px',
                  background: isChecked ? 'rgba(15, 23, 42, 0.8)' : 'rgba(15, 23, 42, 0.3)',
                  border: isChecked ? `1px solid ${color}` : '1px solid rgba(255, 255, 255, 0.08)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div className="flex items-center gap-2">
                  <div
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      backgroundColor: color,
                      boxShadow: isChecked ? `0 0 8px ${color}` : 'none',
                    }}
                  />
                  <span style={{ fontSize: '12px', color: isChecked ? '#F1F5F9' : '#64748B', fontWeight: isChecked ? 600 : 400 }}>
                    {label}
                  </span>
                </div>
                <span style={{ fontSize: '10px', color: isChecked ? color : '#64748B', fontWeight: 700 }}>
                  {isChecked ? 'ACTIVE' : 'MUTED'}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Color Mode Selector */}
      <div className="flex flex-col gap-2">
        <label style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Palette size={13} className="text-cyan" />
          VEHICLE COLOR MODE
        </label>
        <select
          value={colorMode}
          onChange={(e) => setColorMode(e.target.value as any)}
          style={{
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            color: '#F1F5F9',
            padding: '8px 10px',
            borderRadius: '6px',
            fontSize: '12px',
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          <option value="TAXI_TYPE" style={{ background: '#0A1628' }}>🚕 Fleet Type (Yellow/Green/FHV)</option>
          <option value="SPEED" style={{ background: '#0A1628' }}>⚡ Velocity (Congested vs Cruising)</option>
          <option value="FARE" style={{ background: '#0A1628' }}>💵 In-flight Fare Amount ($)</option>
          <option value="EFFICIENCY" style={{ background: '#0A1628' }}>🎯 Route Efficiency Rating</option>
        </select>
      </div>

      {/* Map Theme */}
      <div className="flex flex-col gap-2">
        <label style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Compass size={13} className="text-sky" />
          CARTOGRAPHIC BASEMAP
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
          {(['DARK', 'VOYAGER', 'LIGHT'] as const).map((t) => {
            const isSelected = mapTheme === t;
            return (
              <button
                key={t}
                onClick={() => setMapTheme(t)}
                style={{
                  padding: '6px 4px',
                  borderRadius: '6px',
                  border: isSelected ? '1px solid #00F5FF' : '1px solid rgba(255, 255, 255, 0.1)',
                  background: isSelected ? 'rgba(0, 245, 255, 0.15)' : 'rgba(15, 23, 42, 0.6)',
                  color: isSelected ? '#00F5FF' : '#94A3B8',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {t === 'DARK' ? 'Dark' : t === 'VOYAGER' ? 'Voyager' : 'Light'}
              </button>
            );
          })}
        </div>
      </div>

      {/* Layer Toggles */}
      <div className="flex flex-col gap-2" style={{ borderTop: '1px solid rgba(56, 189, 248, 0.15)', paddingTop: '12px' }}>
        <label style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8' }}>SPATIAL OVERLAYS</label>
        <div className="flex flex-col gap-2">
          {[
            { key: 'vehicles' as const, label: 'Active Fleet Vehicles' },
            { key: 'demandHeatmap' as const, label: 'Demand Surge Heatmap' },
            { key: 'busiest' as const, label: 'Top Hotspots & Beacons' },
            { key: 'airports' as const, label: 'NYC Airports (JFK/LGA/EWR)' },
          ].map(({ key, label }) => {
            const active = layerToggles[key];
            return (
              <label
                key={key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '12px',
                  color: active ? '#F1F5F9' : '#64748B',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggleLayer(key)}
                  style={{ accentColor: '#00F5FF', width: '14px', height: '14px', cursor: 'pointer' }}
                />
                {label}
              </label>
            );
          })}
        </div>
      </div>
    </aside>
  );
};
