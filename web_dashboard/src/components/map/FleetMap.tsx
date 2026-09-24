import React, { useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { Map as MapLibreMap } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import { useFleetStore } from '../../store/useFleetStore';
import { buildFleetLayers } from '../../lib/deckLayers';
import { MapLegend } from './MapLegend';
import { FleetDispatch } from './FleetDispatch';
import { DemandSurgePanel } from './DemandSurgePanel';
import { Vehicle, Zone } from '../../lib/types';
import { FLEET_COLORS, formatCurrency } from '../../lib/colorScales';

const MAP_STYLES = {
  VOYAGER: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
  DARK: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  LIGHT: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
};

const INITIAL_VIEW_STATE = {
  longitude: -73.9712,
  latitude: 40.7589,
  zoom: 11.6,
  pitch: 45,
  bearing: -15,
  maxZoom: 18,
  minZoom: 9,
};

export const FleetMap: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);
  const topZones = useFleetStore((s) => s.topZones);
  const selectedTripId = useFleetStore((s) => s.selectedTripId);
  const setSelectedTripId = useFleetStore((s) => s.setSelectedTripId);
  const setTrackedRoute = useFleetStore((s) => s.setTrackedRoute);
  const trackedRoute = useFleetStore((s) => s.trackedRoute);
  const colorMode = useFleetStore((s) => s.colorMode);
  const mapTheme = useFleetStore((s) => s.mapTheme);
  const layerToggles = useFleetStore((s) => s.layerToggles);
  const selectedBorough = useFleetStore((s) => s.selectedBorough);
  const allowedSources = useFleetStore((s) => s.allowedSources);

  const [hoverInfo, setHoverInfo] = useState<any>(null);
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  // Filtered vehicles
  const filteredVehicles = useMemo(() => {
    return vehicles.filter((v) => {
      if (selectedBorough !== 'ALL' && v.borough !== selectedBorough) return false;
      if (!allowedSources.includes(v.dataset_source)) return false;
      return true;
    });
  }, [vehicles, selectedBorough, allowedSources]);

  const selectedVehicle = useMemo(() => {
    return vehicles.find((v) => v.trip_id === selectedTripId) || null;
  }, [vehicles, selectedTripId]);

  const handleSelectVehicle = async (v: Vehicle) => {
    if (selectedTripId === v.trip_id) {
      setSelectedTripId(null);
      return;
    }
    setSelectedTripId(v.trip_id);

    // Smooth camera fly-to
    setViewState((prev) => ({
      ...prev,
      longitude: v.lng,
      latitude: v.lat,
      zoom: 13.5,
      pitch: 50,
      transitionDuration: 800,
    } as any));

    try {
      const resp = await fetch(
        `/api/v1/route?s_lng=${v.start_lng}&s_lat=${v.start_lat}&t_lng=${v.target_lng}&t_lat=${v.target_lat}`
      );
      if (resp.ok) {
        const routeData = await resp.json();
        setTrackedRoute(routeData);
      }
    } catch (e) {
      console.warn('Failed to load route:', e);
    }
  };

  const handleFlyToZone = (zone: Zone) => {
    setViewState((prev) => ({
      ...prev,
      longitude: zone.lng,
      latitude: zone.lat,
      zoom: 13.2,
      pitch: 45,
      transitionDuration: 900,
    } as any));
  };

  const layers = useMemo(() => {
    return buildFleetLayers({
      vehicles: filteredVehicles,
      topZones,
      selectedVehicle,
      trackedRoute,
      colorMode,
      layerToggles,
      onSelectVehicle: handleSelectVehicle,
    });
  }, [
    filteredVehicles,
    topZones,
    selectedVehicle,
    trackedRoute,
    colorMode,
    layerToggles,
  ]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={(e: any) => setViewState(e.viewState)}
        controller={{ doubleClickZoom: false }}
        layers={layers}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'default')}
        onHover={(info) => setHoverInfo(info)}
      >
        <MapLibreMap
          mapLib={maplibregl}
          mapStyle={MAP_STYLES[mapTheme] || MAP_STYLES.VOYAGER}
          attributionControl={false}
        />
      </DeckGL>

      {/* Floating Hover Tooltip */}
      {hoverInfo && hoverInfo.object && (hoverInfo.object.is_tracked_node || hoverInfo.object.trip_id || hoverInfo.object.name || hoverInfo.object.zone_name) && (
        <div
          style={{
            position: 'absolute',
            left: hoverInfo.x + 12,
            top: hoverInfo.y + 12,
            pointerEvents: 'none',
            zIndex: 100,
            background: 'rgba(10, 22, 40, 0.94)',
            backdropFilter: 'blur(12px)',
            border: hoverInfo.object.is_tracked_node
              ? hoverInfo.object.node_type === 'PICKUP'
                ? '1px solid rgba(34, 197, 94, 0.65)'
                : '1px solid rgba(244, 63, 94, 0.65)'
              : '1px solid rgba(0, 245, 255, 0.4)',
            borderRadius: '8px',
            padding: '10px 14px',
            boxShadow: hoverInfo.object.is_tracked_node
              ? hoverInfo.object.node_type === 'PICKUP'
                ? '0 6px 24px rgba(34, 197, 94, 0.3)'
                : '0 6px 24px rgba(244, 63, 94, 0.3)'
              : '0 4px 20px rgba(0, 0, 0, 0.6)',
            color: '#F1F5F9',
            fontSize: '12px',
            minWidth: '200px',
          }}
        >
          {hoverInfo.object.is_tracked_node ? (
            <div>
              <div className="flex items-center justify-between" style={{ marginBottom: '6px', gap: '8px' }}>
                <span
                  style={{
                    fontWeight: 800,
                    fontSize: '11px',
                    letterSpacing: '0.05em',
                    color: hoverInfo.object.node_type === 'PICKUP' ? '#22C55E' : '#F43F5E',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {hoverInfo.object.node_type === 'PICKUP' ? '📍 PICKUP (START)' : '🏁 DROPOFF (END)'}
                </span>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: '4px',
                    color: FLEET_COLORS[hoverInfo.object.dataset_source as 'YELLOW']?.hex || '#00F5FF',
                    background: 'rgba(255,255,255,0.08)',
                  }}
                >
                  {hoverInfo.object.dataset_source}
                </span>
              </div>
              <div style={{ fontWeight: 700, fontSize: '13px', color: '#F1F5F9', marginBottom: '3px' }}>
                {hoverInfo.object.zone_name}
              </div>
              <div style={{ color: '#94A3B8', fontSize: '11px', marginBottom: '6px' }}>
                Borough: <span style={{ color: '#E2E8F0', fontWeight: 600 }}>{hoverInfo.object.borough}</span>
              </div>
              <div
                style={{
                  borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                  paddingTop: '6px',
                  marginTop: '4px',
                  fontSize: '11px',
                  color: '#94A3B8',
                }}
              >
                <div className="flex items-center justify-between font-mono" style={{ marginBottom: '3px' }}>
                  <span>Trip ID:</span>
                  <span style={{ color: '#00F5FF', fontWeight: 700 }}>{hoverInfo.object.trip_id}</span>
                </div>
                {hoverInfo.object.node_type === 'DROPOFF' ? (
                  <div className="flex items-center justify-between font-mono" style={{ marginBottom: '3px' }}>
                    <span>Trip Progress:</span>
                    <span style={{ color: '#F43F5E', fontWeight: 700 }}>
                      {((hoverInfo.object.progress_ratio ?? 0) * 100).toFixed(0)}% completed
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center justify-between font-mono" style={{ marginBottom: '3px' }}>
                    <span>Trip Fare:</span>
                    <span className="text-green" style={{ fontWeight: 700 }}>
                      {formatCurrency(hoverInfo.object.fare_amount || 0)}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between font-mono" style={{ fontSize: '10px', color: '#64748B', marginTop: '4px' }}>
                  <span>Coordinates:</span>
                  <span>{hoverInfo.object.lat?.toFixed(5)}, {hoverInfo.object.lng?.toFixed(5)}</span>
                </div>
              </div>
            </div>
          ) : hoverInfo.object.trip_id ? (
            <div>
              <div className="flex items-center justify-between" style={{ marginBottom: '6px' }}>
                <span className="font-mono" style={{ fontWeight: 800, color: '#00F5FF' }}>
                  {hoverInfo.object.trip_id}
                </span>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '2px 5px',
                    borderRadius: '4px',
                    color: FLEET_COLORS[hoverInfo.object.dataset_source as 'YELLOW']?.hex,
                    background: 'rgba(255,255,255,0.06)',
                  }}
                >
                  {hoverInfo.object.dataset_source}
                </span>
              </div>
              <div style={{ color: '#94A3B8', fontSize: '11px', marginBottom: '4px' }}>
                📍 {hoverInfo.object.zone_name} ({hoverInfo.object.borough})
              </div>
              <div className="flex items-center justify-between font-mono" style={{ fontSize: '11px', marginTop: '6px' }}>
                <span className="text-yellow">⚡ {hoverInfo.object.speed_mph?.toFixed(1)} mph</span>
                <span className="text-green">💵 {formatCurrency(hoverInfo.object.fare_amount || 0)}</span>
              </div>
            </div>
          ) : hoverInfo.object.name ? (
            <div>
              <div style={{ fontWeight: 700, color: '#38BDF8' }}>✈️ {hoverInfo.object.name}</div>
              <div style={{ fontSize: '11px', color: '#94A3B8' }}>Major International Transit Hub</div>
            </div>
          ) : hoverInfo.object.zone_name ? (
            <div>
              <div style={{ fontWeight: 700, color: '#F43F5E' }}>🔥 {hoverInfo.object.zone_name}</div>
              <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                Active Vehicles: {hoverInfo.object.vehicle_count}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* Floating Demand Surge Hotspots Panel */}
      <DemandSurgePanel onFlyToZone={handleFlyToZone} />

      {/* Floating Dynamic Legend */}
      <MapLegend />

      {/* Floating Right Dispatch Sidebar */}
      <FleetDispatch />
    </div>
  );
};
