import React, { useMemo } from 'react';
import { 
  RotateCcw, 
  AlertTriangle, 
  Radio, 
  MapPin, 
  Users, 
  FileText,
  ShieldAlert
} from 'lucide-react';
import { Badge, Button } from '../../ui';
import { Incident } from '../../../types/incident';
import { SelectedIncidentCard } from './SelectedIncidentCard';
import './IncidentQueueRail.css';

export interface IncidentQueueRailProps {
  incidents: Incident[];
  selectedIncident: Incident | null;
  selectedIncidentId: string | null;
  onSelectIncident: (incidentId: string) => void;
  onInvestigateIncident: (incidentId: string) => void;
  searchQuery: string;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  criticalCount: number;
  className?: string;
}

export const IncidentQueueRail: React.FC<IncidentQueueRailProps> = ({
  incidents,
  selectedIncident,
  selectedIncidentId,
  onSelectIncident,
  onInvestigateIncident,
  searchQuery,
  isLoading,
  error,
  onRetry,
  criticalCount,
  className = '',
}) => {
  // Filter incidents matching search query
  const filteredIncidents = useMemo(() => {
    if (!searchQuery.trim()) return incidents;
    const q = searchQuery.toLowerCase().trim();
    return incidents.filter((inc) => {
      const idMatch = inc.incident_id.toLowerCase().includes(q);
      const typeMatch = (inc.incident_type || '').toLowerCase().includes(q);
      const locMatch = (inc.location?.text || '').toLowerCase().includes(q);
      const statusMatch = (inc.status || '').toLowerCase().includes(q);
      return idMatch || typeMatch || locMatch || statusMatch;
    });
  }, [incidents, searchQuery]);

  // Other remaining incidents in queue (excluding the currently focused one to avoid repetition)
  const remainingIncidents = useMemo(() => {
    if (!selectedIncidentId) return filteredIncidents;
    return filteredIncidents.filter((inc) => inc.incident_id !== selectedIncidentId);
  }, [filteredIncidents, selectedIncidentId]);

  const getPriorityBadgeVariant = (incident: Incident): 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low' | 'needs-review' => {
    if (incident.status === 'NEEDS_REVIEW') return 'needs-review';
    switch (incident.priority?.level) {
      case 'CRITICAL': return 'p0-critical';
      case 'HIGH': return 'p1-high';
      case 'MEDIUM': return 'p2-medium';
      case 'LOW': return 'p3-low';
      default: return 'p2-medium';
    }
  };

  return (
    <aside className={`incident-queue-rail ${className}`} aria-label="Incident Triage Cockpit and Priority Rail">
      {/* Dock Header */}
      <div className="rail-dock-header">
        <div className="rail-header-title-group">
          <span className="rail-dock-title">TRIAGE COCKPIT</span>
          <span className="rail-urgent-pill">{criticalCount} CRITICAL</span>
        </div>
        <div className="rail-header-controls">
          <span className="rail-sort-note">SORT: PRIORITY DESC</span>
          <button
            type="button"
            className="rail-refresh-btn"
            onClick={onRetry}
            title="Refresh Incident Queue"
            aria-label="Refresh Incident Queue"
          >
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* Selected Incident Deep-Card (Focused Item) */}
      <SelectedIncidentCard 
        incident={selectedIncident} 
        onInvestigate={onInvestigateIncident}
      />

      {/* Incident Queue Stream Section */}
      <div className="rail-queue-stream-section">
        <div className="queue-stream-header">
          <span className="stream-header-title">
            ACTIVE QUEUE STREAM ({remainingIncidents.length} REMAINING)
          </span>
          <span className="stream-refresh-tag">LIVE WS SYNC</span>
        </div>

        {/* Loading State */}
        {isLoading && incidents.length === 0 && (
          <div className="rail-state-box">
            <Radio size={28} color="var(--color-multiverse-cyan)" className="rotating" />
            <span className="rail-state-text">SYNCING OPERATIONAL QUEUE...</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="rail-error-box">
            <AlertTriangle size={20} color="var(--color-p0-critical)" />
            <div className="rail-error-title">DATA STREAM ERROR</div>
            <div className="rail-error-msg">{error}</div>
            <Button variant="secondary" size="sm" onClick={onRetry}>
              RETRY CONNECTION
            </Button>
          </div>
        )}

        {/* Empty Standby State */}
        {!isLoading && !error && incidents.length === 0 && (
          <div className="rail-empty-box">
            <ShieldAlert size={32} color="var(--color-text-muted)" />
            <div className="rail-empty-title">AWAITING LIVE DISPATCHES</div>
            <div className="rail-empty-desc">
              Tingle kinetic triage engine primed. Incoming emergency dispatches and multi-signal correlations will queue here automatically.
            </div>
          </div>
        )}

        {/* Remaining Incident Cards List */}
        {!isLoading && !error && remainingIncidents.length > 0 && (
          <div className="rail-cards-list">
            {remainingIncidents.map((incident) => {
              const isSelected = selectedIncidentId === incident.incident_id;
              const isReview = incident.status === 'NEEDS_REVIEW';
              const badgeVariant = getPriorityBadgeVariant(incident);

              return (
                <div
                  key={incident.incident_id}
                  className={`rail-incident-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => onSelectIncident(incident.incident_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectIncident(incident.incident_id);
                    }
                  }}
                  aria-label={`Select incident ${incident.incident_id}`}
                >
                  <div className="item-tape-row">
                    <div className="item-prio-group">
                      <Badge variant={badgeVariant} size="sm">
                        {isReview ? 'NEEDS REVIEW' : `${incident.priority?.level || 'PRIO'} P${incident.priority?.level === 'CRITICAL' ? '0' : incident.priority?.level === 'HIGH' ? '1' : incident.priority?.level === 'MEDIUM' ? '2' : '3'}`}
                      </Badge>
                      <span className="item-id-text">{incident.incident_id}</span>
                    </div>
                    <span className="item-score-text">
                      PTS: {Math.round(incident.priority?.score ?? 0)}
                    </span>
                  </div>

                  <div className="item-title-text">
                    {incident.incident_type ? incident.incident_type.replace(/_/g, ' ') : 'UNCLASSIFIED HAZARD'}
                  </div>

                  <div className="item-location-row">
                    <MapPin size={11} color="var(--color-multiverse-cyan)" />
                    <span className="item-location-name">
                      {incident.location?.text || 'Unverified Location'}
                    </span>
                  </div>

                  <div className="item-footer-row">
                    <div className="item-metrics">
                      <span className="metric-pill">
                        <Users size={10} />
                        {incident.people_at_risk?.count ?? 0} RISK
                      </span>
                      <span className="metric-pill">
                        <FileText size={10} />
                        {incident.corroboration?.report_count ?? 1} REPS
                      </span>
                    </div>
                    <span className="item-status-tag">
                      {incident.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
};

export default IncidentQueueRail;
