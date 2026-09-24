import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useFleetStore } from '../../store/useFleetStore';

export const BoroughDonut: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);

  const option = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const v of vehicles) {
      const b = v.borough || 'Unknown';
      counts[b] = (counts[b] || 0) + 1;
    }

    const data = Object.entries(counts).map(([name, value]) => ({ name, value }));

    const colorPalette = ['#00F5FF', '#38BDF8', '#FACC15', '#22C55E', '#A855F7', '#F43F5E'];

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} units ({d}%)',
        backgroundColor: 'rgba(10, 22, 40, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        textStyle: { color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: 12 },
      },
      legend: {
        bottom: 0,
        textStyle: { color: '#94A3B8', fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
      },
      series: [
        {
          name: 'Borough Share',
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['50%', '42%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 6,
            borderColor: '#020B18',
            borderWidth: 2,
          },
          label: {
            show: false,
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 12,
              fontWeight: 'bold',
              color: '#F1F5F9',
              fontFamily: 'JetBrains Mono',
            },
          },
          data,
          color: colorPalette,
        },
      ],
    };
  }, [vehicles]);

  return (
    <div className="glass-card" style={{ padding: '16px', height: '260px', display: 'flex', flexDirection: 'column' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '8px' }}>
        <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', color: '#F1F5F9' }}>
          BOROUGH MARKET PENETRATION
        </span>
        <span className="font-mono text-cyan" style={{ fontSize: '11px' }}>
          SHARE
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
