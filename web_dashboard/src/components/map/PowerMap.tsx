import React, { useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { Map as MapLibreMap } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import { useFleetStore } from '../../store/useFleetStore';
import { buildPowerMapLayers } from '../../lib/deckLayers';
import { TerritoryBar } from '../analytics/TerritoryBar';
import { Zone } from '../../lib/types';
import { FLEET_COLORS } from '../../lib/colorScales';
import { Swords, ShieldAlert, Award } from 'lucide-react';

const MAP_STYLE_DARK = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const INITIAL_VIEW_STATE = {
  longitude: -73.9712,
  latitude: 40.7589,
  zoom: 11.2,
  pitch: 35,
  bearing: 0,
  maxZoom: 18,
  minZoom: 9,
};

export const PowerMap: React.FC = () => {
  const zones = useFleetStore((s) => s.zones);
  const topZones = useFleetStore((s) => s.topZones);
  const invasionZones = useFleetStore((s) => s.invasionZones);

  const [hoverInfo, setHoverInfo] = useState<any>(null);
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null);

  const displayZones = useMemo(() => {
    return zones.length > 0 ? zones : topZones;
  }, [zones, topZones]);

  const layers = useMemo(() => {
    return buildPowerMapLayers({
      zones: displayZones,
      invasionZones,
      onSelectZone: (z) => setSelectedZone(z),
    });
  }, [displayZones, invasionZones]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Top Territory Bar */}
      <div style={{ margin: '8px 12px 0 12px', zIndex: 10 }}>
        <TerritoryBar />
      </div>

      <div style={{ position: 'relative', flex: 1, margin: '0 12px 12px 12px', borderRadius: '12px', overflow: 'hidden' }}>
        <DeckGL
          initialViewState={INITIAL_VIEW_STATE}
          controller={{ doubleClickZoom: false }}
          layers={layers}
          getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'default')}
          onHover={(info) => setHoverInfo(info)}
        >
          <MapLibreMap mapLib={maplibregl} mapStyle={MAP_STYLE_DARK} attributionControl={false} />
        </DeckGL>

        {/* Hover Tooltip */}
        {hoverInfo && hoverInfo.object && (
          <div
            style={{
              position: 'absolute',
              left: hoverInfo.x + 12,
              top: hoverInfo.y + 12,
              pointerEvents: 'none',
              zIndex: 100,
              background: 'rgba(10, 22, 40, 0.94)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(0, 245, 255, 0.4)',
              borderRadius: '8px',
              padding: '10px 14px',
              color: '#F1F5F9',
              fontSize: '12px',
              minWidth: '200px',
            }}
          >
            <div style={{ fontWeight: 800, color: '#00F5FF', marginBottom: '4px' }}>
              {hoverInfo.object.zone_name}
            </div>
            <div style={{ color: '#94A3B8', fontSize: '11px', marginBottom: '6px' }}>
              Borough: {hoverInfo.object.borough} &middot; Total Units: {hoverInfo.object.vehicle_count || 0}
            </div>
            <div className="flex items-center justify-between" style={{ fontSize: '11px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '6px' }}>
              <span>Dominant Fleet:</span>
              <span
                style={{
                  fontWeight: 700,
                  color: FLEET_COLORS[hoverInfo.object.dominant_fleet as 'YELLOW']?.hex || '#94A3B8',
                }}
              >
                {hoverInfo.object.dominant_fleet || 'NONE'}
              </span>
            </div>
          </div>
        )}

        {/* Right Intel Feed */}
        <aside
          className="glass-panel"
          style={{
            position: 'absolute',
            top: '12px',
            right: '12px',
            bottom: '12px',
            width: '320px',
            padding: '14px',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 25,
            pointerEvents: 'auto',
          }}
        >
          <div className="flex items-center gap-2" style={{ paddingBottom: '10px', borderBottom: '1px solid rgba(56, 189, 248, 0.15)' }}>
            <Swords size={16} className="text-yellow" />
            <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.04em' }}>
              ZONE DOMINANCE FEED
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', marginTop: '10px' }} className="flex flex-col gap-2">
            {topZones.map((z) => {
              const dom = z.dominant_fleet as 'YELLOW' | 'GREEN' | 'FHVHV';
              const col = FLEET_COLORS[dom]?.hex || '#94A3B8';
              const isSelected = selectedZone?.zone_id === z.zone_id;

              return (
                <div
                  key={z.zone_id}
                  onClick={() => setSelectedZone(z)}
                  className="glass-card"
                  style={{
                    padding: '10px',
                    cursor: 'pointer',
                    borderColor: isSelected ? '#00F5FF' : undefined,
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#F1F5F9' }}>
                      {z.zone_name}
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        color: col,
                        background: 'rgba(255,255,255,0.05)',
                        padding: '2px 5px',
                        borderRadius: '4px',
                      }}
                    >
                      {dom || 'CONTESTED'}
                    </span>
                  </div>

                  <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '3px' }}>
                    {z.borough} &middot; {z.vehicle_count} active cabs
                  </div>

                  {z.fleet_breakdown && (
                    <div className="flex items-center gap-3 font-mono" style={{ marginTop: '6px', fontSize: '10px' }}>
                      <span style={{ color: '#FACC15' }}>Y: {z.fleet_breakdown.YELLOW || 0}</span>
                      <span style={{ color: '#22C55E' }}>G: {z.fleet_breakdown.GREEN || 0}</span>
                      <span style={{ color: '#A855F7' }}>F: {z.fleet_breakdown.FHVHV || 0}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </aside>
      </div>
    </div>
  );
};
