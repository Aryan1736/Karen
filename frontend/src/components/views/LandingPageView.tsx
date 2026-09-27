import React, { useState } from 'react';
import { useNavigation, NavigationView } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { useWebSocketStatus } from '../../context/WebSocketContext';
import './LandingPageView.css';

export interface LandingPageViewProps {
  className?: string;
}

interface RadarIncident {
  id: string;
  tier: 'P0' | 'P1' | 'P2' | 'P3';
  tierLabel: string;
  title: string;
  sector: string;
  coords: string;
  hazardVelocity: number;
  lifeSafety: number;
  corroboration: number;
  infrastructure: number;
  confidence: string;
  transcripts: string[];
  recommendedUnits: string[];
  pinPos: { x: number; y: number };
}

const RADAR_INCIDENTS: RadarIncident[] = [
  {
    id: 'INC-08802',
    tier: 'P0',
    tierLabel: 'P0 CRITICAL // ACTIVE RESCUE',
    title: 'FLASH FLOOD & STRUCTURAL ENTRAPMENT',
    sector: 'SECTOR 04 // PATIA UNDERPASS',
    coords: '20.3541°N, 85.8194°E',
    lifeSafety: 95,
    hazardVelocity: 92,
    corroboration: 80,
    infrastructure: 75,
    confidence: '94.8%',
    transcripts: [
      '"Underpass water rising fast, already to driver window level!"',
      '"Multiple vehicles submerged, occupants hammering on glass against water pressure!"',
      '"Municipal storm sensor #04 indicates +4.2 cm/min influx surge."'
    ],
    recommendedUnits: [
      'WATER RESCUE BOAT 02',
      'HEAVY RESCUE TENDER 04',
      'TACTICAL PARAMEDIC SQUAD 11'
    ],
    pinPos: { x: 38, y: 44 }
  },
  {
    id: 'INC-08799',
    tier: 'P1',
    tierLabel: 'P1 HIGH // SEVERE HAZARD',
    title: 'SUBSTATION TRANSFORMER BLAST & ELECTRICAL ARC',
    sector: 'SECTOR 09 // SUBSTATION GRID',
    coords: '20.3612°N, 85.8245°E',
    lifeSafety: 72,
    hazardVelocity: 84,
    corroboration: 75,
    infrastructure: 90,
    confidence: '91.2%',
    transcripts: [
      '"High-voltage transformer explosion heard across 3 city blocks!"',
      '"Live 33kV lines down across eastbound transit corridor, heavy electrical arcing."'
    ],
    recommendedUnits: [
      'POWER GRID HAZMAT TACTICAL 01',
      'ENGINE COMPANY 12',
      'TRAFFIC PERIMETER UNIT'
    ],
    pinPos: { x: 68, y: 32 }
  },
  {
    id: 'INC-08794',
    tier: 'P2',
    tierLabel: 'P2 MEDIUM // PROPERTY RISK',
    title: 'MAJOR TRANSIT WATERLOGGING & STALLED BUS',
    sector: 'SECTOR 02 // COMMERCIAL BLVD',
    coords: '20.3488°N, 85.8091°E',
    lifeSafety: 45,
    hazardVelocity: 58,
    corroboration: 65,
    infrastructure: 60,
    confidence: '87.5%',
    transcripts: [
      '"Water depth at 18 inches, city bus stalled near central median."',
      '"Passengers safely evacuated to elevated sidewalk; roadway blocked."'
    ],
    recommendedUnits: [
      'MUNICIPAL DRAINAGE CREW 03',
      'TRAFFIC DIVERSION SQUAD'
    ],
    pinPos: { x: 80, y: 64 }
  },
  {
    id: 'INC-08781',
    tier: 'P3',
    tierLabel: 'P3 LOW // ADVISORY',
    title: 'LOCALIZED RESIDENTIAL BASIN SURCHARGE',
    sector: 'SECTOR 07 // NORTH BASIN',
    coords: '20.3705°N, 85.8310°E',
    lifeSafety: 20,
    hazardVelocity: 30,
    corroboration: 40,
    infrastructure: 25,
    confidence: '78.0%',
    transcripts: [
      '"Storm gutter overflowing onto private driveway, zero structural risk."'
    ],
    recommendedUnits: [
      'LOGGED FOR SHIFT REVIEW // AUTOMATED ADVISORY'
    ],
    pinPos: { x: 22, y: 72 }
  }
];

export const LandingPageView: React.FC<LandingPageViewProps> = ({ className = '' }) => {
  const { setActiveView } = useNavigation();
  const { isOnline } = useBackendHealth();
  const { status: wsStatus } = useWebSocketStatus();

  const isConnected = isOnline === true && wsStatus === 'CONNECTED';

  // Full-width radar incident selection
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('INC-08802');
  const selectedIncident = RADAR_INCIDENTS.find(inc => inc.id === selectedIncidentId) || RADAR_INCIDENTS[0];

  // Console preview module selector
  const [activeConsoleTab, setActiveConsoleTab] = useState<NavigationView>('command-deck');

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className={`landing-page ${className}`} role="region" aria-label="Tingle Landing Page">
      {/* ==========================================================================
          1. CLEAN MINIMAL HEADER (NO DUPLICATE BUTTON, SLEEK BRAND & NAV)
          ========================================================================== */}
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

            <div 
              className="landing-sync-pill"
              title={`Backend: ${isOnline ? 'Online' : 'Offline'} | WebSocket: ${wsStatus}`}
            >
              <span className={`sync-dot ${isConnected ? 'online' : isOnline ? 'standby' : 'offline'}`} />
              <span className="sync-text">
                {isConnected ? 'ONLINE' : isOnline ? 'CONNECTING' : 'OFFLINE'}
              </span>
            </div>
          </div>

          {/* Clean Page Navigation Links (No Clutter, No Redundant Button) */}
          <nav className="landing-nav-links" aria-label="Page Navigation">
            <a href="#signals" className="landing-nav-anchor" onClick={(e) => scrollToSection(e, 'signals')}>
              Signals
            </a>
            <a href="#correlation" className="landing-nav-anchor" onClick={(e) => scrollToSection(e, 'correlation')}>
              Correlation
            </a>
            <a href="#priority-matrix" className="landing-nav-anchor" onClick={(e) => scrollToSection(e, 'priority-matrix')}>
              Priority Matrix
            </a>
            <a href="#radar" className="landing-nav-anchor" onClick={(e) => scrollToSection(e, 'radar')}>
              Radar Grid
            </a>
            <a href="#command-center" className="landing-nav-anchor" onClick={(e) => scrollToSection(e, 'command-center')}>
              Console
            </a>
          </nav>
        </div>
      </header>

      {/* ==========================================================================
          MAIN CONTENT AREA
          ========================================================================== */}
      <main className="landing-main">
        {/* ==========================================================================
            2. SPIDER-VERSE CINEMATIC HERO SECTION (Directly inspired by Reference)
            ========================================================================== */}
        <section className="landing-hero-cinematic" id="hero">
          {/* High-Definition Spider-Verse Neon Cityscape Background */}
          <div className="hero-cityscape-bg" aria-hidden="true" />
          <div className="hero-rain-overlay" aria-hidden="true" />
          <div className="hero-gradient-vignette" aria-hidden="true" />

          <div className="hero-cinematic-center">
            {/* Top Red Comic Badge (Like 'AROUND THE WORLD' in Ref) */}
            <div className="hero-comic-badge">
              <span>MUNICIPAL SIGNAL INTELLIGENCE</span>
            </div>

            {/* Huge 3D Extruded Comic Title (Like 'BIT N BUILD' in Ref) */}
            <h1 className="hero-comic-title">
              <span className="title-shadow-layer">THE CITY IS TALKING</span>
            </h1>

            {/* Black Comic Brush Banner using Permanent Marker (Like 'INTERNATIONAL HACKATHON' & 'EVENT BEGINS IN' in Ref 2) */}
            <div className="hero-brush-banner">
              <span>AUTONOMOUS EMERGENCY TRIAGE</span>
            </div>

            {/* High-Contrast Clear Narrative Statement */}
            <p className="hero-cinematic-desc">
              She hears the chaos. You see what matters. TINGLE synthesizes multi-channel 
              emergency audio, police scanners, and sensor streams into verified, explainable 
              incidents in real time.
            </p>

            {/* Single Iconic Yellow Comic Button (Like 'REGISTER NOW →' in Ref) */}
            <div className="hero-single-cta-wrap">
              <button 
                type="button"
                className="hero-spidey-yellow-btn"
                onClick={() => setActiveView('command-deck')}
              >
                <span>ENTER COMMAND DECK</span>
                <span className="btn-arrow-glyph">→</span>
              </button>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            3. THE SIGNAL STREAM SECTION
            ========================================================================== */}
        <section className="landing-section" id="signals">
          <div className="landing-container">
            <div className="section-header">
              <div className="brush-eyebrow">RAW INGESTION FEEDS</div>
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

        {/* ==========================================================================
            4. THE CORRELATION SECTION
            ========================================================================== */}
        <section className="landing-section transformation-section" id="correlation">
          <div className="landing-container">
            <div className="section-header center">
              <div className="brush-eyebrow">SIGNAL FUSION</div>
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
                <div className="convergence-marker">
                  <span className="marker-core-text">4 MIN</span>
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
                    <span className="factor-status high">RAPID WATER INFLUX (+4.2cm/min)</span>
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

        {/* ==========================================================================
            5. TRANSPARENT DECISION SUPPORT
            ========================================================================== */}
        <section className="landing-section" id="logic">
          <div className="landing-container">
            <div className="logic-grid">
              <div className="logic-narrative">
                <div className="brush-eyebrow">DECISION SUPPORT</div>
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
                    <span className="pillar-num">01</span>
                    <div className="pillar-details">
                      <h4 className="pillar-title">Life-Safety Extraction</h4>
                      <p className="pillar-body">
                        Direct extraction of trapped persons, casualties, and life-threatening conditions.
                      </p>
                    </div>
                  </div>

                  <div className="pillar-item">
                    <span className="pillar-num">02</span>
                    <div className="pillar-details">
                      <h4 className="pillar-title">Hazard Velocity Scoring</h4>
                      <p className="pillar-body">
                        Categorization separating rapid-escalation crises from stationary events.
                      </p>
                    </div>
                  </div>

                  <div className="pillar-item">
                    <span className="pillar-num">03</span>
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
                  <span className="tier-tag-p0">P0 CRITICAL</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            6. THE PRIORITY MATRIX SECTION
            ========================================================================== */}
        <section className="landing-section matrix-section" id="priority-matrix">
          <div className="landing-container">
            <div className="section-header">
              <div className="brush-eyebrow">TRIAGE HIERARCHY</div>
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
                <span className="nr-badge">HUMAN INSPECTION QUEUE</span>
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

        {/* ==========================================================================
            7. SHOWSTOPPER FULL-WIDTH SECTION: SPIDER-SENSE MULTIVERSE RADAR
               (Edge-to-Edge 100vw, Clean & Minimal, No Clutter)
            ========================================================================== */}
        <section className="landing-fullwidth-section" id="radar">
          {/* Header Bar spanning full width */}
          <div className="radar-fullwidth-header">
            <div>
              <div className="brush-eyebrow">CITY SURVEILLANCE // 360° THEATER</div>
              <h2 className="radar-theater-title">SPIDER-SENSE MULTIVERSE RADAR</h2>
            </div>
            <div className="radar-telemetry-badge">
              <span>PATIA SECTOR 01–09 // 4 ACTIVE INCIDENTS</span>
            </div>
          </div>

          {/* Panoramic Theater Body (2-Column Surface) */}
          <div className="radar-theater-body">
            {/* Left Column: Cartographic Radar Grid Canvas */}
            <div className="radar-canvas-panel">
              {/* 360-Degree Rotating Radar Beam */}
              <div className="radar-sweep-cone" />

              {/* Concentric Range Rings */}
              <div className="radar-range-ring ring-outer">
                <span className="range-label">2,000M BUFFER</span>
              </div>
              <div className="radar-range-ring ring-mid">
                <span className="range-label">1,000M CORE</span>
              </div>
              <div className="radar-range-ring ring-inner">
                <span className="range-label">500M EPICENTER</span>
              </div>

              {/* Cartographic Crosshairs */}
              <div className="radar-axis-h" />
              <div className="radar-axis-v" />

              {/* Compass Cardinal Points */}
              <span className="compass-pt north">N // 000°</span>
              <span className="compass-pt east">E // 090°</span>
              <span className="compass-pt south">S // 180°</span>
              <span className="compass-pt west">W // 270°</span>

              {/* Interactive Incident Beacons on Map */}
              {RADAR_INCIDENTS.map((inc) => {
                const isSelected = inc.id === selectedIncidentId;
                const isP0 = inc.tier === 'P0';

                return (
                  <div
                    key={inc.id}
                    className={`radar-pin-node ${isSelected ? 'selected' : ''} ${isP0 ? 'p0-threat' : ''}`}
                    style={{ left: `${inc.pinPos.x}%`, top: `${inc.pinPos.y}%` }}
                    onClick={() => setSelectedIncidentId(inc.id)}
                    role="button"
                    tabIndex={0}
                    aria-label={`Select incident ${inc.id}`}
                  >
                    <div className="pin-marker-core">
                      <span className="marker-dot" />
                      <span className="marker-radar-ring" />
                    </div>

                    <div className="pin-callout-tag">
                      <span className="pin-tier-label">{inc.tier}</span>
                      <span className="pin-id-text">{inc.id}</span>
                    </div>
                  </div>
                );
              })}

              <div className="radar-canvas-footer">
                <span>LAT: 20.3541°N // LON: 85.8194°E</span>
                <span>SELECT ANY PIN TO AUDIT TELEMETRY</span>
              </div>
            </div>

            {/* Right Column: Live Incident Inspector HUD */}
            <div className="radar-inspector-panel">
              <div className="inspector-panel-header">
                <span className="inspector-tier-tag">{selectedIncident.tier}</span>
                <span className="inspector-inc-id">{selectedIncident.id}</span>
                <span className="inspector-conf-pill">CONFIDENCE: {selectedIncident.confidence}</span>
              </div>

              <div className="inspector-panel-body">
                <h3 className="inspector-incident-title">
                  {selectedIncident.title}
                </h3>
                <div className="inspector-sector-badge">
                  {selectedIncident.sector}
                </div>

                {/* Score Breakdown Bars */}
                <div className="inspector-scores-box">
                  <div className="scores-box-header">
                    <span>FACTOR SCORING</span>
                    <span>WEIGHTED EXPLAINABLE</span>
                  </div>

                  <div className="factor-meters-list">
                    <div className="factor-meter-item">
                      <div className="meter-label-row">
                        <span>Life-Safety Hazard</span>
                        <span>{selectedIncident.lifeSafety} / 100</span>
                      </div>
                      <div className="meter-track">
                        <div className="meter-fill red" style={{ width: `${selectedIncident.lifeSafety}%` }} />
                      </div>
                    </div>

                    <div className="factor-meter-item">
                      <div className="meter-label-row">
                        <span>Hazard Velocity</span>
                        <span>{selectedIncident.hazardVelocity} / 100</span>
                      </div>
                      <div className="meter-track">
                        <div className="meter-fill orange" style={{ width: `${selectedIncident.hazardVelocity}%` }} />
                      </div>
                    </div>

                    <div className="factor-meter-item">
                      <div className="meter-label-row">
                        <span>Corroboration Multiplier</span>
                        <span>{selectedIncident.corroboration} / 100</span>
                      </div>
                      <div className="meter-track">
                        <div className="meter-fill cyan" style={{ width: `${selectedIncident.corroboration}%` }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Corroborated Evidence Quotes */}
                <div className="inspector-evidence-box">
                  <span className="evidence-header-label">CORROBORATED DISPATCH EVIDENCE:</span>
                  <div className="evidence-quotes-list">
                    {selectedIncident.transcripts.map((text, idx) => (
                      <div key={idx} className="evidence-quote-bubble">
                        <span className="quote-idx">#{idx + 1}</span>
                        <p className="quote-body">{text}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Recommended Units */}
                <div className="inspector-action-box">
                  <span className="action-header-label">DEPLOYMENT UNITS:</span>
                  <div className="units-tag-list">
                    {selectedIncident.recommendedUnits.map((unit, idx) => (
                      <span key={idx} className="unit-pill">{unit}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Full-Width Telemetry Ribbon across bottom */}
          <div className="radar-waterfall-ribbon">
            <div className="waterfall-ticker-track">
              <span>VHF: 442.800 MHz</span>
              <span>•</span>
              <span>CAD FEED: CAD-04</span>
              <span>•</span>
              <span>GEOHASH-6 (tgu0u)</span>
              <span>•</span>
              <span className="text-green">RT-STT: 140ms REALTIME</span>
              <span>•</span>
              <span className="text-yellow">HUMAN-IN-THE-LOOP SOVEREIGN</span>
              <span>•</span>
              <span>APCO PROJECT 33 COMPLIANT</span>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            8. OPERATOR CONTROL & AUTHORITY
            ========================================================================== */}
        <section className="landing-section" id="sovereignty">
          <div className="landing-container">
            <div className="sovereignty-box">
              <div className="sovereignty-inner">
                <div className="brush-eyebrow">HUMAN IN COMMAND</div>
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
                    <span>EVIDENCE VERIFICATION</span>
                  </div>
                  <div className="sovereignty-chip cyan">
                    <span>INSTANT OPERATOR OVERRIDE</span>
                  </div>
                  <div className="sovereignty-chip yellow">
                    <span>FULL AUDIT INTEGRITY</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            9. COMMAND CENTER INTERFACE PREVIEW
            ========================================================================== */}
        <section className="landing-section preview-section" id="command-center">
          <div className="landing-container">
            <div className="section-header between">
              <div>
                <div className="brush-eyebrow">DISPATCH CONSOLE</div>
                <h2 className="section-title">COMMAND CENTER INTERFACE</h2>
              </div>
              <div className="preview-security-badge">
                OPERATIONAL CONSOLE // DISPATCH READY
              </div>
            </div>

            <div className="command-preview-frame">
              {/* Interactive View Selector Tabs */}
              <div className="preview-module-tabs">
                {[
                  { id: 'command-deck', label: 'Command Deck' },
                  { id: 'incident-streams', label: 'Incident Streams' },
                  { id: 'investigation', label: 'Investigation Board' },
                  { id: 'audit-trail', label: 'Audit Ledger' },
                  { id: 'briefing', label: 'System Briefing' }
                ].map((tab) => {
                  const isActive = activeConsoleTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      className={`module-tab-btn ${isActive ? 'active' : ''}`}
                      onClick={() => setActiveConsoleTab(tab.id as NavigationView)}
                    >
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Viewport Preview Area */}
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
                    <span className="floating-title">
                      MODULE: {activeConsoleTab.toUpperCase().replace('-', ' ')}
                    </span>
                    <span className="floating-badge">ACTIVE TRIAGE</span>
                  </div>
                  <p className="floating-card-body">
                    {activeConsoleTab === 'command-deck' && 'Real-time multi-band dispatch matrix with geospatial incident triangulation.'}
                    {activeConsoleTab === 'incident-streams' && 'Live incoming audio packet visualizer, STT transcription, and APCO 10-code parser.'}
                    {activeConsoleTab === 'investigation' && 'Human-in-the-loop quarantine queue for resolving low-confidence distress signals.'}
                    {activeConsoleTab === 'audit-trail' && 'Immutable cryptographic log of all operator override decisions and dispatches.'}
                    {activeConsoleTab === 'briefing' && 'Situational tactical handover briefing generated directly from correlated feeds.'}
                  </p>
                </div>
              </div>

              {/* Clean Single Launch Action */}
              <div className="preview-launcher-rail">
                <span className="launcher-rail-info">
                  SELECTED MODULE READY FOR OPERATOR SESSION
                </span>
                <button 
                  type="button" 
                  className="launcher-direct-btn"
                  onClick={() => setActiveView(activeConsoleTab)}
                >
                  <span>LAUNCH {activeConsoleTab.toUpperCase().replace('-', ' ')}</span>
                  <span>→</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            10. READY CALLOUT
            ========================================================================== */}
        <section className="landing-section">
          <div className="landing-container">
            <div className="tactical-launch-box">
              <div className="brush-eyebrow">OPERATIONAL READINESS</div>
              <h2 className="launch-quote">
                "YOU HANDLE THE CRISIS. <br />
                TINGLE HANDLES THE NOISE."
              </h2>
              <p className="launch-desc">
                Built for high-cognitive-load emergency commanders and dispatchers who demand speed, 
                clarity, and explainable decision support without black-box hallucination.
              </p>
              <button 
                type="button"
                className="tactical-launch-btn"
                onClick={() => setActiveView('command-deck')}
              >
                <span>ENTER COMMAND DECK</span>
                <span>→</span>
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* ==========================================================================
          11. CLEAN, MINIMAL & MODERN FOOTER (NO REDUNDANT BUTTONS)
          ========================================================================== */}
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
            <a href="#radar" onClick={(e) => scrollToSection(e, 'radar')}>Radar Grid</a>
            <a href="#command-center" onClick={(e) => scrollToSection(e, 'command-center')}>Console</a>
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
