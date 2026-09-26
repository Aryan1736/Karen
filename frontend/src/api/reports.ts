import { apiFetch } from './client';
import { LocationPrecision, ReportSource } from '../types/incident';

export interface LocationHintPayload {
  raw_text?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  precision?: LocationPrecision;
}

export interface SubmitReportPayload {
  report_id?: string;
  text: string;
  source: ReportSource;
  is_synthetic: boolean;
  reported_at: string;
  location_hint?: LocationHintPayload | null;
  metadata?: Record<string, unknown>;
}

export interface ReportIngestResult {
  report_id: string;
  incident_id: string;
  is_new_incident: boolean;
  relationship: string;
  processing_status: string;
}

export async function submitReport(payload: SubmitReportPayload): Promise<ReportIngestResult> {
  return apiFetch<ReportIngestResult>('/reports', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
