import React from 'react';
import { 
  Users, 
  MapPin, 
  Sliders, 
  Radio,
  Flame,
} from 'lucide-react';
import { Incident } from '../../../types/incident';
import './IncidentFactPanel.css';

export interface IncidentFactPanelProps {
  incident: Incident;
}

export const IncidentFactPanel: React.FC<IncidentFactPanelProps> = ({ incident }) => {
  const isCritical = incident.priority?.level === 'CRITICAL';
  const isHigh = incident.priority?.level === 'HIGH';

  const priorityScore = incident.priority?.score != null ? Math.round(incident.priority.score) : 0;
  const priorityLevel = incident.priority?.level || 'MEDIUM';
  const priorityFactors = incident.priority?.factors || [];

  const locationText = incident.location?.text || 'Location Pending';
  const coordinatesStr = (incident.location?.latitude != null && incident.location?.longitude != null)
    ? `${incident.location.latitude.toFixed(4)}° N, ${incident.location.longitude.toFixed(4)}° E`
    : null;
  const locationPrecision = incident.location?.precision || 'approximate';

  const peopleRiskCount = incident.people_at_risk?.count != null ? incident.people_at_risk.count : null;
  const urgency = incident.urgency || 'MEDIUM';

  const corroborationScore = incident.corroboration?.score != null 
    ? Math.round(incident.corroboration.score * 100) 
    : null;
  const corroborationReports = incident.corroboration?.report_count ?? incident.source_report_ids?.length ?? 0;

  const confidenceComponents = incident.ml_confidence?.components 
    ? Object.entries(incident.ml_confidence.components) 
    : [];

  const createdAtFormatted = incident.created_at 
    ? new Date(incident.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
    : '--';

  const updatedAtFormatted = incident.updated_at 
    ? new Date(incident.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '--';

  return (
    <div className="fact-overview-container">
      {/* 1. Top Key Metric Cards */}
      <div className="fact-metrics-grid">
        {/* Metric 1: Priority */}
        <div className="metric-card metric-priority">
          <div className="metric-header">
            <span className="metric-label">Priority Rating</span>
            <Sliders size={14} className="text-dispatch-yellow" />
          </div>
          <div className="metric-value-row">
            <span className="metric-number">{priorityScore}</span>
            <span className="metric-denom">/ 100</span>
            <span className={`metric-tier-tag tier-${priorityLevel.toLowerCase()}`}>
              {priorityLevel}
            </span>
          </div>
          <div className="metric-progress-track">
            <div 
              className={`metric-progress-bar bar-${priorityLevel.toLowerCase()}`} 
              style={{ width: `${Math.min(100, Math.max(5, priorityScore))}%` }} 
            />
          </div>
        </div>

        {/* Metric 2: Urgency */}
        <div className="metric-card metric-urgency">
          <div className="metric-header">
            <span className="metric-label">Urgency Level</span>
            <Flame size={14} className={isCritical ? 'text-crimson' : 'text-hazard'} />
          </div>
          <div className="metric-value-row">
            <span className={`metric-urgency-val urgency-${urgency.toLowerCase()}`}>
              {urgency}
            </span>
          </div>
          <span className="metric-subtext">
            {isCritical ? 'Immediate life-safety threat' : isHigh ? 'High risk situation' : 'Standard triage urgency'}
          </span>
        </div>

        {/* Metric 3: People at Risk */}
        <div className="metric-card metric-risk">
          <div className="metric-header">
            <span className="metric-label">People at Risk</span>
            <Users size={14} className="text-cyan" />
          </div>
          <div className="metric-value-row">
            <span className="metric-number">
              {peopleRiskCount != null ? peopleRiskCount : '—'}
            </span>
            {peopleRiskCount != null && (
              <span className="metric-unit">{peopleRiskCount === 1 ? 'Person' : 'Individuals'}</span>
            )}
          </div>
          <span className="metric-subtext">
            {peopleRiskCount != null && peopleRiskCount > 0 ? 'Assessed casualties or trapped' : 'No confirmed trapped reported'}
          </span>
        </div>

        {/* Metric 4: Corroboration */}
        <div className="metric-card metric-corroboration">
          <div className="metric-header">
            <span className="metric-label">Source Verification</span>
            <Radio size={14} className="text-cyan" />
          </div>
          <div className="metric-value-row">
            <span className="metric-number">
              {corroborationScore != null ? `${corroborationScore}%` : '—'}
            </span>
            <span className="metric-unit">{corroborationReports} {corroborationReports === 1 ? 'Dispatch' : 'Dispatches'}</span>
          </div>
          <span className="metric-subtext">
            {corroborationReports > 1 ? 'Corroborated by multi-source telemetry' : 'Single eyewitness report'}
          </span>
        </div>
      </div>

      {/* 2. Side-by-Side Detailed Breakdown */}
      <div className="fact-details-grid">
        {/* Incident Summary Card */}
        <div className="detail-card">
          <div className="detail-card-header">
            <MapPin size={15} className="text-cyan" />
            <h3>Incident Location & Response</h3>
          </div>

          <div className="detail-list">
            <div className="detail-item">
              <span className="item-label">Location</span>
              <div className="item-value-wrap">
                <span className="item-value font-bold">{locationText}</span>
                {coordinatesStr && (
                  <span className="item-coords font-mono">{coordinatesStr}</span>
                )}
                <span className="item-precision">Precision: <strong>{locationPrecision}</strong></span>
              </div>
            </div>

            <div className="detail-item">
              <span className="item-label">Required Response</span>
              <div className="response-pills-wrap">
                {incident.required_response && incident.required_response.length > 0 ? (
                  incident.required_response.map((resp, i) => (
                    <span key={i} className="response-pill">
                      {resp.replace(/_/g, ' ')}
                    </span>
                  ))
                ) : (
                  <span className="text-muted">Standard incident response protocols</span>
                )}
              </div>
            </div>

            <div className="detail-item time-row">
              <div>
                <span className="item-label">First Detected</span>
                <span className="item-time font-mono">{createdAtFormatted}</span>
              </div>
              <div>
                <span className="item-label">Last Updated</span>
                <span className="item-time font-mono">{updatedAtFormatted}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Priority Breakdown Card */}
        <div className="detail-card">
          <div className="detail-card-header">
            <Sliders size={15} className="text-dispatch-yellow" />
            <h3>Priority Factor Breakdown</h3>
          </div>

          <div className="factors-list">
            {priorityFactors.length > 0 ? (
              priorityFactors.map((f, idx) => {
                const contribNum = typeof f.contribution === 'number' ? f.contribution : parseFloat(String(f.contribution)) || 0;
                const percent = Math.min(100, Math.max(0, (contribNum / 50) * 100));

                return (
                  <div key={idx} className="factor-row">
                    <div className="factor-info">
                      <span className="factor-name">{f.factor}</span>
                      <span className="factor-val font-mono">{String(f.value)}</span>
                    </div>
                    <div className="factor-bar-wrap">
                      <div className="factor-bar-fill" style={{ width: `${percent}%` }} />
                    </div>
                    <span className="factor-contrib font-mono">
                      +{contribNum.toFixed(1)} pts
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="empty-factors text-muted font-body text-sm">
                Default triage calculation applied.
              </div>
            )}
          </div>

          {/* Model Confidence Chips */}
          {confidenceComponents.length > 0 && (
            <div className="confidence-footer">
              <span className="conf-label">Model Confidence:</span>
              <div className="conf-chips">
                {confidenceComponents.map(([k, v]) => (
                  <span key={k} className="conf-chip font-mono">
                    {k.replace(/_/g, ' ')}: <strong>{v != null ? `${(Number(v) * 100).toFixed(0)}%` : '—'}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default IncidentFactPanel;
