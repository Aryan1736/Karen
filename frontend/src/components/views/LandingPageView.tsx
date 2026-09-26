import React, { useState, useEffect } from 'react';
import { 
  Radio, 
  Layers, 
  CheckCircle2, 
  Sliders, 
  Clock, 
  Activity, 
  Zap, 
  Eye, 
  Terminal,
  FileText,
  Compass
} from 'lucide-react';
import { Badge, Button, StatusIndicator, AudioVisualizerBar } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { useWebSocket } from '../../context/WebSocketContext';
import './LandingPageView.css';

export interface LandingPageViewProps {
  className?: string;
}

export const LandingPageView: React.FC<LandingPageViewProps> = ({ className = '' }) => {
  const { setActiveView } = useNavigation();
  const { isOnline } = useBackendHealth();
  const { status: wsStatus } = useWebSocket();

  const [currentTime, setCurrentTime] = useState<string>(() => 
    new Date().toISOString().substring(11, 19) + ' UTC'
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toISOString().substring(11, 19) + ' UTC');
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const engineIndicatorStatus = isOnline === true ? 'online' : isOnline === false ? 'offline' : 'standby';
  const engineIndicatorLabel = isOnline === true ? 'API ONLINE' : isOnline === false ? 'API OFFLINE' : 'PROBING...';

  const wsIndicatorStatus = wsStatus === 'CONNECTED' ? 'online' : (wsStatus === 'DISCONNECTED' || wsStatus === 'ERROR') ? 'offline' : 'standby';
  const wsIndicatorLabel = `WS ${wsStatus}`;

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className={`landing-page ${className}`} role="region" aria-label="Tingle Landing Page">
      {/* 1. STICKY TACTICAL NAVIGATION BAR */}
      <header className="landing-header" role="banner">
        <div className="landing-header-inner">
          <div className="landing-brand-group">
            <div 
              className="landing-brand-badge" 
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') window.scrollTo({ top: 0, behavior: 'smooth' }); }}
              title="Tingle Emergency Intelligence"
            >
              TINGLE
            </div>
            <div className="landing-sector-pill">
              <span className="live-indicator-dot" />
              <span className="sector-text">EMERGENCY INTELLIGENCE</span>
            </div>
            <div className="landing-status-indicators">
              <StatusIndicator status={engineIndicatorStatus} label={engineIndicatorLabel} />
              <StatusIndicator status={wsIndicatorStatus} label={wsIndicatorLabel} />
            </div>
          </div>

          <nav className="landing-nav-links" aria-label="Landing Navigation">
            <a 
              href="#chaos-stream" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'chaos-stream')}
            >
              Chaos Stream
            </a>
            <a 
              href="#transformation" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'transformation')}
            >
              Transformation
            </a>
            <a 
              href="#priority-matrix" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'priority-matrix')}
            >
              Priority Matrix
            </a>
            <a 
              href="#sovereignty" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'sovereignty')}
            >
              Human Decides
            </a>
            <a 
              href="#command-center" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'command-center')}
            >
              Interface Preview
            </a>
          </nav>

          <div className="landing-header-action">
            <Button 
              variant="warning" 
              size="md"
              className="landing-header-btn"
              onClick={() => setActiveView('command-deck')}
            >
              ENTER COMMAND DECK
            </Button>
          </div>
        </div>

        {/* Tactical Telemetry Ribbon */}
        <div className="landing-telemetry-ribbon" role="complementary" aria-label="System Telemetry">
          <div className="telemetry-item">
            <span className="telemetry-label">SYSTEM CLOCK:</span>
            <span className="telemetry-val">{currentTime}</span>
          </div>
          <div className="telemetry-item">
            <span className="telemetry-label">OPERATING PIPELINE:</span>
            <span className="telemetry-val highlight">CHAOS → SIGNAL → INCIDENT → PRIORITY → ACTION</span>
          </div>
          <div className="telemetry-item">
            <span className="telemetry-label">RF MONITOR:</span>
            <span className="telemetry-val">STANDBY // NO DRILL SIMULATION</span>
          </div>
        </div>
      </header>

      {/* MAIN CONTENT AREA */}
      <main className="landing-main">
        {/* 2. HERO SECTION */}
        <section className="landing-hero-section pattern-halftone" id="hero">
          <div className="landing-container landing-hero-grid">
            <div className="hero-content">
              <div className="hero-tag-badge">
                <span className="tag-beacon" />
                <span>TACTICAL EMERGENCY INTELLIGENCE & CORRELATION</span>
              </div>

              <h1 className="hero-title">
                THE CITY IS <br />
                <span className="hero-title-accent">TALKING.</span>
              </h1>

              <p className="hero-statement">
                She hears the chaos. You see what matters. TINGLE correlates unstructured 911 audio 
                transcripts, citizen alerts, and sensor streams into structured, explainable 
                emergency incidents in real time.
              </p>

              <div className="hero-cta-group">
                <button 
                  type="button"
                  className="tactical-cta-btn primary"
                  onClick={() => setActiveView('command-deck')}
                >
                  ENTER COMMAND DECK
                </button>
                <a 
                  href="#transformation" 
                  className="tactical-cta-btn secondary"
                  onClick={(e) => scrollToSection(e, 'transformation')}
                >
                  EXPLORE ARCHITECTURE
                </a>
              </div>
            </div>

            {/* Tactical Audio & Status HUD Card */}
            <div className="hero-hud-card">
              <div className="hud-card-header">
                <span className="hud-title">SYS_RF_AUDIO_MONITOR</span>
                <span className="hud-badge">{engineIndicatorLabel}</span>
              </div>

              <div className="hud-card-body">
                <div className="hud-standby-screen">
                  <div className="hud-crosshair-bg" />
                  <div className="hud-monitor-center">
                    <Radio className="hud-icon" size={32} />
                    <span className="hud-freq-label">FREQUENCY: 442.800 MHz</span>
                    <span className="hud-standby-text">AUDIO MONITOR ON STANDBY</span>
                  </div>
                </div>

                <div className="hud-visualizer-dock">
                  <div className="visualizer-header">
                    <span>RF SPECTRUM TELEMETRY</span>
                    <span className="standby-tag">[ STANDBY ]</span>
                  </div>
                  <AudioVisualizerBar active={false} />
                  <p className="hud-visualizer-note">
                    Non-simulated standby state. Real-time visualizer engages when validated incident audio streams connect.
                  </p>
                </div>
              </div>

              <div className="hud-card-footer">
                <span>CHANNEL: MUNICIPAL_TAC_01</span>
                <span className="hud-mode-text">DISPATCH READY</span>
              </div>
            </div>
          </div>
        </section>

        {/* 3. THE CHAOS STREAM SECTION */}
        <section className="landing-section" id="chaos-stream">
          <div className="landing-container">
            <div className="section-header">
              <div className="section-eyebrow">[PHASE 01: INCOMING NOISE]</div>
              <h2 className="section-title">THE CHAOS STREAM</h2>
              <p className="section-desc">
                Raw, unfiltered emergency signals flooding in simultaneously from emergency radio bands, 
                civilian panic calls, and municipal sensors.
              </p>
            </div>

            <div className="chaos-grid">
              {/* Card 1 */}
              <div className="comic-card card-rotate-left">
                <div className="comic-card-top">
                  <span className="source-tag">SRC: 911_DISPATCH_Q4</span>
                  <span className="timestamp-tag">14:02:11.04 UTC</span>
                </div>
                <blockquote className="comic-quote">
                  "There's thick black smoke billowing out near 5th and Vernon! People are coughing, I can't see the crosswalk!"
                </blockquote>
                <div className="comic-card-bottom">
                  <span className="confusion-badge">CONFUSION: HIGH</span>
                  <span className="sector-tag">SECTOR: PATIA_WEST</span>
                </div>
              </div>

              {/* Card 2 */}
              <div className="comic-card card-rotate-right">
                <div className="comic-card-top">
                  <span className="source-tag highlight-orange">SRC: POLICE_SCANNER_B1</span>
                  <span className="timestamp-tag">14:02:13.88 UTC</span>
                </div>
                <blockquote className="comic-quote">
                  "Multiple vehicles stalled out in the underpass! Water level rising fast, doors won't open against the current!"
                </blockquote>
                <div className="comic-card-bottom">
                  <span className="urgency-badge">URGENCY: ELEVATED</span>
                  <span className="sector-tag">SECTOR: UNDERPASS_SECTOR</span>
                </div>
              </div>

              {/* Card 3 */}
              <div className="comic-card card-rotate-slight">
                <div className="comic-card-top">
                  <span className="source-tag highlight-cyan">SRC: CIV_MOBILE_NODE</span>
                  <span className="timestamp-tag">14:02:15.12 UTC</span>
                </div>
                <blockquote className="comic-quote">
                  "Explosion sound heard near the electrical substation! Sparks flying everywhere, pedestrians scattering!"
                </blockquote>
                <div className="comic-card-bottom">
                  <span className="noise-badge">NOISE: STANDBY</span>
                  <span className="sector-tag">SECTOR: SUBSTATION_GRID</span>
                </div>
              </div>
            </div>

            <div className="exploratory-disclaimer">
              <span>* ARCHITECTURAL WALKTHROUGH — EXPLANATORY MULTI-SOURCE EMERGENCY SIGNAL DEMONSTRATION</span>
            </div>
          </div>
        </section>

        {/* 4. THE TRANSFORMATION (SIGNATURE SECTION) */}
        <section className="landing-section transformation-section pattern-hazard-orange" id="transformation">
          <div className="landing-container">
            <div className="section-header center">
              <div className="section-eyebrow dark">[PHASE 02: SIGNAL TO STRUCTURE]</div>
              <h2 className="section-title">THE TRANSFORMATION</h2>
              <p className="section-desc">
                TINGLE cuts through overlapping panic. Disparate voice fragments and emergency 
                transcripts lock together via semantic correlation and spatiotemporal clustering.
              </p>
            </div>

            <div className="transformation-grid">
              {/* Left Column: Stacked Incoming Fragments */}
              <div className="fragments-stack">
                <div className="fragment-card fragment-red">
                  <div className="fragment-meta">
                    <span>FRAGMENT #01</span>
                    <span>14:02:11 UTC</span>
                  </div>
                  <p className="fragment-text">"Smoke near 5th and Vernon..."</p>
                </div>

                <div className="fragment-card fragment-orange">
                  <div className="fragment-meta">
                    <span>FRAGMENT #02</span>
                    <span>14:02:13 UTC</span>
                  </div>
                  <p className="fragment-text">"Water rising fast in the underpass..."</p>
                </div>

                <div className="fragment-card fragment-cyan">
                  <div className="fragment-meta">
                    <span>FRAGMENT #03</span>
                    <span>14:02:15 UTC</span>
                  </div>
                  <p className="fragment-text">"Vehicles trapped, people shouting for help..."</p>
                </div>

                <div className="fragments-conclusion">
                  "SAME INCIDENT. INDEPENDENT WITNESSES."
                </div>
              </div>

              {/* Center Column: Correlation Convergence Node */}
              <div className="convergence-node">
                <div className="bolt-icon-box">
                  <Zap size={36} />
                </div>
                <div className="node-label">SEMANTIC CORRELATION & FUSION</div>
                <div className="node-sublabel">SPATIOTEMPORAL TRIANGULATION</div>
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

            <div className="transformation-note">
              * Explanatory product visualization demonstrating deterministic incident fusion from multi-point emergency feeds.
            </div>
          </div>
        </section>

        {/* 5. PATTERN RECOGNITION & DETERMINISTIC LOGIC */}
        <section className="landing-section" id="logic">
          <div className="landing-container">
            <div className="logic-grid">
              <div className="logic-narrative">
                <div className="section-eyebrow">[DETERMINISTIC LOGIC]</div>
                <h2 className="section-title">
                  REPORTS BECOME <br />
                  <span className="cyan-highlight">ACTIONABLE INCIDENTS</span>
                </h2>
                <p className="section-desc">
                  By extracting life-safety distress markers, hazard velocity, and critical infrastructure 
                  proximity, TINGLE computes explainable priority scores without black-box hallucination.
                </p>

                <div className="pillars-list">
                  <div className="pillar-item">
                    <CheckCircle2 className="pillar-icon cyan" size={24} />
                    <div className="pillar-details">
                      <h4 className="pillar-title">Life-Safety Extraction</h4>
                      <p className="pillar-body">
                        Direct extraction of trapped persons, casualties, and life-threatening conditions ("help", "screaming", "submerged").
                      </p>
                    </div>
                  </div>

                  <div className="pillar-item">
                    <CheckCircle2 className="pillar-icon yellow" size={24} />
                    <div className="pillar-details">
                      <h4 className="pillar-title">Hazard Velocity Scoring</h4>
                      <p className="pillar-body">
                        Deterministic categorization separating rapid-escalation crises (active flash flood, structural collapse) from stationary events.
                      </p>
                    </div>
                  </div>

                  <div className="pillar-item">
                    <CheckCircle2 className="pillar-icon green" size={24} />
                    <div className="pillar-details">
                      <h4 className="pillar-title">Independent Corroboration Curve</h4>
                      <p className="pillar-body">
                        Multi-witness saturation curves prevent duplicate gaming while rewarding genuinely corroborating independent reports.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Simulation Architecture Card */}
              <div className="simulation-preview-card">
                <div className="sim-card-tag">EXPLAINABLE FACTOR BREAKDOWN</div>
                <div className="sim-card-header">
                  <span>DETERMINISTIC PRIORITY ENGINE</span>
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
                  <span>FINAL TACTICAL TIER:</span>
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
              <div className="section-eyebrow">[TACTICAL HIERARCHY]</div>
              <h2 className="section-title">THE PRIORITY MATRIX</h2>
              <p className="section-desc">
                Absolute triage clarity. Every incoming emergency is categorized into deterministic 
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
                  Active violence, structural collapse, life-or-death water rescue, mass casualties.
                </p>
                <div className="matrix-card-bottom">
                  <span className="response-time">RESPONSE: IMMEDIATE</span>
                </div>
              </div>

              {/* P1 High */}
              <div className="matrix-card card-p1">
                <div className="matrix-card-top">
                  <span className="matrix-badge p1">[ HIGH ]</span>
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
                  General advisory reports, historical status updates, recovery requests, non-urgent citizen inquiries.
                </p>
                <div className="matrix-card-bottom">
                  <span className="response-time cyan">LOGGED FOR REVIEW</span>
                </div>
              </div>
            </div>

            {/* Needs Review Callout */}
            <div className="needs-review-banner">
              <div className="nr-left">
                <Badge variant="needs-review" size="md">NEEDS REVIEW PROTOCOL</Badge>
                <span className="nr-text">
                  Any report with low confidence (&lt; 0.60), missing location coordinates, or contradictory field data is automatically quarantined for mandatory human inspection.
                </span>
              </div>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={() => setActiveView('investigation')}
              >
                OPEN INVESTIGATION
              </Button>
            </div>
          </div>
        </section>

        {/* 7. OPERATOR SOVEREIGNTY PROTOCOL */}
        <section className="landing-section" id="sovereignty">
          <div className="landing-container">
            <div className="sovereignty-box">
              <div className="sovereignty-corner-tape">
                OPERATOR SOVEREIGNTY PROTOCOL
              </div>

              <div className="sovereignty-inner">
                <div className="section-eyebrow dark">[HUMAN IN COMMAND]</div>
                <h2 className="sovereignty-title">
                  TINGLE RECOMMENDS. <br />
                  <span className="sovereignty-accent">HUMANS DECIDE.</span>
                </h2>
                <p className="sovereignty-desc">
                  No black-box algorithms making unilateral emergency deployments. Every correlated incident 
                  presents clear factor breakdowns, raw evidence playback, and instant manual override 
                  controls with mandatory audit justification.
                </p>

                <div className="sovereignty-chips">
                  <div className="sovereignty-chip green">
                    <CheckCircle2 size={18} />
                    <span>EVIDENCE VERIFICATION</span>
                  </div>
                  <div className="sovereignty-chip cyan">
                    <Sliders size={18} />
                    <span>INSTANT HUMAN OVERRIDE</span>
                  </div>
                  <div className="sovereignty-chip yellow">
                    <Activity size={18} />
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
                <div className="section-eyebrow">[TACTICAL OPERATING SYSTEM]</div>
                <h2 className="section-title">COMMAND CENTER INTERFACE</h2>
              </div>
              <div className="preview-security-badge">
                SECURE DISPATCH ENVIRONMENT // SECTOR PATIA
              </div>
            </div>

            <div className="command-preview-frame">
              <div className="preview-radar-canvas">
                <div className="radar-grid" />
                <div className="radar-sweep" />
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
                    <span className="floating-title">ACTIVE SECTOR: PATIA_CENTRAL</span>
                    <Badge variant="p0-critical" size="sm">HIGH ALERT</Badge>
                  </div>
                  <p className="floating-card-body">
                    Triangulated 3 active incidents across the municipal grid. Operational triage active.
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
                  <Compass size={18} />
                  <span>LAUNCH COMMAND DECK (#deck)</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('incident-streams')}
                >
                  <Layers size={18} />
                  <span>VIEW INCIDENT STREAMS (#streams)</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('investigation')}
                >
                  <Eye size={18} />
                  <span>INVESTIGATION BOARD (#investigation)</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('audit-trail')}
                >
                  <Terminal size={18} />
                  <span>AUDIT TRAIL LOGS (#audit)</span>
                </button>
                <button 
                  type="button" 
                  className="launcher-btn"
                  onClick={() => setActiveView('briefing')}
                >
                  <FileText size={18} />
                  <span>INCIDENT BRIEFINGS (#briefing)</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* 9. TACTICAL LAUNCH CALLOUT PANEL */}
        <section className="landing-section">
          <div className="landing-container">
            <div className="tactical-launch-box">
              <div className="launch-tag">SYSTEM READINESS</div>
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
                ENTER COMMAND DECK
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* 10. TACTICAL LANDING FOOTER */}
      <footer className="landing-footer" role="contentinfo">
        <div className="landing-container landing-footer-inner">
          <div className="footer-meta">
            <span className="footer-title">TINGLE v1.2 // EMERGENCY INTELLIGENCE & CORRELATION SYSTEM</span>
            <span className="footer-subtitle">HUMAN-IN-THE-LOOP SOVEREIGN // DETERMINISTIC DISPATCH SUPPORT</span>
          </div>
          <div className="footer-telemetry">
            <span className="footer-time"><Clock size={12} /> {currentTime}</span>
            <span className="footer-status"><Activity size={12} /> WS {wsStatus}</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPageView;
