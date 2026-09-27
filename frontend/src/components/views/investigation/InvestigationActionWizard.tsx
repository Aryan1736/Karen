import React, { useState, useId, useMemo } from 'react';
import { 
  ShieldCheck, 
  Zap, 
  ArrowRight, 
  ArrowLeft, 
  Check, 
  X, 
  AlertTriangle, 
  CheckCircle2, 
  RotateCcw,
  User,
  Users,
  MapPin,
  Flame,
  FileText,
  Sliders
} from 'lucide-react';
import { Button, Badge, TacticalInput } from '../../ui';
import { 
  Incident, 
  IncidentStatus, 
  UrgencyLevel, 
  IncidentType, 
  LocationPrecision 
} from '../../../types/incident';
import { reviewIncident, overrideIncident } from '../../../api/incidents';
import { getOperatorId, ApiRequestError } from '../../../api/client';
import './InvestigationActionWizard.css';

export interface InvestigationActionWizardProps {
  incident: Incident;
  onActionSuccess: () => Promise<void> | void;
  isOnline?: boolean | null;
  defaultAction?: 'STATUS' | 'OVERRIDE';
}

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

const STATUS_OPTIONS: {
  status: IncidentStatus;
  label: string;
  badgeVariant: 'p0-critical' | 'p1-high' | 'p2-medium' | 'p3-low' | 'needs-review' | 'neutral';
  shortDesc: string;
}[] = [
  {
    status: 'VERIFIED',
    label: 'Verify Incident',
    badgeVariant: 'p3-low',
    shortDesc: 'Confirm report accuracy & apply +10 priority boost',
  },
  {
    status: 'ESCALATED',
    label: 'Escalate Threat',
    badgeVariant: 'p1-high',
    shortDesc: 'Flag as severe for immediate tactical dispatch (+15 priority)',
  },
  {
    status: 'NEEDS_REVIEW',
    label: 'Request Corroboration',
    badgeVariant: 'needs-review',
    shortDesc: 'Flag for secondary field verification or missing coordinates',
  },
  {
    status: 'RESOLVED',
    label: 'Mark Resolved',
    badgeVariant: 'neutral',
    shortDesc: 'Hazard mitigated; remove from active response queue',
  },
  {
    status: 'FALSE_REPORT',
    label: 'Dismiss as False Alarm',
    badgeVariant: 'p0-critical',
    shortDesc: 'Dismiss hoax or invalid report (terminal state)',
  },
];

type OverrideField = 
  | 'urgency'
  | 'incident_type'
  | 'people_at_risk_count'
  | 'location'
  | 'required_response'
  | 'priority_score';

const URGENCY_CHOICES: UrgencyLevel[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

const HAZARD_TYPES: { key: IncidentType; label: string }[] = [
  { key: 'FLOOD_FLASH_FLOOD', label: 'Flood / Flash Flood' },
  { key: 'FIRE_WILDFIRE_EXPLOSION', label: 'Fire / Explosion' },
  { key: 'STRUCTURAL_COLLAPSE', label: 'Structural Collapse' },
  { key: 'EARTHQUAKE_LANDSLIDE', label: 'Earthquake / Landslide' },
  { key: 'SEVERE_WEATHER_STORM', label: 'Severe Weather / Storm' },
  { key: 'MEDICAL_EMERGENCY', label: 'Mass Medical Emergency' },
  { key: 'CIVIL_UNREST_ACTIVE_THREAT', label: 'Civil Unrest / Active Threat' },
  { key: 'UTILITY_INFRASTRUCTURE_FAILURE', label: 'Utility Failure' },
  { key: 'OTHER_GENERAL_INCIDENT', label: 'Other General Incident' },
];

const CANONICAL_RESPONSES = [
  { key: 'SEARCH_AND_RESCUE', label: 'Search & Rescue' },
  { key: 'MEDICAL_EMS', label: 'Medical EMS' },
  { key: 'FIRE_HAZMAT', label: 'Fire & Hazmat' },
  { key: 'POLICE_SECURITY', label: 'Police & Security' },
  { key: 'PUBLIC_WORKS_UTILITY', label: 'Public Works' },
];

export const InvestigationActionWizard: React.FC<InvestigationActionWizardProps> = ({
  incident,
  onActionSuccess,
  isOnline = true,
  defaultAction = 'STATUS',
}) => {
  const operatorId = getOperatorId();
  const notesInputId = useId();

  // Wizard state: Step 1 = Select Mode, Step 2 = Enter Details, Step 3 = Review & Submit
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [actionType, setActionType] = useState<'STATUS' | 'OVERRIDE'>(defaultAction);

  // Status transition state
  const [targetStatus, setTargetStatus] = useState<IncidentStatus | ''>('');

  // Field override state
  const [selectedField, setSelectedField] = useState<OverrideField>('urgency');
  const [newUrgency, setNewUrgency] = useState<UrgencyLevel>((incident.urgency as UrgencyLevel) || 'HIGH');
  const [newIncidentType, setNewIncidentType] = useState<IncidentType>((incident.incident_type as IncidentType) || 'STRUCTURAL_COLLAPSE');
  const [newPeopleRisk, setNewPeopleRisk] = useState<string>(
    incident.people_at_risk?.count != null ? String(incident.people_at_risk.count) : '0'
  );
  const [newLocationText, setNewLocationText] = useState<string>(incident.location?.text || '');
  const [newLocationLat, setNewLocationLat] = useState<string>(
    incident.location?.latitude != null ? String(incident.location.latitude) : ''
  );
  const [newLocationLon, setNewLocationLon] = useState<string>(
    incident.location?.longitude != null ? String(incident.location.longitude) : ''
  );
  const [newLocationPrec, setNewLocationPrec] = useState<LocationPrecision>(incident.location?.precision || 'approximate');
  const [newResponses, setNewResponses] = useState<string[]>([...(incident.required_response || [])]);
  const [newPriorityScore, setNewPriorityScore] = useState<string>(
    incident.priority?.score != null ? String(Math.round(incident.priority.score)) : '50'
  );

  // Justification
  const [justification, setJustification] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const allowedTargets = useMemo(() => {
    return ALLOWED_TRANSITIONS[incident.status] || [];
  }, [incident.status]);

  const isTerminal = allowedTargets.length === 0;

  const isReasonValid = justification.trim().length >= 5;

  // Validation for Step 2
  const isStep2Valid = useMemo(() => {
    if (actionType === 'STATUS') {
      return Boolean(targetStatus);
    }
    if (actionType === 'OVERRIDE') {
      if (selectedField === 'urgency') return Boolean(newUrgency);
      if (selectedField === 'incident_type') return Boolean(newIncidentType);
      if (selectedField === 'people_at_risk_count') {
        const p = parseInt(newPeopleRisk, 10);
        return !isNaN(p) && p >= 0;
      }
      if (selectedField === 'location') {
        return Boolean(newLocationText.trim() || (newLocationLat && newLocationLon));
      }
      if (selectedField === 'required_response') return true;
      if (selectedField === 'priority_score') {
        const score = parseFloat(newPriorityScore);
        return !isNaN(score) && score >= 0 && score <= 100;
      }
    }
    return false;
  }, [
    actionType,
    targetStatus,
    selectedField,
    newUrgency,
    newIncidentType,
    newPeopleRisk,
    newLocationText,
    newLocationLat,
    newLocationLon,
    newPriorityScore,
  ]);

  // Compute resolved payload for override
  const resolvedOverridePayload = useMemo(() => {
    if (selectedField === 'urgency') return newUrgency;
    if (selectedField === 'incident_type') return newIncidentType;
    if (selectedField === 'people_at_risk_count') {
      const p = parseInt(newPeopleRisk, 10);
      return isNaN(p) ? 0 : p;
    }
    if (selectedField === 'location') {
      const lat = newLocationLat.trim() ? parseFloat(newLocationLat) : null;
      const lon = newLocationLon.trim() ? parseFloat(newLocationLon) : null;
      return {
        text: newLocationText.trim() || null,
        latitude: lat && !isNaN(lat) ? lat : null,
        longitude: lon && !isNaN(lon) ? lon : null,
        precision: newLocationPrec,
      };
    }
    if (selectedField === 'required_response') return newResponses;
    if (selectedField === 'priority_score') {
      const s = parseFloat(newPriorityScore);
      return isNaN(s) ? 50 : Math.min(100, Math.max(0, s));
    }
    return null;
  }, [
    selectedField,
    newUrgency,
    newIncidentType,
    newPeopleRisk,
    newLocationText,
    newLocationLat,
    newLocationLon,
    newLocationPrec,
    newResponses,
    newPriorityScore,
  ]);

  const handleSubmit = async () => {
    if (!isReasonValid || isSubmitting || !isOnline) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      if (actionType === 'STATUS') {
        if (!targetStatus) return;
        const res = await reviewIncident(incident.incident_id, {
          target_status: targetStatus,
          notes: justification.trim(),
          operator_id: operatorId,
        });
        setSuccessMessage(`Status updated to ${res.incident.status}. Audit entry committed.`);
      } else {
        if (resolvedOverridePayload == null) return;
        await overrideIncident(incident.incident_id, {
          field: selectedField,
          new_value: resolvedOverridePayload,
          reason: justification.trim(),
          operator_id: operatorId,
        });
        setSuccessMessage(`Field "${selectedField}" updated successfully.`);
      }

      await onActionSuccess();
      // Reset state
      setCurrentStep(1);
      setJustification('');
      setTargetStatus('');
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setSubmitError(err.message);
      } else {
        setSubmitError(err instanceof Error ? err.message : 'Action submission failed');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleResponse = (key: string) => {
    setNewResponses((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  return (
    <div className="action-wizard-card">
      {/* Wizard Header */}
      <div className="wizard-header">
        <div className="wizard-title-group">
          <ShieldCheck size={18} className="text-cyan" />
          <h2 className="wizard-title">Operator Incident Actions</h2>
          <span className="wizard-target-pill">Target: #{incident.incident_id.replace(/^inc-/, '').substring(0, 8)}</span>
        </div>
        <div className="wizard-operator-badge">
          <User size={13} />
          <span>Operator: <strong>{operatorId}</strong></span>
        </div>
      </div>

      {/* Stepper Progress */}
      <div className="wizard-stepper">
        <button 
          type="button" 
          className={`step-bubble ${currentStep === 1 ? 'is-active' : currentStep > 1 ? 'is-complete' : ''}`}
          onClick={() => setCurrentStep(1)}
        >
          <span className="step-num">1</span>
          <span className="step-label">Select Action</span>
        </button>
        <div className={`step-connector ${currentStep > 1 ? 'is-active' : ''}`} />
        <button 
          type="button" 
          className={`step-bubble ${currentStep === 2 ? 'is-active' : currentStep > 2 ? 'is-complete' : ''}`}
          onClick={() => currentStep > 1 && setCurrentStep(2)}
          disabled={currentStep < 2}
        >
          <span className="step-num">2</span>
          <span className="step-label">Configure Details</span>
        </button>
        <div className={`step-connector ${currentStep > 2 ? 'is-active' : ''}`} />
        <button 
          type="button" 
          className={`step-bubble ${currentStep === 3 ? 'is-active' : ''}`}
          disabled={!isStep2Valid || currentStep < 3}
          onClick={() => isStep2Valid && setCurrentStep(3)}
        >
          <span className="step-num">3</span>
          <span className="step-label">Review & Apply</span>
        </button>
      </div>

      {/* Success Notification */}
      {successMessage && (
        <div className="wizard-alert alert-success">
          <CheckCircle2 size={16} />
          <div className="alert-content">
            <strong>Update Successful</strong>
            <p>{successMessage}</p>
          </div>
          <button type="button" className="alert-close" onClick={() => setSuccessMessage(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Error Notification */}
      {submitError && (
        <div className="wizard-alert alert-error">
          <AlertTriangle size={16} />
          <div className="alert-content">
            <strong>Action Failed</strong>
            <p>{submitError}</p>
          </div>
          <button type="button" className="alert-close" onClick={() => setSubmitError(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Terminal State Notice */}
      {isTerminal && actionType === 'STATUS' && (
        <div className="wizard-alert alert-locked">
          <AlertTriangle size={16} />
          <div className="alert-content">
            <strong>Status Locked: {incident.status}</strong>
            <p>This incident is in a terminal state. No further status changes can be performed.</p>
          </div>
        </div>
      )}

      {/* STEP 1: Select Action Mode */}
      {currentStep === 1 && (
        <div className="wizard-step-body">
          <div className="step-intro">
            <h3>Step 1: Choose Action Type</h3>
            <p>Select whether you want to update the lifecycle status of this incident or override specific tactical fields.</p>
          </div>

          <div className="action-type-grid">
            <button
              type="button"
              className={`action-card ${actionType === 'STATUS' ? 'is-selected' : ''}`}
              onClick={() => { setActionType('STATUS'); setCurrentStep(2); }}
              disabled={isTerminal}
            >
              <div className="action-card-icon status-icon">
                <ShieldCheck size={24} />
              </div>
              <div className="action-card-info">
                <h4>Update Incident Status</h4>
                <p>Verify report authenticity, escalate priority level, request further corroboration, or close as resolved.</p>
                <span className="action-current-meta">Current Status: <strong>{incident.status}</strong></span>
              </div>
              <ArrowRight size={18} className="action-arrow" />
            </button>

            <button
              type="button"
              className={`action-card ${actionType === 'OVERRIDE' ? 'is-selected' : ''}`}
              onClick={() => { setActionType('OVERRIDE'); setCurrentStep(2); }}
            >
              <div className="action-card-icon override-icon">
                <Zap size={24} />
              </div>
              <div className="action-card-info">
                <h4>Adjust Tactical Field Value</h4>
                <p>Correct urgency tier, hazard category, people at risk count, location coordinates, or recommended response units.</p>
                <span className="action-current-meta">Lock values against automated changes</span>
              </div>
              <ArrowRight size={18} className="action-arrow" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: Configure Details */}
      {currentStep === 2 && (
        <div className="wizard-step-body">
          <div className="step-intro">
            <h3>Step 2: {actionType === 'STATUS' ? 'Select New Status' : 'Configure Field Override'}</h3>
            <p>{actionType === 'STATUS' ? 'Choose the target status transition for this incident.' : 'Select the parameter you wish to update and input the new value.'}</p>
          </div>

          {actionType === 'STATUS' ? (
            <div className="status-selection-list">
              {STATUS_OPTIONS.map((opt) => {
                const isAllowed = allowedTargets.includes(opt.status);
                const isSelected = targetStatus === opt.status;

                return (
                  <button
                    key={opt.status}
                    type="button"
                    disabled={!isAllowed}
                    className={`status-choice-btn ${isSelected ? 'is-selected' : ''} ${!isAllowed ? 'is-disabled' : ''}`}
                    onClick={() => isAllowed && setTargetStatus(opt.status)}
                  >
                    <div className="status-choice-top">
                      <Badge variant={opt.badgeVariant} size="sm">{opt.status}</Badge>
                      <span className="status-choice-title">{opt.label}</span>
                      {isSelected && <Check size={16} className="text-cyan check-icon" />}
                    </div>
                    <span className="status-choice-desc">{opt.shortDesc}</span>
                    {!isAllowed && (
                      <span className="status-not-allowed">Not permitted from {incident.status}</span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="override-configuration-panel">
              {/* Field Tabs */}
              <div className="field-selector-tabs">
                <button
                  type="button"
                  className={`field-tab ${selectedField === 'urgency' ? 'is-active' : ''}`}
                  onClick={() => setSelectedField('urgency')}
                >
                  <Flame size={13} />
                  <span>Urgency</span>
                </button>
                <button
                  type="button"
                  className={`field-tab ${selectedField === 'incident_type' ? 'is-active' : ''}`}
                  onClick={() => setSelectedField('incident_type')}
                >
                  <FileText size={13} />
                  <span>Hazard Type</span>
                </button>
                <button
                  type="button"
                  className={`field-tab ${selectedField === 'people_at_risk_count' ? 'is-active' : ''}`}
                  onClick={() => setSelectedField('people_at_risk_count')}
                >
                  <Users size={13} />
                  <span>Casualties</span>
                </button>
                <button
                  type="button"
                  className={`field-tab ${selectedField === 'location' ? 'is-active' : ''}`}
                  onClick={() => setSelectedField('location')}
                >
                  <MapPin size={13} />
                  <span>Location</span>
                </button>
                <button
                  type="button"
                  className={`field-tab ${selectedField === 'required_response' ? 'is-active' : ''}`}
                  onClick={() => setSelectedField('required_response')}
                >
                  <Sliders size={13} />
                  <span>Protocols</span>
                </button>
                <button
                  type="button"
                  className={`field-tab ${selectedField === 'priority_score' ? 'is-active' : ''}`}
                  onClick={() => setSelectedField('priority_score')}
                >
                  <Zap size={13} />
                  <span>Priority</span>
                </button>
              </div>

              {/* Sub-inputs based on selected field */}
              <div className="field-input-container">
                {selectedField === 'urgency' && (
                  <div className="field-input-row">
                    <label className="field-label">Assigned Urgency Level</label>
                    <div className="urgency-pills-row">
                      {URGENCY_CHOICES.map((u) => (
                        <button
                          key={u}
                          type="button"
                          className={`urgency-pill pill-${u.toLowerCase()} ${newUrgency === u ? 'is-chosen' : ''}`}
                          onClick={() => setNewUrgency(u)}
                        >
                          {u}
                          {newUrgency === u && <Check size={12} />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {selectedField === 'incident_type' && (
                  <div className="field-input-row">
                    <label htmlFor="wizard-hazard-select" className="field-label">Incident Hazard Category</label>
                    <select
                      id="wizard-hazard-select"
                      className="tactical-select font-mono"
                      value={newIncidentType}
                      onChange={(e) => setNewIncidentType(e.target.value as IncidentType)}
                    >
                      {HAZARD_TYPES.map((t) => (
                        <option key={t.key} value={t.key}>{t.label}</option>
                      ))}
                    </select>
                  </div>
                )}

                {selectedField === 'people_at_risk_count' && (
                  <div className="field-input-row">
                    <label htmlFor="wizard-risk-input" className="field-label">Assessed People at Risk (Count)</label>
                    <TacticalInput
                      id="wizard-risk-input"
                      type="number"
                      min="0"
                      value={newPeopleRisk}
                      onChange={(e) => setNewPeopleRisk(e.target.value)}
                      placeholder="e.g. 5"
                      leftIcon={<Users size={16} />}
                    />
                  </div>
                )}

                {selectedField === 'location' && (
                  <div className="field-input-row location-inputs-grid">
                    <div className="loc-col full">
                      <label htmlFor="wizard-loc-text" className="field-label">Location Address / Landmark</label>
                      <TacticalInput
                        id="wizard-loc-text"
                        type="text"
                        value={newLocationText}
                        onChange={(e) => setNewLocationText(e.target.value)}
                        placeholder="e.g. Patia Square, Near KIIT"
                        leftIcon={<MapPin size={16} />}
                      />
                    </div>
                    <div className="loc-col">
                      <label htmlFor="wizard-loc-lat" className="field-label">Latitude</label>
                      <TacticalInput
                        id="wizard-loc-lat"
                        type="number"
                        step="0.0001"
                        value={newLocationLat}
                        onChange={(e) => setNewLocationLat(e.target.value)}
                        placeholder="20.3550"
                      />
                    </div>
                    <div className="loc-col">
                      <label htmlFor="wizard-loc-lon" className="field-label">Longitude</label>
                      <TacticalInput
                        id="wizard-loc-lon"
                        type="number"
                        step="0.0001"
                        value={newLocationLon}
                        onChange={(e) => setNewLocationLon(e.target.value)}
                        placeholder="85.8188"
                      />
                    </div>
                    <div className="loc-col full">
                      <label htmlFor="wizard-loc-prec" className="field-label">Precision</label>
                      <select
                        id="wizard-loc-prec"
                        className="tactical-select font-mono"
                        value={newLocationPrec}
                        onChange={(e) => setNewLocationPrec(e.target.value as LocationPrecision)}
                      >
                        <option value="exact">Exact (GPS Verified)</option>
                        <option value="approximate">Approximate (Neighborhood)</option>
                        <option value="unknown">Unknown / Broad Area</option>
                      </select>
                    </div>
                  </div>
                )}

                {selectedField === 'required_response' && (
                  <div className="field-input-row">
                    <label className="field-label">Required Response Capability</label>
                    <div className="response-checkboxes">
                      {CANONICAL_RESPONSES.map((r) => {
                        const active = newResponses.includes(r.key);
                        return (
                          <button
                            key={r.key}
                            type="button"
                            className={`response-chip-toggle ${active ? 'is-active' : ''}`}
                            onClick={() => toggleResponse(r.key)}
                          >
                            <span className="checkbox-indicator">{active && <Check size={12} />}</span>
                            <span>{r.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {selectedField === 'priority_score' && (
                  <div className="field-input-row">
                    <label htmlFor="wizard-score-input" className="field-label">Priority Score (0 - 100)</label>
                    <TacticalInput
                      id="wizard-score-input"
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      value={newPriorityScore}
                      onChange={(e) => setNewPriorityScore(e.target.value)}
                      placeholder="e.g. 75"
                      leftIcon={<Zap size={16} />}
                    />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step 2 Footer Navigation */}
          <div className="wizard-step-footer">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setCurrentStep(1)}
            >
              <ArrowLeft size={13} style={{ marginRight: 5 }} />
              Back
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={!isStep2Valid}
              onClick={() => setCurrentStep(3)}
            >
              Next: Review & Apply
              <ArrowRight size={13} style={{ marginLeft: 5 }} />
            </Button>
          </div>
        </div>
      )}

      {/* STEP 3: Justification, Review & Confirmation */}
      {currentStep === 3 && (
        <div className="wizard-step-body">
          <div className="step-intro">
            <h3>Step 3: Verification & Justification</h3>
            <p>Review the requested mutation and provide a mandatory operator justification note.</p>
          </div>

          {/* Change Summary Card */}
          <div className="change-summary-card">
            <div className="summary-row">
              <span className="summary-label">Action:</span>
              <span className="summary-value font-bold">
                {actionType === 'STATUS' ? 'Status Transition' : `Field Override (${selectedField})`}
              </span>
            </div>
            <div className="summary-row">
              <span className="summary-label">Target:</span>
              <span className="summary-value font-mono text-cyan">{incident.incident_id}</span>
            </div>
            <div className="summary-row">
              <span className="summary-label">Transition:</span>
              <span className="summary-value transition-flow">
                {actionType === 'STATUS' ? (
                  <>
                    <span className="badge-old">{incident.status}</span>
                    <ArrowRight size={13} className="text-muted" />
                    <Badge variant={STATUS_OPTIONS.find(s => s.status === targetStatus)?.badgeVariant || 'p2-medium'} size="sm">
                      {targetStatus}
                    </Badge>
                  </>
                ) : (
                  <>
                    <span className="text-muted">Override field with:</span>
                    <strong className="text-cyan">
                      {typeof resolvedOverridePayload === 'object' ? JSON.stringify(resolvedOverridePayload) : String(resolvedOverridePayload)}
                    </strong>
                  </>
                )}
              </span>
            </div>
            <div className="summary-row">
              <span className="summary-label">Operator:</span>
              <span className="summary-value font-mono">{operatorId}</span>
            </div>
          </div>

          {/* Justification Textarea */}
          <div className="justification-box">
            <div className="justification-header">
              <label htmlFor={notesInputId} className="field-label">
                Mandatory Operator Justification Notes
              </label>
              <span className={`char-count ${isReasonValid ? 'valid' : 'invalid'}`}>
                {justification.trim().length} / 5 chars min
              </span>
            </div>
            <textarea
              id={notesInputId}
              rows={3}
              className="wizard-textarea font-body"
              placeholder="e.g. Eyewitness report verified via municipal CCTV and responder dispatch..."
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              disabled={isSubmitting}
            />
            <span className="wizard-helper-text">
              This note will be permanently recorded in the immutable audit history.
            </span>
          </div>

          {/* Step 3 Footer Navigation */}
          <div className="wizard-step-footer">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setCurrentStep(2)}
              disabled={isSubmitting}
            >
              <ArrowLeft size={13} style={{ marginRight: 5 }} />
              Back
            </Button>
            <Button
              type="button"
              variant="hazard"
              size="md"
              disabled={!isReasonValid || isSubmitting || !isOnline}
              onClick={handleSubmit}
            >
              {isSubmitting ? (
                <>
                  <RotateCcw size={14} className="spinning" style={{ marginRight: 6 }} />
                  Applying Mutation...
                </>
              ) : (
                <>
                  <Check size={14} style={{ marginRight: 6 }} />
                  Confirm & Apply Change
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default InvestigationActionWizard;
