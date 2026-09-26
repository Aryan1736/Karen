import { apiFetch } from './client';
import { Incident, IncidentStatus, RawReport, AuditLog } from '../types/incident';

export interface IncidentListParams {
  status?: string;
  level?: string;
  limit?: number;
  offset?: number;
}

export interface IncidentListResult {
  incidents: Incident[];
  total_count: number;
  critical_count: number;
}

export interface IncidentDetailResult {
  incident: Incident;
  source_reports: RawReport[];
  audit_trail: AuditLog[];
}

export interface ReviewIncidentPayload {
  target_status: IncidentStatus;
  notes: string;
  operator_id?: string;
}

export interface OverrideIncidentPayload {
  field: string;
  new_value: unknown;
  reason: string;
  operator_id?: string;
}

export interface IncidentReviewResult {
  incident: Incident;
  audit: AuditLog;
}

export interface IncidentOverrideResult {
  incident: Incident;
  audit: AuditLog;
}

export interface TimelineEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  summary: string;
  details: Record<string, unknown>;
}

export interface IncidentTimelineResult {
  incident_id: string;
  total_events: number;
  events: TimelineEvent[];
}

export async function listIncidents(params: IncidentListParams = {}): Promise<IncidentListResult> {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.level) query.set('level', params.level);
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));

  const qs = query.toString();
  const endpoint = qs ? `/incidents?${qs}` : '/incidents';
  return apiFetch<IncidentListResult>(endpoint);
}

export async function getIncidentDetail(id: string): Promise<IncidentDetailResult> {
  return apiFetch<IncidentDetailResult>(`/incidents/${encodeURIComponent(id)}`);
}

export async function reviewIncident(
  id: string,
  payload: ReviewIncidentPayload
): Promise<IncidentReviewResult> {
  return apiFetch<IncidentReviewResult>(`/incidents/${encodeURIComponent(id)}/review`, {
    method: 'POST',
    includeOperatorId: true,
    body: JSON.stringify(payload),
  });
}

export async function overrideIncident(
  id: string,
  payload: OverrideIncidentPayload
): Promise<IncidentOverrideResult> {
  return apiFetch<IncidentOverrideResult>(`/incidents/${encodeURIComponent(id)}/override`, {
    method: 'POST',
    includeOperatorId: true,
    body: JSON.stringify(payload),
  });
}

export async function getIncidentTimeline(
  id: string,
  order: 'asc' | 'desc' = 'asc'
): Promise<IncidentTimelineResult> {
  return apiFetch<IncidentTimelineResult>(
    `/incidents/${encodeURIComponent(id)}/timeline?order=${encodeURIComponent(order)}`
  );
}
