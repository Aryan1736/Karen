import React from 'react';
import { 
  Radio, 
  MapPin, 
  Layers,
  Activity
} from 'lucide-react';
import { Badge } from '../ui';
import { useNavigation, IncidentPriorityFilter } from '../../context/NavigationContext';
import './CommandDeckView.css';

interface FilterOption {
  id: IncidentPriorityFilter;
  label: string;
}

const FILTER_OPTIONS: FilterOption[] = [
  { id: 'ALL', label: 'ALL' },
  { id: 'CRITICAL', label: 'P0 CRITICAL' },
  { id: 'HIGH', label: 'P1 HIGH' },
  { id: 'MEDIUM', label: 'P2 MED' },
  { id: 'NEEDS_REVIEW', label: 'NEEDS REVIEW' },
];

export const CommandDeckView: React.FC = () => {
  const { activeFilter, setActiveFilter } = useNavigation();

  return (
    <div className="command-deck-view" role="region" aria-label="Tactical Command Deck">
      {/* Triage Filter / Quick Search Bar */}
      <div className="triage-filter-bar">
        <div className="filter-chip-group">
          {FILTER_OPTIONS.map((filter) => {
            const isActive = activeFilter === filter.id;
            return (
              <button
                key={filter.id}
                type="button"
                className={`filter-chip-btn ${isActive ? 'active' : ''}`}
                onClick={() => setActiveFilter(filter.id)}
              >
                <span>{filter.label}</span>
                <span className="filter-chip-count">0</span>
              </button>
            );
          })}
        </div>
        <div className="deck-status-readout">
          <span>WORKSPACE: DUAL-PANE SPLIT [QUEUE // TACTICAL MAP]</span>
        </div>
      </div>

      {/* Main Workspace Split */}
      <main className="workspace-split">
        {/* Left Pane: Incident Queue Container */}
        <section className="queue-panel" aria-label="Incident Queue">
          <div className="panel-header">
            <div className="panel-title-group">
              <span className="panel-title">Prioritized Incident Queue</span>
              <Badge variant="neutral" size="sm">0 QUEUED</Badge>
            </div>
            <div className="panel-controls">
              <Layers size={14} color="var(--color-text-muted)" />
            </div>
          </div>

          <div className="panel-body-placeholder">
            <div className="placeholder-icon">
              <Radio size={40} color="var(--color-multiverse-cyan)" />
            </div>
            <div className="placeholder-title">Awaiting Live Dispatches</div>
            <div className="placeholder-desc">
              Tingle kinetic triage engine initialized. Incoming emergency signals, multi-report fusion, and deterministic priority scoring will stream here.
            </div>
            <div className="placeholder-tags">
              <Badge variant="p0-critical" size="sm">P0 CRITICAL</Badge>
              <Badge variant="p1-high" size="sm">P1 HIGH</Badge>
              <Badge variant="p2-medium" size="sm">P2 MED</Badge>
              <Badge variant="p3-low" size="sm">P3 LOW</Badge>
              <Badge variant="needs-review" size="sm">NEEDS REVIEW</Badge>
            </div>
          </div>
        </section>

        {/* Right Pane: Tactical Geographic Map Container */}
        <section className="map-panel" aria-label="Tactical Map">
          <div className="map-overlay-badge">
            <MapPin size={14} color="var(--color-multiverse-cyan)" />
            <span>TACTICAL GEOGRAPHIC MAP — LEAFLET / OSM ENGINE</span>
          </div>

          <div className="map-view-area">
            <div className="placeholder-icon">
              <Activity size={44} color="var(--color-text-muted)" />
            </div>
            <div className="placeholder-title">Cartographic Grid Primed</div>
            <div className="placeholder-desc">
              Validated hazard coordinates and corroboration vectors will be plotted with 0px neo-brutalist pins without coordinate hallucination.
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

export default CommandDeckView;
