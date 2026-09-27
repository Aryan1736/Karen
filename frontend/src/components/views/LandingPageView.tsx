import React, { useState, useEffect } from 'react';
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
  ArrowRight,
  Volume2,
  VolumeX,
  Crosshair,
  MapPin,
  Sparkles
} from 'lucide-react';
import { Badge } from '../ui';
import { useNavigation, NavigationView } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { useWebSocketStatus } from '../../context/WebSocketContext';
import { getOperatorId } from '../../api/client';
import './LandingPageView.css';

export interface LandingPageViewProps {
  className?: string;
}

// Full-width radar incident dataset
interface MultiverseIncident {
  id: string;
  tier: 'P0' | 'P1' | 'P2' | 'P3';
  tierLabel: string;
  badgeVariant: 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low';
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
  pinPos: { x: number; y: number }; // Percentage coords on radar
  isCorrelatedSurge?: boolean;
}

const RADAR_INCIDENTS: MultiverseIncident[] = [
  {
    id: 'INC-08802',
    tier: 'P0',
    tierLabel: 'P0 CRITICAL // LIFE-SAFETY ENTRAPMENT',
    badgeVariant: 'p0-critical',
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
      '"Multiple vehicles submerged, occupants screaming, doors jammed shut against pressure!"',
      '"Municipal storm sensor #04 indicates +4.2 cm/min influx surge."'
    ],
    recommendedUnits: [
      'WATER RESCUE BOAT 02',
      'HEAVY RESCUE TENDER 04',
      'TACTICAL PARAMEDIC SQUAD 11'
    ],
    pinPos: { x: 38, y: 44 },
    isCorrelatedSurge: true
  },
  {
    id: 'INC-08799',
    tier: 'P1',
    tierLabel: 'P1 HIGH // SEVERE INFRASTRUCTURE',
    badgeVariant: 'p1-high',
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
      '"Live 33kV lines down across eastbound transit corridor, violent electrical arcing."'
    ],
    recommendedUnits: [
      'POWER GRID HAZMAT TACTICAL 01',
      'ENGINE COMPANY 12',
      'TRAFFIC PERIMETER UNIT'
    ],
    pinPos: { x: 68, y: 32 },
    isCorrelatedSurge: true
  },
  {
    id: 'INC-08794',
    tier: 'P2',
    tierLabel: 'P2 MEDIUM // PROPERTY & TRANSIT HAZARD',
    badgeVariant: 'p2-medium',
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
      '"Passengers safely evacuated to elevated sidewalk; roadway fully blocked."'
    ],
    recommendedUnits: [
      'MUNICIPAL DRAINAGE CREW 03',
      'TRAFFIC DIVERSION SQUAD'
    ],
    pinPos: { x: 80, y: 64 },
    isCorrelatedSurge: false
  },
  {
    id: 'INC-08781',
    tier: 'P3',
    tierLabel: 'P3 LOW // ADVISORY NOTICE',
    badgeVariant: 'p3-low',
    title: 'LOCALIZED RESIDENTIAL BASIN SURCHARGE',
    sector: 'SECTOR 07 // NORTH BASIN',
    coords: '20.3705°N, 85.8310°E',
    lifeSafety: 20,
    hazardVelocity: 30,
    corroboration: 40,
    infrastructure: 25,
    confidence: '78.0%',
    transcripts: [
      '"Storm gutter overflowing onto private driveway, zero structural or life threat."'
    ],
    recommendedUnits: [
      'LOGGED FOR SHIFT REVIEW // AUTOMATED ADVISORY'
    ],
    pinPos: { x: 22, y: 72 },
    isCorrelatedSurge: false
  }
];

// Audio channel stream data for the Spider-Verse hero HUD
interface HeroChannelData {
  id: string;
  name: string;
  freq: string;
  band: string;
  type: string;
  transcript: string;
  urgency: string;
  dbLevel: string;
  signalStrength: number;
}

const HERO_CHANNELS: Record<string, HeroChannelData> = {
  'ch-01': {
    id: 'ch-01',
    name: 'MUNICIPAL EMERGENCY DISPATCH',
    freq: '442.800 MHz',
    band: 'VHF HIGH',
    type: 'APCO 10-33 PRIORITY',
    transcript: '"10-33 Flash flood emergency in Underpass Sector 4! 3 vehicles submerged with water rapidly entering cabin compartments. Trapped occupants hammering on glass!"',
    urgency: 'P0 CRITICAL',
    dbLevel: '-3.2 dBFS',
    signalStrength: 96
  },
  'ch-02': {
    id: 'ch-02',
    name: 'COUNTY CAD-04 911 VOIP',
    freq: '154.280 MHz',
    band: 'VHF NARROW',
    type: 'INBOUND CAD STREAM',
    transcript: '"Caller reporting massive transformer explosion near electrical substation! Sparks flying across four lanes, power severed, secondary smoke visible!"',
    urgency: 'P1 SEVERE',
    dbLevel: '-6.8 dBFS',
    signalStrength: 88
  },
  'ch-03': {
    id: 'ch-03',
    name: 'CIVILIAN CITIZEN-NET',
    freq: '868.500 MHz',
    band: 'ISM TELEMETRY',
    type: 'GEOLOCATED DISTRESS',
    transcript: '"Water rising over curbs fast on Vernon! We cannot open building doors against incoming current! Requesting water rescue boats now!"',
    urgency: 'P0 CORROBORATING',
    dbLevel: '-5.1 dBFS',
    signalStrength: 92
  }
};

export const LandingPageView: React.FC<LandingPageViewProps> = ({ className = '' }) => {
  const { setActiveView } = useNavigation();
  const { isOnline } = useBackendHealth();
  const { status: wsStatus } = useWebSocketStatus();
  const operatorId = getOperatorId();

  const isConnected = isOnline === true && wsStatus === 'CONNECTED';

  // Live ticking UTC time clock
  const [utcTime, setUtcTime] = useState<string>('');
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toTimeString().split(' ')[0] + ' UTC');
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Spider-Verse Hero Interactive States
  const [activeHeroChannel, setActiveHeroChannel] = useState<'ch-01' | 'ch-02' | 'ch-03'>('ch-01');
  const [isSpiderSenseToggled, setIsSpiderSenseToggled] = useState<boolean>(true);

  // Audio previewing in the Signal Stream section
  const [playingAudioId, setPlayingAudioId] = useState<string | null>(null);

  // Full-width Multiverse Radar Section States
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('INC-08802');
  const [isSurgeActive, setIsSurgeActive] = useState<boolean>(false);

  // Console preview module selector
  const [activeConsoleTab, setActiveConsoleTab] = useState<NavigationView>('command-deck');

  const selectedIncident = RADAR_INCIDENTS.find(inc => inc.id === selectedIncidentId) || RADAR_INCIDENTS[0];
  const currentChannel = HERO_CHANNELS[activeHeroChannel];

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleSimulateSurge = () => {
    setIsSurgeActive(true);
    setTimeout(() => {
      setIsSurgeActive(false);
    }, 4500);
  };

  const toggleSpiderSense = () => {
    setIsSpiderSenseToggled(prev => !prev);
  };

  return (
    <div className={`landing-page ${className}`} role="region" aria-label="Tingle Landing Page">
      {/* ==========================================================================
          1. CLEAN TACTICAL HEADER (SPIDER-VERSE POLISHED, NO REDUNDANT BUTTONS)
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
              {/* Spider-Verse Spider-Sense Pulse Glyph */}
              <div className="spidey-brand-icon" aria-hidden="true">
                <span className="spidey-pulse-wave ring-1" />
                <span className="spidey-pulse-wave ring-2" />
                <Zap size={14} className="spidey-bolt-glyph" />
              </div>
              <div className="brand-text-stack">
                <span className="brand-name spidey-chromatic-text">TINGLE</span>
                <span className="brand-subtext">KAREN // DISPATCH AI</span>
              </div>
            </div>

            {/* Tactical Telemetry Badge */}
            <div 
              className="landing-sync-pill"
              title={`Backend: ${isOnline ? 'Online' : 'Offline'} | WebSocket: ${wsStatus}`}
              aria-label="System Connection Status"
            >
              <span className={`sync-dot ${isConnected ? 'online' : isOnline ? 'standby' : 'offline'}`} />
              <span className="sync-text">
                {isConnected ? 'ONLINE // 140ms' : isOnline ? 'CONNECTING' : 'OFFLINE'}
              </span>
            </div>
          </div>

          {/* Clean, Non-Redundant Page Anchors */}
          <nav className="landing-nav-links" aria-label="Page Navigation">
            <a 
              href="#signals" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'signals')}
            >
              <span className="nav-index">01</span> Signals
            </a>
            <a 
              href="#correlation" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'correlation')}
            >
              <span className="nav-index">02</span> Correlation
            </a>
            <a 
              href="#priority-matrix" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'priority-matrix')}
            >
              <span className="nav-index">03</span> Priority Matrix
            </a>
            <a 
              href="#multiverse-radar" 
              className="landing-nav-anchor spidey-radar-link"
              onClick={(e) => scrollToSection(e, 'multiverse-radar')}
            >
              <span className="nav-index">04</span> Radar Grid
            </a>
            <a 
              href="#command-center" 
              className="landing-nav-anchor"
              onClick={(e) => scrollToSection(e, 'command-center')}
            >
              <span className="nav-index">05</span> Console
            </a>
          </nav>

          {/* Single Sleek Tactical CTA (Replaced jarring yellow button with refined tactical launcher) */}
          <div className="landing-header-action">
            <button 
              type="button"
              className="landing-header-btn"
              onClick={() => setActiveView('command-deck')}
              title="Enter Tingle Tactical Command Deck"
            >
              <span className="btn-bracket">[</span>
              <span>LAUNCH CONSOLE</span>
              <span className="btn-arrow">↗</span>
              <span className="btn-bracket">]</span>
            </button>
          </div>
        </div>
      </header>

      {/* ==========================================================================
          MAIN CONTENT AREA
          ========================================================================== */}
      <main className="landing-main">
        {/* ==========================================================================
            2. SPIDER-VERSE HERO SECTION
            ========================================================================== */}
        <section className="landing-hero-section" id="hero">
          {/* Comic Halftone Overlay & Multiverse Glitch Backing */}
          <div className="spidey-halftone-bg" aria-hidden="true" />
          <div className="spidey-ambient-glow" aria-hidden="true" />

          <div className="landing-container landing-hero-grid">
            <div className="hero-content">
              {/* Comic-Tech Eyebrow with Spider-Sense Warning Beacon */}
              <div className="hero-tag-badge spidey-hero-badge">
                <span className="spidey-sensory-ping">
                  <span className="spidey-ping-arc arc-left">)))</span>
                  <Zap size={14} className="spidey-bolt-mini" />
                  <span className="spidey-ping-arc arc-right">(((</span>
                </span>
                <span>SPIDER-SENSE FOR MUNICIPAL DISPATCH // NEURAL SIGNAL FUSION</span>
              </div>

              {/* Kinetic Spider-Verse Display Headline */}
              <h1 className="hero-title">
                THE CITY IS <br />
                <span className="hero-title-accent spidey-glitch" data-text="TALKING.">TALKING.</span>
                <span className="hero-title-sub">TINGLE WARNS FIRST.</span>
              </h1>

              {/* Narrative Grounded in Karen AI & Peter Tingle Origin */}
              <p className="hero-statement">
                When catastrophe strikes, the first signals aren't neat incident reports—they are 
                frantic screams on 911, garbled police scanner bursts on VHF 442.800 MHz, and erratic 
                sensor surges. Like Peter Parker's spider-sense tingling seconds before the blow connects, 
                TINGLE synthesizes multi-channel emergency chaos into verified, explainable P0–P3 
                triage before lives are lost.
              </p>

              {/* Purposeful, Non-Redundant Action Group */}
              <div className="hero-cta-group">
                <button 
                  type="button"
                  className="tactical-cta-btn primary spidey-glow-btn"
                  onClick={() => setActiveView('command-deck')}
                >
                  <span className="cta-icon-zap">⚡</span>
                  <span>INITIALIZE COMMAND DECK</span>
                  <ArrowRight size={17} />
                </button>

                {/* Interactive Simulator Trigger (Not a duplicate button!) */}
                <button 
                  type="button" 
                  className={`tactical-cta-btn secondary spidey-trigger-btn ${isSpiderSenseToggled ? 'active' : ''}`}
                  onClick={toggleSpiderSense}
                  title="Simulate Spider-Sense Threat Interception"
                >
                  <Activity size={16} className={isSpiderSenseToggled ? 'spin-icon' : ''} />
                  <span>{isSpiderSenseToggled ? 'SPIDER-SENSE ENGAGED' : 'ENGAGE SPIDER-SENSE'}</span>
                </button>
              </div>

              {/* Tactical Architecture Metadata Bar */}
              <div className="hero-meta-bar">
                <div className="meta-item">
                  <span className="meta-label">ENGINE:</span>
                  <span className="meta-val">KAREN NEURAL v1.2</span>
                </div>
                <div className="meta-sep">//</div>
                <div className="meta-item">
                  <span className="meta-label">LATENCY:</span>
                  <span className="meta-val cyan">140ms RT-STT</span>
                </div>
                <div className="meta-sep">//</div>
                <div className="meta-item">
                  <span className="meta-label">TRIAGE:</span>
                  <span className="meta-val yellow">DETERMINISTIC FORMULA</span>
                </div>
              </div>
            </div>

            {/* Interactive Spider-Verse Audio Ingestion HUD Card */}
            <div className={`hero-hud-card ${isSpiderSenseToggled ? 'spider-sense-active' : ''}`}>
              {/* Halftone edge pattern */}
              <div className="hud-card-halftone" />

              <div className="hud-card-header">
                <div className="hud-header-left">
                  <div className="spidey-radar-pulse">
                    <span className="radar-ping-ring" />
                    <span className="hud-live-dot" />
                  </div>
                  <div>
                    <span className="hud-title">KAREN SENSORY INTERCEPTOR</span>
                    <span className="hud-channel-sub">BAND SCAN // {currentChannel.band}</span>
                  </div>
                </div>
                <div className="hud-header-right">
                  <span className="spidey-threat-badge">
                    {currentChannel.urgency}
                  </span>
                </div>
              </div>

              <div className="hud-card-body">
                {/* Interactive Channel Selector Pills */}
                <div className="hud-channel-selector" role="tablist" aria-label="Emergency Ingestion Channels">
                  {(['ch-01', 'ch-02', 'ch-03'] as const).map(chId => (
                    <button
                      key={chId}
                      type="button"
                      role="tab"
                      aria-selected={activeHeroChannel === chId}
                      className={`hud-channel-tab ${activeHeroChannel === chId ? 'active' : ''}`}
                      onClick={() => setActiveHeroChannel(chId)}
                    >
                      <Radio size={12} />
                      <span>{HERO_CHANNELS[chId].freq}</span>
                    </button>
                  ))}
                </div>

                {/* Animated Spectrum Waveform Visualizer */}
                <div className="hud-waveform-container">
                  <div className="waveform-telemetry-row">
                    <span className="waveform-tag">LIVE FFT SPECTROGRAM</span>
                    <span className="waveform-db">{currentChannel.dbLevel}</span>
                  </div>

                  {/* Dynamic SVG Animated Waveform */}
                  <div className="waveform-svg-box">
                    <svg className="waveform-svg" viewBox="0 0 400 64" preserveAspectRatio="none">
                      <path 
                        className={`wave-path primary ${isSpiderSenseToggled ? 'animated' : ''}`} 
                        d="M0,32 Q25,8 50,32 T100,32 T150,12 T200,52 T250,18 T300,44 T350,22 T400,32" 
                      />
                      <path 
                        className={`wave-path secondary ${isSpiderSenseToggled ? 'animated-delayed' : ''}`} 
                        d="M0,32 Q30,50 60,32 T120,20 T180,48 T240,16 T300,50 T360,28 T400,32" 
                      />
                    </svg>

                    {/* Animated Equalizer Columns */}
                    <div className="spidey-equalizer-row">
                      {[65, 82, 45, 95, 78, 55, 92, 88, 70, 98, 84, 60, 90, 75, 50, 85].map((val, idx) => (
                        <div 
                          key={idx} 
                          className="equalizer-bar-unit"
                          style={{
                            height: isSpiderSenseToggled ? `${val}%` : '20%',
                            animationDelay: `${idx * 0.08}s`
                          }} 
                        />
                      ))}
                    </div>
                  </div>
                </div>

                {/* Spider-Verse Comic Live Transcript Bubble */}
                <div className="spidey-transcript-bubble">
                  <div className="bubble-notch" />
                  <div className="bubble-header">
                    <div className="bubble-source">
                      <Zap size={12} className="source-bolt" />
                      <span>{currentChannel.name}</span>
                    </div>
                    <span className="bubble-time">{utcTime || '14:02:11 UTC'}</span>
                  </div>
                  <p className="bubble-body">{currentChannel.transcript}</p>
                </div>

                {/* Sensory Spider-Sense Warning Banner */}
                {isSpiderSenseToggled && (
                  <div className="spidey-sense-alert-strip">
                    <span className="spidey-alert-arcs">⚡ ⚡ ⚡</span>
                    <span className="spidey-alert-text">
                      SPIDER-SENSE TRIGGERED // 120ms BEFORE ESCALATION
                    </span>
                    <span className="spidey-alert-confidence">{currentChannel.signalStrength}% SIG</span>
                  </div>
                )}
              </div>

              <div className="hud-card-footer">
                <span className="footer-freq">CARRIER: {currentChannel.freq}</span>
                <span className="footer-status-chip">
                  <span className="chip-beacon" />
                  INGESTION ACTIVE
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            3. THE SIGNAL STREAM SECTION (INTERACTIVE AUDIO PREVIEW)
            ========================================================================== */}
        <section className="landing-section" id="signals">
          <div className="landing-container">
            <div className="section-header">
              <div className="section-eyebrow">
                <span className="eyebrow-num">01 //</span> MULTI-CHANNEL INGESTION
              </div>
              <h2 className="section-title">THE SIGNAL STREAM</h2>
              <p className="section-desc">
                Emergency audio and reports ingested simultaneously from public safety dispatch 
                bands, civilian distress calls, and municipal sensors. Listen into the raw intercepted chatter.
              </p>
            </div>

            <div className="chaos-grid">
              {/* Card 1 */}
              <div className={`dispatch-card ${playingAudioId === 'card-1' ? 'playing' : ''}`}>
                <div className="dispatch-card-top">
                  <span className="source-tag">911 CALL // CAD-04</span>
                  <span className="timestamp-tag">14:02:11 UTC</span>
                </div>
                <blockquote className="dispatch-quote">
                  "There's thick black smoke billowing out near 5th and Vernon! People are coughing, I can't see the crosswalk!"
                </blockquote>

                {/* Interactive Audio Frequency Player */}
                <div className="dispatch-audio-sim">
                  <button 
                    type="button" 
                    className="audio-play-toggle"
                    onClick={() => setPlayingAudioId(playingAudioId === 'card-1' ? null : 'card-1')}
                    title="Simulate audio stream playback"
                  >
                    {playingAudioId === 'card-1' ? <VolumeX size={14} /> : <Volume2 size={14} />}
                    <span>{playingAudioId === 'card-1' ? 'STOP RAW FEED' : 'PREVIEW AUDIO PACKET'}</span>
                  </button>
                  {playingAudioId === 'card-1' && (
                    <div className="mini-equalizer-bars">
                      <span className="mini-bar b1" />
                      <span className="mini-bar b2" />
                      <span className="mini-bar b3" />
                      <span className="mini-bar b4" />
                      <span className="mini-bar b5" />
                    </div>
                  )}
                </div>

                <div className="dispatch-card-bottom">
                  <span className="urgency-badge critical">URGENCY: HIGH</span>
                  <span className="sector-tag">PATIA WEST</span>
                </div>
              </div>

              {/* Card 2 */}
              <div className={`dispatch-card ${playingAudioId === 'card-2' ? 'playing' : ''}`}>
                <div className="dispatch-card-top">
                  <span className="source-tag highlight-orange">RADIO SCANNER // B1</span>
                  <span className="timestamp-tag">14:02:13 UTC</span>
                </div>
                <blockquote className="dispatch-quote">
                  "Multiple vehicles stalled out in the underpass! Water level rising fast, doors won't open against the current!"
                </blockquote>

                <div className="dispatch-audio-sim">
                  <button 
                    type="button" 
                    className="audio-play-toggle"
                    onClick={() => setPlayingAudioId(playingAudioId === 'card-2' ? null : 'card-2')}
                    title="Simulate audio stream playback"
                  >
                    {playingAudioId === 'card-2' ? <VolumeX size={14} /> : <Volume2 size={14} />}
                    <span>{playingAudioId === 'card-2' ? 'STOP RAW FEED' : 'PREVIEW AUDIO PACKET'}</span>
                  </button>
                  {playingAudioId === 'card-2' && (
                    <div className="mini-equalizer-bars">
                      <span className="mini-bar b1" />
                      <span className="mini-bar b2" />
                      <span className="mini-bar b3" />
                      <span className="mini-bar b4" />
                      <span className="mini-bar b5" />
                    </div>
                  )}
                </div>

                <div className="dispatch-card-bottom">
                  <span className="urgency-badge">URGENCY: ELEVATED</span>
                  <span className="sector-tag">UNDERPASS 04</span>
                </div>
              </div>

              {/* Card 3 */}
              <div className={`dispatch-card ${playingAudioId === 'card-3' ? 'playing' : ''}`}>
                <div className="dispatch-card-top">
                  <span className="source-tag highlight-cyan">CITIZEN REPORT</span>
                  <span className="timestamp-tag">14:02:15 UTC</span>
                </div>
                <blockquote className="dispatch-quote">
                  "Explosion sound heard near the electrical substation! Sparks flying everywhere, pedestrians scattering!"
                </blockquote>

                <div className="dispatch-audio-sim">
                  <button 
                    type="button" 
                    className="audio-play-toggle"
                    onClick={() => setPlayingAudioId(playingAudioId === 'card-3' ? null : 'card-3')}
                    title="Simulate audio stream playback"
                  >
                    {playingAudioId === 'card-3' ? <VolumeX size={14} /> : <Volume2 size={14} />}
                    <span>{playingAudioId === 'card-3' ? 'STOP RAW FEED' : 'PREVIEW AUDIO PACKET'}</span>
                  </button>
                  {playingAudioId === 'card-3' && (
                    <div className="mini-equalizer-bars">
                      <span className="mini-bar b1" />
                      <span className="mini-bar b2" />
                      <span className="mini-bar b3" />
                      <span className="mini-bar b4" />
                      <span className="mini-bar b5" />
                    </div>
                  )}
                </div>

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
              <div className="section-eyebrow">
                <span className="eyebrow-num">02 //</span> GEOSPATIAL & TEMPORAL FUSION
              </div>
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
                  <Sparkles size={14} />
                  <span>CORROBORATED BY 3 INDEPENDENT SOURCES</span>
                </div>
              </div>

              {/* Center Column: Correlation Convergence Node */}
              <div className="convergence-node">
                <div className="bolt-icon-box spidey-convergence-box">
                  <Zap size={32} />
                  <span className="convergence-ripple" />
                </div>
                <div className="node-label">SIGNAL CORRELATION</div>
                <div className="node-sublabel">GEOSPATIAL & TIME CLUSTERING</div>
                <div className="node-formula">4-MIN WINDOW // GEOHASH-6</div>
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
                <div className="section-eyebrow">
                  <span className="eyebrow-num">03 //</span> EXPLAINABLE SCORING
                </div>
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
                  <div className="formula-label">DETERMINISTIC PRIORITY FORMULA:</div>
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

        {/* ==========================================================================
            6. THE PRIORITY MATRIX SECTION
            ========================================================================== */}
        <section className="landing-section matrix-section" id="priority-matrix">
          <div className="landing-container">
            <div className="section-header">
              <div className="section-eyebrow">
                <span className="eyebrow-num">04 //</span> TRIAGE HIERARCHY
              </div>
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

        {/* ==========================================================================
            7. SHOWSTOPPER FULL-WIDTH SECTION: SPIDER-SENSE MULTIVERSE RADAR
               (Takes 100% full width of viewport with live interactive incident inspection)
            ========================================================================== */}
        <section className="landing-fullwidth-section" id="multiverse-radar">
          {/* Section Header Strip spanning 100% width */}
          <div className="radar-fullwidth-header">
            <div className="radar-header-left">
              <div className="radar-live-badge">
                <span className="radar-beacon-dot" />
                <span className="radar-beacon-text">360° LIVE SURVEILLANCE THEATER</span>
              </div>
              <h2 className="radar-theater-title">
                SPIDER-SENSE MULTIVERSE RADAR
              </h2>
            </div>

            <div className="radar-header-center">
              <div className="radar-telemetry-tag">
                <span className="tag-k">ACTIVE GRID:</span>
                <span className="tag-v">PATIA METROPOLITAN // SECTOR 01–09</span>
              </div>
              <div className="radar-telemetry-tag">
                <span className="tag-k">INCOMING SIGNALS:</span>
                <span className="tag-v cyan">4 ACTIVE INCIDENTS</span>
              </div>
            </div>

            <div className="radar-header-right">
              {/* Interactive Signal Surge Trigger */}
              <button 
                type="button" 
                className={`radar-surge-btn ${isSurgeActive ? 'active' : ''}`}
                onClick={handleSimulateSurge}
                title="Trigger simulated multi-signal 911 distress surge"
              >
                <Zap size={14} className={isSurgeActive ? 'bolt-active' : ''} />
                <span>{isSurgeActive ? 'SURGE WAVE CORRELATING...' : 'TRIGGER SIGNAL SURGE'}</span>
              </button>
            </div>
          </div>

          {/* Panoramic Theater Body (2-Column Full-Width Interactive Surface) */}
          <div className="radar-theater-body">
            {/* Left/Center Column: Panoramic Cartographic Radar Canvas */}
            <div className="radar-canvas-panel">
              {/* Comic Halftone Overlay Pattern */}
              <div className="radar-halftone-mesh" />

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

              {/* Cartographic Crosshair Axes */}
              <div className="radar-axis-h" />
              <div className="radar-axis-v" />

              {/* Compass Cardinal Points */}
              <span className="compass-pt north">N // 000°</span>
              <span className="compass-pt east">E // 090°</span>
              <span className="compass-pt south">S // 180°</span>
              <span className="compass-pt west">W // 270°</span>

              {/* Animated Surge Connection Vectors */}
              {isSurgeActive && (
                <svg className="radar-surge-vectors" viewBox="0 0 100 100" preserveAspectRatio="none">
                  <line x1="38" y1="44" x2="68" y2="32" className="surge-line" />
                  <line x1="38" y1="44" x2="80" y2="64" className="surge-line-delayed" />
                  <circle cx="38" cy="44" r="8" className="surge-epicenter" />
                </svg>
              )}

              {/* Interactive Incident Beacons on Map */}
              {RADAR_INCIDENTS.map((inc) => {
                const isSelected = inc.id === selectedIncidentId;
                const isP0 = inc.tier === 'P0';

                return (
                  <div
                    key={inc.id}
                    className={`radar-pin-node ${isSelected ? 'selected' : ''} ${isP0 ? 'p0-threat' : ''} ${isSurgeActive && inc.isCorrelatedSurge ? 'surge-pulse' : ''}`}
                    style={{ left: `${inc.pinPos.x}%`, top: `${inc.pinPos.y}%` }}
                    onClick={() => setSelectedIncidentId(inc.id)}
                    role="button"
                    tabIndex={0}
                    aria-label={`Select incident ${inc.id}`}
                  >
                    {/* Spider-Verse Spider-Sense Danger Halo for P0 */}
                    {isP0 && (
                      <div className="spidey-danger-halo">
                        <span className="spidey-halo-arc arc-t">)))</span>
                        <span className="spidey-halo-arc arc-b">(((</span>
                      </div>
                    )}

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

              {/* Radar Footer Overlay */}
              <div className="radar-canvas-footer">
                <span className="canvas-coords">LAT: 20.3541°N // LON: 85.8194°E</span>
                <span className="canvas-guide">CLICK ANY INCIDENT NODE TO AUDIT TELEMETRY</span>
              </div>
            </div>

            {/* Right Column: Live Incident Inspector HUD */}
            <div className="radar-inspector-panel">
              <div className="inspector-panel-header">
                <div className="inspector-tier-group">
                  <Badge variant={selectedIncident.badgeVariant} size="md">
                    {selectedIncident.tier}
                  </Badge>
                  <span className="inspector-inc-id">{selectedIncident.id}</span>
                </div>
                <span className="inspector-conf-pill">
                  CONFIDENCE: {selectedIncident.confidence}
                </span>
              </div>

              <div className="inspector-panel-body">
                <h3 className="inspector-incident-title">
                  {selectedIncident.title}
                </h3>
                <div className="inspector-sector-badge">
                  <MapPin size={12} />
                  <span>{selectedIncident.sector}</span>
                </div>

                {/* Real-time Explainable Factor Score Breakdown */}
                <div className="inspector-scores-box">
                  <div className="scores-box-header">
                    <span>DETERMINISTIC FACTOR SCORING</span>
                    <span className="scores-formula-sub">WEIGHTED SUM // EXPLAINABLE</span>
                  </div>

                  <div className="factor-meters-list">
                    <div className="factor-meter-item">
                      <div className="meter-label-row">
                        <span>Life-Safety Hazard</span>
                        <span className="meter-score-num">{selectedIncident.lifeSafety} / 100</span>
                      </div>
                      <div className="meter-track">
                        <div 
                          className="meter-fill red" 
                          style={{ width: `${selectedIncident.lifeSafety}%` }} 
                        />
                      </div>
                    </div>

                    <div className="factor-meter-item">
                      <div className="meter-label-row">
                        <span>Hazard Velocity</span>
                        <span className="meter-score-num">{selectedIncident.hazardVelocity} / 100</span>
                      </div>
                      <div className="meter-track">
                        <div 
                          className="meter-fill orange" 
                          style={{ width: `${selectedIncident.hazardVelocity}%` }} 
                        />
                      </div>
                    </div>

                    <div className="factor-meter-item">
                      <div className="meter-label-row">
                        <span>Corroboration Multiplier</span>
                        <span className="meter-score-num">{selectedIncident.corroboration} / 100</span>
                      </div>
                      <div className="meter-track">
                        <div 
                          className="meter-fill cyan" 
                          style={{ width: `${selectedIncident.corroboration}%` }} 
                        />
                      </div>
                    </div>

                    <div className="factor-meter-item">
                      <div className="meter-label-row">
                        <span>Infrastructure Criticality</span>
                        <span className="meter-score-num">{selectedIncident.infrastructure} / 100</span>
                      </div>
                      <div className="meter-track">
                        <div 
                          className="meter-fill yellow" 
                          style={{ width: `${selectedIncident.infrastructure}%` }} 
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Linked Voice Fragments & Corroborated Evidence */}
                <div className="inspector-evidence-box">
                  <span className="evidence-header-label">CORROBORATED INCOMING DISPATCH FRAGMENTS:</span>
                  <div className="evidence-quotes-list">
                    {selectedIncident.transcripts.map((text, idx) => (
                      <div key={idx} className="evidence-quote-bubble">
                        <span className="quote-idx">#{idx + 1}</span>
                        <p className="quote-body">{text}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Recommended Dispatch Deployment Vector */}
                <div className="inspector-action-box">
                  <span className="action-header-label">ACTIONABLE DISPATCH VECTOR:</span>
                  <div className="units-tag-list">
                    {selectedIncident.recommendedUnits.map((unit, idx) => (
                      <span key={idx} className="unit-pill">
                        <Crosshair size={12} />
                        <span>{unit}</span>
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Inspector Action Button */}
              <div className="inspector-panel-footer">
                <button 
                  type="button" 
                  className="inspector-engage-btn"
                  onClick={() => setActiveView('command-deck')}
                >
                  <span>ENGAGE DISPATCH PROTOCOL</span>
                  <ArrowRight size={15} />
                </button>
              </div>
            </div>
          </div>

          {/* Full-Width Panoramic Audio Spectrogram Waterfall Ribbon */}
          <div className="radar-waterfall-ribbon">
            <div className="waterfall-ticker-track">
              <div className="ticker-segment">
                <span className="ticker-label">VHF FREQ:</span>
                <span className="ticker-val">442.800 MHz</span>
              </div>
              <div className="ticker-dot">•</div>
              <div className="ticker-segment">
                <span className="ticker-label">CAD BAND:</span>
                <span className="ticker-val">PUBLIC SAFETY 911-04</span>
              </div>
              <div className="ticker-dot">•</div>
              <div className="ticker-segment">
                <span className="ticker-label">GEOCLUSTER:</span>
                <span className="ticker-val">GEOHASH-6 (tgu0u)</span>
              </div>
              <div className="ticker-dot">•</div>
              <div className="ticker-segment">
                <span className="ticker-label">RT-STT INGESTION:</span>
                <span className="ticker-val green">140ms REALTIME // 0% LOSS</span>
              </div>
              <div className="ticker-dot">•</div>
              <div className="ticker-segment">
                <span className="ticker-label">SOVEREIGNTY:</span>
                <span className="ticker-val yellow">HUMAN-IN-THE-LOOP MANDATE</span>
              </div>
              <div className="ticker-dot">•</div>
              <div className="ticker-segment">
                <span className="ticker-label">STANDARDS:</span>
                <span className="ticker-val">APCO PROJECT 33 COMPLIANT</span>
              </div>
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
                <div className="section-eyebrow">
                  <span className="eyebrow-num">05 //</span> HUMAN IN COMMAND
                </div>
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

        {/* ==========================================================================
            9. COMMAND CENTER INTERFACE PREVIEW (CLEANED TABS, NO REDUNDANT BUTTONS)
            ========================================================================== */}
        <section className="landing-section preview-section" id="command-center">
          <div className="landing-container">
            <div className="section-header between">
              <div>
                <div className="section-eyebrow">
                  <span className="eyebrow-num">06 //</span> DISPATCH CONSOLE
                </div>
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
                  { id: 'command-deck', label: 'Command Deck', icon: Compass },
                  { id: 'incident-streams', label: 'Incident Streams', icon: Layers },
                  { id: 'investigation', label: 'Investigation Board', icon: Eye },
                  { id: 'audit-trail', label: 'Audit Ledger', icon: Terminal },
                  { id: 'briefing', label: 'System Briefing', icon: FileText }
                ].map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeConsoleTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      className={`module-tab-btn ${isActive ? 'active' : ''}`}
                      onClick={() => setActiveConsoleTab(tab.id as NavigationView)}
                    >
                      <Icon size={14} />
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
                    <Badge variant="p0-critical" size="sm">ACTIVE TRIAGE</Badge>
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

              {/* Dedicated Single Launch Action Rail */}
              <div className="preview-launcher-rail">
                <div className="launcher-rail-info">
                  <span className="info-indicator" />
                  <span>SELECTED MODULE READY FOR DISPATCH COMMANDER SESSION</span>
                </div>
                <button 
                  type="button" 
                  className="launcher-direct-btn"
                  onClick={() => setActiveView(activeConsoleTab)}
                >
                  <span>LAUNCH {activeConsoleTab.toUpperCase().replace('-', ' ')}</span>
                  <ArrowRight size={15} />
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
              <div className="launch-tag">OPERATIONAL READINESS</div>
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
                <span>ACCESS OPERATOR DECK</span>
                <ArrowRight size={18} />
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* ==========================================================================
          11. CLEAN, MODERN & TACTICAL FOOTER (NO REDUNDANT BUTTONS)
          ========================================================================== */}
      <footer className="landing-footer" role="contentinfo">
        <div className="landing-container">
          <div className="landing-footer-grid">
            {/* Col 1: System Identity */}
            <div className="footer-col brand-col">
              <div className="footer-brand-title">
                <Zap size={16} className="footer-bolt" />
                <span>TINGLE</span>
              </div>
              <p className="footer-tagline">
                Real-time emergency intelligence & explainable triage decision support built on Karen Engine.
              </p>
              <div className="footer-compliance-tags">
                <span className="compliance-tag">APCO 33 COMPLIANT</span>
                <span className="compliance-tag">DETERMINISTIC TRIAGE</span>
              </div>
            </div>

            {/* Col 2: Architectural Principles */}
            <div className="footer-col specs-col">
              <h4 className="footer-col-header">SYSTEM ARCHITECTURE</h4>
              <ul className="footer-specs-list">
                <li><span>•</span> Multi-Band VHF & CAD Ingestion</li>
                <li><span>•</span> Geohash-6 Spatiotemporal Clustering</li>
                <li><span>•</span> 140ms Real-Time Audio Transcription</li>
                <li><span>•</span> Human-in-the-Loop Sovereign Authority</li>
              </ul>
            </div>

            {/* Col 3: Direct Quick Jump Links (Zero Redundant Buttons) */}
            <div className="footer-col nav-col">
              <h4 className="footer-col-header">NAVIGATION</h4>
              <nav className="footer-nav-list" aria-label="Footer Quick Navigation">
                <a href="#signals" onClick={(e) => scrollToSection(e, 'signals')}>The Signal Stream</a>
                <a href="#correlation" onClick={(e) => scrollToSection(e, 'correlation')}>Incident Correlation</a>
                <a href="#priority-matrix" onClick={(e) => scrollToSection(e, 'priority-matrix')}>Priority Matrix</a>
                <a href="#multiverse-radar" onClick={(e) => scrollToSection(e, 'multiverse-radar')}>Multiverse Radar</a>
                <a href="#command-center" onClick={(e) => scrollToSection(e, 'command-center')}>Command Console</a>
              </nav>
            </div>

            {/* Col 4: Live Telemetry & Health */}
            <div className="footer-col telemetry-col">
              <h4 className="footer-col-header">LIVE DISPATCH TELEMETRY</h4>
              <div className="footer-telemetry-card">
                <div className="tel-row">
                  <span className="tel-k">SYSTEM CLOCK:</span>
                  <span className="tel-v mono">{utcTime || '14:02:11 UTC'}</span>
                </div>
                <div className="tel-row">
                  <span className="tel-k">WS TRANSPORT:</span>
                  <span className={`tel-v ${isConnected ? 'green' : 'yellow'}`}>
                    {isConnected ? 'ESTABLISHED' : 'STANDBY'}
                  </span>
                </div>
                <div className="tel-row">
                  <span className="tel-k">OPERATOR:</span>
                  <span className="tel-v mono">{operatorId.toUpperCase()}</span>
                </div>
                <div className="tel-row">
                  <span className="tel-k">BUILD VERSION:</span>
                  <span className="tel-v cyan">v1.2-STITCH</span>
                </div>
              </div>
            </div>
          </div>

          {/* Footer Sub-Bar with Copyright & Integrity Disclosures */}
          <div className="footer-bottom-bar">
            <div className="footer-copyright">
              © 2026 TINGLE DISPATCH INTELLIGENCE. ALL RIGHTS RESERVED.
            </div>
            <div className="footer-mandate">
              CONFIDENTIAL EMERGENCY OPERATIONS // APCO PROJECT 33 AUDIT INTEGRITY MANDATE
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPageView;
