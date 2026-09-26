import React from 'react';
import { Search, ArrowLeft, ShieldAlert } from 'lucide-react';
import { Badge, Button } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import './InvestigationView.css';

export const InvestigationView: React.FC = () => {
  const { selectedIncidentId, setSelectedIncidentId, setActiveView } = useNavigation();

  if (!selectedIncidentId) {
    return (
      <div className="investigation-view" role="region" aria-label="Investigation Evidence Board">
        <div className="investigation-header">
          <div className="investigation-title-group">
            <Search size={18} color="var(--color-multiverse-cyan)" />
            <h2 className="investigation-title">INCIDENT INVESTIGATION & EVIDENCE BOARD</h2>
          </div>
          <Button 
            variant="secondary" 
            size="sm" 
            onClick={() => setActiveView('command-deck')}
          >
            <ArrowLeft size={14} style={{ marginRight: 6 }} />
            BACK TO COMMAND DECK
          </Button>
        </div>

        <div className="investigation-empty-container">
          <div className="investigation-empty-card">
            <div className="investigation-empty-icon">
              <ShieldAlert size={48} color="var(--color-hazard-orange)" />
            </div>
            <h3 className="investigation-empty-title">No Incident Selected</h3>
            <p className="investigation-empty-text">
              Select an active incident from the Command Deck queue to examine multi-source signal triangulation, explainable priority factors, and fused dispatch timelines.
            </p>
            <Button 
              variant="primary" 
              size="md" 
              onClick={() => setActiveView('command-deck')}
            >
              OPEN COMMAND DECK QUEUE
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="investigation-view" role="region" aria-label="Investigation Evidence Board">
      <div className="investigation-header">
        <div className="investigation-title-group">
          <Search size={18} color="var(--color-multiverse-cyan)" />
          <h2 className="investigation-title">
            INVESTIGATION // EVIDENCE BOARD [TARGET: {selectedIncidentId}]
          </h2>
          <Badge variant="needs-review" size="sm">ACTIVE TARGET</Badge>
        </div>
        <div className="investigation-actions">
          <Button 
            variant="secondary" 
            size="sm" 
            onClick={() => setSelectedIncidentId(null)}
          >
            CLEAR SELECTION
          </Button>
          <Button 
            variant="secondary" 
            size="sm" 
            onClick={() => setActiveView('command-deck')}
          >
            <ArrowLeft size={14} style={{ marginRight: 6 }} />
            BACK TO DECK
          </Button>
        </div>
      </div>

      <div className="investigation-scaffold-grid">
        <div className="investigation-section-card">
          <h3 className="section-card-title">SIGNAL TRIANGULATION & CORROBORATION GRAPH</h3>
          <div className="section-card-placeholder">
            [SCAFFOLD: Phase 4 will mount multi-source spatiotemporal triangulation vectors and distance decay curves here.]
          </div>
        </div>

        <div className="investigation-section-card">
          <h3 className="section-card-title">EXPLAINABLE PRIORITY FACTOR BREAKDOWN</h3>
          <div className="section-card-placeholder">
            [SCAFFOLD: Phase 4 will mount deterministic priority formula weights, urgency tiers, and life-safety contribution bars here.]
          </div>
        </div>

        <div className="investigation-section-card" style={{ gridColumn: '1 / -1' }}>
          <h3 className="section-card-title">FUSED CITIZEN DISPATCHES & RAW CALL TIMELINE</h3>
          <div className="section-card-placeholder">
            [SCAFFOLD: Phase 4 will mount chronological citizen reports, duplicate tags, and corroborating witness records here.]
          </div>
        </div>
      </div>
    </div>
  );
};

export default InvestigationView;
