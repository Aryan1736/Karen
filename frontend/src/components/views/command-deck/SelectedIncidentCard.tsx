import React, { useMemo } from 'react';
import { 
  MapPin, 
  Search, 
  Users, 
  Radio, 
  Layers, 
  Clock,
  ShieldCheck
} from 'lucide-react';
import { Badge, Button } from '../../ui';
import { Incident } from '../../../types/incident';
import './SelectedIncidentCard.css';

export interface SelectedIncidentCardProps {
  incident: Incident | null;
  onInvestigate: (incidentId: string) => void;
  className?: string;
}

export const SelectedIncidentCard: React.FC<SelectedIncidentCardProps> = ({
  incident,
  onInvestigate,
  className = '',
}) => {
  // Calculate elapsed time from created_at
  const elapsedTime = useMemo(() => {
    if (!incident?.created_at) return '';
    try {
      const created = new Date(incident.created_at).getTime();
      const now = Date.now();
      const diffSecs = Math.max(0, Math.floor((now - created) / 1000));
      const hours = String(Math.floor(diffSecs / 3600)).padStart(2, '0');
      const mins = String(Math.floor((diffSecs % 3600) / 60)).padStart(2, '0');
      const secs = String(diffSecs % 60).padStart(2, '0');
      return `${hours}:${mins}:${secs} ELAPSED`;
    } catch {
      return '';
    }
  }, [incident?.created_at]);

  if (!incident) {
    return (
      <div className={`selected-incident-card empty-standby ${className}`}>
        <div className="standby-icon-wrap">
          <Radio size={28} color="var(--color-text-muted)" />
        </div>
        <div className="standby-title">NO ACTIVE INCIDENT SELECTED</div>
        <div className="standby-desc">
          Select an incident from the priority queue or tactical map to inspect multi-signal correlation, corroboration metrics, and taskforce response recommendations.
        </div>
      </div>
    );
  }

  const isReview = incident.status === 'NEEDS_REVIEW';
  let badgeVariant: 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low' | 'needs-review' = 'p2-medium';
  if (isReview) badgeVariant = 'needs-review';
  else if (incident.priority?.level === 'CRITICAL') badgeVariant = 'p0-critical';
  else if (incident.priority?.level === 'HIGH') badgeVariant = 'p1-high';
  else if (incident.priority?.level === 'LOW') badgeVariant = 'p3-low';

  const precisionTag = incident.location?.precision === 'exact' 
    ? 'EXACT GPS' 
    : incident.location?.precision === 'approximate' 
      ? 'APPROXIMATE' 
      : 'NO GPS LOCKED';

  const hasCoords = incident.location?.latitude != null && incident.location?.longitude != null;

  return (
    <section className={`selected-incident-card ${className}`} aria-label="Focused Incident Deep Triage">
      {/* Top Tape Header */}
      <div className="deep-card-tape">
        <div className="tape-left">
          <Badge variant={badgeVariant} size="sm" showBeacon={incident.priority?.level === 'CRITICAL'}>
            {isReview ? 'NEEDS REVIEW' : `${incident.priority?.level || 'PRIORITY'} P${incident.priority?.level === 'CRITICAL' ? '0' : incident.priority?.level === 'HIGH' ? '1' : incident.priority?.level === 'MEDIUM' ? '2' : '3'}`}
          </Badge>
          <span className="tape-id-badge" title={incident.incident_id}>
            {incident.incident_id.length > 14 ? `#${incident.incident_id.substring(4, 12)}` : incident.incident_id}
          </span>
          <span className="tape-score-badge">
            SCORE: {Math.round(incident.priority?.score ?? 0)}
          </span>
        </div>
        {elapsedTime && (
          <div className="tape-time">
            <Clock size={11} style={{ marginRight: 3 }} />
            <span>{elapsedTime}</span>
          </div>
        )}
      </div>

      {/* Incident Headline */}
      <h2 className="deep-card-headline">
        {incident.incident_type ? incident.incident_type.replace(/_/g, ' ') : 'UNCLASSIFIED HAZARD'}
      </h2>

      {/* Location Bar */}
      <div className="deep-card-location">
        <MapPin size={13} color="var(--color-dispatch-yellow)" />
        <span className="location-name">{incident.location?.text || 'Unverified Location'}</span>
        <span className="location-precision-tag">{precisionTag}</span>
        {hasCoords && (
          <span className="location-coords">
            {incident.location.latitude!.toFixed(4)}°, {incident.location.longitude!.toFixed(4)}°
          </span>
        )}
      </div>


      {/* Corroboration & Witness Signal Feeds */}
      <div className="deep-card-corroboration">
        <div className="corrob-header">
          <Layers size={12} color="var(--color-text-muted)" />
          <span>VERIFIED REPORTS: {incident.corroboration?.report_count ?? 1} DISPATCH ({incident.corroboration?.independent_source_count ?? 1} INDEPENDENT)</span>
        </div>
        {incident.corroboration?.explanation && (
          <div className="corrob-note">
            {incident.corroboration.explanation}
          </div>
        )}
        {incident.source_report_ids && incident.source_report_ids.length > 0 && (
          <div className="corrob-source-tags">
            {incident.source_report_ids.map((reportId) => (
              <span key={reportId} className="source-tag-pill">
                SRC #{reportId.substring(0, 10)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Recommended Taskforce Units */}
      <div className="deep-card-taskforce">
        <div className="taskforce-title">RECOMMENDED TASKFORCE:</div>
        <div className="taskforce-tags">
          {incident.required_response && incident.required_response.length > 0 ? (
            incident.required_response.map((unit) => (
              <span key={unit} className="taskforce-unit-badge">
                {unit.replace(/_/g, ' ')}
              </span>
            ))
          ) : (
            <span className="taskforce-unit-unassigned">NO UNITS DESIGNATED</span>
          )}
        </div>
        <div className="taskforce-risk">
          <Users size={12} />
          <span>
            {incident.people_at_risk?.count != null
              ? `ESTIMATED POPULATION AT RISK: ~${incident.people_at_risk.count}`
              : 'POPULATION RISK: UNASSESSED'}
          </span>
        </div>
      </div>

      {/* Tactile Action Trigger Buttons */}
      <div className="deep-card-actions">
        <Button
          variant="primary"
          size="md"
          className="action-btn-investigate"
          onClick={() => onInvestigate(incident.incident_id)}
          title="Open deep evidence board in Investigation View"
        >
          <Search size={14} style={{ marginRight: 6 }} />
          INVESTIGATE EVIDENCE
        </Button>
        <Button
          variant="secondary"
          size="md"
          className="action-btn-review"
          onClick={() => onInvestigate(incident.incident_id)}
          title="Open operator review and sovereign override console in Investigation"
          aria-label={`Open operator review for incident ${incident.incident_id}`}
        >
          <ShieldCheck size={14} style={{ marginRight: 6 }} />
          OPERATOR REVIEW
        </Button>
      </div>
    </section>
  );
};

export default SelectedIncidentCard;
