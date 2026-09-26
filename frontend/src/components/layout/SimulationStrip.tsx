import React from 'react';
import { Badge } from '../ui';
import './SimulationStrip.css';

export const SimulationStrip: React.FC = () => {
  return (
    <aside className="sim-alert-strip" aria-label="Drill & Simulation Banner">
      <div className="sim-strip-left">
        <Badge variant="simulation" size="sm" showBeacon beaconColor="var(--color-void-dark)">
          MODE: SIM-LIVE
        </Badge>
        <span className="sim-strip-text">
          DRILL RUNBOOK READY // TINGLE OPERATOR DECISION SUPPORT CONSOLE
        </span>
      </div>
      <div className="sim-strip-right">
        <span className="sim-id">SYSTEM: TINGLE v0.2.0-STARK</span>
        <span className="sim-speed">SPEED: 1.0X</span>
      </div>
    </aside>
  );
};

export default SimulationStrip;
