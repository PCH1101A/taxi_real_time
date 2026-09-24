import React, { useState, useMemo } from 'react';
import { useFleetStore } from '../../store/useFleetStore';
import { Vehicle } from '../../lib/types';
import { FLEET_COLORS, formatCurrency } from '../../lib/colorScales';
import { Search, Navigation, X, Gauge, DollarSign, Users, ChevronRight, Loader2 } from 'lucide-react';

export const FleetDispatch: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);
  const selectedTripId = useFleetStore((s) => s.selectedTripId);
  const setSelectedTripId = useFleetStore((s) => s.setSelectedTripId);
  const setTrackedRoute = useFleetStore((s) => s.setTrackedRoute);
  const trackedRoute = useFleetStore((s) => s.trackedRoute);
  const isLoadingRoute = useFleetStore((s) => s.isLoadingRoute);
  const setIsLoadingRoute = useFleetStore((s) => s.setIsLoadingRoute);

  const selectedBorough = useFleetStore((s) => s.selectedBorough);
  const allowedSources = useFleetStore((s) => s.allowedSources);

  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 15;

  // Filtered vehicles
  const filteredVehicles = useMemo(() => {
    return vehicles.filter((v) => {
      if (selectedBorough !== 'ALL' && v.borough !== selectedBorough) return false;
      if (!allowedSources.includes(v.dataset_source)) return false;
      if (searchTerm) {
        const q = searchTerm.toLowerCase();
        return (
          v.trip_id.toLowerCase().includes(q) ||
          v.zone_name.toLowerCase().includes(q) ||
          (v.dropoff_zone_name && v.dropoff_zone_name.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [vehicles, selectedBorough, allowedSources, searchTerm]);

  const pagedVehicles = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filteredVehicles.slice(start, start + PAGE_SIZE);
  }, [filteredVehicles, page]);

  const selectedVehicle = useMemo(() => {
    return vehicles.find((v) => v.trip_id === selectedTripId) || null;
  }, [vehicles, selectedTripId]);

  const handleSelectVehicle = async (v: Vehicle) => {
    if (selectedTripId === v.trip_id) {
      setSelectedTripId(null);
      return;
    }
    setSelectedTripId(v.trip_id);
    setIsLoadingRoute(true);

    try {
      const resp = await fetch(
        `/api/v1/route?s_lng=${v.start_lng}&s_lat=${v.start_lat}&t_lng=${v.target_lng}&t_lat=${v.target_lat}`
      );
      if (resp.ok) {
        const routeData = await resp.json();
        setTrackedRoute(routeData);
      }
    } catch (e) {
      console.warn('Failed to load driving route:', e);
    } finally {
      setIsLoadingRoute(false);
    }
  };

  return (
    <aside
      className="glass-panel"
      style={{
        position: 'absolute',
        top: '12px',
        right: '12px',
        bottom: '12px',
        width: '340px',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 25,
        pointerEvents: 'auto',
      }}
    >
      {/* Header */}
      <div style={{ padding: '14px', borderBottom: '1px solid rgba(56, 189, 248, 0.15)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Navigation size={16} className="text-cyan" />
            <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.04em' }}>
              FLEET DISPATCH
            </span>
          </div>
          <span className="font-mono text-cyan" style={{ fontSize: '11px', background: 'rgba(0, 245, 255, 0.1)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(0, 245, 255, 0.25)' }}>
            {filteredVehicles.length} UNITS
          </span>
        </div>

        {/* Search */}
        <div style={{ marginTop: '10px', position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: '#64748B' }} />
          <input
            type="text"
            placeholder="Search trip ID, pickup or dropoff..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(0);
            }}
            style={{
              width: '100%',
              background: 'rgba(15, 23, 42, 0.7)',
              border: '1px solid rgba(56, 189, 248, 0.2)',
              borderRadius: '6px',
              padding: '7px 10px 7px 32px',
              fontSize: '12px',
              color: '#F1F5F9',
              outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Selected Vehicle Card (Pinned at top if selected) */}
      {selectedVehicle && (
        <div
          style={{
            margin: '10px',
            padding: '12px',
            background: 'rgba(0, 245, 255, 0.08)',
            border: '1px solid rgba(0, 245, 255, 0.4)',
            borderRadius: '8px',
          }}
        >
          <div className="flex items-center justify-between">
            <span className="font-mono" style={{ fontSize: '13px', fontWeight: 800, color: '#00F5FF' }}>
              {selectedVehicle.trip_id}
            </span>
            <button
              onClick={() => setSelectedTripId(null)}
              style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer' }}
            >
              <X size={15} />
            </button>
          </div>

          <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '4px' }}>
            {selectedVehicle.zone_name} &rarr; {selectedVehicle.dropoff_zone_name || 'Destination'}
          </div>

          {/* Telemetry bar */}
          <div className="flex items-center justify-between" style={{ marginTop: '8px', fontSize: '11px' }}>
            <span className="flex items-center gap-1 font-mono text-yellow">
              <Gauge size={12} /> {selectedVehicle.speed_mph.toFixed(1)} mph
            </span>
            <span className="flex items-center gap-1 font-mono text-green">
              <DollarSign size={12} /> {formatCurrency(selectedVehicle.fare_amount)}
            </span>
            <span className="flex items-center gap-1 font-mono text-sky">
              <Users size={12} /> {selectedVehicle.passenger_count} pax
            </span>
          </div>

          {/* Progress bar */}
          <div style={{ marginTop: '8px' }}>
            <div className="flex items-center justify-between" style={{ fontSize: '10px', color: '#94A3B8', marginBottom: '3px' }}>
              <span>Trip Progress</span>
              <span className="font-mono text-cyan">{Math.round(selectedVehicle.progress_ratio * 100)}%</span>
            </div>
            <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${Math.round(selectedVehicle.progress_ratio * 100)}%`,
                  background: 'linear-gradient(90deg, #00F5FF, #38BDF8)',
                }}
              />
            </div>
          </div>

          {/* OSRM Route Info */}
          {isLoadingRoute ? (
            <div className="flex items-center gap-2" style={{ marginTop: '8px', fontSize: '11px', color: '#38BDF8' }}>
              <Loader2 size={12} className="animate-spin" />
              <span>Routing NYC street geometry...</span>
            </div>
          ) : trackedRoute ? (
            <div className="flex items-center justify-between font-mono" style={{ marginTop: '8px', fontSize: '11px', color: '#E2E8F0', background: 'rgba(15, 23, 42, 0.6)', padding: '4px 8px', borderRadius: '4px' }}>
              <span>🛣️ {trackedRoute.optimal_distance_miles} mi</span>
              <span>⏱️ {trackedRoute.est_duration_min} min ETA</span>
            </div>
          ) : null}
        </div>
      )}

      {/* Vehicle List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 10px' }} className="flex flex-col gap-2">
        {pagedVehicles.map((v) => {
          const fleetCfg = FLEET_COLORS[v.dataset_source];
          const isSelected = v.trip_id === selectedTripId;

          return (
            <div
              key={v.trip_id}
              onClick={() => handleSelectVehicle(v)}
              className="glass-card"
              style={{
                padding: '10px',
                cursor: 'pointer',
                borderColor: isSelected ? '#00F5FF' : undefined,
                background: isSelected ? 'rgba(0, 245, 255, 0.12)' : undefined,
              }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: fleetCfg?.hex || '#94A3B8',
                    }}
                  />
                  <span className="font-mono" style={{ fontSize: '12px', fontWeight: 700, color: '#F1F5F9' }}>
                    {v.trip_id}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    color: fleetCfg?.hex || '#94A3B8',
                    background: 'rgba(255,255,255,0.05)',
                    padding: '2px 5px',
                    borderRadius: '4px',
                  }}
                >
                  {v.dataset_source}
                </span>
              </div>

              <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {v.zone_name}
              </div>

              <div className="flex items-center justify-between" style={{ marginTop: '6px', fontSize: '11px' }}>
                <span className="font-mono text-yellow" style={{ fontSize: '11px' }}>
                  {v.speed_mph.toFixed(0)} mph
                </span>
                <span className="font-mono text-green" style={{ fontSize: '11px' }}>
                  {formatCurrency(v.fare_amount)}
                </span>
                <ChevronRight size={13} style={{ color: '#64748B' }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination Footer */}
      {filteredVehicles.length > PAGE_SIZE && (
        <div
          className="flex items-center justify-between"
          style={{ padding: '10px 14px', borderTop: '1px solid rgba(56, 189, 248, 0.15)', fontSize: '11px' }}
        >
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            style={{
              background: 'rgba(15, 23, 42, 0.8)',
              border: '1px solid rgba(56, 189, 248, 0.2)',
              color: page === 0 ? '#475569' : '#00F5FF',
              padding: '4px 10px',
              borderRadius: '4px',
              cursor: page === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            Prev
          </button>
          <span className="font-mono text-muted">
            Page {page + 1} of {Math.ceil(filteredVehicles.length / PAGE_SIZE)}
          </span>
          <button
            disabled={(page + 1) * PAGE_SIZE >= filteredVehicles.length}
            onClick={() => setPage((p) => p + 1)}
            style={{
              background: 'rgba(15, 23, 42, 0.8)',
              border: '1px solid rgba(56, 189, 248, 0.2)',
              color: (page + 1) * PAGE_SIZE >= filteredVehicles.length ? '#475569' : '#00F5FF',
              padding: '4px 10px',
              borderRadius: '4px',
              cursor: (page + 1) * PAGE_SIZE >= filteredVehicles.length ? 'not-allowed' : 'pointer',
            }}
          >
            Next
          </button>
        </div>
      )}
    </aside>
  );
};
