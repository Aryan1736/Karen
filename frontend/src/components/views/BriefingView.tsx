import React from 'react';
import { BookOpen, Terminal, Radio, ShieldCheck, Activity } from 'lucide-react';
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
    <div className="briefing-view" role="region" aria-label="Mission Briefing">
      <div className="briefing-header">
        <div className="briefing-title-group">
          <BookOpen size={18} color="var(--color-dispatch-yellow)" />
          <h1 className="briefing-title">MISSION BRIEFING // OPERATING SYSTEM DOCTRINE</h1>
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
            ENTER COMMAND DECK
          </Button>
        </div>
      </div>

      <div className="briefing-content">
        {/* System Readiness Strip */}
        <div className="briefing-telemetry-strip font-mono" role="status" aria-label="System operational status">
          <div className="briefing-telemetry-left">
            <Activity size={14} className="text-cyan" />
            <span>OPERATIONAL READINESS:</span>
            <StatusIndicator status={engineIndicatorStatus} label={engineIndicatorLabel} />
            <Badge variant="neutral" size="sm">
              DB: {isLoading ? 'PROBING...' : (databaseStatus || 'UNKNOWN').toUpperCase()}
            </Badge>
          </div>
          <div className="briefing-telemetry-right">
            <span>PLATFORM: TINGLE v0.2.0-STARK</span>
          </div>
        </div>

        <section className="briefing-hero-panel">
          <h2 className="briefing-hero-headline">
            TINGLE EMERGENCY INTELLIGENCE CONSOLE
          </h2>
          <p className="briefing-hero-lead">
            An operator decision-support platform engineered to transform chaotic multi-channel crisis reports into explainable, continuously prioritized incidents. Designed for situational commanders operating under extreme cognitive load.
          </p>

          <div className="pipeline-diagram" aria-label="Operational emergency pipeline">
            <span className="pipeline-node">CHAOS</span>
            <span className="pipeline-arrow" aria-hidden="true">→</span>
            <span className="pipeline-node">SIGNAL</span>
            <span className="pipeline-arrow" aria-hidden="true">→</span>
            <span className="pipeline-node">INCIDENT</span>
            <span className="pipeline-arrow" aria-hidden="true">→</span>
            <span className="pipeline-node active-accent">PRIORITY</span>
            <span className="pipeline-arrow" aria-hidden="true">→</span>
            <span className="pipeline-node">ACTION</span>
          </div>

          <div className="briefing-hero-actions">
            <Button 
              type="button"
              variant="warning" 
              size="md" 
              onClick={() => setActiveView('command-deck')}
            >
              LAUNCH COMMAND DECK
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

        <section className="briefing-pillars-grid" aria-label="Operating system core pillars">
          <div className="pillar-card">
            <h3 className="pillar-title">DETERMINISTIC PRIORITY</h3>
            <p className="pillar-desc">
              AI components extract features and compute semantic embeddings; deterministic formulas compute bounded priority scores with full factor explainability.
            </p>
          </div>

          <div className="pillar-card">
            <h3 className="pillar-title">NO HALLUCINATION</h3>
            <p className="pillar-desc">
              Unverified locations remain approximate or unplotted. Coordinates are never fabricated to place pins on the cartographic map.
            </p>
          </div>

          <div className="pillar-card">
            <h3 className="pillar-title">SOVEREIGN HUMAN REVIEW</h3>
            <p className="pillar-desc">
              The human dispatcher retains absolute command. Every modification is logged to an immutable audit ledger while preserving raw ML telemetry.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
};

export default BriefingView;
