import { apiFetch } from './client';
import {
  SimulationScenario,
  SimulationStatusData,
  SimulationRunResponse,
  SimulationPulseResult,
  SimulationSpeed,
} from '../types/simulation';

export async function fetchSimulationScenarios(): Promise<SimulationScenario[]> {
  return apiFetch<SimulationScenario[]>('simulation/scenarios');
}

export async function fetchSimulationStatus(): Promise<SimulationStatusData> {
  return apiFetch<SimulationStatusData>('simulation/status');
}

export interface StartSimulationParams {
  scenario_id: string;
  speed?: SimulationSpeed;
  rate_per_minute?: number;
}

export async function startSimulation(params: StartSimulationParams): Promise<SimulationRunResponse> {
  return apiFetch<SimulationRunResponse>('simulation/start', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function stopSimulation(): Promise<SimulationStatusData> {
  return apiFetch<SimulationStatusData>('simulation/stop', {
    method: 'POST',
  });
}

export interface InjectPulseParams {
  scenario_id?: string;
  event_index?: number;
}

export async function injectSimulationPulse(params?: InjectPulseParams): Promise<SimulationPulseResult> {
  return apiFetch<SimulationPulseResult>('simulation/pulse', {
    method: 'POST',
    body: JSON.stringify(params || { scenario_id: 'flood_rasulgarh' }),
  });
}
