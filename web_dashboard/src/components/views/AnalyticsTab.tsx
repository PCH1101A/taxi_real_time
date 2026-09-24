import React from 'react';
import { Scoreboard } from '../analytics/Scoreboard';
import { BoroughHeatmap } from '../analytics/BoroughHeatmap';
import { RadarChart } from '../analytics/RadarChart';
import { FleetBoxPlot } from '../analytics/FleetBoxPlot';
import { FleetBubbleScatter } from '../analytics/FleetBubbleScatter';

export const AnalyticsTab: React.FC = () => {
  return (
    <div
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      {/* 3-Fleet Scoreboard */}
      <Scoreboard />

      {/* Grid: Heatmap & Radar Spider */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '12px', minHeight: '380px' }}>
        <BoroughHeatmap />
        <RadarChart />
      </div>

      {/* Grid: 3-Fleet Box Plot & Bubble Scatter */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '12px' }}>
        <FleetBoxPlot />
        <FleetBubbleScatter />
      </div>
    </div>
  );
};
