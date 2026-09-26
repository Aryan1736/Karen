import React, { useState, useId, useMemo } from 'react';
import { 
  Zap, 
  AlertTriangle, 
  ArrowRight, 
  User, 
  RotateCcw,
  Check,
  X,
  Sliders,
  CheckCircle2,
  MapPin,
  Users,
  Flame,
  FileText
} from 'lucide-react';
import { Button, TacticalInput } from '../../ui';
import { Incident, UrgencyLevel, IncidentType, LocationPrecision, AuditLog } from '../../../types/incident';
import { overrideIncident } from '../../../api/incidents';
import { getOperatorId, ApiRequestError } from '../../../api/client';
import './IncidentOverridePanel.css';

export interface IncidentOverridePanelProps {
  incident: Incident;
  onOverrideSuccess: (updatedIncident: Incident, auditLog: AuditLog) => void;
  isOnline?: boolean | null;
}

type OverrideFieldKey = 
  | 'urgency'
  | 'incident_type'
  | 'people_at_risk_count'
  | 'location'
  | 'required_response'
  | 'priority_score';

const URGENCY_OPTIONS: UrgencyLevel[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

const INCIDENT_TYPES: { key: IncidentType; label: string }[] = [
  { key: 'FLOOD_FLASH_FLOOD', label: 'Flood / Flash Flood' },
  { key: 'FIRE_WILDFIRE_EXPLOSION', label: 'Fire / Wildfire / Explosion' },
  { key: 'STRUCTURAL_COLLAPSE', label: 'Structural Collapse' },
  { key: 'EARTHQUAKE_LANDSLIDE', label: 'Earthquake / Landslide' },
  { key: 'SEVERE_WEATHER_STORM', label: 'Severe Weather / Storm' },
  { key: 'MEDICAL_EMERGENCY', label: 'Mass Medical Emergency' },
  { key: 'CIVIL_UNREST_ACTIVE_THREAT', label: 'Civil Unrest / Active Threat' },
  { key: 'UTILITY_INFRASTRUCTURE_FAILURE', label: 'Utility / Infrastructure Failure' },
  { key: 'OTHER_GENERAL_INCIDENT', label: 'Other General Incident' },
];

const CANONICAL_RESPONSES = [
  { key: 'SEARCH_AND_RESCUE', label: 'Search & Rescue' },
  { key: 'MEDICAL_EMS', label: 'Medical EMS' },
  { key: 'FIRE_HAZMAT', label: 'Fire & Hazmat' },
  { key: 'POLICE_SECURITY', label: 'Police & Security' },
  { key: 'PUBLIC_WORKS_UTILITY', label: 'Public Works & Utility' },
];

export const IncidentOverridePanel: React.FC<IncidentOverridePanelProps> = ({
  incident,
  onOverrideSuccess,
  isOnline = true,
}) => {
  const reasonInputId = useId();
  const operatorId = getOperatorId();

  const [selectedField, setSelectedField] = useState<OverrideFieldKey | ''>('');
  const [reason, setReason] = useState<string>('');

  // Per-field input states
  const [newUrgency, setNewUrgency] = useState<UrgencyLevel>('HIGH');
  const [newIncidentType, setNewIncidentType] = useState<IncidentType | ''>('');
  const [newPeopleRisk, setNewPeopleRisk] = useState<string>('');
  const [newLocationText, setNewLocationText] = useState<string>('');
  const [newLocationLat, setNewLocationLat] = useState<string>('');
  const [newLocationLon, setNewLocationLon] = useState<string>('');
  const [newLocationPrec, setNewLocationPrec] = useState<LocationPrecision>('approximate');
  const [newResponses, setNewResponses] = useState<string[]>([]);
  const [newPriorityScore, setNewPriorityScore] = useState<string>('');

  const [showConfirmation, setShowConfirmation] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<{ message: string; details?: unknown } | null>(null);
  const [lastSuccessAudit, setLastSuccessAudit] = useState<AuditLog | null>(null);

  // Initialize field inputs when a field is selected
  const handleSelectField = (fieldKey: OverrideFieldKey) => {
    setSelectedField(fieldKey);
    setSubmitError(null);
    setShowConfirmation(false);

    if (fieldKey === 'urgency') {
      setNewUrgency((incident.urgency as UrgencyLevel) || 'HIGH');
    } else if (fieldKey === 'incident_type') {
      setNewIncidentType((incident.incident_type as IncidentType) || 'FLOOD_FLASH_FLOOD');
    } else if (fieldKey === 'people_at_risk_count') {
      setNewPeopleRisk(incident.people_at_risk?.count != null ? String(incident.people_at_risk.count) : '0');
    } else if (fieldKey === 'location') {
      setNewLocationText(incident.location?.text || '');
      setNewLocationLat(incident.location?.latitude != null ? String(incident.location.latitude) : '');
      setNewLocationLon(incident.location?.longitude != null ? String(incident.location.longitude) : '');
      setNewLocationPrec(incident.location?.precision || 'approximate');
    } else if (fieldKey === 'required_response') {
      setNewResponses([...(incident.required_response || [])]);
    } else if (fieldKey === 'priority_score') {
      setNewPriorityScore(incident.priority?.score != null ? String(incident.priority.score) : '50.0');
    }
  };

  const reasonTrimmed = reason.trim();
  const isReasonValid = reasonTrimmed.length >= 5;

  // Compute resolved new value payload and human-readable string
  const resolvedNewValuePayload = useMemo(() => {
    if (!selectedField) return null;

    if (selectedField === 'urgency') {
      return newUrgency;
    }
    if (selectedField === 'incident_type') {
      return newIncidentType || null;
    }
    if (selectedField === 'people_at_risk_count') {
      const parsed = parseInt(newPeopleRisk, 10);
      return isNaN(parsed) || parsed < 0 ? 0 : parsed;
    }
    if (selectedField === 'location') {
      const latParsed = newLocationLat.trim() !== '' ? parseFloat(newLocationLat) : null;
      const lonParsed = newLocationLon.trim() !== '' ? parseFloat(newLocationLon) : null;
      return {
        text: newLocationText.trim() || null,
        latitude: latParsed != null && !isNaN(latParsed) ? latParsed : null,
        longitude: lonParsed != null && !isNaN(lonParsed) ? lonParsed : null,
        precision: newLocationPrec,
      };
    }
    if (selectedField === 'required_response') {
      return newResponses;
    }
    if (selectedField === 'priority_score') {
      const parsed = parseFloat(newPriorityScore);
      return isNaN(parsed) ? 0.0 : Math.min(100.0, Math.max(0.0, parsed));
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

  // Compute formatted current value
  const formattedCurrentValue = useMemo(() => {
    if (!selectedField) return '--';
    if (selectedField === 'urgency') return incident.urgency || '--';
    if (selectedField === 'incident_type') return incident.incident_type || '--';
    if (selectedField === 'people_at_risk_count') {
      return incident.people_at_risk?.count != null ? `${incident.people_at_risk.count} individuals` : '--';
    }
    if (selectedField === 'location') {
      const parts = [
        incident.location?.text || '--',
        incident.location?.latitude != null && incident.location?.longitude != null
          ? `(${incident.location.latitude.toFixed(4)}, ${incident.location.longitude.toFixed(4)})`
          : null,
        `[${(incident.location?.precision || 'unknown').toUpperCase()}]`,
      ].filter(Boolean);
      return parts.join(' ');
    }
    if (selectedField === 'required_response') {
      return incident.required_response?.length ? incident.required_response.join(', ') : 'NONE';
    }
    if (selectedField === 'priority_score') {
      return incident.priority?.score != null ? `${incident.priority.score.toFixed(1)} pts (${incident.priority.level})` : '--';
    }
    return '--';
  }, [selectedField, incident]);

  // Compute formatted new value
  const formattedNewValue = useMemo(() => {
    if (!selectedField || resolvedNewValuePayload == null) return '--';
    if (selectedField === 'urgency') return String(resolvedNewValuePayload);
    if (selectedField === 'incident_type') return String(resolvedNewValuePayload);
    if (selectedField === 'people_at_risk_count') return `${resolvedNewValuePayload} individuals`;
    if (selectedField === 'location') {
      const loc = resolvedNewValuePayload as { text: string | null; latitude: number | null; longitude: number | null; precision: string };
      const parts = [
        loc.text || '(No text phrasing)',
        loc.latitude != null && loc.longitude != null ? `(${loc.latitude.toFixed(4)}, ${loc.longitude.toFixed(4)})` : '(No coordinates)',
        `[${loc.precision.toUpperCase()}]`,
      ];
      return parts.join(' ');
    }
    if (selectedField === 'required_response') {
      const arr = resolvedNewValuePayload as string[];
      return arr.length ? arr.join(', ') : 'NONE';
    }
    if (selectedField === 'priority_score') {
      return `${resolvedNewValuePayload} pts (Tier derived automatically by backend)`;
    }
    return String(resolvedNewValuePayload);
  }, [selectedField, resolvedNewValuePayload]);

  // Validate value input
  const isValueValid = useMemo(() => {
    if (!selectedField) return false;
    if (selectedField === 'urgency') return Boolean(newUrgency);
    if (selectedField === 'incident_type') return Boolean(newIncidentType);
    if (selectedField === 'people_at_risk_count') {
      const p = parseInt(newPeopleRisk, 10);
      return !isNaN(p) && p >= 0;
    }
    if (selectedField === 'location') {
      const latVal = newLocationLat.trim();
      const lonVal = newLocationLon.trim();
      if (latVal !== '') {
        const lat = parseFloat(latVal);
        if (isNaN(lat) || lat < -90.0 || lat > 90.0) return false;
      }
      if (lonVal !== '') {
        const lon = parseFloat(lonVal);
        if (isNaN(lon) || lon < -180.0 || lon > 180.0) return false;
      }
      return Boolean(newLocationText.trim() || (latVal !== '' && lonVal !== ''));
    }
    if (selectedField === 'required_response') return true; // Can be empty array
    if (selectedField === 'priority_score') {
      const p = parseFloat(newPriorityScore);
      return !isNaN(p) && p >= 0.0 && p <= 100.0;
    }
    return false;
  }, [
    selectedField,
    newUrgency,
    newIncidentType,
    newPeopleRisk,
    newLocationText,
    newLocationLat,
    newLocationLon,
    newPriorityScore,
  ]);

  const canPreview = Boolean(selectedField) && isValueValid && isReasonValid && !isSubmitting && isOnline;

  const handleStartOverride = () => {
    if (!canPreview) return;
    setSubmitError(null);
    setShowConfirmation(true);
  };

  const handleCancelConfirmation = () => {
    if (isSubmitting) return;
    setShowConfirmation(false);
  };

  const handleExecuteOverride = async () => {
    if (!selectedField || resolvedNewValuePayload == null || !isReasonValid || isSubmitting) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const result = await overrideIncident(incident.incident_id, {
        field: selectedField,
        new_value: resolvedNewValuePayload,
        reason: reasonTrimmed,
        operator_id: operatorId,
      });

      setLastSuccessAudit(result.audit);
      setShowConfirmation(false);
      setSelectedField('');
      setReason('');
      onOverrideSuccess(result.incident, result.audit);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setSubmitError({
          message: err.message,
          details: err.details,
        });
      } else {
        setSubmitError({
          message: err instanceof Error ? err.message : 'Unknown error during override submission',
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleResponseCapability = (capKey: string) => {
    setNewResponses((prev) => 
      prev.includes(capKey) ? prev.filter((k) => k !== capKey) : [...prev, capKey]
    );
  };

  return (
    <section 
      id="incident-override-panel"
      className="incident-override-panel"
      aria-label="Incident Field Override Console"
    >
      {/* Panel Header */}
      <div className="override-panel-header">
        <div className="override-header-title-wrap">
          <Zap size={18} className="text-dispatch-yellow override-header-icon" />
          <h2 className="override-header-title font-headline">INCIDENT FIELD OVERRIDE</h2>
          <span className="override-incident-target font-mono">
            TARGET: <strong className="text-cyan">{incident.incident_id}</strong>
          </span>
        </div>
        <div className="override-header-meta font-mono">
          <User size={13} className="text-muted" />
          <span className="override-meta-operator">
            OPERATOR: <strong className="text-newsprint">{operatorId}</strong>
          </span>
        </div>
      </div>

      <div className="override-panel-body">
        {/* Offline Warning */}
        {!isOnline && (
          <div className="op-notice-box op-notice-offline" role="alert">
            <AlertTriangle size={18} className="text-crimson" />
            <div className="op-notice-text">
              <span className="font-headline text-crimson">BACKEND DISCONNECTED</span>
              <p className="font-body text-sm text-secondary mt-1">
                Field override mutations require an active connection to the backend API.
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
                FIELD OVERRIDE REGISTERED & LOCKED AGAINST ML OVERWRITE
              </span>
              <p className="font-mono text-xs text-secondary mt-1">
                OVERRIDE ID: <strong className="text-newsprint">{lastSuccessAudit.override_id}</strong> | FIELD: <strong className="text-cyan">{lastSuccessAudit.field}</strong>
              </p>
              <p className="font-body text-xs text-muted mt-1">
                Reason: "{lastSuccessAudit.reason}"
              </p>
            </div>
            <button
              type="button"
              className="op-success-dismiss font-mono"
              onClick={() => setLastSuccessAudit(null)}
              aria-label="Dismiss field override notice"
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
              <span className="font-headline text-crimson">OVERRIDE MUTATION REJECTED</span>
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
        {!showConfirmation && (
          <form 
            className="override-form"
            onSubmit={(e) => { e.preventDefault(); handleStartOverride(); }}
          >
            {/* 1. Field Selector */}
            <div className="override-form-group">
              <label className="override-form-label font-headline">
                1. SELECT FIELD TO OVERRIDE
              </label>

              <div 
                className="override-fields-grid"
                role="radiogroup" 
                aria-label="Select Incident Field for Override"
              >
                <button
                  type="button"
                  role="radio"
                  aria-checked={selectedField === 'urgency'}
                  className={`override-field-chip ${selectedField === 'urgency' ? 'is-active' : ''}`}
                  onClick={() => handleSelectField('urgency')}
                >
                  <Flame size={14} />
                  <span>URGENCY</span>
                </button>

                <button
                  type="button"
                  role="radio"
                  aria-checked={selectedField === 'incident_type'}
                  className={`override-field-chip ${selectedField === 'incident_type' ? 'is-active' : ''}`}
                  onClick={() => handleSelectField('incident_type')}
                >
                  <FileText size={14} />
                  <span>INCIDENT TYPE</span>
                </button>

                <button
                  type="button"
                  role="radio"
                  aria-checked={selectedField === 'people_at_risk_count'}
                  className={`override-field-chip ${selectedField === 'people_at_risk_count' ? 'is-active' : ''}`}
                  onClick={() => handleSelectField('people_at_risk_count')}
                >
                  <Users size={14} />
                  <span>PEOPLE AT RISK</span>
                </button>

                <button
                  type="button"
                  role="radio"
                  aria-checked={selectedField === 'location'}
                  className={`override-field-chip ${selectedField === 'location' ? 'is-active' : ''}`}
                  onClick={() => handleSelectField('location')}
                >
                  <MapPin size={14} />
                  <span>LOCATION</span>
                </button>

                <button
                  type="button"
                  role="radio"
                  aria-checked={selectedField === 'required_response'}
                  className={`override-field-chip ${selectedField === 'required_response' ? 'is-active' : ''}`}
                  onClick={() => handleSelectField('required_response')}
                >
                  <Sliders size={14} />
                  <span>REQUIRED RESPONSE</span>
                </button>

                <button
                  type="button"
                  role="radio"
                  aria-checked={selectedField === 'priority_score'}
                  className={`override-field-chip ${selectedField === 'priority_score' ? 'is-active' : ''}`}
                  onClick={() => handleSelectField('priority_score')}
                >
                  <Zap size={14} />
                  <span>PRIORITY SCORE</span>
                </button>
              </div>
            </div>

            {/* 2. Specific Field Input Area */}
            {selectedField && (
              <div className="override-value-box">
                <div className="override-value-header font-mono">
                  <span>CURRENT: <strong className="text-newsprint">{formattedCurrentValue}</strong></span>
                </div>

                {/* Case 1: Urgency */}
                {selectedField === 'urgency' && (
                  <div className="override-input-group">
                    <span className="override-input-label font-headline">ASSIGN NEW URGENCY TIER:</span>
                    <div className="override-urgency-choices">
                      {URGENCY_OPTIONS.map((u) => {
                        const isChosen = newUrgency === u;
                        return (
                          <button
                            key={u}
                            type="button"
                            className={`urgency-choice-btn urgency-${u.toLowerCase()} ${isChosen ? 'is-chosen' : ''}`}
                            onClick={() => setNewUrgency(u)}
                          >
                            <span>{u}</span>
                            {isChosen && <Check size={14} />}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Case 2: Incident Type */}
                {selectedField === 'incident_type' && (
                  <div className="override-input-group">
                    <label htmlFor="select-incident-type" className="override-input-label font-headline">
                      ASSIGN NEW INCIDENT HAZARD CATEGORY:
                    </label>
                    <select
                      id="select-incident-type"
                      className="tactical-select font-mono"
                      value={newIncidentType}
                      onChange={(e) => setNewIncidentType(e.target.value as IncidentType)}
                    >
                      {INCIDENT_TYPES.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.label} ({t.key})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Case 3: People at Risk Count */}
                {selectedField === 'people_at_risk_count' && (
                  <div className="override-input-group">
                    <label htmlFor="input-people-risk" className="override-input-label font-headline">
                      ASSESSED INDIVIDUALS AT RISK (CASUALTIES / TRAPPED):
                    </label>
                    <TacticalInput
                      id="input-people-risk"
                      type="number"
                      min="0"
                      step="1"
                      value={newPeopleRisk}
                      onChange={(e) => setNewPeopleRisk(e.target.value)}
                      placeholder="Enter integer >= 0"
                      leftIcon={<Users size={16} />}
                      required
                    />
                  </div>
                )}

                {/* Case 4: Location */}
                {selectedField === 'location' && (
                  <div className="override-location-grid">
                    <div className="override-location-col span-full">
                      <label htmlFor="input-loc-text" className="override-input-label font-headline">
                        PRIMARY LOCATION PHRASING:
                      </label>
                      <TacticalInput
                        id="input-loc-text"
                        type="text"
                        value={newLocationText}
                        onChange={(e) => setNewLocationText(e.target.value)}
                        placeholder="e.g. 104 Main Street, Sector 7"
                        leftIcon={<MapPin size={16} />}
                      />
                    </div>
                    <div className="override-location-col">
                      <label htmlFor="input-loc-lat" className="override-input-label font-headline">
                        LATITUDE (-90.0 TO 90.0):
                      </label>
                      <TacticalInput
                        id="input-loc-lat"
                        type="number"
                        step="0.0001"
                        min="-90"
                        max="90"
                        value={newLocationLat}
                        onChange={(e) => setNewLocationLat(e.target.value)}
                        placeholder="e.g. 37.7749"
                      />
                    </div>
                    <div className="override-location-col">
                      <label htmlFor="input-loc-lon" className="override-input-label font-headline">
                        LONGITUDE (-180.0 TO 180.0):
                      </label>
                      <TacticalInput
                        id="input-loc-lon"
                        type="number"
                        step="0.0001"
                        min="-180"
                        max="180"
                        value={newLocationLon}
                        onChange={(e) => setNewLocationLon(e.target.value)}
                        placeholder="e.g. -122.4194"
                      />
                    </div>
                    <div className="override-location-col span-full">
                      <label htmlFor="select-loc-prec" className="override-input-label font-headline">
                        COORDINATE PRECISION:
                      </label>
                      <select
                        id="select-loc-prec"
                        className="tactical-select font-mono"
                        value={newLocationPrec}
                        onChange={(e) => setNewLocationPrec(e.target.value as LocationPrecision)}
                      >
                        <option value="exact">EXACT (GPS / Verified Cross-street)</option>
                        <option value="approximate">APPROXIMATE (General Neighborhood / Radial)</option>
                        <option value="unknown">UNKNOWN (Unverified / Broad Region)</option>
                      </select>
                    </div>
                  </div>
                )}

                {/* Case 5: Required Response */}
                {selectedField === 'required_response' && (
                  <div className="override-input-group">
                    <span className="override-input-label font-headline">
                      REQUIRED RESPONSE PROTOCOLS:
                    </span>
                    <div className="override-response-toggles">
                      {CANONICAL_RESPONSES.map((cap) => {
                        const isChecked = newResponses.includes(cap.key);
                        return (
                          <button
                            key={cap.key}
                            type="button"
                            className={`response-toggle-chip ${isChecked ? 'is-checked' : ''}`}
                            onClick={() => toggleResponseCapability(cap.key)}
                          >
                            <span className="toggle-box">{isChecked && <Check size={12} />}</span>
                            <span>{cap.label}</span>
                          </button>
                        );
                      })}
                    </div>
                    <p className="font-body text-xs text-muted mt-2">
                      * Informational capability recommendations only. Setting response tags does NOT dispatch emergency units.
                    </p>
                  </div>
                )}

                {/* Case 6: Priority Score */}
                {selectedField === 'priority_score' && (
                  <div className="override-input-group">
                    <label htmlFor="input-priority-score" className="override-input-label font-headline">
                      MANUAL PRIORITY SCORE OVERRIDE [0.0 - 100.0]:
                    </label>
                    <TacticalInput
                      id="input-priority-score"
                      type="number"
                      min="0.0"
                      max="100.0"
                      step="0.1"
                      value={newPriorityScore}
                      onChange={(e) => setNewPriorityScore(e.target.value)}
                      placeholder="e.g. 85.0"
                      leftIcon={<Zap size={16} />}
                      required
                    />
                    <p className="font-body text-xs text-muted mt-2">
                      Direct manual score override. Priority tier (CRITICAL/HIGH/MEDIUM/LOW) will be automatically mapped by the backend and a priority calculation ledger entry will be recorded.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* 3. Mandatory Reason Justification */}
            {selectedField && (
              <div className="override-form-group">
                <div className="op-label-row">
                  <label htmlFor={reasonInputId} className="override-form-label font-headline">
                    2. MANDATORY OVERRIDE REASON & JUSTIFICATION
                  </label>
                  <span className={`op-char-counter font-mono ${isReasonValid ? 'is-valid' : 'is-invalid'}`}>
                    {reasonTrimmed.length} / 5 CHARS MIN
                  </span>
                </div>
                <textarea
                  id={reasonInputId}
                  rows={3}
                  className="op-textarea font-body"
                  placeholder="Enter mandatory justification for overriding this field (e.g. 'Field observer reports active high-voltage line down across highway')..."
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
                <span className="op-input-hint font-body text-xs text-muted">
                  Recorded verbatim in the immutable audit trail and human_override metadata block.
                </span>
              </div>
            )}

            {/* Action Bar */}
            {selectedField && (
              <div className="override-action-bar">
                <div className="override-action-disclaimer font-body text-xs text-muted">
                  * Sovereign operator action: protects overridden field from future automated ML overwrite. Does not dispatch units.
                </div>
                <Button
                  type="submit"
                  variant="hazard"
                  size="md"
                  disabled={!canPreview}
                  title={!isValueValid ? 'Enter a valid field value' : !isReasonValid ? 'Enter at least 5 characters for reason' : 'Preview field override'}
                >
                  <ArrowRight size={14} style={{ marginRight: 6 }} />
                  PREVIEW FIELD OVERRIDE
                </Button>
              </div>
            )}
          </form>
        )}

        {/* DELIBERATE CONFIRMATION STEP */}
        {showConfirmation && selectedField && (
          <div 
            className="override-confirmation-card"
            role="dialog"
            aria-labelledby="confirm-override-heading"
            aria-modal="true"
          >
            <div className="override-confirm-header">
              <Zap size={18} className="text-hazard" />
              <h3 id="confirm-override-heading" className="font-headline text-hazard">
                CONFIRM SOVEREIGN FIELD OVERRIDE
              </h3>
            </div>

            <div className="override-confirm-table font-mono">
              <div className="confirm-row">
                <span className="confirm-col-label">TARGET INCIDENT:</span>
                <span className="confirm-col-val text-cyan font-bold">{incident.incident_id}</span>
              </div>
              <div className="confirm-row">
                <span className="confirm-col-label">OVERRIDE FIELD:</span>
                <span className="confirm-col-val text-hazard font-bold uppercase">{selectedField}</span>
              </div>
              <div className="confirm-row">
                <span className="confirm-col-label">CURRENT VALUE:</span>
                <span className="confirm-col-val text-muted">{formattedCurrentValue}</span>
              </div>
              <div className="confirm-row">
                <span className="confirm-col-label">NEW VALUE:</span>
                <span className="confirm-col-val text-cyan font-bold">{formattedNewValue}</span>
              </div>
              <div className="confirm-row">
                <span className="confirm-col-label">REASON:</span>
                <span className="confirm-col-val text-newsprint font-body text-sm">
                  "{reasonTrimmed}"
                </span>
              </div>
              <div className="confirm-row">
                <span className="confirm-col-label">ACTING OPERATOR:</span>
                <span className="confirm-col-val text-newsprint font-bold">{operatorId}</span>
              </div>
            </div>

            <div className="override-confirm-warning font-body text-xs">
              <strong className="text-hazard">OPERATOR SOVEREIGNTY:</strong> Overriding this field updates the incident's human_override snapshot, recomputes priority where applicable, and locks this dimension from automated machine overwrite.
            </div>

            <div className="override-confirm-actions">
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
                onClick={handleExecuteOverride}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <RotateCcw size={14} className="spinning" style={{ marginRight: 6 }} />
                    APPLYING OVERRIDE...
                  </>
                ) : (
                  <>
                    <Check size={14} style={{ marginRight: 6 }} />
                    CONFIRM & APPLY OVERRIDE
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

export default IncidentOverridePanel;
