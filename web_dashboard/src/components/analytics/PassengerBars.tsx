import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useFleetStore } from '../../store/useFleetStore';

export const PassengerBars: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);

  const option = useMemo(() => {
    const categories = ['1 Pax (Solo)', '2 Pax', '3-4 Pax', '5+ Pax'];
    const yellow = [0, 0, 0, 0];
    const green = [0, 0, 0, 0];
    const fhvhv = [0, 0, 0, 0];

    const getPaxIdx = (p: number) => {
      if (p <= 1) return 0;
      if (p === 2) return 1;
      if (p <= 4) return 2;
      return 3;
    };

    for (const v of vehicles) {
      const idx = getPaxIdx(v.passenger_count || 1);
      if (v.dataset_source === 'YELLOW') yellow[idx]++;
      else if (v.dataset_source === 'GREEN') green[idx]++;
      else if (v.dataset_source === 'FHVHV') fhvhv[idx]++;
    }

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(10, 22, 40, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        textStyle: { color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: 12 },
      },
      legend: {
        top: 0,
        textStyle: { color: '#94A3B8', fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
      },
      grid: { top: 35, right: 15, bottom: 25, left: 35 },
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
        axisLabel: { color: '#94A3B8', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
        axisLabel: { color: '#64748B', fontFamily: 'JetBrains Mono', fontSize: 10 },
      },
      series: [
        {
          name: 'Yellow Cab',
          type: 'bar',
          barGap: 0.2,
          color: '#FACC15',
          data: yellow,
        },
        {
          name: 'Green Boro',
          type: 'bar',
          color: '#22C55E',
          data: green,
        },
        {
          name: 'FHVHV (Uber/Lyft)',
          type: 'bar',
          color: '#A855F7',
          data: fhvhv,
        },
      ],
    };
  }, [vehicles]);

  return (
    <div className="glass-card" style={{ padding: '16px', height: '260px', display: 'flex', flexDirection: 'column' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
        <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', color: '#F1F5F9' }}>
          PASSENGER CAPACITY UTILIZATION
        </span>
        <span className="font-mono text-cyan" style={{ fontSize: '11px' }}>
          LOAD BARS
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
