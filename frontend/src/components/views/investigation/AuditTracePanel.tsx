import React from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  Clock,
  User,
  ArrowRight
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
    <div className="audit-panel-container">
      {/* 1. Status Indicator Card */}
      <div className={`audit-status-banner ${isOverrideActive ? 'status-override' : 'status-automated'}`}>
        <div className="status-icon-wrap">
          {isOverrideActive ? (
            <ShieldAlert size={18} className="text-hazard" />
          ) : (
            <ShieldCheck size={18} className="text-green" />
          )}
        </div>
        <div className="status-text-wrap">
          <div className="status-title-row">
            <h4>
              {isOverrideActive ? 'Operator Override Active' : 'Automated Assessment (No Overrides)'}
            </h4>
            <Badge variant={isOverrideActive ? 'p1-high' : 'neutral'} size="sm">
              {isOverrideActive ? 'Overridden' : 'Standard'}
            </Badge>
          </div>
          <p className="status-desc">
            {isOverrideActive ? (
              <>
                Field values manually adjusted by Operator{' '}
                <strong className="font-mono text-cyan">{humanOverride?.updated_by || 'Unknown'}</strong>
                {humanOverride?.updated_at && (
                  <> on {new Date(humanOverride.updated_at).toLocaleDateString()} at {new Date(humanOverride.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</>
                )}
                {humanOverride?.reason && (
                  <span className="override-reason-quote">
                    "{humanOverride.reason}"
                  </span>
                )}
              </>
            ) : (
              'All incident classifications and priority scores are computed automatically from verified dispatches and telemetry.'
            )}
          </p>
        </div>
      </div>

      {/* 2. Audit Trail Records Table */}
      <div className="audit-table-card">
        <div className="audit-table-header">
          <div className="table-title-group">
            <Clock size={14} className="text-muted" />
            <h3>Action & Mutation History</h3>
            <span className="table-count-pill font-mono">{auditTrail.length} {auditTrail.length === 1 ? 'Entry' : 'Entries'}</span>
          </div>
        </div>

        {auditTrail.length === 0 ? (
          <div className="audit-empty-state font-body">
            <span>No operator adjustments or status mutations recorded for this incident.</span>
          </div>
        ) : (
          <div className="audit-table-wrapper">
            <table className="audit-data-table" aria-label="Incident Audit Records">
              <thead>
                <tr>
                  <th scope="col">Operator</th>
                  <th scope="col">Field / Action</th>
                  <th scope="col">Change (From → To)</th>
                  <th scope="col">Justification</th>
                  <th scope="col" className="text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {auditTrail.map((log) => {
                  const timeFormatted = log.created_at
                    ? new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', month: 'short', day: 'numeric' })
                    : '--';

                  const prevVal = log.previous_value != null ? String(log.previous_value) : '—';
                  const newVal = log.new_value != null ? String(log.new_value) : '—';

                  return (
                    <tr key={log.override_id}>
                      <td className="cell-operator font-mono">
                        <User size={11} className="text-muted" style={{ marginRight: 4, display: 'inline' }} />
                        {log.operator_id}
                      </td>
                      <td className="cell-field font-mono text-cyan">
                        {log.field}
                      </td>
                      <td className="cell-transition">
                        <span className="val-prev font-mono">{prevVal}</span>
                        <ArrowRight size={11} className="text-muted inline-arrow" />
                        <span className="val-new font-mono font-bold text-newsprint">{newVal}</span>
                      </td>
                      <td className="cell-reason font-body">
                        "{log.reason}"
                      </td>
                      <td className="cell-time font-mono text-right text-muted">
                        {timeFormatted}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditTracePanel;
