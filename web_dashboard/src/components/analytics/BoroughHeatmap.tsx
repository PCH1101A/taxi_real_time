import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useFleetStore } from '../../store/useFleetStore';

// Locked Warm Color Scale: Low/Zero (Light Cream) -> Mid (Amber/Orange) -> High/Peak (Deep Burgundy)
const WARM_COLORS = [
  '#FEF3C7', // Zero / Low: Light Warm Cream
  '#FDE68A', // Pale Amber
  '#FBBF24', // Golden Amber
  '#F97316', // Fiery Orange
  '#EF4444', // Crimson Red
  '#B91C1C', // Deep Red
  '#7F1D1D', // Burgundy Wine
  '#450A0A', // Peak: Deep Maroon
];

export const BoroughHeatmap: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);

  const option = useMemo(() => {
    const boroughs = ['Manhattan', 'Queens', 'Brooklyn', 'Bronx', 'Staten Island'];
    const fleets = ['Yellow Cab', 'Green Boro', 'FHVHV'];

    // Map: [boroughIndex, fleetIndex, count]
    const rawMatrix: number[][] = [];
    for (let b = 0; b < boroughs.length; b++) {
      for (let f = 0; f < fleets.length; f++) {
        rawMatrix.push([b, f, 0]);
      }
    }

    const fleetKeyMap: Record<string, number> = {
      YELLOW: 0,
      GREEN: 1,
      FHVHV: 2,
    };

    let maxVal = 1;
    for (const v of vehicles) {
      const bIdx = boroughs.indexOf(v.borough);
      const fIdx = fleetKeyMap[v.dataset_source];
      if (bIdx !== -1 && fIdx !== undefined) {
        const cell = rawMatrix.find((m) => m[0] === bIdx && m[1] === fIdx);
        if (cell) {
          cell[2]++;
          if (cell[2] > maxVal) maxVal = cell[2];
        }
      }
    }

    // Attach high-contrast text color per individual cell item:
    // Low/zero values (light background) -> dark readable text (#1C1917 / #78716C)
    // High values (deep background) -> crisp white text (#FFFFFF)
    const data = rawMatrix.map(([b, f, v]) => ({
      value: [b, f, v],
      label: {
        color: v === 0 ? '#78716C' : v > maxVal * 0.42 ? '#FFFFFF' : '#1C1917',
      },
    }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        position: 'top',
        backgroundColor: 'rgba(10, 22, 40, 0.96)',
        borderColor: 'rgba(245, 158, 11, 0.5)',
        borderWidth: 1,
        padding: [10, 14],
        extraCssText: 'backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius: 8px;',
        formatter: (params: any) => {
          const valData = params.data.value || params.data;
          const boro = boroughs[valData[0]];
          const fleet = fleets[valData[1]];
          const val = valData[2];
          return `<div style="font-family: Plus Jakarta Sans, sans-serif; font-size: 11px; color: #94A3B8; margin-bottom: 3px;">📍 ${boro}</div>
                  <div style="font-weight: 700; font-size: 13px; color: #F1F5F9; font-family: JetBrains Mono;">
                    ${fleet}: <span style="color: #F59E0B; font-weight: 800;">${val} vehicles</span>
                  </div>`;
        },
      },
      grid: { top: 24, right: 90, bottom: 35, left: 92 },
      xAxis: {
        type: 'category',
        data: boroughs,
        splitArea: { show: false },
        axisLabel: { color: '#CBD5E1', fontSize: 11, fontWeight: 600, fontFamily: 'Plus Jakarta Sans, sans-serif' },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
      },
      yAxis: {
        type: 'category',
        data: fleets,
        splitArea: { show: false },
        axisLabel: { color: '#CBD5E1', fontSize: 11, fontWeight: 600, fontFamily: 'Plus Jakarta Sans, sans-serif' },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
      },
      visualMap: {
        min: 0,
        max: Math.max(10, maxVal),
        calculable: true,
        orient: 'vertical',
        right: 14,
        top: 'middle',
        itemWidth: 12,
        itemHeight: 160,
        text: ['Peak', 'Zero'],
        align: 'right',
        inRange: {
          color: WARM_COLORS,
        },
        textStyle: { color: '#94A3B8', fontSize: 10, fontFamily: 'JetBrains Mono', fontWeight: 600 },
      },
      series: [
        {
          name: 'Cross Density',
          type: 'heatmap',
          data,
          itemStyle: {
            borderRadius: 6,
            borderColor: '#060E1C',
            borderWidth: 3,
          },
          label: {
            show: true,
            formatter: (p: any) => `${p.data.value[2]}`,
            fontFamily: 'JetBrains Mono',
            fontSize: 13,
            fontWeight: 800,
          },
          emphasis: {
            itemStyle: {
              borderColor: '#F59E0B',
              borderWidth: 2,
              shadowBlur: 16,
              shadowColor: 'rgba(245, 158, 11, 0.7)',
            },
          },
        },
      ],
    };
  }, [vehicles]);

  return (
    <div className="glass-card" style={{ padding: '16px', height: '100%', minHeight: '340px', display: 'flex', flexDirection: 'column' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
        <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', color: '#F1F5F9' }}>
          BOROUGH &times; FLEET CROSS-DENSITY MATRIX
        </span>

        <span
          style={{
            fontSize: '9.5px',
            fontFamily: 'JetBrains Mono',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: '9999px',
            background: 'rgba(245, 158, 11, 0.12)',
            color: '#F59E0B',
            border: '1px solid rgba(245, 158, 11, 0.3)',
          }}
        >
          WARM DENSITY
        </span>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
