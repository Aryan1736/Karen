import React from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  Clock, 
  Lock
} from 'lucide-react';
import { Badge } from '../../ui';
import { AuditLog, HumanOverrideBlock } from '../../../types/incident';
import './AuditTracePanel.css';

export interface AuditTracePanelProps {
  auditTrail: AuditLog[];
  humanOverride?: HumanOverrideBlock;
}

export const AuditTracePanel: React.FC<AuditTracePanelProps> = ({
  auditTrail,
  humanOverride,
}) => {
  const isOverrideActive = Boolean(humanOverride?.active);

  return (
    <section className="inv-audit-panel" aria-label="Sovereign Human Review and Audit Trail">
      {/* Audit Panel Header */}
      <div className="audit-header">
        <div className="audit-title-group">
          <ShieldCheck size={16} className="audit-title-icon" />
          <h2 className="audit-title">AUDIT TRAIL & TRACEABILITY</h2>
          <Badge variant={isOverrideActive ? 'p0-critical' : 'neutral'} size="sm">
            {isOverrideActive ? 'OVERRIDE ACTIVE' : 'NO OVERRIDES'}
          </Badge>
        </div>
        <span className="audit-compliance-tag font-mono">
          IMMUTABLE LEDGER
        </span>
      </div>

      <div className="audit-content-body">
        {/* Sovereign State Status Card */}
        <div className={`audit-state-card ${isOverrideActive ? 'state-active' : 'state-intact'}`}>
          <div className="audit-state-icon-wrap">
            {isOverrideActive ? (
              <ShieldAlert size={20} className="text-crimson" />
            ) : (
              <ShieldCheck size={20} className="text-green" />
            )}
          </div>
          <div className="audit-state-text">
            <span className="audit-state-title font-headline">
              {isOverrideActive
                ? 'HUMAN SOVEREIGN OVERRIDE REGISTERED'
                : 'AUTONOMOUS SYSTEM CONSENSUS INTACT'}
            </span>
            <p className="audit-state-desc font-body">
              {isOverrideActive ? (
                <>
                  Override executed by Operator{' '}
                  <strong className="font-mono text-cyan">{humanOverride?.updated_by || 'UNKNOWN'}</strong>
                  {humanOverride?.updated_at && (
                    <> at <span className="font-mono">{new Date(humanOverride.updated_at).toUTCString().replace('GMT', 'UTC')}</span></>
                  )}
                  {humanOverride?.reason && (
                    <span className="block mt-1 font-body text-secondary">
                      Reason: "{humanOverride.reason}"
                    </span>
                  )}
                </>
              ) : (
                'No human operator overrides have mutated this incident. All values reflect deterministic model predictions and validated pipeline correlations.'
              )}
            </p>
          </div>
        </div>

        {/* Audit Trail Records Table */}
        <div className="audit-records-section">
          <div className="audit-records-head font-mono">
            <span>CHAIN OF CUSTODY LOGS ({auditTrail.length})</span>
          </div>

          {auditTrail.length === 0 ? (
            <div className="audit-empty-card font-mono">
              <Clock size={16} className="text-muted" />
              <span>No audit logs recorded for this incident.</span>
            </div>
          ) : (
            <div className="audit-table-wrap">
              <table className="audit-table font-mono" aria-label="Incident Audit Records">
                <thead>
                  <tr>
                    <th scope="col">OPERATOR</th>
                    <th scope="col">FIELD</th>
                    <th scope="col">VALUE TRANSITION</th>
                    <th scope="col">JUSTIFICATION REASON</th>
                    <th scope="col" className="text-right">TIMESTAMP (UTC)</th>
                  </tr>
                </thead>
                <tbody>
                  {auditTrail.map((log) => {
                    const timeFormatted = log.created_at
                      ? new Date(log.created_at).toUTCString().replace('GMT', 'UTC')
                      : '--';

                    const prevValStr = log.previous_value != null ? String(log.previous_value) : '--';
                    const newValStr = log.new_value != null ? String(log.new_value) : '--';

                    return (
                      <tr key={log.override_id}>
                        <td className="log-op-cell font-bold">{log.operator_id}</td>
                        <td className="log-field-cell text-cyan">{log.field}</td>
                        <td className="log-transition-cell">
                          <span className="val-prev">{prevValStr}</span>
                          <span className="val-arrow">→</span>
                          <span className="val-new">{newValStr}</span>
                        </td>
                        <td className="log-reason-cell">
                          "{log.reason}"
                        </td>
                        <td className="log-time-cell text-right text-muted">{timeFormatted}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Phase 7 Deferred Boundary Notice */}
        <div className="audit-deferred-notice" role="region" aria-label="Phase 7 Scope Boundary">
          <div className="deferred-notice-head">
            <Lock size={14} className="text-dispatch-yellow" />
            <span className="font-headline text-dispatch-yellow text-sm uppercase">
              OPERATOR REVIEW & OVERRIDE MUTATIONS [PHASE 7 BOUNDARY]
            </span>
          </div>
          <p className="deferred-notice-text font-body">
            This workspace provides read-only traceability and observability. Interactive status review transitions (Verify, Escalate, Resolve, Flag False Alarm) and field overrides are strictly scoped to <strong>Phase 7 (Human Sovereign Review Console)</strong> and are not executable in Phase 6.
          </p>
        </div>
      </div>
    </section>
  );
};
