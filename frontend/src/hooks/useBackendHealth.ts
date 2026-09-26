import { useState, useEffect, useCallback } from 'react';
import { getHealth, HealthCheckData } from '../api/health';

export interface BackendHealthState {
  isOnline: boolean | null;
  databaseStatus: string | null;
  isLoading: boolean;
  error: string | null;
  checkHealth: () => Promise<void>;
}

export function useBackendHealth(pollIntervalMs = 15000): BackendHealthState {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [databaseStatus, setDatabaseStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const data: HealthCheckData = await getHealth();
      if (data && data.status === 'healthy') {
        setIsOnline(true);
        setDatabaseStatus(data.database);
        setError(null);
      } else {
        setIsOnline(false);
        setDatabaseStatus(data?.database || 'unknown');
        setError('Service report unhealthy');
      }
    } catch (err) {
      setIsOnline(false);
      setDatabaseStatus('unreachable');
      setError(err instanceof Error ? err.message : 'Backend unreachable');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    if (pollIntervalMs > 0) {
      const interval = setInterval(checkHealth, pollIntervalMs);
      return () => clearInterval(interval);
    }
  }, [checkHealth, pollIntervalMs]);

  return {
    isOnline,
    databaseStatus,
    isLoading,
    error,
    checkHealth,
  };
}
