export type SimulationSpeed = 'burst' | '10x' | '5x' | '2x' | '1x';

export interface SimulationScenario {
  id: string;
  name: string;
  description: string;
  total_events: number;
  default_rate_per_minute: number;
}

export interface SimulationStatusData {
  status: 'IDLE' | 'RUNNING' | 'STOPPED' | 'COMPLETED';
  is_running: boolean;
  simulation_id: string | null;
  scenario_id: string | null;
  reports_injected: number;
  total_events: number;
  started_at: string | null;
  ended_at: string | null;
}

export interface SimulationRunResponse {
  simulation_id: string;
  scenario_id: string;
  status: string;
  reports_injected: number;
  started_at: string;
  ended_at?: string | null;
}

export interface SimulationPulseResult {
  success: boolean;
  scenario_id: string;
  event_index: number;
  total_events: number;
  report_id: string;
  incident_id: string;
  is_new_incident: boolean;
  relationship: string | null;
  processing_status: string | null;
  incident?: any;
}
