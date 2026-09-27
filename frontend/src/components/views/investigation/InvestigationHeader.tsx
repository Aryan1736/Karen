import React from 'react';
import { 
  ArrowLeft, 
  RotateCcw, 
  MapPin, 
  Layers, 
  Clock,
  ShieldCheck
} from 'lucide-react';
import { Badge, Button } from '../../ui';
import { Incident } from '../../../types/incident';
import './InvestigationHeader.css';

export interface InvestigationHeaderProps {
  incident: Incident | null;
  selectedIncidentId: string;
  onBackToDeck: () => void;
  onNavigateToStreams?: () => void;
  onNavigateToAudit?: () => void;
  onClearSelection?: () => void;
  onRefetch: () => void;
  onTakeAction?: () => void;
  isLoading: boolean;
}

export const InvestigationHeader: React.FC<InvestigationHeaderProps> = ({
  incident,
  selectedIncidentId,
  onBackToDeck,
  onRefetch,
  onTakeAction,
  isLoading,
}) => {
  const isCritical = incident?.priority?.level === 'CRITICAL';
  const isHigh = incident?.priority?.level === 'HIGH';
  const isReview = incident?.status === 'NEEDS_REVIEW';

  let badgeVariant: 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low' | 'needs-review' | 'neutral' = 'p2-medium';
  if (isReview) badgeVariant = 'needs-review';
  else if (isCritical) badgeVariant = 'p0-critical';
  else if (isHigh) badgeVariant = 'p1-high';
  else if (incident?.priority?.level === 'LOW') badgeVariant = 'p3-low';

  const locationText = incident?.location?.text || (
    incident?.location?.latitude != null && incident?.location?.longitude != null
      ? `${incident.location.latitude.toFixed(4)}° N, ${incident.location.longitude.toFixed(4)}° E`
      : 'Location Pending'
  );

  const incidentTypeDisplay = incident?.incident_type
    ? incident.incident_type.replace(/_/g, ' ')
    : 'Emergency Incident';

  const shortId = selectedIncidentId.length > 14
    ? `#${selectedIncidentId.replace(/^inc-/, '').substring(0, 8)}`
    : selectedIncidentId;

  const updatedTime = incident?.updated_at
    ? new Date(incident.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '--';

  return (
    <header className="inv-header" role="banner" aria-label="Investigation Console Header">
      <div className="inv-header-main">
        <div className="inv-header-identity">
          {/* Breadcrumb Navigation */}
          <div className="inv-header-topline">
            <button 
              type="button" 
              className="inv-back-btn" 
              onClick={onBackToDeck}
              aria-label="Return to Command Deck"
            >
              <ArrowLeft size={13} />
              <span>Back to Incidents</span>
            </button>
            <span className="inv-header-breadcrumbs">
              <span className="inv-crumb-sep">/</span>
              <span className="inv-crumb-id">{shortId}</span>
            </span>
          </div>

          {/* Title Row */}
          <div className="inv-header-title-row">
            <h1 className="inv-incident-title">
              {incident?.location?.text ? `${incidentTypeDisplay} · ${incident.location.text}` : incidentTypeDisplay}
            </h1>
            {incident && (
              <Badge variant={badgeVariant} size="md">
                {incident.status}
              </Badge>
            )}
            {incident?.priority?.score != null && (
              <span className="inv-priority-score-pill">
                Priority {Math.round(incident.priority.score)}/100
              </span>
            )}
            {incident?.urgency && (
              <span className={`inv-urgency-pill urgency-${incident.urgency.toLowerCase()}`}>
                {incident.urgency}
              </span>
            )}
          </div>

          {/* Meta Row */}
          <div className="inv-header-meta-row">
            <div className="inv-meta-item">
              <MapPin size={12} className="inv-meta-icon text-cyan" />
              <span className="inv-meta-val">{locationText}</span>
              {incident?.location?.precision && (
                <span className="inv-meta-precision">({incident.location.precision})</span>
              )}
            </div>
            <span className="inv-meta-divider">•</span>
            <div className="inv-meta-item">
              <Clock size={12} className="inv-meta-icon text-muted" />
              <span className="inv-meta-val">Updated {updatedTime}</span>
            </div>
            <span className="inv-meta-divider">•</span>
            <div className="inv-meta-item">
              <Layers size={12} className="inv-meta-icon text-muted" />
              <span className="inv-meta-val">{incident?.source_report_ids?.length ?? 0} Linked Reports</span>
            </div>
          </div>
        </div>

        {/* Action Controls - Cleaned up and focused */}
        <div className="inv-header-actions">
          {onTakeAction && (
            <Button
              type="button"
              variant="hazard"
              size="sm"
              onClick={onTakeAction}
              title="Review status or override parameters"
              aria-label="Take operator action"
            >
              <ShieldCheck size={14} style={{ marginRight: 6 }} />
              Take Action
            </Button>
          )}

          <button
            type="button"
            className="inv-refresh-btn"
            onClick={onRefetch}
            disabled={isLoading}
            title="Refresh incident data"
            aria-label="Refresh incident data"
          >
            <RotateCcw size={13} className={isLoading ? 'spinning' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default InvestigationHeader;
