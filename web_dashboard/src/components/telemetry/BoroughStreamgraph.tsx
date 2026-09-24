import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { useFleetStore } from '../../store/useFleetStore';
import { Activity } from 'lucide-react';

interface BoroughConfig {
  name: string;
  color: string;
  gradientTo: string;
}

// Ordered for aesthetic stream flow: lighter/smaller boroughs at edges, major hubs toward core
const BOROUGHS: BoroughConfig[] = [
  { name: 'Staten Island', color: '#F43F5E', gradientTo: 'rgba(244, 63, 94, 0.45)' },
  { name: 'Bronx', color: '#38BDF8', gradientTo: 'rgba(56, 189, 248, 0.45)' },
  { name: 'Brooklyn', color: '#22C55E', gradientTo: 'rgba(34, 197, 94, 0.45)' },
  { name: 'Queens', color: '#FACC15', gradientTo: 'rgba(250, 204, 21, 0.45)' },
  { name: 'Manhattan', color: '#00F5FF', gradientTo: 'rgba(0, 245, 255, 0.45)' },
];

export const BoroughStreamgraph: React.FC = () => {
  const history = useFleetStore((s) => s.history);
  const vehicles = useFleetStore((s) => s.vehicles);

  const option = useMemo(() => {
    let timestamps = history.timestamps || [];
    let boroughStreams = history.boroughStreams || {};

    // Live counts fallback
    const currentCounts: Record<string, number> = {
      Manhattan: 0,
      Queens: 0,
      Brooklyn: 0,
      Bronx: 0,
      'Staten Island': 0,
    };

    for (const v of vehicles) {
      const b = v.borough || 'Manhattan';
      if (b in currentCounts) currentCounts[b] = (currentCounts[b] || 0) + 1;
    }

    // Seed mock window if we have fewer than 5 frames so the streamgraph is immediately vibrant
    if (timestamps.length < 5) {
      const mockPoints = 14;
      const now = Date.now();
      timestamps = Array.from({ length: mockPoints }, (_, i) => {
        const d = new Date(now - (mockPoints - i) * 3000);
        return d.toLocaleTimeString('en-US', { hour12: false });
      });

      boroughStreams = {
        Manhattan: Array.from({ length: mockPoints }, (_, i) =>
          Math.max(20, Math.round((currentCounts.Manhattan || 220) * (0.88 + 0.18 * Math.sin(i * 0.45))))
        ),
        Queens: Array.from({ length: mockPoints }, (_, i) =>
          Math.max(15, Math.round((currentCounts.Queens || 110) * (0.85 + 0.22 * Math.sin(i * 0.5 + 1.2))))
        ),
        Brooklyn: Array.from({ length: mockPoints }, (_, i) =>
          Math.max(12, Math.round((currentCounts.Brooklyn || 85) * (0.9 + 0.18 * Math.cos(i * 0.4))))
        ),
        Bronx: Array.from({ length: mockPoints }, (_, i) =>
          Math.max(6, Math.round((currentCounts.Bronx || 32) * (0.85 + 0.22 * Math.sin(i * 0.65))))
        ),
        'Staten Island': Array.from({ length: mockPoints }, (_, i) =>
          Math.max(4, Math.round((currentCounts['Staten Island'] || 14) * (0.85 + 0.25 * Math.cos(i * 0.5))))
        ),
      };
    }

    const nPoints = timestamps.length;
    const OFFSET = 1200; // Positive baseline anchor to prevent negative stacking clipping

    // 1. Calculate total thickness and wavy center axis C(t) for every time point
    const baselineData: number[] = [];
    const boroughDataMap: Record<string, number[]> = {};

    for (const b of BOROUGHS) {
      const raw = boroughStreams[b.name] || [];
      boroughDataMap[b.name] = timestamps.map((_, idx) => {
        const val = raw[idx];
        return typeof val === 'number' ? val : currentCounts[b.name] || 10;
      });
    }

    for (let i = 0; i < nPoints; i++) {
      let totalAtT = 0;
      for (const b of BOROUGHS) {
        totalAtT += boroughDataMap[b.name][i];
      }

      // Free-flowing organic wave for the central axis C(t)
      // Combines multi-frequency harmonics for natural fluid river motion
      const wave = Math.sin(i * 0.38) * 36 + Math.cos(i * 0.18 + 0.8) * 20;

      // Symmetric Streamgraph formula: Base(t) = Center(t) - Total(t) / 2
      // Center(t) = OFFSET + wave
      const baseAtT = Math.round(OFFSET + wave - totalAtT / 2);
      baselineData.push(baseAtT);
    }

    // 2. Build series: Series 0 is the invisible baseline foundation
    const series: any[] = [
      {
        name: '__baseline__',
        type: 'line',
        stack: 'boroughStream',
        smooth: 0.5,
        symbol: 'none',
        lineStyle: { opacity: 0 },
        areaStyle: { opacity: 0, color: 'rgba(0,0,0,0)' },
        tooltip: { show: false },
        data: baselineData,
      },
      ...BOROUGHS.map((b) => ({
        name: b.name,
        type: 'line',
        stack: 'boroughStream',
        smooth: 0.5,
        symbol: 'none',
        lineStyle: {
          width: 1.2,
          color: b.color,
        },
        areaStyle: {
          opacity: 0.82,
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: b.color },
            { offset: 1, color: b.gradientTo },
          ]),
        },
        emphasis: {
          focus: 'series',
        },
        data: boroughDataMap[b.name],
      })),
    ];

    return {
      backgroundColor: 'transparent',
      animationDuration: 500,
      animationEasing: 'cubicOut',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(10, 22, 40, 0.96)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: '#F1F5F9',
          fontFamily: 'JetBrains Mono',
          fontSize: 11,
        },
        axisPointer: {
          type: 'line',
          lineStyle: {
            color: 'rgba(0, 245, 255, 0.5)',
            type: 'dashed',
            width: 1.2,
          },
        },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return '';
          // Filter out the invisible baseline series
          const activeLayers = params.filter((p) => p.seriesName !== '__baseline__');
          if (activeLayers.length === 0) return '';

          const time = activeLayers[0].axisValue;
          let total = 0;
          activeLayers.forEach((p) => {
            total += Number(p.value || 0);
          });

          let lines = `<div style="font-weight:700; color:#00F5FF; margin-bottom:4px; font-family:'Plus Jakarta Sans',sans-serif;">⏱ ${time}</div>`;
          lines += `<div style="color:#94A3B8; font-size:10.5px; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px;">
            Total Active Fleet: <strong style="color:#F1F5F9;">${total} units</strong>
          </div>`;

          // Reverse display in tooltip to show Manhattan on top down to Staten Island
          [...activeLayers].reverse().forEach((item) => {
            const val = Number(item.value || 0);
            const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
            lines += `
              <div style="display:flex; align-items:center; justify-content:space-between; gap:16px; margin:3px 0;">
                <span style="display:flex; align-items:center; gap:6px;">
                  <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${item.color}; box-shadow: 0 0 6px ${item.color};"></span>
                  <span style="color:#E2E8F0;">${item.seriesName}</span>
                </span>
                <span style="font-weight:700; color:#F1F5F9;">${val} <span style="color:#94A3B8; font-size:10px;">(${pct}%)</span></span>
              </div>
            `;
          });
          return lines;
        },
      },
      legend: {
        top: 0,
        right: 0,
        data: ['Manhattan', 'Queens', 'Brooklyn', 'Bronx', 'Staten Island'],
        itemWidth: 8,
        itemHeight: 8,
        icon: 'circle',
        textStyle: {
          color: '#94A3B8',
          fontSize: 10,
          fontFamily: 'Plus Jakarta Sans, sans-serif',
        },
      },
      grid: {
        top: 28,
        left: 12,
        right: 12,
        bottom: 22,
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: timestamps,
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.08)' } },
        axisLabel: {
          color: '#64748B',
          fontSize: 9.5,
          fontFamily: 'JetBrains Mono',
          interval: Math.max(1, Math.floor(timestamps.length / 4)),
        },
        axisTick: { show: false },
        splitLine: {
          show: true,
          lineStyle: { color: 'rgba(255, 255, 255, 0.03)', type: 'dashed' },
        },
      },
      // Real Streamgraphs have no arbitrary numeric Y-axis origin; they float organically
      yAxis: {
        type: 'value',
        show: false,
        min: 'dataMin',
        max: 'dataMax',
      },
      series,
    };
  }, [history.timestamps, history.boroughStreams, vehicles]);

  return (
    <div
      className="glass-card"
      style={{
        padding: '16px',
        height: '240px',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: '6px' }}>
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-cyan animate-pulse" />
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            STREAMING BOROUGH STREAMGRAPH
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            style={{
              fontSize: '9.5px',
              fontFamily: 'JetBrains Mono',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '9999px',
              background: 'rgba(0, 245, 255, 0.12)',
              color: '#00F5FF',
              border: '1px solid rgba(0, 245, 255, 0.3)',
            }}
          >
            SYMMETRIC RIVER FLOW
          </span>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, width: '100%' }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
