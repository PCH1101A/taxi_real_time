import React, { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { useFleetStore } from '../../store/useFleetStore';
import { Activity, Zap, Layers } from 'lucide-react';

const BOROUGH_COLORS: Record<string, string> = {
  Manhattan: '#00F5FF',
  Queens: '#38BDF8',
  Brooklyn: '#22C55E',
  Bronx: '#FACC15',
  'Staten Island': '#A855F7',
};

export const ThroughputVelocityChart: React.FC = () => {
  const history = useFleetStore((s) => s.history);
  const vehicles = useFleetStore((s) => s.vehicles);
  const [viewMode, setViewMode] = useState<'telemetry' | 'borough'>('telemetry');

  // Compute live snapshot metrics for header badges
  const currentOps = useMemo(() => {
    if (history.throughput && history.throughput.length > 0) {
      return history.throughput[history.throughput.length - 1];
    }
    return 412;
  }, [history.throughput]);

  const currentSpeed = useMemo(() => {
    if (history.velocity && history.velocity.length > 0) {
      return history.velocity[history.velocity.length - 1];
    }
    return 34.2;
  }, [history.velocity]);

  const option = useMemo(() => {
    const rawTimes = history.timestamps || [];
    const len = rawTimes.length;
    let xData = rawTimes;

    if (len < 5) {
      const now = Date.now();
      xData = Array.from({ length: 15 }, (_, i) => {
        const d = new Date(now - (14 - i) * 2000);
        return d.toLocaleTimeString('en-US', { hour12: false });
      });
    }

    const nPoints = xData.length;

    // ── 1. TELEMETRY MODE: DYNAMIC THROUGHPUT & VELOCITY ───────────────────────
    if (viewMode === 'telemetry') {
      let throughputData = history.throughput || [];
      if (throughputData.length < nPoints) {
        const fillLen = nPoints - throughputData.length;
        const initialFill = Array.from({ length: fillLen }, (_, i) => 380 + Math.round(Math.sin(i * 0.8) * 35 + Math.random() * 20));
        throughputData = [...initialFill, ...throughputData];
      }

      let velocityData = history.velocity || [];
      if (velocityData.length < nPoints) {
        const fillLen = nPoints - velocityData.length;
        const initialFill = Array.from({ length: fillLen }, (_, i) => +(32 + Math.sin(i * 0.6) * 6 + Math.random() * 2).toFixed(1));
        velocityData = [...initialFill, ...velocityData];
      }

      return {
        backgroundColor: 'transparent',
        animation: true,
        animationDuration: 300,
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'line',
            lineStyle: {
              color: 'rgba(0, 245, 255, 0.4)',
              type: 'dashed',
              width: 1,
            },
          },
          backgroundColor: 'rgba(10, 22, 40, 0.95)',
          borderColor: 'rgba(56, 189, 248, 0.4)',
          borderWidth: 1,
          padding: [10, 14],
          extraCssText: 'backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius: 8px;',
          formatter: (params: any[]) => {
            if (!params || params.length === 0) return '';
            const time = params[0].axisValue;
            let html = `<div style="font-size:11px; color:#94A3B8; font-family:'JetBrains Mono'; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:3px;">
              TIME: <span style="color:#F1F5F9; font-weight:700;">${time}</span>
            </div>`;

            params.forEach((p) => {
              const isOps = p.seriesName.includes('Throughput');
              const unit = isOps ? 'ops/s' : 'mph';
              html += `
                <div style="display:flex; align-items:center; justify-content:space-between; gap:16px; margin:3px 0;">
                  <span style="display:flex; align-items:center; gap:6px;">
                    <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${p.color};"></span>
                    <span style="color:#CBD5E1; font-size:11px;">${p.seriesName}</span>
                  </span>
                  <span style="font-weight:700; color:#F1F5F9; font-family:'JetBrains Mono'; font-size:11px;">
                    ${p.value} <span style="color:#64748B; font-size:9.5px;">${unit}</span>
                  </span>
                </div>
              `;
            });
            return html;
          },
        },
        legend: {
          top: 0,
          right: 0,
          data: ['Throughput (Events/s)', 'Fleet Velocity (MPH)'],
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
          top: 32,
          right: 38,
          bottom: 22,
          left: 42,
          containLabel: false,
        },
        xAxis: {
          type: 'category',
          data: xData,
          boundaryGap: false,
          axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
          axisTick: { show: false },
          axisLabel: {
            color: '#64748B',
            fontFamily: 'JetBrains Mono',
            fontSize: 9.5,
            interval: Math.max(1, Math.floor(nPoints / 4)),
          },
        },
        yAxis: [
          {
            type: 'value',
            name: 'ops/s',
            scale: true,
            min: (val: { min: number; max: number }) => Math.max(0, Math.floor(val.min * 0.88)),
            max: (val: { min: number; max: number }) => Math.ceil(val.max * 1.12),
            nameTextStyle: {
              color: '#00F5FF',
              fontFamily: 'JetBrains Mono',
              fontSize: 9,
              padding: [0, 0, 0, -12],
            },
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
            axisLabel: {
              color: '#00F5FF',
              fontFamily: 'JetBrains Mono',
              fontSize: 9.5,
            },
          },
          {
            type: 'value',
            name: 'MPH',
            position: 'right',
            scale: true,
            min: (val: { min: number; max: number }) => Math.max(0, Math.floor(val.min * 0.85)),
            max: (val: { min: number; max: number }) => Math.ceil(val.max * 1.15),
            nameTextStyle: {
              color: '#FACC15',
              fontFamily: 'JetBrains Mono',
              fontSize: 9,
              padding: [0, -12, 0, 0],
            },
            splitLine: { show: false },
            axisLabel: {
              color: '#FACC15',
              fontFamily: 'JetBrains Mono',
              fontSize: 9.5,
            },
          },
        ],
        series: [
          {
            name: 'Throughput (Events/s)',
            type: 'line',
            yAxisIndex: 0,
            smooth: 0.35,
            showSymbol: false,
            lineStyle: {
              width: 2.2,
              color: '#00F5FF',
              shadowColor: 'rgba(0, 245, 255, 0.5)',
              shadowBlur: 8,
            },
            itemStyle: { color: '#00F5FF' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(0, 245, 255, 0.32)' },
                { offset: 1, color: 'rgba(0, 245, 255, 0.0)' },
              ]),
            },
            data: throughputData,
          },
          {
            name: 'Fleet Velocity (MPH)',
            type: 'line',
            yAxisIndex: 1,
            smooth: 0.35,
            showSymbol: false,
            lineStyle: {
              width: 2,
              color: '#FACC15',
              shadowColor: 'rgba(250, 204, 21, 0.4)',
              shadowBlur: 6,
            },
            itemStyle: { color: '#FACC15' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(250, 204, 21, 0.18)' },
                { offset: 1, color: 'rgba(250, 204, 21, 0.0)' },
              ]),
            },
            data: velocityData,
          },
        ],
      };
    }

    // ── 2. BOROUGH DISTRIBUTION MODE: STACKED REAL-TIME AREA FLOW ─────────────
    const boroughNames = ['Manhattan', 'Queens', 'Brooklyn', 'Bronx', 'Staten Island'];
    const boroughSeries = boroughNames.map((name) => {
      let bData = (history.boroughStreams && history.boroughStreams[name]) || [];
      if (bData.length < nPoints) {
        const fillLen = nPoints - bData.length;
        const seedBase = name === 'Manhattan' ? 180 : name === 'Queens' ? 95 : name === 'Brooklyn' ? 80 : 25;
        const initialFill = Array.from({ length: fillLen }, (_, i) => Math.max(5, Math.round(seedBase + Math.sin(i * 0.7) * 15 + Math.random() * 8)));
        bData = [...initialFill, ...bData];
      }

      const color = BOROUGH_COLORS[name] || '#38BDF8';

      return {
        name,
        type: 'line',
        stack: 'Total',
        smooth: 0.3,
        showSymbol: false,
        lineStyle: { width: 1.5, color },
        itemStyle: { color },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color },
            { offset: 1, color: 'rgba(0,0,0,0.2)' },
          ]),
          opacity: 0.75,
        },
        data: bData,
      };
    });

    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { backgroundColor: '#0A1628' } },
        backgroundColor: 'rgba(10, 22, 40, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        textStyle: { color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: 11 },
      },
      legend: {
        top: 0,
        right: 0,
        data: boroughNames,
        itemWidth: 8,
        itemHeight: 8,
        icon: 'circle',
        textStyle: { color: '#94A3B8', fontSize: 9.5, fontFamily: 'Plus Jakarta Sans' },
      },
      grid: { top: 32, right: 16, bottom: 22, left: 32, containLabel: false },
      xAxis: {
        type: 'category',
        data: xData,
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
        axisLabel: { color: '#64748B', fontFamily: 'JetBrains Mono', fontSize: 9.5, interval: Math.max(1, Math.floor(nPoints / 4)) },
      },
      yAxis: {
        type: 'value',
        name: 'Vehicles',
        scale: true,
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
        axisLabel: { color: '#94A3B8', fontFamily: 'JetBrains Mono', fontSize: 9.5 },
      },
      series: boroughSeries,
    };
  }, [history.timestamps, history.throughput, history.velocity, history.boroughStreams, viewMode]);

  return (
    <div
      className="glass-card"
      style={{
        padding: '16px',
        height: '260px',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div className="flex items-center justify-between" style={{ marginBottom: '8px', minHeight: '26px' }}>
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-cyan animate-pulse" />
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            {viewMode === 'telemetry' ? 'STREAMING THROUGHPUT & VELOCITY' : 'STREAMING BOROUGH LOAD'}
          </span>
        </div>

        {/* View Mode Toggle & Live Badge */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1" style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '2px', borderRadius: '6px' }}>
            <button
              onClick={() => setViewMode('telemetry')}
              style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '10px',
                fontFamily: 'JetBrains Mono',
                fontWeight: viewMode === 'telemetry' ? 700 : 500,
                background: viewMode === 'telemetry' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
                color: viewMode === 'telemetry' ? '#00F5FF' : '#94A3B8',
                border: viewMode === 'telemetry' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              TELEMETRY
            </button>
            <button
              onClick={() => setViewMode('borough')}
              style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '10px',
                fontFamily: 'JetBrains Mono',
                fontWeight: viewMode === 'borough' ? 700 : 500,
                background: viewMode === 'borough' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
                color: viewMode === 'borough' ? '#00F5FF' : '#94A3B8',
                border: viewMode === 'borough' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              BOROUGHS
            </button>
          </div>

          {viewMode === 'telemetry' && (
            <div className="flex items-center gap-1.5">
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
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <Zap size={10} />
                {currentOps} ops/s
              </span>
              <span
                style={{
                  fontSize: '10px',
                  fontFamily: 'JetBrains Mono',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  background: 'rgba(250, 204, 21, 0.12)',
                  color: '#FACC15',
                  border: '1px solid rgba(250, 204, 21, 0.3)',
                }}
              >
                {currentSpeed} MPH
              </span>
            </div>
          )}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, width: '100%' }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
