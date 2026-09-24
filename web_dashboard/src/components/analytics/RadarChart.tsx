import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { useFleetStore } from '../../store/useFleetStore';
import { Compass } from 'lucide-react';

export const RadarChart: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);

  const option = useMemo(() => {
    const calcFleetMetrics = (type: string) => {
      const subset = vehicles.filter((v) => v.dataset_source === type);
      const count = subset.length;
      if (count === 0) {
        return { count: 0, avgFare: 0, avgSpeed: 0, zones: 0, fastRatio: 0 };
      }

      const sumFare = subset.reduce((acc, v) => acc + (v.fare_amount || 0), 0);
      const avgFare = sumFare / count;

      const sumSpeed = subset.reduce((acc, v) => acc + (v.speed_mph || 0), 0);
      const avgSpeed = sumSpeed / count;

      const zones = new Set(subset.map((v) => v.zone_id)).size;
      const fastCount = subset.filter((v) => (v.speed_mph || 0) > 20).length;
      const fastRatio = (fastCount / count) * 100;

      return {
        count,
        avgFare: Number(avgFare.toFixed(1)),
        avgSpeed: Number(avgSpeed.toFixed(1)),
        zones,
        fastRatio: Number(fastRatio.toFixed(1)),
      };
    };

    const yellow = calcFleetMetrics('YELLOW');
    const green = calcFleetMetrics('GREEN');
    const fhvhv = calcFleetMetrics('FHVHV');

    const totalFleet = yellow.count + green.count + fhvhv.count;

    // Dynamically calculate headroom max values to prevent clumping at the outer edge
    const maxVolume = Math.max(80, Math.ceil(Math.max(yellow.count, green.count, fhvhv.count, 40) * 1.2));
    const maxFare = Math.max(35, Math.ceil(Math.max(yellow.avgFare, green.avgFare, fhvhv.avgFare, 20) * 1.25));
    const maxSpeed = Math.max(30, Math.ceil(Math.max(yellow.avgSpeed, green.avgSpeed, fhvhv.avgSpeed, 15) * 1.2));
    const maxZones = Math.max(40, Math.ceil(Math.max(yellow.zones, green.zones, fhvhv.zones, 20) * 1.2));
    const maxFastRatio = 100;

    return {
      backgroundColor: 'transparent',
      animationDuration: 400,
      animationEasing: 'cubicOut',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(10, 22, 40, 0.96)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        borderWidth: 1,
        padding: [10, 14],
        extraCssText: 'backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius: 8px;',
        formatter: (params: any) => {
          const val = params.value as number[];
          if (!val) return '';
          const name = params.name;
          const color = params.color;
          const share = totalFleet > 0 ? ((val[0] / totalFleet) * 100).toFixed(1) : '0';

          return `
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:6px; font-weight:800; font-size:12.5px; color:${color}; font-family:'Plus Jakarta Sans',sans-serif;">
              <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${color};"></span>
              ${name} Capabilities
            </div>
            <div style="font-family:'JetBrains Mono',monospace; font-size:11px; line-height:1.65; color:#CBD5E1;">
              <div>• Fleet Size: <strong style="color:#F1F5F9;">${val[0]} units</strong> <span style="color:#94A3B8; font-size:9.5px;">(${share}% total)</span></div>
              <div>• Avg Fare: <strong style="color:#F1F5F9;">$${val[1].toFixed(2)}</strong></div>
              <div>• Avg Velocity: <strong style="color:#F1F5F9;">${val[2].toFixed(1)} MPH</strong></div>
              <div>• Active Zones: <strong style="color:#F1F5F9;">${val[3]} zones</strong></div>
              <div>• High-Speed (>20mph): <strong style="color:#00F5FF;">${val[4].toFixed(1)}%</strong></div>
            </div>
          `;
        },
      },
      legend: {
        bottom: 0,
        data: ['Yellow Cab', 'Green Boro', 'FHVHV (Uber/Lyft)'],
        textStyle: { color: '#94A3B8', fontSize: 10.5, fontFamily: 'Plus Jakarta Sans' },
        itemWidth: 10,
        itemHeight: 10,
        icon: 'circle',
      },
      radar: {
        indicator: [
          { name: `Fleet Size\n(max ${maxVolume})`, max: maxVolume },
          { name: `Avg Fare\n(max $${maxFare})`, max: maxFare },
          { name: `Speed\n(max ${maxSpeed}mph)`, max: maxSpeed },
          { name: `Zone Scope\n(max ${maxZones})`, max: maxZones },
          { name: 'High-Velocity\n(>20mph %)', max: maxFastRatio },
        ],
        shape: 'polygon',
        splitNumber: 4,
        radius: '62%',
        center: ['50%', '48%'],
        axisName: {
          color: '#94A3B8',
          fontSize: 9.5,
          fontWeight: 600,
          fontFamily: 'JetBrains Mono',
          lineHeight: 13,
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(56, 189, 248, 0.22)',
            width: 1,
          },
        },
        splitArea: {
          show: true,
          areaStyle: {
            color: ['rgba(56, 189, 248, 0.02)', 'rgba(56, 189, 248, 0.06)'],
          },
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(56, 189, 248, 0.25)',
          },
        },
      },
      series: [
        {
          name: 'Fleet Capabilities',
          type: 'radar',
          symbol: 'circle',
          symbolSize: 5,
          data: [
            {
              value: [yellow.count, yellow.avgFare, yellow.avgSpeed, yellow.zones, yellow.fastRatio],
              name: 'Yellow Cab',
              itemStyle: { color: '#FACC15' },
              lineStyle: { width: 2.2, color: '#FACC15' },
              areaStyle: { color: 'rgba(250, 204, 21, 0.22)' },
              emphasis: {
                lineStyle: { width: 3.5, shadowBlur: 10, shadowColor: 'rgba(250, 204, 21, 0.6)' },
                areaStyle: { color: 'rgba(250, 204, 21, 0.35)' },
              },
            },
            {
              value: [green.count, green.avgFare, green.avgSpeed, green.zones, green.fastRatio],
              name: 'Green Boro',
              itemStyle: { color: '#22C55E' },
              lineStyle: { width: 2.2, color: '#22C55E' },
              areaStyle: { color: 'rgba(34, 197, 94, 0.22)' },
              emphasis: {
                lineStyle: { width: 3.5, shadowBlur: 10, shadowColor: 'rgba(34, 197, 94, 0.6)' },
                areaStyle: { color: 'rgba(34, 197, 94, 0.35)' },
              },
            },
            {
              value: [fhvhv.count, fhvhv.avgFare, fhvhv.avgSpeed, fhvhv.zones, fhvhv.fastRatio],
              name: 'FHVHV (Uber/Lyft)',
              itemStyle: { color: '#A855F7' },
              lineStyle: { width: 2.2, color: '#A855F7' },
              areaStyle: { color: 'rgba(168, 85, 247, 0.22)' },
              emphasis: {
                lineStyle: { width: 3.5, shadowBlur: 10, shadowColor: 'rgba(168, 85, 247, 0.6)' },
                areaStyle: { color: 'rgba(168, 85, 247, 0.35)' },
              },
            },
          ],
        },
      ],
    };
  }, [vehicles]);

  return (
    <div className="glass-card" style={{ padding: '16px', height: '100%', minHeight: '340px', display: 'flex', flexDirection: 'column' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '4px' }}>
        <div className="flex items-center gap-2">
          <Compass size={14} className="text-cyan" />
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            MULTI-METRIC FLEET RADAR SPIDER
          </span>
        </div>
        <span
          style={{
            fontSize: '10px',
            fontFamily: 'JetBrains Mono',
            padding: '1px 6px',
            borderRadius: '4px',
            background: 'rgba(0, 245, 255, 0.1)',
            color: '#00F5FF',
            border: '1px solid rgba(0, 245, 255, 0.25)',
          }}
        >
          CALIBRATED
        </span>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
