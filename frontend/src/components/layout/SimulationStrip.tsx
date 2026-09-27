import React from 'react';
import './SimulationStrip.css';

export const SimulationStrip: React.FC = () => {
  return (
    <aside className="sim-alert-strip" aria-label="Simulation Environment">
      <div className="sim-strip-left">
        <span className="sim-indicator-dot" />
        <span className="sim-mode-tag">LIVE SIMULATION</span>
        <span className="sim-strip-text">
          Municipal Dispatch Triage Environment
        </span>
      </div>
      <div className="sim-strip-right">
        <span className="sim-id">v1.2</span>
        <span className="sim-speed">1.0X REALTIME</span>
      </div>
    </aside>
  );
};

export default SimulationStrip;
