import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { wsClient, WebSocketConnectionStatus } from '../websocket/client';
import { RealtimeEvent } from '../types/incident';

export interface WebSocketContextValue {
  status: WebSocketConnectionStatus;
  lastEvent: RealtimeEvent | null;
  events: RealtimeEvent[];
  reconnect: () => void;
  clearEvents: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | undefined>(undefined);

const MAX_EVENT_HISTORY = 50;

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<WebSocketConnectionStatus>(() => wsClient.getStatus());
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);

  useEffect(() => {
    // Subscribe to status changes
    const unsubStatus = wsClient.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });

    // Subscribe to all incoming events
    const unsubEvents = wsClient.on('*', (envelope) => {
      setLastEvent(envelope);
      setEvents((prev) => [envelope, ...prev].slice(0, MAX_EVENT_HISTORY));
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
    setEvents([]);
    setLastEvent(null);
  }, []);

  return (
    <WebSocketContext.Provider
      value={{
        status,
        lastEvent,
        events,
        reconnect,
        clearEvents,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = (): WebSocketContextValue => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};
