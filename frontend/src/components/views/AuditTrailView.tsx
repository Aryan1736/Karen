import React from 'react';
import { FileText, ShieldCheck } from 'lucide-react';
import { Badge } from '../ui';
import './AuditTrailView.css';

export const AuditTrailView: React.FC = () => {
  return (
    <div className="audit-trail-view" role="region" aria-label="Human Sovereign Review and Audit Trail">
      <div className="audit-header">
        <div className="audit-title-group">
          <ShieldCheck size={18} color="var(--color-system-green)" />
          <h2 className="audit-title">HUMAN SOVEREIGN REVIEW // AUDIT LEDGER</h2>
          <Badge variant="p2-medium" size="sm">CLEARANCE: OP-07 (L5)</Badge>
        </div>
        <div className="audit-status">
          <Badge variant="neutral" size="sm">0 OVERRIDES RECORDED</Badge>
        </div>
      </div>

      <div className="audit-body">
        <div className="audit-empty-card">
          <div className="audit-empty-icon">
            <FileText size={48} color="var(--color-multiverse-cyan)" />
          </div>
          <h3 className="audit-empty-title">Audit Ledger Primed</h3>
          <p className="audit-empty-desc">
            All human operator modifications, urgency adjustments, and triage confirmations will be recorded in an immutable append-only ledger with mandatory operator justification.
          </p>
          <div className="audit-meta-pills">
            <Badge variant="neutral" size="sm">SOVEREIGN_AUTHORITY: ENFORCED</Badge>
            <Badge variant="neutral" size="sm">AUDIT_LOG_SCHEMA: CANONICAL</Badge>
            <Badge variant="neutral" size="sm">TAMPER_PROOF: ACTIVE</Badge>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuditTrailView;
