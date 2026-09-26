/**
 * Karen's Ear — Canonical Frontend TypeScript Types
 * 
 * Target: Srinivash (Frontend), Daksh (Backend API)
 * Authority: Follows gemini.md (v1.2), docs/data-schema.md, and docs/api-contract.md.
 * Status: FROZEN FOR SPRINT IMPLEMENTATION
 */

// ==========================================
// 1. Core Enumerations & Union Literals
// ==========================================

export type IncidentStatus = 
  | 'NEW'
  | 'ANALYZING'
  | 'ACTIVE'
  | 'NEEDS_REVIEW'
  | 'VERIFIED'
  | 'ESCALATED'
  | 'RESOLVED'
  | 'FALSE_REPORT';

export type IncidentType =
  | 'FLOOD_FLASH_FLOOD'
  | 'FIRE_WILDFIRE_EXPLOSION'
  | 'STRUCTURAL_COLLAPSE'
  | 'EARTHQUAKE_LANDSLIDE'
  | 'SEVERE_WEATHER_STORM'
  | 'MEDICAL_EMERGENCY'
  | 'CIVIL_UNREST_ACTIVE_THREAT'
  | 'UTILITY_INFRASTRUCTURE_FAILURE'
  | 'OTHER_GENERAL_INCIDENT';

export type UrgencyLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type PriorityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type LocationPrecision = 'exact' | 'approximate' | 'unknown';

export type ReportSource = 'manual' | 'simulator' | 'dataset' | 'other';

export type RelationshipType = 
  | 'INITIAL'
  | 'CORROBORATING'
  | 'DUPLICATE'
  | 'RELATED'
  | 'UNCERTAIN';

export type RequiredResponseType =
  | 'SEARCH_AND_RESCUE'
  | 'MEDICAL_EMS'
  | 'FIRE_HAZMAT'
  | 'POLICE_SECURITY'
  | 'PUBLIC_WORKS_UTILITY';

export type ProcessingStatus = 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'NEEDS_REVIEW';

// ==========================================
// 2. Incident Sub-Structures
// ==========================================

export interface IncidentLocation {
  text: string | null;
  latitude: number | null;
  longitude: number | null;
  precision: LocationPrecision;
}

export interface IncidentRisk {
  count: number | null;
}

export interface Corroboration {
  report_count: number;
  independent_source_count: number;
  score: number; // [0.0, 1.0]
  explanation: string;
}

export interface ConfidenceBlock {
  overall: number | null; // [0.0, 1.0]
  components: Record<string, number | null>;
}

export interface PriorityFactor {
  factor: string;
  value: number | string;
  weight: number;
  contribution: number;
}

export interface PriorityBlock {
  score: number; // [0.0, 100.0]
  level: PriorityLevel;
  explanation: string;
  factors: PriorityFactor[];
}

export interface HumanOverrideBlock {
  active: boolean;
  updated_by: string | null;
  updated_at: string | null; // ISO-8601 UTC
  reason: string | null;
}

// ==========================================
// 3. Primary Incident Contract
// ==========================================

export interface Incident {
  incident_id: string;
  status: IncidentStatus;
  incident_type: IncidentType | string | null;
  urgency: UrgencyLevel | string | null;
  location: IncidentLocation;
  people_at_risk: IncidentRisk;
  required_response: string[];
  source_report_ids: string[];
  corroboration: Corroboration;
  ml_confidence: ConfidenceBlock;
  priority: PriorityBlock;
  human_override: HumanOverrideBlock;
  is_synthetic: boolean;
  created_at: string; // ISO-8601 UTC
  updated_at: string; // ISO-8601 UTC
}

// ==========================================
// 4. Raw Report Contract
// ==========================================

export interface LocationHint {
  raw_text?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  precision: LocationPrecision;
}

export interface RawReport {
  report_id: string;
  text: string;
  source: ReportSource;
  is_synthetic: boolean;
  reported_at: string; // ISO-8601 UTC
  location_hint?: LocationHint | null;
  metadata?: Record<string, unknown> | null;
}

// ==========================================
// 5. ML Output Contract (ml/schemas/incident_output.json)
// ==========================================

export interface MLTypePrediction {
  label: IncidentType | string | null;
  confidence: number | null;
}

export interface MLUrgencyPrediction {
  label: UrgencyLevel | string | null;
  confidence: number | null;
}

export interface MLLocationPrediction {
  text: string | null;
  latitude: number | null;
  longitude: number | null;
  precision: LocationPrecision;
  confidence: number | null;
}

export interface MLRiskPrediction {
  count: number | null;
  confidence: number | null;
}

export interface MLResponseNeed {
  type: RequiredResponseType | string;
  confidence: number | null;
}

export interface MLEntityToken {
  text: string;
  type: string;
  confidence: number | null;
}

export interface MLOutput {
  report_id: string;
  model_version: string;
  incident_type: MLTypePrediction;
  urgency: MLUrgencyPrediction;
  location: MLLocationPrediction;
  people_at_risk: MLRiskPrediction;
  required_response: MLResponseNeed[];
  entities: MLEntityToken[];
  embedding_reference: string | null;
  processing_status: ProcessingStatus;
  warnings: string[];
}

// ==========================================
// 6. Audit & Human Review Types
// ==========================================

export interface AuditLog {
  override_id: string;
  incident_id: string;
  operator_id: string;
  field: string;
  previous_value: unknown;
  new_value: unknown;
  reason: string;
  created_at: string; // ISO-8601 UTC
}

export interface OperatorOverridePayload {
  operator_id: string;
  field: string;
  new_value: unknown;
  reason: string;
}

export interface OperatorReviewPayload {
  operator_id: string;
  target_status: IncidentStatus;
  notes?: string;
}

// ==========================================
// 7. Canonical API Envelopes
// ==========================================

export interface ApiErrorDetail {
  field?: string;
  issue: string;
}

export interface ApiError {
  code: string;
  message: string;
  details?: ApiErrorDetail[];
}

export interface ApiResponseEnvelope<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
  request_id: string;
  timestamp: string; // ISO-8601 UTC
}

// ==========================================
// 8. Real-Time WebSocket Event Types
// ==========================================

export type RealtimeEventType = 
  | 'INCIDENT_CREATED'
  | 'INCIDENT_UPDATED'
  | 'INCIDENT_STATUS_CHANGED'
  | 'SIMULATION_PULSE'
  | 'PING'
  | 'PONG';

export interface RealtimeEvent<T = unknown> {
  event: RealtimeEventType;
  payload: T;
  timestamp: string; // ISO-8601 UTC
}

export interface IncidentUpdatedPayload {
  incident_id: string;
  previous_priority_score?: number;
  new_priority_score: number;
  new_priority_level: PriorityLevel;
  corroboration: Corroboration;
  latest_report_id?: string;
  explanation: string;
}

export interface IncidentStatusChangedPayload {
  incident_id: string;
  old_status: IncidentStatus;
  new_status: IncidentStatus;
}
