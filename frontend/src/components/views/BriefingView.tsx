import React from 'react';
import { Terminal, Radio, ShieldCheck, Activity, Cpu, Layers, CheckCircle2 } from 'lucide-react';
import { Button, Badge, StatusIndicator } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import './BriefingView.css';

export const BriefingView: React.FC = () => {
  const { setActiveView } = useNavigation();
  const { isOnline, databaseStatus, isLoading } = useBackendHealth();

  const engineIndicatorStatus = isOnline === true ? 'online' : isOnline === false ? 'offline' : 'standby';
  const engineIndicatorLabel = isOnline === true ? 'API ONLINE' : isOnline === false ? 'API OFFLINE' : 'CHECKING...';

  return (
    <div className="briefing-view" role="region" aria-label="System Briefing">
      <div className="briefing-header">
        <div className="briefing-title-group">
          <Cpu size={18} color="var(--color-dispatch-yellow)" />
          <h1 className="briefing-title">OPERATIONAL SYSTEM BRIEFING</h1>
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
      </div>

      <div className="briefing-content">
        {/* System Telemetry Bar */}
        <div className="briefing-telemetry-strip" role="status" aria-label="System operational status">
          <div className="briefing-telemetry-left">
            <Activity size={14} className="text-cyan" />
            <span className="telemetry-label">SYSTEM HEALTH:</span>
            <StatusIndicator status={engineIndicatorStatus} label={engineIndicatorLabel} />
            <Badge variant="neutral" size="sm">
              DATABASE: {isLoading ? 'PROBING...' : (databaseStatus || 'CONNECTED').toUpperCase()}
            </Badge>
          </div>
          <div className="briefing-telemetry-right">
            <span className="telemetry-meta">TINGLE // RELEASE v1.2</span>
          </div>
        </div>

        {/* Hero Mission Panel */}
        <section className="briefing-hero-panel">
          <h2 className="briefing-hero-headline">
            DISPATCH DECISION SUPPORT PLATFORM
          </h2>
          <p className="briefing-hero-lead">
            TINGLE correlates multi-channel emergency transcripts, citizen alerts, and sensor streams into verified, explainable incidents in real time. Built specifically for high-stress dispatchers and situational commanders to eliminate noise and accelerate life-saving decisions.
          </p>

          {/* Quick Capability Feature Row (replaces cheesy pipeline diagram) */}
          <div className="briefing-feature-row">
            <div className="briefing-feature-item">
              <CheckCircle2 size={16} className="feature-icon green" />
              <div className="feature-text">
                <strong>Multi-Source Fusion</strong>
                <span>Correlates 911 calls, radio bands & sensor alerts</span>
              </div>
            </div>

            <div className="briefing-feature-item">
              <CheckCircle2 size={16} className="feature-icon yellow" />
              <div className="feature-text">
                <strong>Explainable Priority</strong>
                <span>Scored by life-safety, velocity & corroboration</span>
              </div>
            </div>

            <div className="briefing-feature-item">
              <CheckCircle2 size={16} className="feature-icon cyan" />
              <div className="feature-text">
                <strong>Operator Final Authority</strong>
                <span>Complete manual override with immutable audit logging</span>
              </div>
            </div>
          </div>

          <div className="briefing-hero-actions">
            <Button 
              type="button"
              variant="warning" 
              size="md" 
              onClick={() => setActiveView('command-deck')}
            >
              OPEN COMMAND DECK
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
              onClick={() => setActiveView('audit-trail')}
            >
              <ShieldCheck size={14} style={{ marginRight: 6 }} />
              INSPECT AUDIT LEDGER
            </Button>
          </div>
        </section>

        {/* Core Architecture Pillars */}
        <section className="briefing-pillars-grid" aria-label="System core architecture pillars">
          <div className="pillar-card">
            <div className="pillar-card-icon">
              <Layers size={20} color="var(--color-dispatch-yellow)" />
            </div>
            <h3 className="pillar-title">TRANSPARENT FACTOR ATTRIBUTION</h3>
            <p className="pillar-desc">
              Every incident priority score is deterministically derived from verified signals: life-safety threats, hazard velocity, and independent witness corroboration.
            </p>
          </div>

          <div className="pillar-card">
            <div className="pillar-card-icon">
              <ShieldCheck size={20} color="var(--color-system-green)" />
            </div>
            <h3 className="pillar-title">GEOSPATIAL VERIFICATION</h3>
            <p className="pillar-desc">
              Unverified locations remain approximate and flag needs-review status. Coordinates are never hallucinated, ensuring responders are dispatched with validated precision.
            </p>
          </div>

          <div className="pillar-card">
            <div className="pillar-card-icon">
              <Terminal size={20} color="var(--color-multiverse-cyan)" />
            </div>
            <h3 className="pillar-title">OPERATOR COMMAND AUTHORITY</h3>
            <p className="pillar-desc">
              The human dispatcher holds ultimate operational authority. Any algorithmic triage can be overridden instantly with mandatory recorded justification.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
};

export default BriefingView;
