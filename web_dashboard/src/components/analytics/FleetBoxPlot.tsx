import React, { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { useFleetStore } from '../../store/useFleetStore';
import { BoxSelect, DollarSign, Gauge, Users } from 'lucide-react';

type MetricType = 'fare' | 'speed' | 'passengers';

interface BoxStats {
  count: number;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  mean: number;
  lowerWhisker: number;
  upperWhisker: number;
  outliers: number[];
}

function calcStats(data: number[]): BoxStats {
  const filtered = data.filter((v) => !isNaN(v) && v > 0);
  if (filtered.length === 0) {
    return {
      count: 0,
      min: 0,
      q1: 0,
      median: 0,
      q3: 0,
      max: 0,
      mean: 0,
      lowerWhisker: 0,
      upperWhisker: 0,
      outliers: [],
    };
  }

  const sorted = [...filtered].sort((a, b) => a - b);
  const n = sorted.length;
  const min = sorted[0];
  const max = sorted[n - 1];
  const mean = sorted.reduce((sum, v) => sum + v, 0) / n;

  const getPercentile = (p: number) => {
    const pos = (n - 1) * p;
    const base = Math.floor(pos);
    const rest = pos - base;
    if (sorted[base + 1] !== undefined) {
      return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
    }
    return sorted[base];
  };

  const q1 = getPercentile(0.25);
  const median = getPercentile(0.5);
  const q3 = getPercentile(0.75);
  const iqr = q3 - q1;

  const lowerBound = q1 - 1.5 * iqr;
  const upperBound = q3 + 1.5 * iqr;

  let lowerWhisker = min;
  for (let i = 0; i < n; i++) {
    if (sorted[i] >= lowerBound) {
      lowerWhisker = sorted[i];
      break;
    }
  }

  let upperWhisker = max;
  for (let i = n - 1; i >= 0; i--) {
    if (sorted[i] <= upperBound) {
      upperWhisker = sorted[i];
      break;
    }
  }

  const outliers: number[] = [];
  for (const v of sorted) {
    if (v < lowerWhisker || v > upperWhisker) {
      outliers.push(v);
    }
  }

  return {
    count: n,
    min,
    q1,
    median,
    q3,
    max,
    mean,
    lowerWhisker,
    upperWhisker,
    outliers,
  };
}

export const FleetBoxPlot: React.FC = () => {
  const vehicles = useFleetStore((s) => s.vehicles);
  const [metric, setMetric] = useState<MetricType>('fare');

  const { stats, option } = useMemo(() => {
    const extractValues = (type: string) => {
      const subset = vehicles.filter((v) => v.dataset_source === type);
      if (metric === 'fare') return subset.map((v) => v.fare_amount || 0);
      if (metric === 'speed') return subset.map((v) => v.speed_mph || 0);
      return subset.map((v) => v.passenger_count || 1);
    };

    const yellowVals = extractValues('YELLOW');
    const greenVals = extractValues('GREEN');
    const fhvhvVals = extractValues('FHVHV');

    const yellow = calcStats(yellowVals);
    const green = calcStats(greenVals);
    const fhvhv = calcStats(fhvhvVals);

    const unit = metric === 'fare' ? '$' : metric === 'speed' ? ' MPH' : ' pax';
    const metricTitle =
      metric === 'fare'
        ? 'Trip Fare ($ USD)'
        : metric === 'speed'
        ? 'Velocity (MPH)'
        : 'Passenger Count';

    // Box plot 5-number array: [minWhisker, Q1, median, Q3, maxWhisker]
    const boxData = [
      {
        value: [
          Number(yellow.lowerWhisker.toFixed(1)),
          Number(yellow.q1.toFixed(1)),
          Number(yellow.median.toFixed(1)),
          Number(yellow.q3.toFixed(1)),
          Number(yellow.upperWhisker.toFixed(1)),
        ],
        itemStyle: {
          borderColor: '#FACC15',
          borderWidth: 2,
          color: 'rgba(250, 204, 21, 0.25)',
        },
      },
      {
        value: [
          Number(green.lowerWhisker.toFixed(1)),
          Number(green.q1.toFixed(1)),
          Number(green.median.toFixed(1)),
          Number(green.q3.toFixed(1)),
          Number(green.upperWhisker.toFixed(1)),
        ],
        itemStyle: {
          borderColor: '#22C55E',
          borderWidth: 2,
          color: 'rgba(34, 197, 94, 0.25)',
        },
      },
      {
        value: [
          Number(fhvhv.lowerWhisker.toFixed(1)),
          Number(fhvhv.q1.toFixed(1)),
          Number(fhvhv.median.toFixed(1)),
          Number(fhvhv.q3.toFixed(1)),
          Number(fhvhv.upperWhisker.toFixed(1)),
        ],
        itemStyle: {
          borderColor: '#A855F7',
          borderWidth: 2,
          color: 'rgba(168, 85, 247, 0.25)',
        },
      },
    ];

    const outlierPoints: [number, number, string, string][] = [
      ...yellow.outliers.map((v) => [0, Number(v.toFixed(1)), '#FACC15', 'Yellow Cab'] as [number, number, string, string]),
      ...green.outliers.map((v) => [1, Number(v.toFixed(1)), '#22C55E', 'Green Boro'] as [number, number, string, string]),
      ...fhvhv.outliers.map((v) => [2, Number(v.toFixed(1)), '#A855F7', 'FHVHV (Uber/Lyft)'] as [number, number, string, string]),
    ];

    const meanPoints: [number, number, string, string][] = [
      [0, Number(yellow.mean.toFixed(1)), '#FACC15', 'Yellow Cab Mean'],
      [1, Number(green.mean.toFixed(1)), '#22C55E', 'Green Boro Mean'],
      [2, Number(fhvhv.mean.toFixed(1)), '#A855F7', 'FHVHV Mean'],
    ];

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
          if (params.seriesType === 'boxplot') {
            const fleets = [
              { name: 'Yellow Cab', color: '#FACC15', s: yellow },
              { name: 'Green Boro', color: '#22C55E', s: green },
              { name: 'FHVHV (Uber/Lyft)', color: '#A855F7', s: fhvhv },
            ];
            const item = fleets[params.dataIndex];
            if (!item) return '';

            return `
              <div style="font-weight:800; color:${item.color}; font-size:12px; margin-bottom:3px; font-family:'Plus Jakarta Sans',sans-serif;">
                ${item.name} • ${metricTitle}
              </div>
              <div style="font-size:10.5px; color:#94A3B8; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px;">
                Active Sample: <strong style="color:#F1F5F9;">${item.s.count} vehicles</strong>
              </div>
              <div style="display:grid; grid-template-columns: 1fr 1fr; gap:5px 16px; font-family:'JetBrains Mono',monospace; font-size:11px;">
                <div><span style="color:#94A3B8;">Upper Whisker:</span> <strong style="color:#F1F5F9;">${metric === 'fare' ? '$' : ''}${item.s.upperWhisker.toFixed(1)}${metric !== 'fare' ? unit : ''}</strong></div>
                <div><span style="color:#94A3B8;">Q3 (75%):</span> <strong style="color:#F1F5F9;">${metric === 'fare' ? '$' : ''}${item.s.q3.toFixed(1)}${metric !== 'fare' ? unit : ''}</strong></div>
                <div><span style="color:#00F5FF; font-weight:700;">Median:</span> <strong style="color:#00F5FF;">${metric === 'fare' ? '$' : ''}${item.s.median.toFixed(1)}${metric !== 'fare' ? unit : ''}</strong></div>
                <div><span style="color:#F87171;">Mean (Avg):</span> <strong style="color:#F87171;">${metric === 'fare' ? '$' : ''}${item.s.mean.toFixed(1)}${metric !== 'fare' ? unit : ''}</strong></div>
                <div><span style="color:#94A3B8;">Q1 (25%):</span> <strong style="color:#F1F5F9;">${metric === 'fare' ? '$' : ''}${item.s.q1.toFixed(1)}${metric !== 'fare' ? unit : ''}</strong></div>
                <div><span style="color:#94A3B8;">Lower Whisker:</span> <strong style="color:#F1F5F9;">${metric === 'fare' ? '$' : ''}${item.s.lowerWhisker.toFixed(1)}${metric !== 'fare' ? unit : ''}</strong></div>
                <div><span style="color:#CBD5E1;">IQR Span:</span> <strong style="color:#CBD5E1;">${(item.s.q3 - item.s.q1).toFixed(1)}</strong></div>
                <div><span style="color:#FB7185;">Outliers:</span> <strong style="color:#FB7185;">${item.s.outliers.length} trips</strong></div>
              </div>
            `;
          }

          if (params.seriesType === 'scatter' && params.seriesName === 'Outliers') {
            const data = params.data;
            return `
              <div style="font-family:'JetBrains Mono',monospace; font-size:11px;">
                <span style="color:${data[2]}; font-weight:700;">${data[3]} Outlier</span>:
                <strong style="color:#F1F5F9; font-size:12px;">${metric === 'fare' ? '$' : ''}${data[1]}${metric !== 'fare' ? unit : ''}</strong>
              </div>
            `;
          }

          if (params.seriesType === 'scatter' && params.seriesName === 'Mean') {
            const data = params.data;
            return `
              <div style="font-family:'JetBrains Mono',monospace; font-size:11px;">
                <span style="color:${data[2]}; font-weight:700;">${data[3]}</span>:
                <strong style="color:#F1F5F9; font-size:12px;">${metric === 'fare' ? '$' : ''}${data[1]}${metric !== 'fare' ? unit : ''}</strong>
              </div>
            `;
          }

          return '';
        },
      },
      grid: {
        top: 26,
        right: 24,
        bottom: 28,
        left: 42,
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        data: ['Yellow Cab', 'Green Boro', 'FHVHV (Uber/Lyft)'],
        axisLine: { lineStyle: { color: 'rgba(56, 189, 248, 0.25)' } },
        axisTick: { show: false },
        axisLabel: {
          color: '#F1F5F9',
          fontFamily: 'Plus Jakarta Sans, sans-serif',
          fontSize: 11,
          fontWeight: 600,
        },
      },
      yAxis: {
        type: 'value',
        name: metricTitle,
        nameTextStyle: {
          color: '#94A3B8',
          fontSize: 10,
          fontFamily: 'JetBrains Mono',
          padding: [0, 0, 4, 0],
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(255, 255, 255, 0.05)',
            type: 'dashed',
          },
        },
        axisLabel: {
          color: '#64748B',
          fontFamily: 'JetBrains Mono',
          fontSize: 9.5,
          formatter: (val: number) => (metric === 'fare' ? `$${val}` : `${val}`),
        },
      },
      series: [
        {
          name: 'Box Quartiles',
          type: 'boxplot',
          boxWidth: ['25%', '42%'],
          data: boxData,
        },
        {
          name: 'Outliers',
          type: 'scatter',
          data: outlierPoints,
          symbolSize: 6,
          itemStyle: {
            color: (param: any) => param.data[2] || '#00F5FF',
            shadowBlur: 6,
            shadowColor: 'rgba(0, 245, 255, 0.4)',
          },
        },
        {
          name: 'Mean',
          type: 'scatter',
          symbol: 'diamond',
          symbolSize: 9,
          data: meanPoints,
          itemStyle: {
            color: '#F87171',
            borderColor: '#FFFFFF',
            borderWidth: 1,
            shadowBlur: 8,
            shadowColor: 'rgba(248, 113, 113, 0.6)',
          },
        },
      ],
    };

    return {
      stats: { yellow, green, fhvhv, unit },
      option: chartOpt,
    };
  }, [vehicles, metric]);

  return (
    <div className="glass-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header with Title and Metric Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BoxSelect size={15} className="text-cyan" />
          <span style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '0.04em', color: '#F1F5F9' }}>
            3-FLEET STATISTICAL DISTRIBUTION (BOX PLOT)
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
            IQR & OUTLIERS
          </span>
        </div>

        {/* Metric Selector Buttons */}
        <div className="flex items-center gap-1" style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '2px', borderRadius: '6px' }}>
          <button
            onClick={() => setMetric('fare')}
            className="flex items-center gap-1"
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontFamily: 'JetBrains Mono',
              fontWeight: metric === 'fare' ? 700 : 500,
              background: metric === 'fare' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
              color: metric === 'fare' ? '#00F5FF' : '#94A3B8',
              border: metric === 'fare' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <DollarSign size={11} />
            FARE ($)
          </button>
          <button
            onClick={() => setMetric('speed')}
            className="flex items-center gap-1"
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontFamily: 'JetBrains Mono',
              fontWeight: metric === 'speed' ? 700 : 500,
              background: metric === 'speed' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
              color: metric === 'speed' ? '#00F5FF' : '#94A3B8',
              border: metric === 'speed' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Gauge size={11} />
            SPEED (MPH)
          </button>
          <button
            onClick={() => setMetric('passengers')}
            className="flex items-center gap-1"
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontFamily: 'JetBrains Mono',
              fontWeight: metric === 'passengers' ? 700 : 500,
              background: metric === 'passengers' ? 'rgba(0, 245, 255, 0.15)' : 'transparent',
              color: metric === 'passengers' ? '#00F5FF' : '#94A3B8',
              border: metric === 'passengers' ? '1px solid rgba(0, 245, 255, 0.35)' : '1px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Users size={11} />
            PASSENGERS
          </button>
        </div>
      </div>

      {/* Box Plot ECharts canvas */}
      <div style={{ height: '220px', width: '100%' }}>
        <ReactECharts option={option} style={{ height: '100%', width: '100%' }} notMerge={true} />
      </div>

      {/* 3 Fleet Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
        {/* Yellow Cab */}
        <div
          style={{
            background: 'rgba(250, 204, 21, 0.05)',
            border: '1px solid rgba(250, 204, 21, 0.25)',
            borderRadius: '8px',
            padding: '8px 12px',
          }}
        >
          <div className="flex items-center justify-between" style={{ marginBottom: '4px' }}>
            <span style={{ color: '#FACC15', fontSize: '11px', fontWeight: 700 }}>Yellow Cab</span>
            <span style={{ color: '#94A3B8', fontSize: '9.5px', fontFamily: 'JetBrains Mono' }}>
              N = {stats.yellow.count}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <span style={{ color: '#94A3B8', fontSize: '10px' }}>Median:</span>
            <span style={{ color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: '13px', fontWeight: 800 }}>
              {metric === 'fare' ? '$' : ''}{stats.yellow.median.toFixed(1)}{metric !== 'fare' ? stats.unit : ''}
            </span>
          </div>
          <div className="flex items-center justify-between" style={{ marginTop: '2px', fontSize: '9.5px', color: '#64748B' }}>
            <span>IQR: {(stats.yellow.q3 - stats.yellow.q1).toFixed(1)}</span>
            <span>Avg: {metric === 'fare' ? '$' : ''}{stats.yellow.mean.toFixed(1)}</span>
          </div>
        </div>

        {/* Green Boro */}
        <div
          style={{
            background: 'rgba(34, 197, 94, 0.05)',
            border: '1px solid rgba(34, 197, 94, 0.25)',
            borderRadius: '8px',
            padding: '8px 12px',
          }}
        >
          <div className="flex items-center justify-between" style={{ marginBottom: '4px' }}>
            <span style={{ color: '#22C55E', fontSize: '11px', fontWeight: 700 }}>Green Boro</span>
            <span style={{ color: '#94A3B8', fontSize: '9.5px', fontFamily: 'JetBrains Mono' }}>
              N = {stats.green.count}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <span style={{ color: '#94A3B8', fontSize: '10px' }}>Median:</span>
            <span style={{ color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: '13px', fontWeight: 800 }}>
              {metric === 'fare' ? '$' : ''}{stats.green.median.toFixed(1)}{metric !== 'fare' ? stats.unit : ''}
            </span>
          </div>
          <div className="flex items-center justify-between" style={{ marginTop: '2px', fontSize: '9.5px', color: '#64748B' }}>
            <span>IQR: {(stats.green.q3 - stats.green.q1).toFixed(1)}</span>
            <span>Avg: {metric === 'fare' ? '$' : ''}{stats.green.mean.toFixed(1)}</span>
          </div>
        </div>

        {/* FHVHV */}
        <div
          style={{
            background: 'rgba(168, 85, 247, 0.05)',
            border: '1px solid rgba(168, 85, 247, 0.25)',
            borderRadius: '8px',
            padding: '8px 12px',
          }}
        >
          <div className="flex items-center justify-between" style={{ marginBottom: '4px' }}>
            <span style={{ color: '#A855F7', fontSize: '11px', fontWeight: 700 }}>FHVHV (Uber/Lyft)</span>
            <span style={{ color: '#94A3B8', fontSize: '9.5px', fontFamily: 'JetBrains Mono' }}>
              N = {stats.fhvhv.count}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <span style={{ color: '#94A3B8', fontSize: '10px' }}>Median:</span>
            <span style={{ color: '#F1F5F9', fontFamily: 'JetBrains Mono', fontSize: '13px', fontWeight: 800 }}>
              {metric === 'fare' ? '$' : ''}{stats.fhvhv.median.toFixed(1)}{metric !== 'fare' ? stats.unit : ''}
            </span>
          </div>
          <div className="flex items-center justify-between" style={{ marginTop: '2px', fontSize: '9.5px', color: '#64748B' }}>
            <span>IQR: {(stats.fhvhv.q3 - stats.fhvhv.q1).toFixed(1)}</span>
            <span>Avg: {metric === 'fare' ? '$' : ''}{stats.fhvhv.mean.toFixed(1)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
