import React from 'react';
import { 
  Radio, 
  Layers, 
  CheckCircle2, 
  Sliders, 
  Activity, 
  Zap, 
  Eye, 
  Terminal,
  FileText,
  Compass,
  ArrowRight
} from 'lucide-react';
import { Badge, AudioVisualizerBar } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { useWebSocketStatus } from '../../context/WebSocketContext';
import './LandingPageView.css';

export interface LandingPageViewProps {
  className?: string;
}

export const LandingPageView: React.FC<LandingPageViewProps> = ({ className = '' }) => {
  const { setActiveView } = useNavigation();
  const { isOnline } = useBackendHealth();
  const { status: wsStatus } = useWebSocketStatus();

  const isConnected = isOnline === true && wsStatus === 'CONNECTED';

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className={`landing-page ${className}`} role="region" aria-label="Tingle Landing Page">
      {/* 1. CLEAN MODERN HEADER */}
      <header className="landing-header" role="banner">
        <div className="landing-header-inner">
          <div className="landing-brand-group">
            <div 
              className="landing-brand-badge" 
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') window.scrollTo({ top: 0, behavior: 'smooth' }); }}
              title="Tingle Emergency Operations"
            >
              <span className="brand-dot" aria-hidden="true" />
              <span className="brand-name">TINGLE</span>
            </div>

            {/* Small letter size sync element */}
            <div 
              className="landing-sync-pill"
              title={`Backend: ${isOnline ? 'Online' : 'Offline'} | WebSocket: ${wsStatus}`}
              aria-label="System Connection Status"
            >
              <span className={`sync-dot ${isConnected ? 'online' : isOnline ? 'standby' : 'offline'}`} />
              <span className="sync-text">
                {isConnected ? 'ONLINE' : isOnline ? 'CONNECTING' : 'OFFLINE'}
              </span>
            </div>
          </div>

          {/* Essential page navigation links only */}
          <nav className="landing-nav-links" aria-label="Page Navigation">
            <a 
              href="#signals" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'signals')}
            >
              Signals
            </a>
            <a 
              href="#correlation" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'correlation')}
            >
              Correlation
            </a>
            <a 
              href="#priority-matrix" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'priority-matrix')}
            >
              Priority Matrix
            </a>
            <a 
              href="#command-center" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'command-center')}
            >
              Console
            </a>
          </nav>

          <div className="landing-header-action">
            <button 
              type="button"
              className="landing-header-btn"
              onClick={() => setActiveView('command-deck')}
            >
              <span>ENTER COMMAND DECK</span>
              <ArrowRight size={14} className="btn-arrow" />
            </button>
          </div>
        </div>
      </header>

      {/* MAIN CONTENT AREA */}
      <main className="landing-main">
        {/* 2. HERO SECTION */}
        <section className="landing-hero-section" id="hero">
          <div className="landing-container landing-hero-grid">
            <div className="hero-content">
              <div className="hero-tag-badge">
                <span className="tag-beacon" />
                <span>REAL-TIME DISPATCH INTELLIGENCE</span>
              </div>

              <h1 className="hero-title">
                THE CITY IS <br />
                <span className="hero-title-accent">TALKING.</span>
              </h1>

              <p className="hero-statement">
                She hears the chaos. You see what matters. TINGLE correlates multi-channel 
                emergency audio, citizen alerts, and sensor streams into verified, explainable 
                incidents in real time.
              </p>

              <div className="hero-cta-group">
                <button 
                  type="button"
                  className="tactical-cta-btn primary"
                  onClick={() => setActiveView('command-deck')}
                >
                  <span>ENTER COMMAND DECK</span>
                  <ArrowRight size={18} />
                </button>
                <a 
                  href="#correlation" 
                  className="tactical-cta-btn secondary"
                  onClick={(e) => scrollToSection(e, 'correlation')}
                >
                  EXPLORE ARCHITECTURE
                </a>
              </div>
            </div>

            {/* Live Audio & Status Card */}
            <div className="hero-hud-card">
              <div className="hud-card-header">
                <div className="hud-header-left">
                  <span className="hud-live-dot" />
                  <span className="hud-title">AUDIO INGESTION STREAM</span>
                </div>
                <span className="hud-badge">{isOnline ? 'MONITORING' : 'STANDBY'}</span>
              </div>

              <div className="hud-card-body">
                <div className="hud-standby-screen">
                  <div className="hud-monitor-center">
                    <Radio className="hud-icon" size={28} />
                    <span className="hud-freq-label">CHANNEL 01 // 442.800 MHz</span>
                    <span className="hud-standby-text">MUNICIPAL EMERGENCY DISPATCH</span>
                  </div>
                </div>

                <div className="hud-visualizer-dock">
                  <div className="visualizer-header">
                    <span>SPECTRUM TELEMETRY</span>
                    <span className="standby-tag">{isConnected ? '[ LIVE ]' : '[ STANDBY ]'}</span>
                  </div>
                  <AudioVisualizerBar active={isConnected} />
                  <p className="hud-visualizer-note">
                    Visualizer synchronizes automatically with incoming 911 dispatch audio packets.
                  </p>
                </div>
              </div>

              <div className="hud-card-footer">
                <span>BAND: VHF HIGH</span>
                <span className="hud-mode-text">DISPATCH READY</span>
              </div>
            </div>
          </div>
        </section>

        {/* 3. THE SIGNAL STREAM SECTION */}
        <section className="landing-section" id="signals">
          <div className="landing-container">
            <div className="section-header">
              <div className="section-eyebrow">LIVE FEEDS</div>
              <h2 className="section-title">THE SIGNAL STREAM</h2>
              <p className="section-desc">
                Emergency audio and reports ingested simultaneously from public safety dispatch 
                bands, civilian distress calls, and municipal sensors.
              </p>
            </div>

            <div className="chaos-grid">
              {/* Card 1 */}
              <div className="dispatch-card">
                <div className="dispatch-card-top">
                  <span className="source-tag">911 CALL // CAD-04</span>
                  <span className="timestamp-tag">14:02:11 UTC</span>
                </div>
                <blockquote className="dispatch-quote">
                  "There's thick black smoke billowing out near 5th and Vernon! People are coughing, I can't see the crosswalk!"
                </blockquote>
                <div className="dispatch-card-bottom">
                  <span className="urgency-badge critical">URGENCY: HIGH</span>
                  <span className="sector-tag">PATIA WEST</span>
                </div>
              </div>

              {/* Card 2 */}
              <div className="dispatch-card">
                <div className="dispatch-card-top">
                  <span className="source-tag highlight-orange">RADIO SCANNER // B1</span>
                  <span className="timestamp-tag">14:02:13 UTC</span>
                </div>
                <blockquote className="dispatch-quote">
                  "Multiple vehicles stalled out in the underpass! Water level rising fast, doors won't open against the current!"
                </blockquote>
                <div className="dispatch-card-bottom">
                  <span className="urgency-badge">URGENCY: ELEVATED</span>
                  <span className="sector-tag">UNDERPASS 04</span>
                </div>
              </div>

              {/* Card 3 */}
              <div className="dispatch-card">
                <div className="dispatch-card-top">
                  <span className="source-tag highlight-cyan">CITIZEN REPORT</span>
                  <span className="timestamp-tag">14:02:15 UTC</span>
                </div>
                <blockquote className="dispatch-quote">
                  "Explosion sound heard near the electrical substation! Sparks flying everywhere, pedestrians scattering!"
                </blockquote>
                <div className="dispatch-card-bottom">
                  <span className="urgency-badge info">URGENCY: MODERATE</span>
                  <span className="sector-tag">SUBSTATION GRID</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 4. THE CORRELATION SECTION */}
        <section className="landing-section transformation-section" id="correlation">
          <div className="landing-container">
            <div className="section-header center">
              <div className="section-eyebrow">SIGNAL FUSION</div>
              <h2 className="section-title">INCIDENT CORRELATION</h2>
              <p className="section-desc">
                Disparate voice fragments and emergency transcripts lock together into a single, 
                coherent incident via geospatial clustering and temporal correlation.
              </p>
            </div>

            <div className="transformation-grid">
              {/* Left Column: Stacked Incoming Fragments */}
              <div className="fragments-stack">
                <div className="fragment-card fragment-red">
                  <div className="fragment-meta">
                    <span>CALL FRAGMENT #01</span>
                    <span>14:02:11 UTC</span>
                  </div>
                  <p className="fragment-text">"Smoke near 5th and Vernon..."</p>
                </div>

                <div className="fragment-card fragment-orange">
                  <div className="fragment-meta">
                    <span>CALL FRAGMENT #02</span>
                    <span>14:02:13 UTC</span>
                  </div>
                  <p className="fragment-text">"Water rising fast in the underpass..."</p>
                </div>

                <div className="fragment-card fragment-cyan">
                  <div className="fragment-meta">
                    <span>CALL FRAGMENT #03</span>
                    <span>14:02:15 UTC</span>
                  </div>
                  <p className="fragment-text">"Vehicles trapped, people shouting for help..."</p>
                </div>

                <div className="fragments-conclusion">
                  <span>CORROBORATED BY 3 INDEPENDENT SOURCES</span>
                </div>
              </div>

              {/* Center Column: Correlation Convergence Node */}
              <div className="convergence-node">
                <div className="bolt-icon-box">
                  <Zap size={32} />
                </div>
                <div className="node-label">SIGNAL CORRELATION</div>
                <div className="node-sublabel">GEOSPATIAL & TIME CLUSTERING</div>
              </div>

              {/* Right Column: Consolidated Incident Card */}
              <div className="consolidated-panel">
                <div className="panel-corner-badge">
                  P0 CRITICAL INCIDENT
                </div>

                <div className="panel-header">
                  <span className="panel-id">ID: #INC-08802</span>
                  <span className="panel-status-tag">CORRELATED</span>
                </div>

                <h3 className="panel-title">FLASH FLOOD & STRUCTURAL ENTRAPMENT</h3>
                
                <p className="panel-narrative">
                  Underpass Sector 4. Multiple vehicles submerged with rapid water rise. 
                  High-voltage short circuit detected in vicinity. 3 independent reports 
                  correlated within 4 minutes.
                </p>

                <div className="panel-factors">
                  <div className="factor-row">
                    <span className="factor-name">LIFE-SAFETY RISK:</span>
                    <span className="factor-status critical">ACTIVE ENTRAPMENT</span>
                  </div>
                  <div className="factor-row">
                    <span className="factor-name">HAZARD VELOCITY:</span>
                    <span className="factor-status high">RAPID WATER INFLUX</span>
                  </div>
                  <div className="factor-row">
                    <span className="factor-name">CORROBORATION:</span>
                    <span className="factor-status verified">3 INDEPENDENT SOURCES</span>
                  </div>
                </div>

                <div className="panel-footer">
                  <span className="panel-confidence">CONFIDENCE: 94.2%</span>
                  <span className="panel-dispatch-chip">DISPATCH READY</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 5. TRANSPARENT DECISION SUPPORT */}
        <section className="landing-section" id="logic">
          <div className="landing-container">
            <div className="logic-grid">
              <div className="logic-narrative">
                <div className="section-eyebrow">DECISION SUPPORT</div>
                <h2 className="section-title">
                  REPORTS BECOME <br />
                  <span className="cyan-highlight">ACTIONABLE INCIDENTS</span>
                </h2>
                <p className="section-desc">
                  By extracting life-safety distress markers, hazard velocity, and critical infrastructure 
                  proximity, TINGLE computes explainable priority scores without black-box guessing.
                </p>

                <div className="pillars-list">
                  <div className="pillar-item">
                    <CheckCircle2 className="pillar-icon cyan" size={22} />
                    <div className="pillar-details">
                      <h4 className="pillar-title">Life-Safety Extraction</h4>
                      <p className="pillar-body">
                        Direct extraction of trapped persons, casualties, and life-threatening conditions.
                      </p>
                    </div>
                  </div>

                  <div className="pillar-item">
                    <CheckCircle2 className="pillar-icon yellow" size={22} />
                    <div className="pillar-details">
                      <h4 className="pillar-title">Hazard Velocity Scoring</h4>
                      <p className="pillar-body">
                        Categorization separating rapid-escalation crises from stationary events.
                      </p>
                    </div>
                  </div>

                  <div className="pillar-item">
                    <CheckCircle2 className="pillar-icon green" size={22} />
                    <div className="pillar-details">
                      <h4 className="pillar-title">Independent Corroboration Curve</h4>
                      <p className="pillar-body">
                        Multi-witness saturation curves prevent duplicate gaming while rewarding corroborating reports.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Priority Architecture Card */}
              <div className="simulation-preview-card">
                <div className="sim-card-tag">EXPLAINABLE FACTOR BREAKDOWN</div>
                <div className="sim-card-header">
                  <span>TRANSPARENT PRIORITY ENGINE</span>
                  <span className="live-pill">v1.2</span>
                </div>

                <div className="formula-box">
                  <div className="formula-label">PRIORITY FORMULA:</div>
                  <code className="formula-code">
                    Score = (0.35 × LifeSafety) + (0.25 × HazardVelocity) + (0.20 × Corroboration) + (0.20 × Infrastructure)
                  </code>
                </div>

                <div className="factors-breakdown">
                  <div className="breakdown-bar">
                    <div className="bar-label">
                      <span>Life Safety (Entrapment detected)</span>
                      <span>95 / 100</span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill red" style={{ width: '95%' }} />
                    </div>
                  </div>

                  <div className="breakdown-bar">
                    <div className="bar-label">
                      <span>Hazard Velocity (Active Water Surge)</span>
                      <span>85 / 100</span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill orange" style={{ width: '85%' }} />
                    </div>
                  </div>

                  <div className="breakdown-bar">
                    <div className="bar-label">
                      <span>Corroboration (3 distinct sources)</span>
                      <span>80 / 100</span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill cyan" style={{ width: '80%' }} />
                    </div>
                  </div>
                </div>

                <div className="sim-card-footer">
                  <span>CALCULATED TIER:</span>
                  <Badge variant="p0-critical" size="sm">P0 CRITICAL</Badge>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 6. THE PRIORITY MATRIX SECTION */}
        <section className="landing-section matrix-section" id="priority-matrix">
          <div className="landing-container">
            <div className="section-header">
              <div className="section-eyebrow">TRIAGE HIERARCHY</div>
              <h2 className="section-title">THE PRIORITY MATRIX</h2>
              <p className="section-desc">
                Clear triage hierarchy. Every incoming incident is classified into deterministic 
                priority tiers based on immediate threat to life and infrastructure.
              </p>
            </div>

            <div className="matrix-grid">
              {/* P0 Critical */}
              <div className="matrix-card card-p0">
                <div className="matrix-card-top">
                  <span className="matrix-badge p0">P0 CRITICAL</span>
                  <span className="beacon-ping" />
                </div>
                <h3 className="matrix-tier-title">IMMINENT THREAT</h3>
                <p className="matrix-tier-desc">
                  Active structural collapse, life-or-death water rescue, trapped civilians, mass casualties.
                </p>
                <div className="matrix-card-bottom">
                  <span className="response-time">RESPONSE: IMMEDIATE</span>
                </div>
              </div>

              {/* P1 High */}
              <div className="matrix-card card-p1">
                <div className="matrix-card-top">
                  <span className="matrix-badge p1">P1 HIGH</span>
                </div>
                <h3 className="matrix-tier-title">SEVERE HAZARD</h3>
                <p className="matrix-tier-desc">
                  Major transit grid obstruction, electrical arcing, active fires without reported entrapment.
                </p>
                <div className="matrix-card-bottom">
                  <span className="response-time orange">RESPONSE: 2 MIN</span>
                </div>
              </div>

              {/* P2 Medium */}
              <div className="matrix-card card-p2">
                <div className="matrix-card-top">
                  <span className="matrix-badge p2">P2 MEDIUM</span>
                </div>
                <h3 className="matrix-tier-title">PROPERTY RISK</h3>
                <p className="matrix-tier-desc">
                  Non-injury collisions, street waterlogging, localized infrastructure warnings.
                </p>
                <div className="matrix-card-bottom">
                  <span className="response-time yellow">RESPONSE: 10 MIN</span>
                </div>
              </div>

              {/* P3 Low */}
              <div className="matrix-card card-p3">
                <div className="matrix-card-top">
                  <span className="matrix-badge p3">P3 LOW</span>
                </div>
                <h3 className="matrix-tier-title">ADVISORY</h3>
                <p className="matrix-tier-desc">
                  General advisory reports, historical updates, non-urgent citizen inquiries.
                </p>
                <div className="matrix-card-bottom">
                  <span className="response-time cyan">LOGGED FOR REVIEW</span>
                </div>
              </div>
            </div>

            {/* Needs Review Callout */}
            <div className="needs-review-banner">
              <div className="nr-left">
                <Badge variant="needs-review" size="md">HUMAN INSPECTION QUEUE</Badge>
                <span className="nr-text">
                  Any report with low confidence (&lt; 0.60), missing location coordinates, or contradictory field data is automatically quarantined for operator review.
                </span>
              </div>
              <button 
                type="button"
                className="nr-action-btn"
                onClick={() => setActiveView('investigation')}
              >
                OPEN INVESTIGATION
              </button>
            </div>
          </div>
        </section>

        {/* 7. OPERATOR CONTROL & AUTHORITY */}
        <section className="landing-section" id="sovereignty">
          <div className="landing-container">
            <div className="sovereignty-box">
              <div className="sovereignty-inner">
                <div className="section-eyebrow">HUMAN IN COMMAND</div>
                <h2 className="sovereignty-title">
                  AUTOMATION RECOMMENDS. <br />
                  <span className="sovereignty-accent">OPERATORS DECIDE.</span>
                </h2>
                <p className="sovereignty-desc">
                  No automated system should deploy emergency units without human oversight. Every prioritized incident 
                  presents clear factor breakdowns, raw evidence playback, and instant manual override 
                  controls with mandatory audit justification.
                </p>

                <div className="sovereignty-chips">
                  <div className="sovereignty-chip green">
                    <CheckCircle2 size={16} />
                    <span>EVIDENCE VERIFICATION</span>
                  </div>
                  <div className="sovereignty-chip cyan">
                    <Sliders size={16} />
                    <span>INSTANT OPERATOR OVERRIDE</span>
                  </div>
                  <div className="sovereignty-chip yellow">
                    <Activity size={16} />
                    <span>FULL AUDIT INTEGRITY</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 8. COMMAND CENTER INTERFACE PREVIEW */}
        <section className="landing-section preview-section" id="command-center">
          <div className="landing-container">
            <div className="section-header between">
              <div>
                <div className="section-eyebrow">DISPATCH CONSOLE</div>
                <h2 className="section-title">COMMAND CENTER INTERFACE</h2>
              </div>
              <div className="preview-security-badge">
                OPERATIONAL CONSOLE // DISPATCH READY
              </div>
            </div>

            <div className="command-preview-frame">
              <div className="preview-radar-canvas">
                <div className="radar-grid" />
                <div className="radar-incident-pin pin-1">
                  <span className="pin-pulse" />
                  <span className="pin-label">INC-08802 (P0)</span>
                </div>
                <div className="radar-incident-pin pin-2">
                  <span className="pin-label">INC-08799 (P1)</span>
                </div>
                <div className="radar-incident-pin pin-3">
                  <span className="pin-label">INC-08794 (P2)</span>
                </div>

                <div className="preview-floating-card">
                  <div className="floating-card-header">
                    <span className="floating-title">ACTIVE SECTOR: PATIA CENTRAL</span>
                    <Badge variant="p0-critical" size="sm">ACTIVE TRIAGE</Badge>
                  </div>
                  <p className="floating-card-body">
                    3 active incidents correlated across the municipal grid. Operational triage active.
                  </p>
                </div>
              </div>

              {/* Viewport Action Launcher Rail */}
              <div className="preview-launcher-rail">
                <button 
                  type="button" 
                  className="launcher-btn primary"
                  onClick={() => setActiveView('command-deck')}
                >
                  <Compass size={16} />
                  <span>Launch Command Deck</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('incident-streams')}
                >
                  <Layers size={16} />
                  <span>Incident Streams</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('investigation')}
                >
                  <Eye size={16} />
                  <span>Investigation Board</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('audit-trail')}
                >
                  <Terminal size={16} />
                  <span>Audit Trail Ledger</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('briefing')}
                >
                  <FileText size={16} />
                  <span>System Briefing</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* 9. READY CALLOUT */}
        <section className="landing-section">
          <div className="landing-container">
            <div className="tactical-launch-box">
              <div className="launch-tag">OPERATIONAL READINESS</div>
              <h2 className="launch-quote">
                "YOU HANDLE THE CRISIS. <br />
                TINGLE HANDLES THE NOISE."
              </h2>
              <p className="launch-desc">
                Built for high-cognitive-load emergency commanders and dispatchers who demand speed, 
                clarity, and explainable decision support.
              </p>
              <button 
                type="button"
                className="tactical-launch-btn"
                onClick={() => setActiveView('command-deck')}
              >
                <span>ENTER COMMAND DECK</span>
                <ArrowRight size={18} />
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* 10. CLEAN & MODERN FOOTER */}
      <footer className="landing-footer" role="contentinfo">
        <div className="landing-container landing-footer-inner">
          <div className="footer-brand-col">
            <div className="footer-brand-title">TINGLE</div>
            <p className="footer-tagline">
              Real-time emergency intelligence & explainable triage decision support.
            </p>
          </div>

          <nav className="footer-nav-links" aria-label="Footer Quick Links">
            <a href="#signals" onClick={(e) => scrollToSection(e, 'signals')}>Signals</a>
            <a href="#correlation" onClick={(e) => scrollToSection(e, 'correlation')}>Correlation</a>
            <a href="#priority-matrix" onClick={(e) => scrollToSection(e, 'priority-matrix')}>Priority Matrix</a>
            <a href="#command-center" onClick={(e) => scrollToSection(e, 'command-center')}>Console</a>
            <button 
              type="button" 
              className="footer-deck-btn"
              onClick={() => setActiveView('command-deck')}
            >
              Launch Console
            </button>
          </nav>

          <div className="footer-meta-col">
            <span className="footer-status-pill">OPERATIONAL // v1.2</span>
            <span className="footer-copy">© 2026 Tingle. All rights reserved.</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPageView;
