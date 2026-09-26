import React from 'react';
import { Search, ArrowLeft, ShieldAlert, AlertTriangle, Radio, RotateCcw } from 'lucide-react';
import { Badge, Button } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import { useIncidentDetail } from '../../hooks/useIncidentDetail';
import './InvestigationView.css';

export const InvestigationView: React.FC = () => {
  const { selectedIncidentId, setSelectedIncidentId, setActiveView } = useNavigation();
  const { data, isLoading, error, refetch } = useIncidentDetail(selectedIncidentId);

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

  const incident = data?.incident;
  const reports = data?.source_reports || [];
  const auditTrail = data?.audit_trail || [];

  return (
    <div className="investigation-view" role="region" aria-label="Investigation Evidence Board">
      <div className="investigation-header">
        <div className="investigation-title-group">
          <Search size={18} color="var(--color-multiverse-cyan)" />
          <h2 className="investigation-title">
            INVESTIGATION // EVIDENCE BOARD [{selectedIncidentId}]
          </h2>
          {incident && (
            <Badge variant={incident.priority?.level === 'CRITICAL' ? 'p0-critical' : 'p1-high'} size="sm">
              {incident.status} // {incident.priority?.level} ({Math.round(incident.priority?.score ?? 0)} PTS)
            </Badge>
          )}
        </div>
        <div className="investigation-actions">
          <Button 
            variant="secondary" 
            size="sm" 
            onClick={() => refetch()}
            title="Refresh incident details"
          >
            <RotateCcw size={14} style={{ marginRight: 6 }} />
            REFETCH
          </Button>
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

      {isLoading && (
        <div className="investigation-empty-container">
          <Radio size={36} color="var(--color-multiverse-cyan)" className="rotating" />
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 13, marginTop: 12 }}>
            FETCHING INCIDENT EVIDENCE [{selectedIncidentId}]...
          </p>
        </div>
      )}

      {error && (
        <div className="investigation-empty-container">
          <div className="investigation-empty-card" style={{ borderColor: 'var(--color-hazard-crimson)' }}>
            <AlertTriangle size={36} color="var(--color-hazard-crimson)" />
            <h3 className="investigation-empty-title" style={{ color: 'var(--color-hazard-crimson)', marginTop: 12 }}>
              FETCH FAILURE
            </h3>
            <p className="investigation-empty-text">{error}</p>
            <Button variant="secondary" size="md" onClick={() => refetch()}>
              RETRY FETCH
            </Button>
          </div>
        </div>
      )}

      {!isLoading && !error && incident && (
        <div className="investigation-grid">
          {/* Section 1: Signal Triangulation & Corroboration */}
          <div className="investigation-section-card">
            <div className="section-card-title">
              <span>SIGNAL TRIANGULATION & CORROBORATION</span>
              <Badge variant="neutral" size="sm">
                SCORE: {Math.round((incident.corroboration?.score ?? 0) * 100)}%
              </Badge>
            </div>
            <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-secondary)' }}>
              {incident.corroboration?.explanation || 'Awaiting multi-signal corroboration analysis.'}
            </p>
            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
              <div className="factor-item" style={{ flex: 1 }}>
                <span className="factor-label">LINKED DISPATCHES</span>
                <span className="factor-points">{incident.corroboration?.report_count ?? 1}</span>
              </div>
              <div className="factor-item" style={{ flex: 1 }}>
                <span className="factor-label">DISTINCT SOURCES</span>
                <span className="factor-points">{incident.corroboration?.independent_source_count ?? 1}</span>
              </div>
            </div>
          </div>

          {/* Section 2: Explainable Priority Factors */}
          <div className="investigation-section-card">
            <div className="section-card-title">
              <span>EXPLAINABLE PRIORITY FACTORS</span>
              <Badge variant="p0-critical" size="sm">
                {incident.priority?.score} POINTS
              </Badge>
            </div>
            <p style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--color-text-secondary)' }}>
              {incident.priority?.explanation}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
              {incident.priority?.factors && incident.priority.factors.length > 0 ? (
                incident.priority.factors.map((factor, idx) => (
                  <div key={idx} className="factor-item">
                    <span className="factor-label">{factor.factor}</span>
                    <span className="factor-value">{String(factor.value)}</span>
                    <span className="factor-points">+{factor.contribution.toFixed(1)}</span>
                  </div>
                ))
              ) : (
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-muted)' }}>
                  No factor weights available.
                </div>
              )}
            </div>
          </div>

          {/* Section 3: Linked Raw Citizen Reports */}
          <div className="investigation-section-card" style={{ gridColumn: '1 / -1' }}>
            <div className="section-card-title">
              <span>FUSED CITIZEN DISPATCHES & RAW CALL TIMELINE</span>
              <Badge variant="neutral" size="sm">{reports.length} LINKED</Badge>
            </div>
            {reports.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {reports.map((report) => (
                  <div key={report.report_id} className="source-report-item">
                    <div className="source-report-header">
                      <span>ID: {report.report_id} // SOURCE: {report.source.toUpperCase()}</span>
                      <span>{report.reported_at ? report.reported_at.substring(11, 19) + ' UTC' : ''}</span>
                    </div>
                    <div className="source-report-text">"{report.text}"</div>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)' }}>
                No raw reports recorded for this incident.
              </p>
            )}
          </div>

          {/* Section 4: Human Sovereign Review Ledger */}
          <div className="investigation-section-card" style={{ gridColumn: '1 / -1' }}>
            <div className="section-card-title">
              <span>HUMAN SOVEREIGN REVIEW & AUDIT TRAIL</span>
              <Badge variant={incident.human_override?.active ? 'p0-critical' : 'neutral'} size="sm">
                {incident.human_override?.active ? 'OVERRIDE ACTIVE' : 'NO OVERRIDES'}
              </Badge>
            </div>
            {auditTrail.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {auditTrail.map((audit) => (
                  <div key={audit.override_id} className="audit-entry-item">
                    <span>OP: {audit.operator_id} // FIELD: {audit.field}</span>
                    <span style={{ color: 'var(--color-dispatch-yellow)' }}>"{audit.reason}"</span>
                    <span>{audit.created_at ? audit.created_at.substring(11, 19) + ' UTC' : ''}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text-muted)' }}>
                No human overrides applied to this incident. Sovereign state intact.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default InvestigationView;
