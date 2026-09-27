import React, { useMemo } from 'react';
import { 
  FileText, 
  ShieldCheck, 
  ShieldAlert, 
  ArrowRight, 
  RotateCcw, 
  Clock, 
  User, 
  Radio, 
  AlertTriangle 
} from 'lucide-react';
import { Badge, Button } from '../ui';
import { useIncidents } from '../../hooks/useIncidents';
import { useNavigation } from '../../context/NavigationContext';
import './AuditTrailView.css';

export const AuditTrailView: React.FC = () => {
  const { incidents, isLoading, error, refetch } = useIncidents('ALL');
  const { navigateToIncident, setActiveView } = useNavigation();

  // Find all incidents with active human sovereign overrides
  const overriddenIncidents = useMemo(() => {
    return incidents.filter((inc) => inc.human_override?.active);
  }, [incidents]);

  return (
    <div className="audit-trail-view" role="region" aria-label="Human Sovereign Review and Audit Trail">
      {/* Header */}
      <div className="audit-header">
        <div className="audit-title-group">
          <ShieldCheck size={18} color="var(--color-system-green)" />
          <h1 className="audit-title">OPERATOR OVERRIDE & AUDIT LEDGER</h1>
          <Badge variant={overriddenIncidents.length > 0 ? 'p0-critical' : 'p2-medium'} size="sm">
            {overriddenIncidents.length} ACTIVE {overriddenIncidents.length === 1 ? 'OVERRIDE' : 'OVERRIDES'}
          </Badge>
        </div>
        <div className="audit-status">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
            title="Refresh incident audit ledger"
            aria-label="Refresh audit ledger"
          >
            <RotateCcw size={13} className={isLoading ? 'spinning' : ''} style={{ marginRight: 4 }} />
            REFRESH
          </Button>
        </div>
      </div>

      <div className="audit-body">
        {/* Loading State */}
        {isLoading && incidents.length === 0 && (
          <div className="audit-loading-container">
            <Radio size={36} color="var(--color-multiverse-cyan)" className="rotating" />
            <span className="audit-loading-text font-mono">
              SCANNING INCIDENT AUDIT LEDGER...
            </span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="audit-error-card" role="alert">
            <AlertTriangle size={36} color="var(--color-p0-critical)" />
            <h2 className="audit-error-title font-headline">AUDIT QUERY ERROR</h2>
            <p className="audit-error-desc font-body">{error}</p>
            <Button variant="primary" size="sm" onClick={() => refetch()}>
              <RotateCcw size={13} style={{ marginRight: 4 }} />
              RETRY QUERY
            </Button>
          </div>
        )}

        {/* Populated Overridden Incidents Ledger */}
        {!isLoading && !error && overriddenIncidents.length > 0 && (
          <div className="audit-ledger-container">
            <div className="audit-ledger-banner">
              <ShieldAlert size={16} color="var(--color-p0-critical)" />
              <span className="font-mono text-xs">
                SHOWING {overriddenIncidents.length} INCIDENT{overriddenIncidents.length > 1 ? 'S' : ''} WITH ACTIVE OPERATOR OVERRIDES • IMMUTABLE AUDIT LOG
              </span>
            </div>

            <div className="audit-ledger-cards">
              {overriddenIncidents.map((incident) => {
                const override = incident.human_override;
                const timeFormatted = override?.updated_at
                  ? new Date(override.updated_at).toUTCString().replace('GMT', 'UTC')
                  : '--';

                return (
                  <article key={incident.incident_id} className="audit-ledger-card">
                    <div className="audit-card-top">
                      <div className="audit-card-identity">
                        <span className="audit-incident-id font-headline">{incident.incident_id}</span>
                        <Badge variant="p0-critical" size="sm">OVERRIDE ACTIVE</Badge>
                        <Badge variant="neutral" size="sm">STATUS: {incident.status}</Badge>
                        {incident.priority?.level && (
                          <Badge variant={incident.priority.level === 'CRITICAL' ? 'p0-critical' : 'p1-high'} size="sm">
                            {incident.priority.level} ({Math.round(incident.priority.score)} PTS)
                          </Badge>
                        )}
                      </div>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => navigateToIncident(incident.incident_id)}
                        title={`Inspect full evidence and audit trail for ${incident.incident_id}`}
                        aria-label={`Inspect evidence and audit trail for incident ${incident.incident_id}`}
                      >
                        <span>INSPECT TRACE</span>
                        <ArrowRight size={13} style={{ marginLeft: 4 }} />
                      </Button>
                    </div>

                    <div className="audit-card-meta font-mono">
                      <div className="audit-meta-entry">
                        <User size={12} className="text-muted" />
                        <span className="text-muted">OPERATOR:</span>
                        <strong className="text-cyan">{override?.updated_by || 'UNKNOWN'}</strong>
                      </div>
                      <span className="meta-sep">|</span>
                      <div className="audit-meta-entry">
                        <Clock size={12} className="text-muted" />
                        <span className="text-muted">MUTATED AT:</span>
                        <span>{timeFormatted}</span>
                      </div>
                    </div>

                    <div className="audit-card-reason">
                      <span className="audit-reason-tag font-mono">JUSTIFICATION:</span>
                      <p className="audit-reason-text font-body">
                        "{override?.reason || 'No justification recorded'}"
                      </p>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty Standby State (0 Active Overrides) */}
        {!isLoading && !error && overriddenIncidents.length === 0 && (
          <div className="audit-empty-card">
            <div className="audit-empty-icon">
              <FileText size={48} color="var(--color-multiverse-cyan)" />
            </div>
            <h2 className="audit-empty-title">Audit Ledger Primed</h2>
            <p className="audit-empty-desc">
              All {incidents.length} active emergency incident records in the system are currently governed by autonomous algorithmic consensus. When an operator exercises sovereign authority to adjust status, urgency, location, or response needs, records will be catalogued in this immutable ledger.
            </p>
            <div className="audit-meta-pills">
              <Badge variant="neutral" size="sm">SOVEREIGN_AUTHORITY: ENFORCED</Badge>
              <Badge variant="neutral" size="sm">AUDIT_LOG_SCHEMA: CANONICAL</Badge>
              <Badge variant="neutral" size="sm">TAMPER_PROOF: ACTIVE</Badge>
            </div>
            <div className="audit-empty-actions">
              <Button
                variant="secondary"
                size="md"
                onClick={() => setActiveView('command-deck')}
                aria-label="Return to Command Deck"
              >
                RETURN TO COMMAND DECK
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditTrailView;
