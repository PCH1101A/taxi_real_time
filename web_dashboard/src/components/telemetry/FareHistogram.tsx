import React, { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { useFleetStore } from '../../store/useFleetStore';
import { BarChart3 } from 'lucide-react';

const BINS = ['$0-10', '$10-20', '$20-30', '$30-40', '$40-50', '$50-60', '$60+'];

export const FareHistogram: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);
  const [chartMode, setChartMode] = useState<'stacked' | 'density'>('stacked');

  const option = useMemo(() => {
    const yellow = [0, 0, 0, 0, 0, 0, 0];
    const green = [0, 0, 0, 0, 0, 0, 0];
    const fhvhv = [0, 0, 0, 0, 0, 0, 0];

    const getBin = (f: number) => {
      if (f < 10) return 0;
      if (f < 20) return 1;
      if (f < 30) return 2;
      if (f < 40) return 3;
      if (f < 50) return 4;
      if (f < 60) return 5;
      return 6;
    };

    let totalFareSum = 0;
    let validFareCount = 0;

    for (const v of vehicles) {
      const fare = v.fare_amount || 0;
      if (fare > 0) {
        totalFareSum += fare;
        validFareCount++;
      }
      const idx = getBin(fare);
      if (v.dataset_source === 'YELLOW') yellow[idx]++;
      else if (v.dataset_source === 'GREEN') green[idx]++;
      else if (v.dataset_source === 'FHVHV') fhvhv[idx]++;
    }

    const totals = BINS.map((_, i) => yellow[i] + green[i] + fhvhv[i]);

    // ── STACKED CONTINUOUS HISTOGRAM MODE ──────────────────────────────────
    // In statistical histograms, bins represent continuous ranges and must touch adjacent bins (zero gap)
    if (chartMode === 'stacked') {
      return {
        backgroundColor: 'transparent',
        animationDuration: 400,
        animationEasing: 'cubicOut',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow',
            shadowStyle: { color: 'rgba(0, 245, 255, 0.08)' },
          },
          backgroundColor: 'rgba(10, 22, 40, 0.96)',
          borderColor: 'rgba(56, 189, 248, 0.4)',
          borderWidth: 1,
          padding: [10, 14],
          extraCssText: 'backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius: 8px;',
          formatter: (params: any[]) => {
            if (!params || params.length === 0) return '';
            const binLabel = params[0].axisValue;
            let bracketTotal = 0;
            const items = params.filter((p) => p.seriesName !== 'Macro Distribution');
            items.forEach((p) => {
              bracketTotal += Number(p.value || 0);
            });

            let lines = `<div style="font-weight:700; color:#00F5FF; font-family:'Plus Jakarta Sans',sans-serif; margin-bottom:3px;">
              Fare Range: ${binLabel}
            </div>`;
            lines += `<div style="color:#94A3B8; font-size:10.5px; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px;">
              Total in Bracket: <strong style="color:#F1F5F9;">${bracketTotal} trips</strong>
            </div>`;

            items.forEach((item) => {
              const val = Number(item.value || 0);
              const pct = bracketTotal > 0 ? ((val / bracketTotal) * 100).toFixed(1) : '0.0';
              lines += `
                <div style="display:flex; align-items:center; justify-content:space-between; gap:16px; margin:2px 0;">
                  <span style="display:flex; align-items:center; gap:6px;">
                    <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${item.color};"></span>
                    <span style="color:#CBD5E1; font-size:11px;">${item.seriesName}</span>
                  </span>
                  <span style="font-weight:700; color:#F1F5F9; font-family:'JetBrains Mono'; font-size:11px;">
                    ${val} <span style="color:#94A3B8; font-size:9.5px;">(${pct}%)</span>
                  </span>
                </div>
              `;
            });
            return lines;
          },
        },
        legend: {
          top: 0,
          right: 0,
          data: ['Yellow Cab', 'Green Boro', 'FHVHV (Uber/Lyft)', 'Macro Distribution'],
          itemWidth: 8,
          itemHeight: 8,
          icon: 'circle',
          textStyle: {
            color: '#94A3B8',
            fontSize: 10,
            fontFamily: 'Plus Jakarta Sans, sans-serif',
          },
        },
        grid: { top: 32, right: 16, bottom: 24, left: 32, containLabel: false },
        xAxis: {
          type: 'category',
          data: BINS,
          boundaryGap: true,
          axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
          axisTick: { show: false },
          axisLabel: { color: '#94A3B8', fontFamily: 'JetBrains Mono', fontSize: 10, fontWeight: 500 },
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
          axisLabel: { color: '#64748B', fontFamily: 'JetBrains Mono', fontSize: 9.5 },
        },
        series: [
          {
            name: 'Yellow Cab',
            type: 'bar',
            stack: 'fare',
            barWidth: '100%',
            barCategoryGap: '0%', // Bins touch each other continuously (true histogram)
            itemStyle: {
              borderColor: '#0A1628',
              borderWidth: 1,
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#FACC15' },
                { offset: 1, color: 'rgba(250, 204, 21, 0.45)' },
              ]),
            },
            data: yellow,
          },
          {
            name: 'Green Boro',
            type: 'bar',
            stack: 'fare',
            barWidth: '100%',
            barCategoryGap: '0%', // Bins touch each other continuously (true histogram)
            itemStyle: {
              borderColor: '#0A1628',
              borderWidth: 1,
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#22C55E' },
                { offset: 1, color: 'rgba(34, 197, 94, 0.45)' },
              ]),
            },
            data: green,
          },
          {
            name: 'FHVHV (Uber/Lyft)',
            type: 'bar',
            stack: 'fare',
            barWidth: '100%',
            barCategoryGap: '0%', // Bins touch each other continuously (true histogram)
            itemStyle: {
              borderColor: '#0A1628',
              borderWidth: 1,
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#A855F7' },
                { offset: 1, color: 'rgba(168, 85, 247, 0.45)' },
              ]),
            },
            data: fhvhv,
          },
          {
            name: 'Macro Distribution',
            type: 'line',
            smooth: 0.35,
            symbol: 'circle',
            symbolSize: 5,
            itemStyle: { color: '#00F5FF' },
            lineStyle: {
              width: 2.2,
              color: '#00F5FF',
              shadowBlur: 8,
              shadowColor: 'rgba(0, 245, 255, 0.5)',
            },
            data: totals,
          },
        ],
      };
    }

    // ── SMOOTH DENSITY CURVE MODE (KDE Area) ──────────────────────────────────
    return {
      backgroundColor: 'transparent',
      animationDuration: 400,
      animationEasing: 'cubicOut',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(10, 22, 40, 0.96)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: { color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: 11 },
      },
      legend: {
        top: 0,
        right: 0,
        data: ['Yellow Cab', 'Green Boro', 'FHVHV (Uber/Lyft)'],
        itemWidth: 8,
        itemHeight: 8,
        icon: 'circle',
        textStyle: { color: '#94A3B8', fontSize: 10, fontFamily: 'Plus Jakarta Sans' },
      },
      grid: { top: 32, right: 16, bottom: 24, left: 32, containLabel: false },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: BINS,
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.2)' } },
        axisLabel: { color: '#94A3B8', fontFamily: 'JetBrains Mono', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)', type: 'dashed' } },
        axisLabel: { color: '#64748B', fontFamily: 'JetBrains Mono', fontSize: 9.5 },
      },
      series: [
        {
          name: 'Yellow Cab',
          type: 'line',
          smooth: 0.5,
          showSymbol: false,
          lineStyle: { width: 2, color: '#FACC15' },
          areaStyle: {
            opacity: 0.28,
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#FACC15' },
              { offset: 1, color: 'transparent' },
            ]),
          },
          data: yellow,
        },
        {
          name: 'Green Boro',
          type: 'line',
          smooth: 0.5,
          showSymbol: false,
          lineStyle: { width: 2, color: '#22C55E' },
          areaStyle: {
            opacity: 0.28,
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#22C55E' },
              { offset: 1, color: 'transparent' },
            ]),
          },
          data: green,
        },
        {
          name: 'FHVHV (Uber/Lyft)',
          type: 'line',
          smooth: 0.5,
          showSymbol: false,
          lineStyle: { width: 2, color: '#A855F7' },
          areaStyle: {
            opacity: 0.28,
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#A855F7' },
              { offset: 1, color: 'transparent' },
            ]),
          },
          data: fhvhv,
        },
      ],
    };
  }, [vehicles, chartMode]);

  return (
    <div className="glass-card" style={{ padding: '16px', height: '260px', display: 'flex', flexDirection: 'column' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '8px', minHeight: '26px' }}>
        <div className="flex items-center gap-2">
          <BarChart3 size={14} className="text-cyan" />
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            FARE VALUE DISTRIBUTION ($ USD)
          </span>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1" style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '2px', borderRadius: '6px' }}>
          <button
            onClick={() => setChartMode('stacked')}
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontFamily: 'JetBrains Mono',
              fontWeight: chartMode === 'stacked' ? 700 : 500,
              background: chartMode === 'stacked' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
              color: chartMode === 'stacked' ? '#00F5FF' : '#94A3B8',
              border: chartMode === 'stacked' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            HISTOGRAM
          </button>
          <button
            onClick={() => setChartMode('density')}
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontFamily: 'JetBrains Mono',
              fontWeight: chartMode === 'density' ? 700 : 500,
              background: chartMode === 'density' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
              color: chartMode === 'density' ? '#00F5FF' : '#94A3B8',
              border: chartMode === 'density' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            DENSITY
          </button>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>
    </div>
  );
};
