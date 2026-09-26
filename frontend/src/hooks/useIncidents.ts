import { useState, useEffect, useCallback, useRef } from 'react';
import { listIncidents, IncidentListParams } from '../api/incidents';
import { Incident } from '../types/incident';
import { IncidentPriorityFilter } from '../context/NavigationContext';
import { useWebSocket } from '../context/WebSocketContext';

export interface UseIncidentsResult {
  incidents: Incident[];
  totalCount: number;
  criticalCount: number;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useIncidents(filter: IncidentPriorityFilter = 'ALL'): UseIncidentsResult {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [criticalCount, setCriticalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const { lastEvent } = useWebSocket();
  const filterRef = useRef(filter);
  filterRef.current = filter;

  const fetchIncidents = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const params: IncidentListParams = {};
    if (filterRef.current === 'CRITICAL') {
      params.level = 'CRITICAL';
    } else if (filterRef.current === 'HIGH') {
      params.level = 'HIGH';
    } else if (filterRef.current === 'MEDIUM') {
      params.level = 'MEDIUM';
    } else if (filterRef.current === 'NEEDS_REVIEW') {
      params.status = 'NEEDS_REVIEW';
    }

    try {
      const data = await listIncidents(params);
      setIncidents(data.incidents || []);
      setTotalCount(data.total_count ?? 0);
      setCriticalCount(data.critical_count ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch incidents');
      setIncidents([]);
      setTotalCount(0);
      setCriticalCount(0);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch when active filter changes
  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents, filter]);

  // Handle incoming real-time events without refetching entire list
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.event === 'INCIDENT_CREATED') {
      const newIncident = lastEvent.payload as Incident;
      if (newIncident && newIncident.incident_id) {
        setIncidents((prev) => {
          // Prevent duplicates
          if (prev.some((inc) => inc.incident_id === newIncident.incident_id)) {
            return prev.map((inc) => (inc.incident_id === newIncident.incident_id ? newIncident : inc));
          }

          // Check if matches active filter
          const currentFilter = filterRef.current;
          let matches = true;
          if (currentFilter === 'CRITICAL') matches = newIncident.priority?.level === 'CRITICAL';
          else if (currentFilter === 'HIGH') matches = newIncident.priority?.level === 'HIGH';
          else if (currentFilter === 'MEDIUM') matches = newIncident.priority?.level === 'MEDIUM';
          else if (currentFilter === 'NEEDS_REVIEW') matches = newIncident.status === 'NEEDS_REVIEW';

          if (matches) {
            return [newIncident, ...prev];
          }
          return prev;
        });

        setTotalCount((c) => c + 1);
        if (newIncident.priority?.level === 'CRITICAL') {
          setCriticalCount((c) => c + 1);
        }
      }
    } else if (lastEvent.event === 'INCIDENT_UPDATED') {
      const payload = lastEvent.payload as any;
      if (payload && payload.incident_id) {
        setIncidents((prev) =>
          prev.map((inc) => {
            if (inc.incident_id !== payload.incident_id) return inc;
            // Full incident object update
            if (payload.status && payload.priority) {
              return payload as Incident;
            }
            // Delta update
            return {
              ...inc,
              priority: payload.new_priority_score !== undefined
                ? {
                    ...inc.priority,
                    score: payload.new_priority_score,
                    level: payload.new_priority_level || inc.priority.level,
                    explanation: payload.explanation || inc.priority.explanation,
                  }
                : inc.priority,
              corroboration: payload.corroboration || inc.corroboration,
            };
          })
        );
      }
    } else if (lastEvent.event === 'INCIDENT_STATUS_CHANGED') {
      const payload = lastEvent.payload as { incident_id?: string; new_status?: any };
      if (payload && payload.incident_id && payload.new_status) {
        setIncidents((prev) =>
          prev.map((inc) =>
            inc.incident_id === payload.incident_id
              ? { ...inc, status: payload.new_status }
              : inc
          )
        );
      }
    }
  }, [lastEvent]);

  return {
    incidents,
    totalCount,
    criticalCount,
    isLoading,
    error,
    refetch: fetchIncidents,
  };
}
