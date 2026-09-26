import { RealtimeEvent, RealtimeEventType } from '../types/incident';

export type WebSocketConnectionStatus = 
  | 'STANDBY'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'DISCONNECTED'
  | 'ERROR';

export type EventListener<T = unknown> = (event: RealtimeEvent<T>) => void;
export type StatusListener = (status: WebSocketConnectionStatus) => void;

export function getWebSocketUrl(): string {
  const customWsUrl = import.meta.env.VITE_WS_URL as string | undefined;
  if (customWsUrl && customWsUrl.trim()) {
    let wsUrl = customWsUrl.trim();
    // Guard against accidental /api/ws/events path
    if (wsUrl.includes('/api/ws/events')) {
      wsUrl = wsUrl.replace('/api/ws/events', '/ws/events');
    }
    return wsUrl;
  }

  // If VITE_API_BASE_URL (or legacy VITE_API_URL) is specified as an absolute HTTP(S) URL, derive WS URL
  const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
                  (import.meta.env.VITE_API_URL as string | undefined);
  if (apiBase && /^https?:\/\//i.test(apiBase.trim())) {
    try {
      const parsed = new URL(apiBase.trim());
      const wsProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsProtocol}//${parsed.host}/ws/events`;
    } catch {
      // Fall through to window origin fallback
    }
  }

  const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:';
  const protocol = isHttps ? 'wss:' : 'ws:';
  const host = typeof window !== 'undefined' ? window.location.host : 'localhost:5173';
  return `${protocol}//${host}/ws/events`;
}

export class TingleWebSocketClient {
  private socket: WebSocket | null = null;
  private status: WebSocketConnectionStatus = 'STANDBY';
  private eventListeners: Map<string, Set<EventListener<any>>> = new Map();
  private statusListeners: Set<StatusListener> = new Set();
  private isIntentionallyClosed = false;

  constructor() {
    this.eventListeners.set('*', new Set());
  }

  public getStatus(): WebSocketConnectionStatus {
    return this.status;
  }

  private setStatus(newStatus: WebSocketConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((listener) => {
        try {
          listener(newStatus);
        } catch (err) {
          console.error('[WebSocket] Status listener error:', err);
        }
      });
    }
  }

  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.setStatus('CONNECTING');

    const url = getWebSocketUrl();

    try {
      this.socket = new WebSocket(url);
    } catch (err) {
      console.error('[WebSocket] Failed to instantiate WebSocket:', err);
      this.setStatus('ERROR');
      return;
    }

    this.socket.onopen = () => {
      this.setStatus('CONNECTED');
    };

    this.socket.onmessage = (event: MessageEvent) => {
      this.handleIncomingMessage(event.data);
    };

    this.socket.onerror = (event: Event) => {
      console.warn('[WebSocket] Transport error event encountered:', event);
      this.setStatus('ERROR');
    };

    this.socket.onclose = () => {
      this.socket = null;
      if (!this.isIntentionallyClosed) {
        this.setStatus('DISCONNECTED');
      } else {
        this.setStatus('STANDBY');
      }
    };
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    if (this.socket) {
      try {
        this.socket.close(1000, 'Client intentional disconnect');
      } catch {
        // Ignored
      }
      this.socket = null;
    }
    this.setStatus('STANDBY');
  }

  private handleIncomingMessage(rawPayload: unknown): void {
    if (typeof rawPayload !== 'string') {
      console.warn('[WebSocket] Ignored non-string WebSocket message');
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(rawPayload);
    } catch {
      console.warn('[WebSocket] Malformed non-JSON frame safely ignored, length:', rawPayload.length);
      return;
    }

    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      console.warn('[WebSocket] Non-object JSON frame safely ignored');
      return;
    }

    const messageObj = parsed as Record<string, unknown>;
    const eventName = messageObj.event;

    if (typeof eventName !== 'string') {
      console.warn('[WebSocket] Frame missing string "event" key safely ignored');
      return;
    }

    // Server PING heartbeat handling
    if (eventName === 'PING') {
      this.sendPong();
    }

    const envelope: RealtimeEvent = {
      event: eventName as RealtimeEventType,
      payload: messageObj.payload ?? {},
      timestamp: typeof messageObj.timestamp === 'string' ? messageObj.timestamp : new Date().toISOString(),
    };

    this.dispatchToListeners(envelope);
  }

  private sendPong(): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(JSON.stringify({ type: 'PONG' }));
      } catch (err) {
        console.warn('[WebSocket] Failed to send PONG response:', err);
      }
    }
  }

  private dispatchToListeners(envelope: RealtimeEvent): void {
    // Dispatch to specific event listeners
    const specificListeners = this.eventListeners.get(envelope.event);
    if (specificListeners) {
      specificListeners.forEach((listener) => {
        try {
          listener(envelope);
        } catch (err) {
          console.error(`[WebSocket] Listener error on ${envelope.event}:`, err);
        }
      });
    }

    // Dispatch to wildcard listeners
    const wildcardListeners = this.eventListeners.get('*');
    if (wildcardListeners) {
      wildcardListeners.forEach((listener) => {
        try {
          listener(envelope);
        } catch (err) {
          console.error('[WebSocket] Wildcard listener error:', err);
        }
      });
    }
  }

  public on<T = unknown>(event: RealtimeEventType | '*', listener: EventListener<T>): () => void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    const set = this.eventListeners.get(event)!;
    set.add(listener as EventListener<any>);

    return () => {
      set.delete(listener as EventListener<any>);
    };
  }

  public onStatusChange(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    // Immediately notify caller of current status
    listener(this.status);

    return () => {
      this.statusListeners.delete(listener);
    };
  }
}

export const wsClient = new TingleWebSocketClient();
