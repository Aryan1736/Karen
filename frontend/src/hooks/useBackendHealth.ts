import { useState, useEffect, useCallback } from 'react';
import { getHealth, HealthCheckData } from '../api/health';

export interface BackendHealthState {
  isOnline: boolean | null;
  databaseStatus: string | null;
  isLoading: boolean;
  error: string | null;
  checkHealth: () => Promise<void>;
}

// In-flight request deduplication and 5-second caching across all hook instances
let inFlightHealthPromise: Promise<HealthCheckData> | null = null;
let cachedHealthData: HealthCheckData | null = null;
let lastCheckTime = 0;

export function useBackendHealth(pollIntervalMs = 30000): BackendHealthState {
  const [isOnline, setIsOnline] = useState<boolean | null>(() => {
    return cachedHealthData ? cachedHealthData.status === 'healthy' : null;
  });
  const [databaseStatus, setDatabaseStatus] = useState<string | null>(() => {
    return cachedHealthData ? cachedHealthData.database : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(!cachedHealthData);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    const now = Date.now();
    // Use cached response if checked within last 4 seconds
    if (cachedHealthData && now - lastCheckTime < 4000) {
      setIsOnline(cachedHealthData.status === 'healthy');
      setDatabaseStatus(cachedHealthData.database);
      setIsLoading(false);
      return;
    }

    try {
      if (!inFlightHealthPromise) {
        inFlightHealthPromise = getHealth().finally(() => {
          inFlightHealthPromise = null;
        });
      }

      const data: HealthCheckData = await inFlightHealthPromise;
      cachedHealthData = data;
      lastCheckTime = Date.now();

      if (data && data.status === 'healthy') {
        setIsOnline(true);
        setDatabaseStatus(data.database);
        setError(null);
      } else {
        setIsOnline(false);
        setDatabaseStatus(data?.database || 'unknown');
        setError('Service reported unhealthy');
      }
    } catch (err) {
      cachedHealthData = null;
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
