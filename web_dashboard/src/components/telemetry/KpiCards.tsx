import React, { useMemo } from 'react';
import { useFleetStore } from '../../store/useFleetStore';
import { formatCurrency, formatNumber } from '../../lib/colorScales';
import { Car, Zap, DollarSign, Gauge, TrendingUp } from 'lucide-react';

export const KpiCards: React.FC = () => {
  const kpis = useFleetStore((s) => s.kpis);
  const vehicles = useFleetStore((s) => s.vehicles);
  const history = useFleetStore((s) => s.history);

  const stats = useMemo(() => {
    let totalFare = 0;
    let totalSpeed = 0;
    const count = vehicles.length;

    for (let i = 0; i < count; i++) {
      totalFare += vehicles[i].fare_amount || 0;
      totalSpeed += vehicles[i].speed_mph || 0;
    }

    const avgSpeed = count > 0 ? (totalSpeed / count).toFixed(1) : '0.0';
    const latestThroughput = history.throughput.length > 0
      ? history.throughput[history.throughput.length - 1]
      : 100;

    return {
      activeCount: count || kpis.total_active_vehicles || 0,
      totalFare,
      avgSpeed,
      latestThroughput,
    };
  }, [vehicles, kpis, history]);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '12px',
        margin: '0 0 12px 0',
      }}
    >
      {/* 1. Active Vehicles */}
      <div className="glass-card" style={{ padding: '14px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: '#00F5FF' }} />
        <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', letterSpacing: '0.04em' }}>
            ACTIVE FLEET DEPLOYED
          </span>
          <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: 'rgba(0, 245, 255, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Car size={16} className="text-cyan" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-cyan" style={{ fontSize: '26px', fontWeight: 800 }}>
            {formatNumber(stats.activeCount)}
          </span>
          <span style={{ fontSize: '11px', color: '#22C55E', fontWeight: 600 }}>LIVE UNITS</span>
        </div>
        <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
          Streaming 60 FPS spatial coords
        </div>
      </div>

      {/* 2. Ingestion Throughput */}
      <div className="glass-card" style={{ padding: '14px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: '#FACC15' }} />
        <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', letterSpacing: '0.04em' }}>
            INGESTION THROUGHPUT
          </span>
          <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: 'rgba(250, 204, 21, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Zap size={16} className="text-yellow" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-yellow" style={{ fontSize: '26px', fontWeight: 800 }}>
            {formatNumber(stats.latestThroughput)}
          </span>
          <span style={{ fontSize: '11px', color: '#FACC15', fontWeight: 600 }}>EVT / SEC</span>
        </div>
        <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
          Total processed: {formatNumber(kpis.total_events_processed)}
        </div>
      </div>

      {/* 3. In-flight Fares */}
      <div className="glass-card" style={{ padding: '14px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: '#22C55E' }} />
        <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', letterSpacing: '0.04em' }}>
            IN-FLIGHT FARE REVENUE
          </span>
          <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: 'rgba(34, 197, 94, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <DollarSign size={16} className="text-green" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-green" style={{ fontSize: '26px', fontWeight: 800 }}>
            {formatCurrency(stats.totalFare)}
          </span>
          <span style={{ fontSize: '11px', color: '#22C55E', fontWeight: 600 }}>USD</span>
        </div>
        <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
          Avg: {formatCurrency(stats.activeCount > 0 ? stats.totalFare / stats.activeCount : 0)} / trip
        </div>
      </div>

      {/* 4. Fleet Speed */}
      <div className="glass-card" style={{ padding: '14px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: '#38BDF8' }} />
        <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', letterSpacing: '0.04em' }}>
            FLEET AVERAGE SPEED
          </span>
          <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: 'rgba(56, 189, 248, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Gauge size={16} className="text-sky" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sky" style={{ fontSize: '26px', fontWeight: 800 }}>
            {stats.avgSpeed}
          </span>
          <span style={{ fontSize: '11px', color: '#38BDF8', fontWeight: 600 }}>MPH</span>
        </div>
        <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
          Traffic Condition: Flowing
        </div>
      </div>
    </div>
  );
};
