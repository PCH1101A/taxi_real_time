import React, { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { useFleetStore } from '../../store/useFleetStore';
import { CircleDot, Layers, MapPin, TrendingUp } from 'lucide-react';

type ScatterViewMode = 'trips' | 'zones';

interface RegressionResult {
  m: number;
  b: number;
  r: number;
  correlationText: string;
  points: [number, number][];
}

function computeLinearRegression(points: [number, number][]): RegressionResult | null {
  if (points.length < 2) return null;

  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumX2 = 0;
  let sumY2 = 0;
  let minX = Infinity;
  let maxX = -Infinity;

  for (const [x, y] of points) {
    sumX += x;
    sumY += y;
    sumXY += x * y;
    sumX2 += x * x;
    sumY2 += y * y;
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
  }

  const n = points.length;
  const denomM = n * sumX2 - sumX * sumX;
  if (denomM === 0 || maxX <= minX) return null;

  const m = (n * sumXY - sumX * sumY) / denomM;
  const b = (sumY - m * sumX) / n;

  const denomR = Math.sqrt(Math.max(0, denomM * (n * sumY2 - sumY * sumY)));
  const r = denomR !== 0 ? (n * sumXY - sumX * sumY) / denomR : 0;

  const steps = 24;
  const stepSize = (maxX - minX) / steps;
  const linePoints: [number, number][] = [];

  for (let i = 0; i <= steps; i++) {
    const px = minX + i * stepSize;
    const py = Math.max(0, m * px + b);
    linePoints.push([Number(px.toFixed(1)), Number(py.toFixed(2))]);
  }

  let correlationText = 'Tương quan yếu';
  const absR = Math.abs(r);
  if (absR >= 0.7) correlationText = r > 0 ? 'Tương quan thuận mạnh' : 'Tương quan nghịch mạnh';
  else if (absR >= 0.4) correlationText = r > 0 ? 'Tương quan thuận vừa' : 'Tương quan nghịch vừa';
  else if (absR >= 0.2) correlationText = r > 0 ? 'Tương quan thuận yếu' : 'Tương quan nghịch yếu';

  return {
    m,
    b,
    r,
    correlationText,
    points: linePoints,
  };
}

export const FleetBubbleScatter: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);
  const zones = useFleetStore((s) => s.zones);
  const [viewMode, setViewMode] = useState<ScatterViewMode>('trips');
  const [showTrendline, setShowTrendline] = useState<boolean>(true);

  const { option, stats, regression } = useMemo(() => {
    // ── MODE A: TRIP DYNAMICS (Speed vs Fare per Vehicle) ──────────────────
    if (viewMode === 'trips') {
      const yellowTrips: [number, number, number, string, string][] = [];
      const greenTrips: [number, number, number, string, string][] = [];
      const fhvhvTrips: [number, number, number, string, string][] = [];

      let totalFare = 0;
      let totalSpeed = 0;
      let validCount = 0;

      for (const v of vehicles) {
        const fare = Number(v.fare_amount || 0);
        const speed = Number(v.speed_mph || 0);
        const pax = Math.max(1, Math.min(6, v.passenger_count || 1));
        const zone = v.zone_name || v.borough || 'NYC Zone';
        const tripId = v.trip_id || 'TRIP-LIVE';

        if (fare > 0 && speed >= 0) {
          totalFare += fare;
          totalSpeed += speed;
          validCount++;

          const tuple: [number, number, number, string, string] = [
            Number(speed.toFixed(1)),
            Number(fare.toFixed(2)),
            pax,
            zone,
            tripId,
          ];

          if (v.dataset_source === 'YELLOW') yellowTrips.push(tuple);
          else if (v.dataset_source === 'GREEN') greenTrips.push(tuple);
          else if (v.dataset_source === 'FHVHV') fhvhvTrips.push(tuple);
        }
      }

      const avgSpeed = validCount > 0 ? Number((totalSpeed / validCount).toFixed(1)) : 20;
      const avgFare = validCount > 0 ? Number((totalFare / validCount).toFixed(1)) : 25;

      const allTripPoints: [number, number][] = [
        ...yellowTrips,
        ...greenTrips,
        ...fhvhvTrips,
      ].map((t) => [t[0], t[1]]);
      const reg = computeLinearRegression(allTripPoints);

      const chartOpt = {
        backgroundColor: 'transparent',
        animationDuration: 400,
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(10, 22, 40, 0.96)',
          borderColor: 'rgba(56, 189, 248, 0.4)',
          borderWidth: 1,
          padding: [10, 14],
          extraCssText: 'backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius: 8px;',
          formatter: (params: any) => {
            if (params.seriesName === 'Đường tương quan' && reg) {
              const [speed, fare] = (params.data || [0, 0]) as [number, number];
              const sign = reg.b >= 0 ? '+' : '-';
              const absB = Math.abs(reg.b).toFixed(2);

              return `
                <div style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#F1F5F9; min-width:210px;">
                  <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px; font-weight:800; color:#38BDF8; font-size:12px; font-family:'Plus Jakarta Sans',sans-serif;">
                    <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#38BDF8; box-shadow:0 0 6px #38BDF8;"></span>
                    Đường tương quan (Trendline)
                  </div>
                  <div style="font-size:10px; color:#94A3B8; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px;">
                    ${reg.correlationText} • <strong style="color:#38BDF8;">r = ${reg.r >= 0 ? '+' : ''}${reg.r.toFixed(3)}</strong>
                  </div>
                  <div style="line-height:1.6; color:#CBD5E1;">
                    <div>• Vận tốc: <strong style="color:#00F5FF;">${speed} MPH</strong></div>
                    <div>• Ước lượng cước: <strong style="color:#FACC15;">$${fare.toFixed(2)}</strong></div>
                    <div style="color:#94A3B8; font-size:9.5px; margin-top:3px;">
                      Phương trình: y = ${reg.m.toFixed(2)}x ${sign} ${absB}
                    </div>
                  </div>
                </div>
              `;
            }

            const d = params.data as [number, number, number, string, string];
            if (!d) return '';
            const [speed, fare, pax, zone, tripId] = d;

            return `
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px; font-weight:800; color:${params.color}; font-size:12px; font-family:'Plus Jakarta Sans',sans-serif;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${params.color};"></span>
                ${params.seriesName}
              </div>
              <div style="font-size:10px; color:#94A3B8; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px; font-family:'JetBrains Mono';">
                Trip: <strong style="color:#F1F5F9;">${tripId.slice(0, 16)}</strong>
              </div>
              <div style="font-family:'JetBrains Mono',monospace; font-size:11px; line-height:1.6; color:#CBD5E1;">
                <div>• Location: <strong style="color:#F1F5F9;">${zone}</strong></div>
                <div>• Velocity: <strong style="color:#00F5FF;">${speed} MPH</strong></div>
                <div>• Trip Fare: <strong style="color:#FACC15;">$${fare.toFixed(2)}</strong></div>
                <div>• Passengers: <strong style="color:#F1F5F9;">${pax} pax</strong> (bubble size)</div>
              </div>
            `;
          },
        },
        legend: {
          top: 0,
          right: 0,
          data: [
            'Yellow Cab',
            'Green Boro',
            'FHVHV (Uber/Lyft)',
            ...(showTrendline && reg ? ['Đường tương quan'] : []),
          ],
          textStyle: { color: '#94A3B8', fontSize: 10, fontFamily: 'Plus Jakarta Sans' },
          itemWidth: 10,
          itemHeight: 8,
          icon: 'circle',
        },
        grid: { top: 28, right: 20, bottom: 28, left: 42, containLabel: false },
        xAxis: {
          type: 'value',
          name: 'Speed (MPH)',
          nameLocation: 'middle',
          nameGap: 18,
          nameTextStyle: { color: '#94A3B8', fontSize: 9.5, fontFamily: 'JetBrains Mono' },
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
          axisLabel: { color: '#64748B', fontFamily: 'JetBrains Mono', fontSize: 9.5 },
          axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.25)' } },
        },
        yAxis: {
          type: 'value',
          name: 'Fare ($)',
          nameTextStyle: { color: '#94A3B8', fontSize: 9.5, fontFamily: 'JetBrains Mono', padding: [0, 0, 4, 0] },
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
          axisLabel: {
            color: '#64748B',
            fontFamily: 'JetBrains Mono',
            fontSize: 9.5,
            formatter: (v: number) => `$${v}`,
          },
          axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.25)' } },
        },
        series: [
          {
            name: 'Yellow Cab',
            type: 'scatter',
            data: yellowTrips,
            symbolSize: (data: any) => 5 + (data[2] || 1) * 3,
            itemStyle: {
              color: 'rgba(250, 204, 21, 0.45)',
              borderColor: '#FACC15',
              borderWidth: 1.2,
              shadowBlur: 6,
              shadowColor: 'rgba(250, 204, 21, 0.3)',
            },
            emphasis: {
              itemStyle: {
                color: '#FACC15',
                borderColor: '#FFFFFF',
                borderWidth: 2,
                shadowBlur: 14,
              },
            },
            markLine: {
              silent: true,
              symbol: 'none',
              lineStyle: { color: 'rgba(0, 245, 255, 0.35)', type: 'dashed', width: 1 },
              data: [
                { yAxis: avgFare, label: { formatter: `Avg $${avgFare}`, color: '#00F5FF', fontSize: 9, fontFamily: 'JetBrains Mono' } },
                { xAxis: avgSpeed, label: { formatter: `${avgSpeed} mph`, color: '#00F5FF', fontSize: 9, fontFamily: 'JetBrains Mono' } },
              ],
            },
          },
          {
            name: 'Green Boro',
            type: 'scatter',
            data: greenTrips,
            symbolSize: (data: any) => 5 + (data[2] || 1) * 3,
            itemStyle: {
              color: 'rgba(34, 197, 94, 0.45)',
              borderColor: '#22C55E',
              borderWidth: 1.2,
              shadowBlur: 6,
              shadowColor: 'rgba(34, 197, 94, 0.3)',
            },
            emphasis: {
              itemStyle: {
                color: '#22C55E',
                borderColor: '#FFFFFF',
                borderWidth: 2,
                shadowBlur: 14,
              },
            },
          },
          {
            name: 'FHVHV (Uber/Lyft)',
            type: 'scatter',
            data: fhvhvTrips,
            symbolSize: (data: any) => 5 + (data[2] || 1) * 3,
            itemStyle: {
              color: 'rgba(168, 85, 247, 0.45)',
              borderColor: '#A855F7',
              borderWidth: 1.2,
              shadowBlur: 6,
              shadowColor: 'rgba(168, 85, 247, 0.3)',
            },
            emphasis: {
              itemStyle: {
                color: '#A855F7',
                borderColor: '#FFFFFF',
                borderWidth: 2,
                shadowBlur: 14,
              },
            },
          },
          ...(showTrendline && reg
            ? [
                {
                  name: 'Đường tương quan',
                  type: 'line',
                  data: reg.points,
                  showSymbol: false,
                  smooth: true,
                  lineStyle: {
                    color: '#38BDF8',
                    type: 'dashed',
                    width: 2.2,
                    dashOffset: 2,
                    shadowBlur: 10,
                    shadowColor: 'rgba(56, 189, 248, 0.6)',
                  },
                  endLabel: {
                    show: true,
                    formatter: () => ` Xu hướng (r = ${reg.r >= 0 ? '+' : ''}${reg.r.toFixed(2)})`,
                    color: '#38BDF8',
                    fontSize: 9.5,
                    fontFamily: 'JetBrains Mono',
                    distance: 6,
                  },
                  emphasis: {
                    lineStyle: {
                      width: 3.5,
                      shadowBlur: 16,
                      shadowColor: 'rgba(56, 189, 248, 0.9)',
                    },
                  },
                  z: 15,
                },
              ]
            : []),
        ],
      };

      return {
        option: chartOpt,
        stats: {
          totalBubbles: validCount,
          avgSpeed,
          avgFare,
          yellowCount: yellowTrips.length,
          greenCount: greenTrips.length,
          fhvhvCount: fhvhvTrips.length,
        },
        regression: reg,
      };
    }

    // ── MODE B: ZONE MARKET CLUSTERS (Vehicle Density vs Avg Fare) ──────────
    const zoneMap: Record<string, { count: number; fareSum: number; speedSum: number; fleetCounts: Record<string, number>; borough: string }> = {};

    for (const v of vehicles) {
      const zName = v.zone_name || `Zone-${v.zone_id}`;
      if (!zoneMap[zName]) {
        zoneMap[zName] = { count: 0, fareSum: 0, speedSum: 0, fleetCounts: { YELLOW: 0, GREEN: 0, FHVHV: 0 }, borough: v.borough || 'NYC' };
      }
      zoneMap[zName].count++;
      zoneMap[zName].fareSum += Number(v.fare_amount || 0);
      zoneMap[zName].speedSum += Number(v.speed_mph || 0);
      if (v.dataset_source) {
        zoneMap[zName].fleetCounts[v.dataset_source] = (zoneMap[zName].fleetCounts[v.dataset_source] || 0) + 1;
      }
    }

    const yellowZones: [number, number, number, string, string][] = [];
    const greenZones: [number, number, number, string, string][] = [];
    const fhvhvZones: [number, number, number, string, string][] = [];

    let totalZoneCount = 0;

    Object.entries(zoneMap).forEach(([name, data]) => {
      if (data.count === 0) return;
      totalZoneCount++;
      const avgFare = data.count > 0 ? Number((data.fareSum / data.count).toFixed(1)) : 0;
      const count = data.count;

      // Determine dominant fleet for zone color
      const y = data.fleetCounts.YELLOW || 0;
      const g = data.fleetCounts.GREEN || 0;
      const f = data.fleetCounts.FHVHV || 0;

      const tuple: [number, number, number, string, string] = [
        count,
        avgFare,
        count, // bubble size
        name,
        data.borough,
      ];

      if (y >= g && y >= f) yellowZones.push(tuple);
      else if (g >= y && g >= f) greenZones.push(tuple);
      else fhvhvZones.push(tuple);
    });

    const allZonePoints: [number, number][] = [
      ...yellowZones,
      ...greenZones,
      ...fhvhvZones,
    ].map((z) => [z[0], z[1]]);
    const reg = computeLinearRegression(allZonePoints);

    const chartOpt = {
      backgroundColor: 'transparent',
      animationDuration: 400,
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(10, 22, 40, 0.96)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        borderWidth: 1,
        padding: [10, 14],
        extraCssText: 'backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius: 8px;',
        formatter: (params: any) => {
          if (params.seriesName === 'Đường tương quan' && reg) {
            const [count, fare] = (params.data || [0, 0]) as [number, number];
            const sign = reg.b >= 0 ? '+' : '-';
            const absB = Math.abs(reg.b).toFixed(2);

            return `
              <div style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#F1F5F9; min-width:210px;">
                <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px; font-weight:800; color:#38BDF8; font-size:12px; font-family:'Plus Jakarta Sans',sans-serif;">
                  <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#38BDF8; box-shadow:0 0 6px #38BDF8;"></span>
                  Đường tương quan (Trendline)
                </div>
                <div style="font-size:10px; color:#94A3B8; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px;">
                  ${reg.correlationText} • <strong style="color:#38BDF8;">r = ${reg.r >= 0 ? '+' : ''}${reg.r.toFixed(3)}</strong>
                </div>
                <div style="line-height:1.6; color:#CBD5E1;">
                  <div>• Số lượng xe: <strong style="color:#00F5FF;">${count} xe</strong></div>
                  <div>• Ước lượng cước TB: <strong style="color:#FACC15;">$${fare.toFixed(2)}</strong></div>
                  <div style="color:#94A3B8; font-size:9.5px; margin-top:3px;">
                    Phương trình: y = ${reg.m.toFixed(2)}x ${sign} ${absB}
                  </div>
                </div>
              </div>
            `;
          }

          const d = params.data as [number, number, number, string, string];
          if (!d) return '';
          const [cars, fare, size, zoneName, borough] = d;

          return `
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px; font-weight:800; color:${params.color}; font-size:12px; font-family:'Plus Jakarta Sans',sans-serif;">
              <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${params.color};"></span>
              ${zoneName} (${borough})
            </div>
            <div style="font-size:10px; color:#94A3B8; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px; font-family:'JetBrains Mono';">
              Dominant Fleet: <strong style="color:${params.color};">${params.seriesName}</strong>
            </div>
            <div style="font-family:'JetBrains Mono',monospace; font-size:11px; line-height:1.6; color:#CBD5E1;">
              <div>• Active Vehicles: <strong style="color:#00F5FF;">${cars} units</strong></div>
              <div>• Avg Zone Fare: <strong style="color:#FACC15;">$${fare.toFixed(2)}</strong></div>
              <div>• Relative Activity: <strong style="color:#F1F5F9;">Bubble Volume (${size})</strong></div>
            </div>
          `;
        },
      },
      legend: {
        top: 0,
        right: 0,
        data: [
          'Yellow Dominated',
          'Green Dominated',
          'FHVHV Dominated',
          ...(showTrendline && reg ? ['Đường tương quan'] : []),
        ],
        textStyle: { color: '#94A3B8', fontSize: 10, fontFamily: 'Plus Jakarta Sans' },
        itemWidth: 10,
        itemHeight: 8,
        icon: 'circle',
      },
      grid: { top: 28, right: 20, bottom: 28, left: 42, containLabel: false },
      xAxis: {
        type: 'value',
        name: 'Zone Vehicle Volume',
        nameLocation: 'middle',
        nameGap: 18,
        nameTextStyle: { color: '#94A3B8', fontSize: 9.5, fontFamily: 'JetBrains Mono' },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
        axisLabel: { color: '#64748B', fontFamily: 'JetBrains Mono', fontSize: 9.5 },
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.25)' } },
      },
      yAxis: {
        type: 'value',
        name: 'Avg Fare ($)',
        nameTextStyle: { color: '#94A3B8', fontSize: 9.5, fontFamily: 'JetBrains Mono', padding: [0, 0, 4, 0] },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
        axisLabel: {
          color: '#64748B',
          fontFamily: 'JetBrains Mono',
          fontSize: 9.5,
          formatter: (v: number) => `$${v}`,
        },
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.25)' } },
      },
      series: [
        {
          name: 'Yellow Dominated',
          type: 'scatter',
          data: yellowZones,
          symbolSize: (data: any) => Math.max(8, Math.min(32, 6 + (data[2] || 1) * 1.8)),
          itemStyle: {
            color: 'rgba(250, 204, 21, 0.45)',
            borderColor: '#FACC15',
            borderWidth: 1.5,
            shadowBlur: 6,
            shadowColor: 'rgba(250, 204, 21, 0.3)',
          },
          emphasis: {
            itemStyle: { color: '#FACC15', borderColor: '#FFFFFF', borderWidth: 2, shadowBlur: 14 },
          },
        },
        {
          name: 'Green Dominated',
          type: 'scatter',
          data: greenZones,
          symbolSize: (data: any) => Math.max(8, Math.min(32, 6 + (data[2] || 1) * 1.8)),
          itemStyle: {
            color: 'rgba(34, 197, 94, 0.45)',
            borderColor: '#22C55E',
            borderWidth: 1.5,
            shadowBlur: 6,
            shadowColor: 'rgba(34, 197, 94, 0.3)',
          },
          emphasis: {
            itemStyle: { color: '#22C55E', borderColor: '#FFFFFF', borderWidth: 2, shadowBlur: 14 },
          },
        },
        {
          name: 'FHVHV Dominated',
          type: 'scatter',
          data: fhvhvZones,
          symbolSize: (data: any) => Math.max(8, Math.min(32, 6 + (data[2] || 1) * 1.8)),
          itemStyle: {
            color: 'rgba(168, 85, 247, 0.45)',
            borderColor: '#A855F7',
            borderWidth: 1.5,
            shadowBlur: 6,
            shadowColor: 'rgba(168, 85, 247, 0.3)',
          },
          emphasis: {
            itemStyle: { color: '#A855F7', borderColor: '#FFFFFF', borderWidth: 2, shadowBlur: 14 },
          },
        },
        ...(showTrendline && reg
          ? [
              {
                name: 'Đường tương quan',
                type: 'line',
                data: reg.points,
                showSymbol: false,
                smooth: true,
                lineStyle: {
                  color: '#38BDF8',
                  type: 'dashed',
                  width: 2.2,
                  dashOffset: 2,
                  shadowBlur: 10,
                  shadowColor: 'rgba(56, 189, 248, 0.6)',
                },
                endLabel: {
                  show: true,
                  formatter: () => ` Xu hướng (r = ${reg.r >= 0 ? '+' : ''}${reg.r.toFixed(2)})`,
                  color: '#38BDF8',
                  fontSize: 9.5,
                  fontFamily: 'JetBrains Mono',
                  distance: 6,
                },
                emphasis: {
                  lineStyle: {
                    width: 3.5,
                    shadowBlur: 16,
                    shadowColor: 'rgba(56, 189, 248, 0.9)',
                  },
                },
                z: 15,
              },
            ]
          : []),
      ],
    };

    return {
      option: chartOpt,
      stats: {
        totalBubbles: totalZoneCount,
        avgSpeed: 0,
        avgFare: 0,
        yellowCount: yellowZones.length,
        greenCount: greenZones.length,
        fhvhvCount: fhvhvZones.length,
      },
      regression: reg,
    };
  }, [vehicles, zones, viewMode, showTrendline]);

  return (
    <div className="glass-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header with Switcher & Trendline Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <CircleDot size={15} className="text-cyan" />
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            FLEET BUBBLE SCATTER
          </span>
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
            {viewMode === 'trips' ? 'SPEED × FARE' : 'VOLUME × FARE'}
          </span>
          {regression && (
            <span
              style={{
                fontSize: '10px',
                fontFamily: 'JetBrains Mono',
                padding: '1px 6px',
                borderRadius: '4px',
                background: 'rgba(56, 189, 248, 0.1)',
                color: '#38BDF8',
                border: '1px solid rgba(56, 189, 248, 0.25)',
              }}
              title={regression.correlationText}
            >
              r = {regression.r >= 0 ? '+' : ''}{regression.r.toFixed(2)}
            </span>
          )}
        </div>

        {/* View Mode & Trendline Controls */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setShowTrendline((prev) => !prev)}
            className="flex items-center gap-1"
            title="Bật/Tắt đường thể hiện mối tương quan"
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontFamily: 'JetBrains Mono',
              fontWeight: showTrendline ? 700 : 500,
              background: showTrendline ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.04)',
              color: showTrendline ? '#38BDF8' : '#64748B',
              border: showTrendline ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <TrendingUp size={11} />
            ĐƯỜNG TƯƠNG QUAN
          </button>

          <div className="flex items-center gap-1" style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '2px', borderRadius: '6px' }}>
            <button
              onClick={() => setViewMode('trips')}
              className="flex items-center gap-1"
              style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '10px',
                fontFamily: 'JetBrains Mono',
                fontWeight: viewMode === 'trips' ? 700 : 500,
                background: viewMode === 'trips' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
                color: viewMode === 'trips' ? '#00F5FF' : '#94A3B8',
                border: viewMode === 'trips' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Layers size={11} />
              TRIP SCATTER
            </button>
            <button
              onClick={() => setViewMode('zones')}
              className="flex items-center gap-1"
              style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '10px',
                fontFamily: 'JetBrains Mono',
                fontWeight: viewMode === 'zones' ? 700 : 500,
                background: viewMode === 'zones' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
                color: viewMode === 'zones' ? '#00F5FF' : '#94A3B8',
                border: viewMode === 'zones' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <MapPin size={11} />
              ZONE CLUSTERS
            </button>
          </div>
        </div>
      </div>

      {/* Bubble Scatter Canvas */}
      <div style={{ height: '220px', width: '100%' }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>

      {/* Quadrant & Cluster Info Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
        <div
          style={{
            background: 'rgba(250, 204, 21, 0.05)',
            border: '1px solid rgba(250, 204, 21, 0.25)',
            borderRadius: '8px',
            padding: '8px 12px',
          }}
        >
          <div className="flex items-center justify-between">
            <span style={{ color: '#FACC15', fontSize: '11px', fontWeight: 700 }}>Yellow Cab</span>
            <span style={{ color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: '12px', fontWeight: 800 }}>
              {stats.yellowCount} {viewMode === 'trips' ? 'trips' : 'zones'}
            </span>
          </div>
          <div style={{ fontSize: '9.5px', color: '#64748B', marginTop: '2px' }}>
            {viewMode === 'trips' ? 'High density in lower-speed zones' : 'Dominates Manhattan commercial hubs'}
          </div>
        </div>

        <div
          style={{
            background: 'rgba(34, 197, 94, 0.05)',
            border: '1px solid rgba(34, 197, 94, 0.25)',
            borderRadius: '8px',
            padding: '8px 12px',
          }}
        >
          <div className="flex items-center justify-between">
            <span style={{ color: '#22C55E', fontSize: '11px', fontWeight: 700 }}>Green Boro</span>
            <span style={{ color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: '12px', fontWeight: 800 }}>
              {stats.greenCount} {viewMode === 'trips' ? 'trips' : 'zones'}
            </span>
          </div>
          <div style={{ fontSize: '9.5px', color: '#64748B', marginTop: '2px' }}>
            {viewMode === 'trips' ? 'Economy fares in outer boroughs' : 'Dominates Upper Manhattan & outer boros'}
          </div>
        </div>

        <div
          style={{
            background: 'rgba(168, 85, 247, 0.05)',
            border: '1px solid rgba(168, 85, 247, 0.25)',
            borderRadius: '8px',
            padding: '8px 12px',
          }}
        >
          <div className="flex items-center justify-between">
            <span style={{ color: '#A855F7', fontSize: '11px', fontWeight: 700 }}>FHVHV (Uber/Lyft)</span>
            <span style={{ color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: '12px', fontWeight: 800 }}>
              {stats.fhvhvCount} {viewMode === 'trips' ? 'trips' : 'zones'}
            </span>
          </div>
          <div style={{ fontSize: '9.5px', color: '#64748B', marginTop: '2px' }}>
            {viewMode === 'trips' ? 'Long-haul high velocity airport clusters' : 'Wide perimeter coverage across 5 boroughs'}
          </div>
        </div>
      </div>
    </div>
  );
};
