import React from 'react';
import { 
  Radio, 
  MapPin, 
  Activity, 
  Wifi, 
  Layers,
  Clock
} from 'lucide-react';
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
      {/* Top Header Bar */}
      <header className="header-bar">
        <div className="header-left">
          <div className="header-title-group">
            <span className="brand-icon">🎙️</span>
            <span className="brand-title">Karen's Ear</span>
            <span className="brand-badge">Command Center</span>
          </div>
        </div>

        <div className="header-center">
          <div className="metric-pill">
            <span className="metric-label">TOTAL:</span>
            <span className="metric-value">0</span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">CRITICAL:</span>
            <span className="metric-value critical">0</span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">HIGH:</span>
            <span className="metric-value high">0</span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">REVIEW:</span>
            <span className="metric-value">0</span>
          </div>
        </div>

        <div className="header-right">
          <div className="status-indicator">
            <span className="status-dot" />
            <span>STANDBY</span>
          </div>
          <div className="operator-badge">
            OP: SRINIVASH
          </div>
        </div>
      </header>

      {/* Main Workspace Split */}
      <main className="workspace-split">
        {/* Left Pane: Prioritized Incident Queue Container */}
        <section className="queue-panel" aria-label="Incident Queue">
          <div className="panel-header">
            <div className="panel-title">Prioritized Incident Queue</div>
            <Layers size={14} color="var(--color-text-muted)" />
          </div>

          <div className="panel-body-placeholder">
            <div className="placeholder-icon">
              <Radio size={36} color="var(--color-cyan-corroboration)" />
            </div>
            <div className="placeholder-title">Awaiting Live Dispatches</div>
            <div className="placeholder-desc">
              Incident queue initialized. Real-time correlation and priority ranking will stream here once active.
            </div>
          </div>
        </section>

        {/* Right Pane: Tactical Geographic Map Container */}
        <section className="map-panel" aria-label="Tactical Map">
          <div className="map-overlay-badge">
            <MapPin size={14} color="var(--color-cyan-corroboration)" />
            <span>TACTICAL GEOGRAPHIC MAP — OSM ENGINE</span>
          </div>

          <div className="map-view-area">
            <div className="placeholder-icon">
              <Activity size={40} color="var(--color-text-muted)" />
            </div>
            <div className="placeholder-title">Tactical Grid Ready</div>
            <div className="placeholder-desc">
              Geographic coordinates and verified hazard hotspots will be plotted on OpenStreetMap tiles.
            </div>
          </div>
        </section>
      </main>

      {/* Footer Telemetry Bar */}
      <footer className="footer-bar">
        <div className="footer-left">
          <span>SYSTEM: KAREN DECISION SUPPORT v1.2</span>
          <span>MODE: DETERMINISTIC TRIAGE</span>
          <span>BACKEND: http://127.0.0.1:8000</span>
        </div>
        <div className="footer-right">
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Clock size={12} />
            {currentTime}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Wifi size={12} />
            WS READY
          </span>
        </div>
      </footer>
    </div>
  );
};

export default App;
