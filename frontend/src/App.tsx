import React from 'react';
import { 
  Radio, 
  MapPin, 
  Layers,
  Clock,
  Wifi,
  Search,
  Activity
} from 'lucide-react';
import {
  Badge,
  StatusIndicator,
  AudioVisualizerBar,
  TacticalInput
} from './components/ui';
import './App.css';

export const App: React.FC = () => {
  const [currentTime, setCurrentTime] = React.useState<string>(() => 
    new Date().toISOString().substring(11, 19) + ' UTC'
  );

  React.useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toISOString().substring(11, 19) + ' UTC');
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="command-center">
      {/* Simulation / Training Strip */}
      <div className="sim-alert-strip">
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
      </div>

      {/* Primary Header Bar */}
      <header className="header-bar">
        <div className="header-left">
          <div className="header-brand-group">
            <span className="brand-logo-badge">TINGLE</span>
            <Badge variant="p2-medium" size="sm">TAC-OPS</Badge>
          </div>
          <div className="header-hud-metrics">
            <StatusIndicator status="online" label="ENGINE ONLINE" />
            <StatusIndicator status="connected" label="WS READY" />
          </div>
        </div>

        <div className="header-center">
          <div className="search-container">
            <TacticalInput
              placeholder="SEARCH INCIDENTS, LOCATIONS, TAC-CHANNELS..."
              leftIcon={<Search size={14} />}
              disabled
            />
          </div>
        </div>

        <div className="header-right">
          <div className="header-channel-monitor">
            <span className="channel-label">RF MONITOR:</span>
            <AudioVisualizerBar />
            <span className="channel-freq">470.8125 MHz</span>
          </div>
          <div className="operator-badge">
            OP: SRINIVASH
          </div>
        </div>
      </header>

      {/* Main Workspace Split (Placeholder ready for Phase 4 / Stitch screens) */}
      <main className="workspace-split">
        {/* Left Pane: Incident Queue Container */}
        <section className="queue-panel" aria-label="Incident Queue">
          <div className="panel-header">
            <div className="panel-title-group">
              <span className="panel-title">Prioritized Incident Queue</span>
              <Badge variant="neutral" size="sm">0 QUEUED</Badge>
            </div>
            <div className="panel-controls">
              <Layers size={14} color="var(--color-text-muted)" />
            </div>
          </div>

          <div className="panel-body-placeholder">
            <div className="placeholder-icon">
              <Radio size={40} color="var(--color-multiverse-cyan)" />
            </div>
            <div className="placeholder-title">Awaiting Live Dispatches</div>
            <div className="placeholder-desc">
              Tingle kinetic triage engine initialized. Incoming emergency signals, multi-report fusion, and deterministic priority scoring will stream here.
            </div>
            <div className="placeholder-tags">
              <Badge variant="p0-critical" size="sm">P0 CRITICAL</Badge>
              <Badge variant="p1-high" size="sm">P1 HIGH</Badge>
              <Badge variant="p2-medium" size="sm">P2 MED</Badge>
              <Badge variant="p3-low" size="sm">P3 LOW</Badge>
              <Badge variant="needs-review" size="sm">NEEDS REVIEW</Badge>
            </div>
          </div>
        </section>

        {/* Right Pane: Tactical Geographic Map Container */}
        <section className="map-panel" aria-label="Tactical Map">
          <div className="map-overlay-badge">
            <MapPin size={14} color="var(--color-multiverse-cyan)" />
            <span>TACTICAL GEOGRAPHIC MAP — LEAFLET / OSM ENGINE</span>
          </div>

          <div className="map-view-area">
            <div className="placeholder-icon">
              <Activity size={44} color="var(--color-text-muted)" />
            </div>
            <div className="placeholder-title">Cartographic Grid Primed</div>
            <div className="placeholder-desc">
              Validated hazard coordinates and corroboration vectors will be plotted with 0px neo-brutalist pins without coordinate hallucination.
            </div>
          </div>
        </section>
      </main>

      {/* Footer Telemetry Bar */}
      <footer className="footer-bar">
        <div className="footer-left">
          <span>PRODUCT: TINGLE</span>
          <span>DECISION SUPPORT v1.2</span>
          <span>BACKEND: http://127.0.0.1:8000</span>
          <span>HUMAN-IN-THE-LOOP SOVEREIGN</span>
        </div>
        <div className="footer-right">
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Clock size={12} />
            {currentTime}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Wifi size={12} />
            WS STANDBY
          </span>
        </div>
      </footer>
    </div>
  );
};

export default App;
