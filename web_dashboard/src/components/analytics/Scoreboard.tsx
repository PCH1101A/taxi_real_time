import React, { useMemo } from 'react';
import { useFleetStore } from '../../store/useFleetStore';
import { FLEET_COLORS, formatCurrency, formatNumber } from '../../lib/colorScales';
import { Trophy, TrendingUp, DollarSign, Gauge } from 'lucide-react';
import { FleetType } from '../../lib/types';

export const Scoreboard: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);

  const stats = useMemo(() => {
    const counts: Record<FleetType, { count: number; fareSum: number; speedSum: number }> = {
      YELLOW: { count: 0, fareSum: 0, speedSum: 0 },
      GREEN: { count: 0, fareSum: 0, speedSum: 0 },
      FHVHV: { count: 0, fareSum: 0, speedSum: 0 },
    };

    for (const v of vehicles) {
      if (counts[v.dataset_source]) {
        counts[v.dataset_source].count++;
        counts[v.dataset_source].fareSum += v.fare_amount || 0;
        counts[v.dataset_source].speedSum += v.speed_mph || 0;
      }
    }

    const total = vehicles.length || 1;

    const list = (['YELLOW', 'GREEN', 'FHVHV'] as FleetType[]).map((type) => {
      const c = counts[type];
      const avgFare = c.count > 0 ? c.fareSum / c.count : 0;
      const avgSpeed = c.count > 0 ? c.speedSum / c.count : 0;
      const share = (c.count / total) * 100;
      return {
        type,
        count: c.count,
        share: share.toFixed(1),
        avgFare: avgFare.toFixed(2),
        avgSpeed: avgSpeed.toFixed(1),
        score: c.count * 1.5 + avgFare * 2,
      };
    });

    // Rank list
    list.sort((a, b) => b.score - a.score);
    return list;
  }, [vehicles]);

  const medals = ['🥇', '🥈', '🥉'];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', marginBottom: '14px' }}>
      {stats.map((item, idx) => {
        const fleet = FLEET_COLORS[item.type];
        return (
          <div
            key={item.type}
            className="glass-card"
            style={{
              padding: '16px',
              position: 'relative',
              overflow: 'hidden',
              borderTop: `3px solid ${fleet.hex}`,
            }}
          >
            <div className="flex items-center justify-between" style={{ marginBottom: '10px' }}>
              <div className="flex items-center gap-2">
                <span style={{ fontSize: '18px' }}>{medals[idx]}</span>
                <span style={{ fontWeight: 800, fontSize: '14px', color: fleet.hex }}>
                  {fleet.name}
                </span>
              </div>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: '4px',
                  background: 'rgba(255,255,255,0.06)',
                  color: '#F1F5F9',
                }}
              >
                RANK #{idx + 1}
              </span>
            </div>

            <div className="flex items-baseline justify-between" style={{ marginBottom: '12px' }}>
              <div>
                <div style={{ fontSize: '10px', color: '#94A3B8' }}>ACTIVE FLEET</div>
                <div className="font-mono" style={{ fontSize: '24px', fontWeight: 800, color: '#F1F5F9' }}>
                  {formatNumber(item.count)}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '10px', color: '#94A3B8' }}>MARKET SHARE</div>
                <div className="font-mono text-cyan" style={{ fontSize: '18px', fontWeight: 700 }}>
                  {item.share}%
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs font-mono" style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '10px' }}>
              <span className="flex items-center gap-1 text-green">
                <DollarSign size={13} /> Avg: ${item.avgFare}
              </span>
              <span className="flex items-center gap-1 text-yellow">
                <Gauge size={13} /> Velocity: {item.avgSpeed} mph
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
