import React, { useState, useId, useMemo } from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  User, 
  RotateCcw,
  Check,
  X,
  ShieldCheck
} from 'lucide-react';
import { Button, Badge } from '../../ui';
import { Incident, IncidentStatus, AuditLog } from '../../../types/incident';
import { reviewIncident } from '../../../api/incidents';
import { getOperatorId, ApiRequestError } from '../../../api/client';
import './OperatorReviewPanel.css';

export interface OperatorReviewPanelProps {
  incident: Incident;
  onReviewSuccess: (updatedIncident: Incident, auditLog: AuditLog) => void;
  isOnline?: boolean | null;
}

// Canonical backend transitions from ALLOWED_TRANSITIONS in backend/app/services/incident_service.py
const ALLOWED_TRANSITIONS: Record<string, IncidentStatus[]> = {
  ACTIVE: ['VERIFIED', 'ESCALATED', 'NEEDS_REVIEW', 'RESOLVED', 'FALSE_REPORT'],
  NEEDS_REVIEW: ['ACTIVE', 'VERIFIED', 'ESCALATED', 'RESOLVED', 'FALSE_REPORT'],
  VERIFIED: ['ACTIVE', 'ESCALATED', 'RESOLVED', 'FALSE_REPORT'],
  ESCALATED: ['ACTIVE', 'VERIFIED', 'RESOLVED'],
  RESOLVED: ['ACTIVE', 'NEEDS_REVIEW'],
  FALSE_REPORT: [],
  NEW: [],
  ANALYZING: [],
};

interface StatusOptionMeta {
  status: IncidentStatus;
  badgeVariant: 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low' | 'needs-review' | 'neutral';
  description: string;
  implication: string;
}

const STATUS_METADATA: Record<IncidentStatus, StatusOptionMeta> = {
  VERIFIED: {
    status: 'VERIFIED',
    badgeVariant: 'p3-low',
    description: 'Corroborated Telemetry & Eyewitness Truth',
    implication: 'Calculates +10 priority modifier. Affirms incident authenticity in active dispatch.',
  },
  ESCALATED: {
    status: 'ESCALATED',
    badgeVariant: 'p1-high',
    description: 'Elevated Threat / Command Escalation',
    implication: 'Calculates +15 priority modifier. Flags urgent operator attention for tactical units.',
  },
  NEEDS_REVIEW: {
    status: 'NEEDS_REVIEW',
    badgeVariant: 'needs-review',
    description: 'Flagged for Human Corroboration',
    implication: 'Keeps standard priority calculation. Flags missing coordinates or low signal confidence.',
  },
  RESOLVED: {
    status: 'RESOLVED',
    badgeVariant: 'neutral',
    description: 'Threat Mitigated & Closed',
    implication: 'Forces priority score to 0.00 (LOW) and clears incident from active triage queues.',
  },
  FALSE_REPORT: {
    status: 'FALSE_REPORT',
    badgeVariant: 'p0-critical',
    description: 'Classified False Alarm / Hoax',
    implication: 'Forces priority score to 0.00 and permanently removes from active triage. Terminal state.',
  },
  ACTIVE: {
    status: 'ACTIVE',
    badgeVariant: 'p2-medium',
    description: 'Operational Active Triage',
    implication: 'Reopens incident to standard deterministic priority triage.',
  },
  NEW: {
    status: 'NEW',
    badgeVariant: 'neutral',
    description: 'Pipeline Ingestion State',
    implication: 'Internal ingestion state (not an operator transition target).',
  },
  ANALYZING: {
    status: 'ANALYZING',
    badgeVariant: 'neutral',
    description: 'ML Extraction State',
    implication: 'Internal pipeline state (not an operator transition target).',
  },
};

export const OperatorReviewPanel: React.FC<OperatorReviewPanelProps> = ({
  incident,
  onReviewSuccess,
  isOnline = true,
}) => {
  const notesInputId = useId();
  const operatorId = getOperatorId();

  const [targetStatus, setTargetStatus] = useState<IncidentStatus | ''>('');
  const [notes, setNotes] = useState<string>('');
  const [showConfirmation, setShowConfirmation] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<{ message: string; details?: unknown } | null>(null);
  const [lastSuccessAudit, setLastSuccessAudit] = useState<AuditLog | null>(null);

  // Determine allowed transition options for the incident's current status
  const currentStatus = incident.status;
  const allowedTargets = useMemo(() => {
    return ALLOWED_TRANSITIONS[currentStatus] || [];
  }, [currentStatus]);

  const isTerminal = allowedTargets.length === 0;

  const notesTrimmed = notes.trim();
  const isNotesValid = notesTrimmed.length >= 5;
  const canPreview = Boolean(targetStatus) && isNotesValid && !isSubmitting && isOnline;

  const handleStartReview = () => {
    if (!canPreview) return;
    setSubmitError(null);
    setShowConfirmation(true);
  };

  const handleCancelConfirmation = () => {
    if (isSubmitting) return;
    setShowConfirmation(false);
  };

  const handleExecuteReview = async () => {
    if (!targetStatus || !isNotesValid || isSubmitting) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const result = await reviewIncident(incident.incident_id, {
        target_status: targetStatus,
        notes: notesTrimmed,
        operator_id: operatorId,
      });

      setLastSuccessAudit(result.audit);
      setShowConfirmation(false);
      setTargetStatus('');
      setNotes('');
      onReviewSuccess(result.incident, result.audit);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setSubmitError({
          message: err.message,
          details: err.details,
        });
      } else {
        setSubmitError({
          message: err instanceof Error ? err.message : 'Unknown error during review submission',
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetSuccess = () => {
    setLastSuccessAudit(null);
    setSubmitError(null);
  };

  return (
    <section 
      id="operator-review-panel"
      className="operator-review-panel"
      aria-label="Operator Status Review Console"
    >
      {/* Panel Tactical Header */}
      <div className="op-panel-header">
        <div className="op-header-title-wrap">
          <ShieldCheck size={18} className="text-cyan op-header-icon" />
          <h2 className="op-header-title font-headline">OPERATOR STATUS REVIEW</h2>
          <span className="op-incident-target font-mono">
            TARGET: <strong className="text-cyan">{incident.incident_id}</strong>
          </span>
        </div>
        <div className="op-header-meta font-mono">
          <User size={13} className="text-muted" />
          <span className="op-meta-operator">
            OPERATOR: <strong className="text-newsprint">{operatorId}</strong>
          </span>
        </div>
      </div>

      <div className="op-panel-body">
        {/* Terminal state banner */}
        {isTerminal && (
          <div className="op-notice-box op-notice-terminal" role="status">
            <AlertTriangle size={18} className="text-hazard" />
            <div className="op-notice-text">
              <span className="font-headline text-hazard">
                STATUS LOCKED [{currentStatus}]
              </span>
              <p className="font-body text-sm text-secondary mt-1">
                {currentStatus === 'FALSE_REPORT'
                  ? 'This incident was classified as FALSE_REPORT. The operational state machine treats this as a terminal state with no subsequent transitions allowed.'
                  : `Incident is in pipeline state '${currentStatus}'. Direct operator status mutation is not permitted.`}
              </p>
            </div>
          </div>
        )}

        {/* Offline Warning */}
        {!isOnline && (
          <div className="op-notice-box op-notice-offline" role="alert">
            <AlertTriangle size={18} className="text-crimson" />
            <div className="op-notice-text">
              <span className="font-headline text-crimson">BACKEND DISCONNECTED</span>
              <p className="font-body text-sm text-secondary mt-1">
                Operator mutation requests require an active connection to the backend API.
              </p>
            </div>
          </div>
        )}

        {/* Success Alert Banner */}
        {lastSuccessAudit && (
          <div className="op-notice-box op-notice-success" role="status" aria-live="polite">
            <CheckCircle2 size={20} className="text-green op-notice-icon" />
            <div className="op-notice-text">
              <span className="font-headline text-green">
                STATUS TRANSITION COMMITTED TO IMMUTABLE AUDIT LOG
              </span>
              <p className="font-mono text-xs text-secondary mt-1">
                LOG ID: <strong className="text-newsprint">{lastSuccessAudit.override_id}</strong> | TRANSITION: <span className="text-hazard">{String(lastSuccessAudit.previous_value)}</span> → <strong className="text-cyan">{String(lastSuccessAudit.new_value)}</strong>
              </p>
              <p className="font-body text-xs text-muted mt-1">
                Notes: "{lastSuccessAudit.reason}"
              </p>
            </div>
            <button
              type="button"
              className="op-success-dismiss font-mono"
              onClick={handleResetSuccess}
              aria-label="Dismiss status review success notice"
            >
              DISMISS
            </button>
          </div>
        )}

        {/* Error Alert Banner */}
        {submitError && (
          <div className="op-notice-box op-notice-error" role="alert" aria-live="assertive">
            <AlertTriangle size={20} className="text-crimson op-notice-icon" />
            <div className="op-notice-text">
              <span className="font-headline text-crimson">REVIEW MUTATION REJECTED</span>
              <p className="font-mono text-sm text-newsprint mt-1">
                {submitError.message}
              </p>
              {Boolean(submitError.details) && (
                <pre className="op-error-details font-mono text-xs mt-2">
                  {JSON.stringify(submitError.details, null, 2)}
                </pre>
              )}
            </div>
            <button
              type="button"
              className="op-error-dismiss font-mono"
              onClick={() => setSubmitError(null)}
              aria-label="Dismiss error notice"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* FORM VIEW (when not in confirmation step) */}
        {!isTerminal && !showConfirmation && (
          <form 
            className="op-review-form"
            onSubmit={(e) => { e.preventDefault(); handleStartReview(); }}
          >
            {/* Status Transition Selector */}
            <div className="op-form-group">
              <label className="op-form-label font-headline">
                1. SELECT TARGET STATUS TRANSITION
                <span className="op-label-sub font-mono">
                  CURRENT: <strong className="text-newsprint">{currentStatus}</strong>
                </span>
              </label>

              <div 
                className="op-status-options-grid"
                role="radiogroup" 
                aria-label="Target Incident Status Selection"
              >
                {allowedTargets.map((statusKey) => {
                  const meta = STATUS_METADATA[statusKey];
                  const isSelected = targetStatus === statusKey;

                  return (
                    <button
                      key={statusKey}
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      className={`op-status-card ${isSelected ? 'is-selected' : ''}`}
                      onClick={() => setTargetStatus(statusKey)}
                    >
                      <div className="op-status-card-top">
                        <Badge variant={meta.badgeVariant} size="sm">
                          {statusKey}
                        </Badge>
                        <span className="op-status-radio-indicator">
                          {isSelected && <Check size={12} />}
                        </span>
                      </div>
                      <span className="op-status-desc font-headline">
                        {meta.description}
                      </span>
                      <span className="op-status-implication font-body">
                        {meta.implication}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Mandatory Notes */}
            <div className="op-form-group">
              <div className="op-label-row">
                <label htmlFor={notesInputId} className="op-form-label font-headline">
                  2. OPERATOR REVIEW JUSTIFICATION NOTES
                </label>
                <span className={`op-char-counter font-mono ${isNotesValid ? 'is-valid' : 'is-invalid'}`}>
                  {notesTrimmed.length} / 5 CHARS MIN
                </span>
              </div>
              <textarea
                id={notesInputId}
                rows={3}
                className="op-textarea font-body"
                placeholder="Enter mandatory justification for status change (e.g. 'Eyewitness accounts corroborate flooding at 4th Ave and Broadway')..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={isSubmitting}
                required
              />
              <span className="op-input-hint font-body text-xs text-muted">
                Mandatory justification string. Backend enforces minimum 5 non-whitespace characters.
              </span>
            </div>

            {/* Sovereign Disclaimer & Action Bar */}
            <div className="op-action-bar">
              <div className="op-action-disclaimer font-body text-xs text-muted">
                * Sovereign human action: commits state mutation to backend ledger and triggers priority recalculation. Does not dispatch units.
              </div>
              <Button
                type="submit"
                variant="hazard"
                size="md"
                disabled={!canPreview}
                title={!targetStatus ? 'Select a target status' : !isNotesValid ? 'Enter at least 5 characters of review notes' : 'Preview status change'}
              >
                <ArrowRight size={14} style={{ marginRight: 6 }} />
                PREVIEW STATUS CHANGE
              </Button>
            </div>
          </form>
        )}

        {/* DELIBERATE CONFIRMATION STEP */}
        {showConfirmation && targetStatus && (
          <div 
            className="op-confirmation-card"
            role="dialog"
            aria-labelledby="confirm-review-heading"
            aria-modal="true"
            tabIndex={-1}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.stopPropagation();
                handleCancelConfirmation();
              }
            }}
          >
            <div className="op-confirm-header">
              <AlertTriangle size={18} className="text-dispatch-yellow" />
              <h3 id="confirm-review-heading" className="font-headline text-dispatch-yellow">
                CONFIRM OPERATOR STATUS TRANSITION
              </h3>
            </div>

            <div className="op-confirm-details font-mono">
              <div className="op-confirm-row">
                <span className="op-confirm-label">INCIDENT ID:</span>
                <span className="op-confirm-val text-cyan font-bold">{incident.incident_id}</span>
              </div>
              <div className="op-confirm-row">
                <span className="op-confirm-label">TRANSITION:</span>
                <div className="op-confirm-val flex items-center gap-2">
                  <span className="val-badge text-muted">{currentStatus}</span>
                  <ArrowRight size={14} className="text-cyan" />
                  <Badge variant={STATUS_METADATA[targetStatus].badgeVariant} size="sm">
                    {targetStatus}
                  </Badge>
                </div>
              </div>
              <div className="op-confirm-row">
                <span className="op-confirm-label">IMPLICATION:</span>
                <span className="op-confirm-val text-secondary font-body text-sm">
                  {STATUS_METADATA[targetStatus].implication}
                </span>
              </div>
              <div className="op-confirm-row">
                <span className="op-confirm-label">OPERATOR NOTES:</span>
                <span className="op-confirm-val text-newsprint font-body text-sm">
                  "{notesTrimmed}"
                </span>
              </div>
              <div className="op-confirm-row">
                <span className="op-confirm-label">ACTING OPERATOR:</span>
                <span className="op-confirm-val text-newsprint font-bold">{operatorId}</span>
              </div>
            </div>

            <div className="op-confirm-warning font-body text-xs">
              <strong className="text-hazard">MUTATION AUDIT COMMIT:</strong> This action permanently writes an entry to the immutable database audit ledger. Priority recalculation will execute synchronously.
            </div>

            <div className="op-confirm-actions">
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={handleCancelConfirmation}
                disabled={isSubmitting}
              >
                <X size={14} style={{ marginRight: 6 }} />
                CANCEL
              </Button>
              <Button
                type="button"
                variant="primary"
                size="md"
                onClick={handleExecuteReview}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <RotateCcw size={14} className="spinning" style={{ marginRight: 6 }} />
                    COMMITTING STATUS...
                  </>
                ) : (
                  <>
                    <Check size={14} style={{ marginRight: 6 }} />
                    CONFIRM & COMMIT STATUS
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default OperatorReviewPanel;
