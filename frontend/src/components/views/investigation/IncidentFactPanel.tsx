import React from 'react';
import { 
  Users, 
  MapPin, 
  FileText,
  Sliders,
  Cpu
} from 'lucide-react';
import { Badge } from '../../ui';
import { Incident } from '../../../types/incident';
import './IncidentFactPanel.css';

export interface IncidentFactPanelProps {
  incident: Incident;
}

export const IncidentFactPanel: React.FC<IncidentFactPanelProps> = ({ incident }) => {
  const isCritical = incident.priority?.level === 'CRITICAL';
  const isHigh = incident.priority?.level === 'HIGH';
  const isReview = incident.status === 'NEEDS_REVIEW';

  let priorityBadgeVariant: 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low' | 'needs-review' = 'p2-medium';
  if (isReview) priorityBadgeVariant = 'needs-review';
  else if (isCritical) priorityBadgeVariant = 'p0-critical';
  else if (isHigh) priorityBadgeVariant = 'p1-high';
  else if (incident.priority?.level === 'LOW') priorityBadgeVariant = 'p3-low';

  // Format honest values (placeholder '--')
  const incidentTypeStr = incident.incident_type ? incident.incident_type.replace(/_/g, ' ') : '--';
  const urgencyStr = incident.urgency || '--';
  const peopleRiskCount = incident.people_at_risk?.count != null ? incident.people_at_risk.count : '--';
  
  const locationText = incident.location?.text || '--';
  const coordinatesStr = (incident.location?.latitude != null && incident.location?.longitude != null)
    ? `${incident.location.latitude.toFixed(4)}° N, ${incident.location.longitude.toFixed(4)}° W`
    : '--';
  const locationPrecision = incident.location?.precision || 'unknown';

  const priorityScore = incident.priority?.score != null ? Math.round(incident.priority.score) : '--';
  const priorityExplanation = incident.priority?.explanation || '--';
  const priorityFactors = incident.priority?.factors || [];

  const corroborationScore = incident.corroboration?.score != null 
    ? `${Math.round(incident.corroboration.score * 100)}%` 
    : '--';
  const corroborationReports = incident.corroboration?.report_count ?? incident.source_report_ids?.length ?? '--';
  const corroborationSources = incident.corroboration?.independent_source_count ?? '--';
  const corroborationExplanation = incident.corroboration?.explanation || '--';

  const overallConfidence = incident.ml_confidence?.overall != null 
    ? `${(incident.ml_confidence.overall * 100).toFixed(1)}%` 
    : '--';
  const confidenceComponents = incident.ml_confidence?.components 
    ? Object.entries(incident.ml_confidence.components) 
    : [];

  const createdAtFormatted = incident.created_at 
    ? new Date(incident.created_at).toUTCString().replace('GMT', 'UTC')
    : '--';
  const updatedAtFormatted = incident.updated_at 
    ? new Date(incident.updated_at).toUTCString().replace('GMT', 'UTC')
    : '--';

  return (
    <section className="inv-fact-panel" aria-label="Incident Summary and Telemetry Dossier">
      {/* SECTION 1: Core Fact Grid */}
      <div className="fact-card fact-card-core">
        <div className="fact-card-header">
          <div className="fact-header-title">
            <FileText size={16} className="fact-header-icon" />
            <span>INCIDENT DOSSIER FACTS</span>
          </div>
          <Badge variant={priorityBadgeVariant} size="sm">
            {incident.status}
          </Badge>
        </div>

        <div className="fact-data-grid">
          <div className="fact-cell">
            <span className="fact-label">INCIDENT IDENTIFIER</span>
            <span className="fact-value font-mono highlight-cyan">{incident.incident_id}</span>
          </div>

          <div className="fact-cell">
            <span className="fact-label">INCIDENT TYPE</span>
            <span className="fact-value uppercase">{incidentTypeStr}</span>
          </div>

          <div className="fact-cell">
            <span className="fact-label">URGENCY LEVEL</span>
            <span className="fact-value">
              {incident.urgency ? (
                <span className={`urgency-tag urgency-${incident.urgency.toLowerCase()}`}>
                  {urgencyStr}
                </span>
              ) : '--'}
            </span>
          </div>

          <div className="fact-cell">
            <span className="fact-label">PEOPLE AT RISK</span>
            <div className="fact-value-with-icon">
              <Users size={14} className="fact-subicon" />
              <span className="fact-value font-mono">
                {peopleRiskCount} {peopleRiskCount !== '--' && peopleRiskCount !== 1 ? 'INDIVIDUALS' : peopleRiskCount === 1 ? 'INDIVIDUAL' : ''}
              </span>
            </div>
          </div>

          <div className="fact-cell span-2">
            <span className="fact-label">LOCATION REFERENCE</span>
            <div className="fact-value-with-icon">
              <MapPin size={14} className="fact-subicon text-hazard" />
              <span className="fact-value">{locationText}</span>
            </div>
            <div className="fact-submeta">
              <span>COORDS: {coordinatesStr}</span>
              <span className="fact-divider">|</span>
              <span>PRECISION: <strong className="uppercase">{locationPrecision}</strong></span>
            </div>
          </div>

          <div className="fact-cell span-2">
            <span className="fact-label">REQUIRED TASKFORCE RESPONSE</span>
            <div className="fact-response-tags">
              {incident.required_response && incident.required_response.length > 0 ? (
                incident.required_response.map((resp, idx) => (
                  <span key={idx} className="response-chip">
                    {resp.replace(/_/g, ' ')}
                  </span>
                ))
              ) : (
                <span className="fact-empty-val">None specified (--)</span>
              )}
            </div>
            <div className="protocol-disclaimer">
              * Recommended response protocols only — no autonomous units deployed without sovereign authorization.
            </div>
          </div>

          <div className="fact-cell">
            <span className="fact-label">FIRST DETECTED (UTC)</span>
            <span className="fact-value font-mono text-sm">{createdAtFormatted}</span>
          </div>

          <div className="fact-cell">
            <span className="fact-label">LAST FUSION SYNC (UTC)</span>
            <span className="fact-value font-mono text-sm">{updatedAtFormatted}</span>
          </div>
        </div>
      </div>

      {/* SECTION 2: Priority Engine Breakdown */}
      <div className="fact-card fact-card-priority">
        <div className="fact-card-header">
          <div className="fact-header-title">
            <Sliders size={16} className="fact-header-icon" />
            <span>EXPLAINABLE PRIORITY ENGINE</span>
          </div>
          <span className="fact-score-badge">
            {priorityScore} / 100 PTS
          </span>
        </div>

        <div className="fact-priority-body">
          <div className="priority-summary-box">
            <div className="priority-level-row">
              <span className="priority-level-label">TACTICAL TIER:</span>
              <span className={`priority-level-tag level-${(incident.priority?.level || 'LOW').toLowerCase()}`}>
                {incident.priority?.level || '--'}
              </span>
            </div>
            <p className="priority-explanation-text">
              {priorityExplanation}
            </p>
          </div>

          <div className="priority-factors-section">
            <span className="factors-title">WEIGHTED PRIORITY FACTORS:</span>
            {priorityFactors.length > 0 ? (
              <div className="factors-table-wrap">
                <table className="factors-table" aria-label="Priority Factor Breakdown">
                  <thead>
                    <tr>
                      <th scope="col">FACTOR</th>
                      <th scope="col">VALUE</th>
                      <th scope="col" className="text-right">WEIGHT</th>
                      <th scope="col" className="text-right">CONTRIBUTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {priorityFactors.map((f, idx) => (
                      <tr key={idx}>
                        <td className="factor-name-cell">{f.factor}</td>
                        <td className="factor-val-cell font-mono">{String(f.value)}</td>
                        <td className="text-right font-mono text-muted">{typeof f.weight === 'number' ? f.weight.toFixed(2) : f.weight}</td>
                        <td className="text-right font-mono text-highlight">
                          +{typeof f.contribution === 'number' ? f.contribution.toFixed(1) : f.contribution}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="factors-empty">
                No factor weights recorded for this incident.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SECTION 3: Signal Triangulation & ML Telemetry */}
      <div className="fact-card fact-card-triangulation">
        <div className="fact-card-header">
          <div className="fact-header-title">
            <Cpu size={16} className="fact-header-icon" />
            <span>SIGNAL CORROBORATION & TELEMETRY</span>
          </div>
          <span className="fact-triangulation-badge font-mono">
            SCORE: {corroborationScore}
          </span>
        </div>

        <div className="fact-triangulation-body">
          <p className="triangulation-explanation">
            {corroborationExplanation}
          </p>

          <div className="triangulation-metrics-grid">
            <div className="tri-metric-box">
              <span className="tri-metric-label">LINKED DISPATCHES</span>
              <span className="tri-metric-num">{corroborationReports}</span>
            </div>
            <div className="tri-metric-box">
              <span className="tri-metric-label">INDEPENDENT SOURCES</span>
              <span className="tri-metric-num">{corroborationSources}</span>
            </div>
            <div className="tri-metric-box">
              <span className="tri-metric-label">ML CONFIDENCE (OVERALL)</span>
              <span className="tri-metric-num highlight-cyan">{overallConfidence}</span>
            </div>
          </div>

          {confidenceComponents.length > 0 && (
            <div className="confidence-components-box">
              <span className="conf-subhead">CONFIDENCE COMPONENTS:</span>
              <div className="conf-components-chips">
                {confidenceComponents.map(([k, v]) => (
                  <div key={k} className="conf-chip font-mono">
                    <span className="conf-k">{k}:</span>
                    <span className="conf-v">{v != null ? `${(Number(v) * 100).toFixed(0)}%` : '--'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
