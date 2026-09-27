import React from 'react';
import { 
  Terminal, 
  Radio, 
  ShieldCheck, 
  Activity, 
  Cpu, 
  Layers, 
  CheckCircle2, 
  RadioTower, 
  MapPin, 
  Sliders, 
  Lock
} from 'lucide-react';
import { Button, Badge, StatusIndicator } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import './BriefingView.css';

export const BriefingView: React.FC = () => {
  const { setActiveView } = useNavigation();
  const { isOnline, databaseStatus, isLoading } = useBackendHealth();

  const engineIndicatorStatus = isOnline === true ? 'online' : isOnline === false ? 'offline' : 'standby';
  const engineIndicatorLabel = isOnline === true ? 'API CORE ONLINE' : isOnline === false ? 'API CORE OFFLINE' : 'CHECKING...';

  return (
    <div className="briefing-view pattern-halftone" role="region" aria-label="Operational System Briefing">
      {/* Header Bar */}
      <header className="briefing-header">
        <div className="briefing-title-group">
          <div className="briefing-badge-tape">PROTOCOL SPIDER-CAD</div>
          <div className="briefing-title-combo">
            <Cpu size={20} color="var(--color-dispatch-yellow)" />
            <h1 className="briefing-title font-headline">TACTICAL OPERATIONAL SYSTEM BRIEFING</h1>
          </div>
        </div>
        <div className="briefing-header-actions">
          <Button 
            type="button"
            variant="primary" 
            size="sm" 
            onClick={() => setActiveView('command-deck')}
            aria-label="Enter Tactical Command Deck"
          >
            <Terminal size={14} style={{ marginRight: 6 }} />
            LAUNCH COMMAND DECK
          </Button>
        </div>
      </header>

      <div className="briefing-content">
        {/* System Telemetry Bar */}
        <div className="briefing-telemetry-strip" role="status" aria-label="System operational status">
          <div className="briefing-telemetry-left">
            <Activity size={14} className="text-cyan" />
            <span className="telemetry-label font-headline">SYSTEM TELEMETRY:</span>
            <StatusIndicator status={engineIndicatorStatus} label={engineIndicatorLabel} />
            <Badge variant="neutral" size="sm">
              DATABASE: {isLoading ? 'PROBING...' : (databaseStatus || 'CONNECTED').toUpperCase()}
            </Badge>
            <Badge variant="neutral" size="sm">
              ENGINE: FASTAPI + POSTGRES
            </Badge>
          </div>
          <div className="briefing-telemetry-right font-mono">
            <span>RELEASE // v1.2 TACTICAL SPRINT</span>
          </div>
        </div>

        {/* Hero Mission Panel */}
        <section className="briefing-hero-panel">
          <div className="briefing-hero-badge font-mono">
            <span>[CAD DECISION SUPPORT PLATFORM]</span>
          </div>
          <h2 className="briefing-hero-headline font-headline">
            MULTIVERSE EMERGENCY CORRELATION & DISPATCH ENGINE
          </h2>
          <p className="briefing-hero-lead font-body">
            TINGLE correlates multi-channel citizen 911 calls, emergency radio bands, and sensor streams into verified, explainable incidents in real time. Engineered specifically for high-stress dispatchers and incident commanders to eliminate signal noise and accelerate life-saving tactical decisions.
          </p>

          {/* Quick Capability Feature Row */}
          <div className="briefing-feature-row">
            <div className="briefing-feature-item">
              <div className="feature-icon-wrap green">
                <CheckCircle2 size={16} />
              </div>
              <div className="feature-text">
                <strong className="font-headline">MULTI-SOURCE FUSION</strong>
                <span className="font-body">Correlates 911 transcripts, scanner bands & sensor pings into consolidated incidents</span>
              </div>
            </div>

            <div className="briefing-feature-item">
              <div className="feature-icon-wrap yellow">
                <CheckCircle2 size={16} />
              </div>
              <div className="feature-text">
                <strong className="font-headline">EXPLAINABLE ATTRIBUTION</strong>
                <span className="font-body">Deterministic priority scoring driven by life-safety, velocity & corroboration</span>
              </div>
            </div>

            <div className="briefing-feature-item">
              <div className="feature-icon-wrap cyan">
                <CheckCircle2 size={16} />
              </div>
              <div className="feature-text">
                <strong className="font-headline">SOVEREIGN HUMAN COMMAND</strong>
                <span className="font-body">Human dispatchers retain supreme override authority with immutable audit logging</span>
              </div>
            </div>
          </div>

          {/* Direct Viewport Launchers */}
          <div className="briefing-hero-actions">
            <Button 
              type="button"
              variant="warning" 
              size="md" 
              onClick={() => setActiveView('command-deck')}
            >
              OPEN COMMAND DECK →
            </Button>
            <Button 
              type="button"
              variant="secondary" 
              size="md" 
              onClick={() => setActiveView('incident-streams')}
            >
              <Radio size={14} style={{ marginRight: 6 }} />
              VIEW INCIDENT STREAMS
            </Button>
            <Button 
              type="button"
              variant="secondary" 
              size="md" 
              onClick={() => setActiveView('investigation')}
            >
              <Terminal size={14} style={{ marginRight: 6 }} />
              INVESTIGATION DOSSIERS
            </Button>
            <Button 
              type="button"
              variant="secondary" 
              size="md" 
              onClick={() => setActiveView('audit-trail')}
            >
              <ShieldCheck size={14} style={{ marginRight: 6 }} />
              AUDIT LEDGER
            </Button>
          </div>
        </section>

        {/* Tactical Pipeline Stages Architecture */}
        <section className="briefing-pipeline-section" aria-label="Tactical Processing Pipeline">
          <div className="pipeline-section-header">
            <h3 className="pipeline-section-title font-headline">5-STAGE TACTICAL DISPATCH PIPELINE</h3>
            <span className="pipeline-section-sub font-mono">END-TO-END LATENCY BUDGET: &lt; 1500MS</span>
          </div>

          <div className="pipeline-steps-grid">
            <div className="pipeline-step-card">
              <div className="step-card-num font-mono">01</div>
              <div className="step-card-icon text-cyan">
                <RadioTower size={20} />
              </div>
              <h4 className="step-card-title font-headline">SIGNAL INTERCEPT</h4>
              <p className="step-card-desc font-body">
                Ingests raw transcripts from 911 calls, civic radio scanners, and sensor channels with millisecond timestamps.
              </p>
            </div>

            <div className="pipeline-step-card">
              <div className="step-card-num font-mono">02</div>
              <div className="step-card-icon text-dispatch-yellow">
                <Cpu size={20} />
              </div>
              <h4 className="step-card-title font-headline">NLP EXTRACTION</h4>
              <p className="step-card-desc font-body">
                Zero-hallucination entity recognition extracts hazards, trapped counts, and cross-references canonical landmarks.
              </p>
            </div>

            <div className="pipeline-step-card">
              <div className="step-card-num font-mono">03</div>
              <div className="step-card-icon text-green">
                <MapPin size={20} />
              </div>
              <h4 className="step-card-title font-headline">SPATIAL CORRELATION</h4>
              <p className="step-card-desc font-body">
                Spatiotemporal clustering links corroborating reports within 500m radius and 30-minute rolling windows.
              </p>
            </div>

            <div className="pipeline-step-card">
              <div className="step-card-num font-mono">04</div>
              <div className="step-card-icon text-hazard">
                <Sliders size={20} />
              </div>
              <h4 className="step-card-title font-headline">FACTOR ATTRIBUTION</h4>
              <p className="step-card-desc font-body">
                Deterministic formula evaluates life safety (40%), hazard velocity (25%), and multi-witness corroboration (15%).
              </p>
            </div>

            <div className="pipeline-step-card">
              <div className="step-card-num font-mono">05</div>
              <div className="step-card-icon text-crimson">
                <Lock size={20} />
              </div>
              <h4 className="step-card-title font-headline">OPERATOR OVERRIDE</h4>
              <p className="step-card-desc font-body">
                Dispatcher retains sovereign authority to modify urgency, dispatch units, and log immutable tamper-proof audit trails.
              </p>
            </div>
          </div>
        </section>

        {/* Core Architecture Pillars */}
        <section className="briefing-pillars-grid" aria-label="System core architecture pillars">
          <div className="pillar-card">
            <div className="pillar-card-icon">
              <Layers size={20} color="var(--color-dispatch-yellow)" />
            </div>
            <h3 className="pillar-title font-headline">TRANSPARENT FACTOR ATTRIBUTION</h3>
            <p className="pillar-desc font-body">
              Every incident priority score is deterministically derived from verified signals: life-safety threats, hazard velocity, and independent witness corroboration. No opaque black-box AI scores.
            </p>
            <div className="pillar-tag font-mono">[EXPLAINABLE CALCULATION: 100%]</div>
          </div>

          <div className="pillar-card">
            <div className="pillar-card-icon">
              <ShieldCheck size={20} color="var(--color-system-green)" />
            </div>
            <h3 className="pillar-title font-headline">GEOSPATIAL VERIFICATION</h3>
            <p className="pillar-desc font-body">
              Unverified locations remain approximate and flag needs-review status. Coordinates are never hallucinated, ensuring emergency responders are dispatched to validated ground zero locations.
            </p>
            <div className="pillar-tag font-mono">[ZERO-HALLUCINATION LOCK]</div>
          </div>

          <div className="pillar-card">
            <div className="pillar-card-icon">
              <Terminal size={20} color="var(--color-multiverse-cyan)" />
            </div>
            <h3 className="pillar-title font-headline">OPERATOR SUPREME COMMAND</h3>
            <p className="pillar-desc font-body">
              The human dispatcher holds ultimate operational supremacy. Any machine triage can be overridden instantly under row-level database locks with mandatory recorded justification.
            </p>
            <div className="pillar-tag font-mono">[SOVEREIGN OVERRIDE: ENFORCED]</div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default BriefingView;
