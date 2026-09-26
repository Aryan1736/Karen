import React from 'react';
import { 
  Radio, 
  MapPin, 
  Layers,
  Activity,
  AlertTriangle,
  RotateCcw,
  Users,
  FileText
} from 'lucide-react';
import { Badge, Button } from '../ui';
import { useNavigation, IncidentPriorityFilter } from '../../context/NavigationContext';
import { useIncidents } from '../../hooks/useIncidents';
import { Incident } from '../../types/incident';
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
  const { activeFilter, setActiveFilter, selectedIncidentId, navigateToIncident } = useNavigation();
  const { incidents, totalCount, criticalCount, isLoading, error, refetch } = useIncidents(activeFilter);

  const getPriorityBadgeVariant = (incident: Incident) => {
    if (incident.status === 'NEEDS_REVIEW') return 'needs-review';
    switch (incident.priority?.level) {
      case 'CRITICAL': return 'p0-critical';
      case 'HIGH': return 'p1-high';
      case 'MEDIUM': return 'p2-medium';
      case 'LOW': return 'p3-low';
      default: return 'neutral';
    }
  };

  return (
    <div className="command-deck-view" role="region" aria-label="Tactical Command Deck">
      {/* Triage Filter / Quick Search Bar */}
      <div className="triage-filter-bar">
        <div className="filter-chip-group">
          {FILTER_OPTIONS.map((filter) => {
            const isActive = activeFilter === filter.id;
            let count = 0;
            if (filter.id === 'ALL') count = totalCount;
            else if (filter.id === 'CRITICAL') count = criticalCount;
            else if (filter.id === 'HIGH') count = incidents.filter(i => i.priority?.level === 'HIGH').length;
            else if (filter.id === 'MEDIUM') count = incidents.filter(i => i.priority?.level === 'MEDIUM').length;
            else if (filter.id === 'NEEDS_REVIEW') count = incidents.filter(i => i.status === 'NEEDS_REVIEW').length;

            return (
              <button
                key={filter.id}
                type="button"
                className={`filter-chip-btn ${isActive ? 'active' : ''}`}
                onClick={() => setActiveFilter(filter.id)}
              >
                <span>{filter.label}</span>
                <span className="filter-chip-count">{count}</span>
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
              <Badge variant="neutral" size="sm">{totalCount} QUEUED</Badge>
            </div>
            <div className="panel-controls" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button
                type="button"
                onClick={() => refetch()}
                title="Refresh Incident Queue"
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: 2 }}
              >
                <RotateCcw size={14} color="var(--color-text-muted)" />
              </button>
              <Layers size={14} color="var(--color-text-muted)" />
            </div>
          </div>

          {/* Loading State */}
          {isLoading && incidents.length === 0 && (
            <div className="queue-state-box">
              <Radio size={32} color="var(--color-multiverse-cyan)" className="rotating" />
              <span className="queue-loading-text">SYNCING OPERATIONAL QUEUE...</span>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="queue-error-banner">
              <AlertTriangle size={24} color="var(--color-hazard-crimson)" />
              <div className="queue-error-title">DATA STREAM ERROR</div>
              <div className="queue-error-msg">{error}</div>
              <Button variant="secondary" size="sm" onClick={() => refetch()}>
                RETRY CONNECTION
              </Button>
            </div>
          )}

          {/* Real Incident Cards List */}
          {!isLoading && !error && incidents.length > 0 && (
            <div className="queue-list-container">
              {incidents.map((incident) => {
                const isSelected = selectedIncidentId === incident.incident_id;
                return (
                  <button
                    key={incident.incident_id}
                    type="button"
                    className={`incident-card-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => navigateToIncident(incident.incident_id)}
                  >
                    <div className="incident-card-header">
                      <span className="incident-card-id">{incident.incident_id}</span>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <span className="incident-card-score">
                          SCORE: {Math.round(incident.priority?.score ?? 0)}
                        </span>
                        <Badge variant={getPriorityBadgeVariant(incident)} size="sm">
                          {incident.status === 'NEEDS_REVIEW' ? 'NEEDS REVIEW' : incident.priority?.level}
                        </Badge>
                      </div>
                    </div>

                    <div className="incident-card-type">
                      {incident.incident_type ? incident.incident_type.replace(/_/g, ' ') : 'UNCLASSIFIED HAZARD'}
                    </div>

                    <div className="incident-card-location">
                      <MapPin size={12} color="var(--color-multiverse-cyan)" />
                      <span>{incident.location?.text || 'Unverified Location'}</span>
                    </div>

                    <div className="incident-card-footer">
                      <div className="incident-card-metrics">
                        <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                          <Users size={11} />
                          {incident.people_at_risk?.count ?? 0} AT RISK
                        </span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                          <FileText size={11} />
                          {incident.corroboration?.report_count ?? 1} REPORTS
                        </span>
                      </div>
                      <span>
                        {incident.updated_at ? incident.updated_at.substring(11, 19) + ' UTC' : ''}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* Empty Standby State */}
          {!isLoading && !error && incidents.length === 0 && (
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
          )}
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
