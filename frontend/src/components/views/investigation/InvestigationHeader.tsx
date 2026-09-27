import React from 'react';
import { 
  ArrowLeft, 
  RotateCcw, 
  MapPin, 
  Radio, 
  Layers, 
  FileText,
  X,
  ShieldCheck,
  Zap
} from 'lucide-react';
import { Badge, Button } from '../../ui';
import { Incident } from '../../../types/incident';
import './InvestigationHeader.css';

export interface InvestigationHeaderProps {
  incident: Incident | null;
  selectedIncidentId: string;
  onBackToDeck: () => void;
  onNavigateToStreams: () => void;
  onNavigateToAudit: () => void;
  onRefetch: () => void;
  onClearSelection: () => void;
  isLoading: boolean;
}

export const InvestigationHeader: React.FC<InvestigationHeaderProps> = ({
  incident,
  selectedIncidentId,
  onBackToDeck,
  onNavigateToStreams,
  onNavigateToAudit,
  onRefetch,
  onClearSelection,
  isLoading,
}) => {
  const isCritical = incident?.priority?.level === 'CRITICAL';
  const isHigh = incident?.priority?.level === 'HIGH';
  const isReview = incident?.status === 'NEEDS_REVIEW';

  let badgeVariant: 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low' | 'needs-review' = 'p2-medium';
  if (isReview) badgeVariant = 'needs-review';
  else if (isCritical) badgeVariant = 'p0-critical';
  else if (isHigh) badgeVariant = 'p1-high';
  else if (incident?.priority?.level === 'LOW') badgeVariant = 'p3-low';

  const locationText = incident?.location?.text || (
    incident?.location?.latitude != null && incident?.location?.longitude != null
      ? `${incident.location.latitude.toFixed(4)}° N, ${incident.location.longitude.toFixed(4)}° W`
      : 'Location Pending'
  );

  const incidentTypeDisplay = incident?.incident_type
    ? incident.incident_type.replace(/_/g, ' ')
    : 'Unclassified';

  const updatedTime = incident?.updated_at
    ? new Date(incident.updated_at).toUTCString().replace('GMT', 'UTC')
    : '--';

  return (
    <header className="inv-header" role="banner" aria-label="Investigation Console Header">
      <div className="inv-header-main">
        <div className="inv-header-identity">
          <div className="inv-header-topline">
            <button 
              type="button" 
              className="inv-back-btn" 
              onClick={onBackToDeck}
              aria-label="Return to Command Deck"
            >
              <ArrowLeft size={14} />
              <span>COMMAND DECK</span>
            </button>
            <span className="inv-header-breadcrumbs">
              <span className="inv-crumb-deck">INCIDENTS</span>
              <span className="inv-crumb-arrow">/</span>
              <span className="inv-crumb-active">{selectedIncidentId}</span>
            </span>
          </div>

          <div className="inv-header-title-row">
            <h1 className="inv-incident-id">{selectedIncidentId}</h1>
            {incident && (
              <Badge variant={badgeVariant} size="md">
                {incident.priority?.level ? `${incident.priority.level} P${incident.priority.level === 'CRITICAL' ? '0' : incident.priority.level === 'HIGH' ? '1' : incident.priority.level === 'MEDIUM' ? '2' : '3'}` : incident.status}
              </Badge>
            )}
            {incident?.priority?.score != null && (
              <span className="inv-priority-score-pill">
                SCORE: {Math.round(incident.priority.score)}
              </span>
            )}
            <span className="inv-type-pill">
              {incidentTypeDisplay}
            </span>
          </div>

          <div className="inv-header-meta-row">
            <div className="inv-meta-item">
              <MapPin size={13} className="inv-meta-icon" />
              <span className="inv-meta-label">Location:</span>
              <span className="inv-meta-val" title={locationText}>{locationText}</span>
              {incident?.location?.precision && (
                <span className="inv-meta-precision">({incident.location.precision})</span>
              )}
            </div>
            <span className="inv-meta-divider">•</span>
            <div className="inv-meta-item">
              <span className="inv-meta-label">Updated:</span>
              <span className="inv-meta-val">{updatedTime}</span>
            </div>
            <span className="inv-meta-divider">•</span>
            <div className="inv-meta-item">
              <Layers size={13} className="inv-meta-icon" />
              <span className="inv-meta-label">Linked Reports:</span>
              <span className="inv-meta-val">{incident?.source_report_ids?.length ?? 0}</span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="inv-header-actions">
          {incident && (
            <>
              <Button
                type="button"
                variant="warning"
                size="sm"
                onClick={() => {
                  const el = document.getElementById('operator-review-panel');
                  el?.scrollIntoView({ behavior: 'smooth' });
                }}
                title="Review incident status"
                aria-label="Review incident status"
              >
                <ShieldCheck size={14} style={{ marginRight: 5 }} />
                REVIEW
              </Button>

              <Button
                type="button"
                variant="hazard"
                size="sm"
                onClick={() => {
                  const el = document.getElementById('incident-override-panel');
                  el?.scrollIntoView({ behavior: 'smooth' });
                }}
                title="Override incident field"
                aria-label="Override incident field"
              >
                <Zap size={14} style={{ marginRight: 5 }} />
                OVERRIDE
              </Button>
            </>
          )}

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onRefetch}
            disabled={isLoading}
            title="Refresh incident data"
            aria-label="Refresh incident data"
          >
            <RotateCcw size={13} className={isLoading ? 'spinning' : ''} style={{ marginRight: 5 }} />
            REFRESH
          </Button>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onNavigateToStreams}
            title="Inspect all incident streams"
            aria-label="Navigate to incident streams"
          >
            <Radio size={13} style={{ marginRight: 5 }} />
            STREAMS
          </Button>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onNavigateToAudit}
            title="Inspect system audit trail"
            aria-label="Navigate to audit trail"
          >
            <FileText size={13} style={{ marginRight: 5 }} />
            AUDIT
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClearSelection}
            title="Deselect this incident"
            aria-label="Clear selected incident"
          >
            <X size={14} style={{ marginRight: 4 }} />
            CLEAR
          </Button>
        </div>
      </div>
    </header>
  );
};

export default InvestigationHeader;
