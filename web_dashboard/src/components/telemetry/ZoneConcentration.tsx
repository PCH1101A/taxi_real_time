import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useFleetStore } from '../../store/useFleetStore';
import { Flame } from 'lucide-react';

export const ZoneConcentration: React.FC = () => {
  const topZones = useFleetStore((s) => s.topZones);

  const option = useMemo(() => {
    const zones = (topZones || []).slice(0, 8).reverse();
    const names = zones.map((z) => (z.zone_name.length > 18 ? z.zone_name.slice(0, 16) + '...' : z.zone_name));
    const counts = zones.map((z) => z.vehicle_count || 0);

    return {
      backgroundColor: 'transparent',
      grid: { top: 10, right: 30, bottom: 20, left: 130 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(10, 22, 40, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        textStyle: { color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: 12 },
      },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
        axisLabel: { color: '#64748B', fontFamily: 'JetBrains Mono', fontSize: 10 },
      },
      yAxis: {
        type: 'category',
        data: names,
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
        axisLabel: { color: '#94A3B8', fontSize: 11, fontWeight: 500 },
      },
      series: [
        {
          name: 'Active Cabs',
          type: 'bar',
          barWidth: '60%',
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: '#0284C7' },
                { offset: 1, color: '#00F5FF' },
              ],
            },
          },
          label: {
            show: true,
            position: 'right',
            color: '#00F5FF',
            fontFamily: 'JetBrains Mono',
            fontSize: 11,
          },
          data: counts,
        },
      ],
    };
  }, [topZones]);

  return (
    <div className="glass-card" style={{ padding: '16px', height: '260px', display: 'flex', flexDirection: 'column' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '8px', minHeight: '26px' }}>
        <div className="flex items-center gap-2">
          <Flame size={14} className="text-cyan" />
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            TOP CONGESTED PICKUP HUBS
          </span>
        </div>
        <span
          style={{
            fontSize: '10px',
            fontFamily: 'JetBrains Mono',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: '9999px',
            background: 'rgba(0, 245, 255, 0.12)',
            color: '#00F5FF',
            border: '1px solid rgba(0, 245, 255, 0.3)',
          }}
        >
          HOTSPOTS
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
