import React from 'react';
import { BookOpen, Terminal } from 'lucide-react';
import { Button } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import './BriefingView.css';

export const BriefingView: React.FC = () => {
  const { setActiveView } = useNavigation();

  return (
    <div className="briefing-view" role="region" aria-label="Mission Briefing">
      <div className="briefing-header">
        <div className="briefing-title-group">
          <BookOpen size={18} color="var(--color-dispatch-yellow)" />
          <h2 className="briefing-title">MISSION BRIEFING // OPERATING SYSTEM DOCTRINE</h2>
        </div>
        <Button 
          variant="primary" 
          size="sm" 
          onClick={() => setActiveView('command-deck')}
        >
          <Terminal size={14} style={{ marginRight: 6 }} />
          ENTER COMMAND DECK
        </Button>
      </div>

      <div className="briefing-content">
        <section className="briefing-hero-panel">
          <h1 className="briefing-hero-headline">
            TINGLE EMERGENCY INTELLIGENCE CONSOLE
          </h1>
          <p className="briefing-hero-lead">
            An operator decision-support platform engineered to transform chaotic multi-channel crisis reports into explainable, continuously prioritized incidents. Designed for situational commanders operating under extreme cognitive load.
          </p>

          <div className="pipeline-diagram">
            <span className="pipeline-node">CHAOS</span>
            <span className="pipeline-arrow">→</span>
            <span className="pipeline-node">SIGNAL</span>
            <span className="pipeline-arrow">→</span>
            <span className="pipeline-node">INCIDENT</span>
            <span className="pipeline-arrow">→</span>
            <span className="pipeline-node active-accent">PRIORITY</span>
            <span className="pipeline-arrow">→</span>
            <span className="pipeline-node">ACTION</span>
          </div>

          <Button 
            variant="warning" 
            size="md" 
            onClick={() => setActiveView('command-deck')}
          >
            LAUNCH COMMAND DECK
          </Button>
        </section>

        <section className="briefing-pillars-grid">
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
