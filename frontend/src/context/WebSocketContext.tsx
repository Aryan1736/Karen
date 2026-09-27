import React, { createContext, useContext, useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { wsClient, WebSocketConnectionStatus } from '../websocket/client';
import { RealtimeEvent } from '../types/incident';

export interface WebSocketStatusContextValue {
  status: WebSocketConnectionStatus;
  reconnect: () => void;
}

export interface WebSocketEventsContextValue {
  lastEvent: RealtimeEvent | null;
  events: RealtimeEvent[];
  clearEvents: () => void;
}

export interface WebSocketContextValue extends WebSocketStatusContextValue, WebSocketEventsContextValue {}

const WebSocketStatusContext = createContext<WebSocketStatusContextValue | undefined>(undefined);
const WebSocketEventsContext = createContext<WebSocketEventsContextValue | undefined>(undefined);

const MAX_EVENT_HISTORY = 50;

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<WebSocketConnectionStatus>(() => wsClient.getStatus());
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);

  // Ref to queue events for microtask batching
  const pendingEventsRef = useRef<RealtimeEvent[]>([]);
  const batchScheduledRef = useRef<boolean>(false);

  useEffect(() => {
    // 1. Subscribe to connection status changes
    const unsubStatus = wsClient.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });

    // 2. Subscribe to application events with microtask batching to prevent main-thread lag
    const unsubEvents = wsClient.on('*', (envelope) => {
      pendingEventsRef.current.push(envelope);

      if (!batchScheduledRef.current) {
        batchScheduledRef.current = true;
        // Schedule batch flush on next animation frame
        requestAnimationFrame(() => {
          batchScheduledRef.current = false;
          const pending = pendingEventsRef.current;
          if (pending.length === 0) return;

          pendingEventsRef.current = [];
          const newest = pending[pending.length - 1];
          setLastEvent(newest);
          setEvents((prev) => [...pending.reverse(), ...prev].slice(0, MAX_EVENT_HISTORY));
        });
      }
    });

    // Automatically initiate connection on mount
    wsClient.connect();

    return () => {
      unsubStatus();
      unsubEvents();
      wsClient.disconnect();
    };
  }, []);

  const reconnect = useCallback(() => {
    wsClient.disconnect();
    wsClient.connect();
  }, []);

  const clearEvents = useCallback(() => {
    pendingEventsRef.current = [];
    setEvents([]);
    setLastEvent(null);
  }, []);

  // Memoize status context: only changes when connection status changes
  const statusValue = useMemo<WebSocketStatusContextValue>(() => ({
    status,
    reconnect,
  }), [status, reconnect]);

  // Memoize events context: only changes when actual events update
  const eventsValue = useMemo<WebSocketEventsContextValue>(() => ({
    lastEvent,
    events,
    clearEvents,
  }), [lastEvent, events, clearEvents]);

  return (
    <WebSocketStatusContext.Provider value={statusValue}>
      <WebSocketEventsContext.Provider value={eventsValue}>
        {children}
      </WebSocketEventsContext.Provider>
    </WebSocketStatusContext.Provider>
  );
};

/**
 * High-performance hook for components that ONLY need connection status
 * (e.g., LandingPageView, HeaderBar, TacticalMap).
 * DOES NOT RE-RENDER ON INCOMING INCIDENT EVENTS!
 */
export const useWebSocketStatus = (): WebSocketStatusContextValue => {
  const context = useContext(WebSocketStatusContext);
  if (!context) {
    throw new Error('useWebSocketStatus must be used within a WebSocketProvider');
  }
  return context;
};

/**
 * Hook for components that consume event streams (e.g., IncidentStreamsView).
 */
export const useWebSocketEvents = (): WebSocketEventsContextValue => {
  const context = useContext(WebSocketEventsContext);
  if (!context) {
    throw new Error('useWebSocketEvents must be used within a WebSocketProvider');
  }
  return context;
};

/**
 * Combined convenience hook for backward compatibility.
 */
export const useWebSocket = (): WebSocketContextValue => {
  const statusContext = useContext(WebSocketStatusContext);
  const eventsContext = useContext(WebSocketEventsContext);

  if (!statusContext || !eventsContext) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }

  return useMemo(() => ({
    ...statusContext,
    ...eventsContext,
  }), [statusContext, eventsContext]);
};
