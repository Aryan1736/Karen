import { useState, useEffect, useCallback } from 'react';
import { getIncidentDetail, IncidentDetailResult } from '../api/incidents';
import { useWebSocket } from '../context/WebSocketContext';
import { Incident } from '../types/incident';

export interface UseIncidentDetailResult {
  data: IncidentDetailResult | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useIncidentDetail(incidentId: string | null): UseIncidentDetailResult {
  const [data, setData] = useState<IncidentDetailResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const { lastEvent } = useWebSocket();

  const fetchDetail = useCallback(async () => {
    if (!incidentId) {
      setData(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await getIncidentDetail(incidentId);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to load incident ${incidentId}`);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // Sync real-time updates if the event targets this incident
  useEffect(() => {
    if (!lastEvent || !incidentId || !data) return;

    if (lastEvent.event === 'INCIDENT_UPDATED') {
      const payload = lastEvent.payload as any;
      if (payload && payload.incident_id === incidentId) {
        if (payload.status && payload.priority) {
          setData((prev) => (prev ? { ...prev, incident: payload as Incident } : prev));
        } else {
          // Delta update on priority/corroboration
          setData((prev) => {
            if (!prev) return null;
            return {
              ...prev,
              incident: {
                ...prev.incident,
                priority: payload.new_priority_score !== undefined
                  ? {
                      ...prev.incident.priority,
                      score: payload.new_priority_score,
                      level: payload.new_priority_level || prev.incident.priority.level,
                      explanation: payload.explanation || prev.incident.priority.explanation,
                    }
                  : prev.incident.priority,
                corroboration: payload.corroboration || prev.incident.corroboration,
              },
            };
          });
        }
      }
    } else if (lastEvent.event === 'INCIDENT_STATUS_CHANGED') {
      const payload = lastEvent.payload as { incident_id?: string; new_status?: any };
      if (payload && payload.incident_id === incidentId && payload.new_status) {
        setData((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            incident: {
              ...prev.incident,
              status: payload.new_status,
            },
          };
        });
      }
    }
  }, [lastEvent, incidentId, data]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchDetail,
  };
}
