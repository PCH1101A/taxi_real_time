import React from 'react';
import { KpiCards } from '../telemetry/KpiCards';
import { ZoneConcentration } from '../telemetry/ZoneConcentration';
import { ThroughputVelocityChart } from '../telemetry/ThroughputVelocityChart';
import { FareHistogram } from '../telemetry/FareHistogram';
import { LiveFeedTable } from '../telemetry/LiveFeedTable';

export const TelemetryTab: React.FC = () => {
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
      <KpiCards />

      {/* Analytics Charts Grid (3 columns balanced) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', alignItems: 'stretch' }}>
        <ZoneConcentration />
        <ThroughputVelocityChart />
        <FareHistogram />
      </div>

      {/* Live Micro-Batch Trip Feed */}
      <LiveFeedTable />
    </div>
  );
};
