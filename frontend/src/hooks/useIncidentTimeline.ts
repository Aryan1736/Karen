import { useState, useEffect, useCallback } from 'react';
import { getIncidentTimeline, IncidentTimelineResult } from '../api/incidents';
import { useWebSocket } from '../context/WebSocketContext';

export interface UseIncidentTimelineResult {
  data: IncidentTimelineResult | null;
  isLoading: boolean;
  error: string | null;
  order: 'asc' | 'desc';
  setOrder: (order: 'asc' | 'desc') => void;
  refetch: () => Promise<void>;
}

export function useIncidentTimeline(
  incidentId: string | null,
  initialOrder: 'asc' | 'desc' = 'asc'
): UseIncidentTimelineResult {
  const [data, setData] = useState<IncidentTimelineResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<'asc' | 'desc'>(initialOrder);

  const { lastEvent } = useWebSocket();

  const fetchTimeline = useCallback(async () => {
    if (!incidentId) {
      setData(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await getIncidentTimeline(incidentId, order);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to load timeline for incident ${incidentId}`);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [incidentId, order]);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  // Sync real-time updates: if event targets this incident, refresh timeline events
  useEffect(() => {
    if (!lastEvent || !incidentId) return;

    if (lastEvent.event === 'INCIDENT_UPDATED' || lastEvent.event === 'INCIDENT_STATUS_CHANGED') {
      const payload = lastEvent.payload as { incident_id?: string };
      if (payload && payload.incident_id === incidentId) {
        fetchTimeline();
      }
    }
  }, [lastEvent, incidentId, fetchTimeline]);

  return {
    data,
    isLoading,
    error,
    order,
    setOrder,
    refetch: fetchTimeline,
  };
}
