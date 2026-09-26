import { apiFetch } from './client';

export interface HealthCheckData {
  status: string;
  database: string;
}

export async function getHealth(): Promise<HealthCheckData> {
  return apiFetch<HealthCheckData>('/health');
}
