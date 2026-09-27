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

  // If running in production on a remote host (e.g. Vercel) and no env var was set, fallback to live Render backend
  if (typeof window !== 'undefined' && !window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1')) {
    return 'wss://tingle-backend.onrender.com/ws/events';
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
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;

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
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }

    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.setStatus('CONNECTING');

    const url = getWebSocketUrl();

    try {
      this.socket = new WebSocket(url);
    } catch (err) {
      console.warn('[WebSocket] Failed to instantiate WebSocket:', err instanceof Error ? err.message : 'Unknown error');
      this.setStatus('ERROR');
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.setStatus('CONNECTED');
    };

    this.socket.onmessage = (event: MessageEvent) => {
      this.handleIncomingMessage(event.data);
    };

    this.socket.onerror = () => {
      // Don't dump entire Event object to prevent DevTools stutter
      this.setStatus('ERROR');
    };

    this.socket.onclose = () => {
      this.socket = null;
      if (!this.isIntentionallyClosed) {
        this.setStatus('DISCONNECTED');
        this.scheduleReconnect();
      } else {
        this.setStatus('STANDBY');
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.isIntentionallyClosed || this.reconnectTimeoutId) {
      return;
    }

    // Exponential backoff: 3s, 6s, 12s, capped at 15s
    const backoffMs = Math.min(3000 * Math.pow(1.8, this.reconnectAttempts), 15000);
    this.reconnectAttempts++;

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectTimeoutId = null;
      this.connect();
    }, backoffMs);
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
    this.reconnectAttempts = 0;

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
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(rawPayload);
    } catch {
      return;
    }

    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return;
    }

    const messageObj = parsed as Record<string, unknown>;
    const eventName = messageObj.event;

    if (typeof eventName !== 'string') {
      return;
    }

    // Server PING heartbeat handling - respond immediately with PONG and do not dispatch to UI listeners!
    if (eventName === 'PING') {
      this.sendPong();
      return;
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
      } catch {
        // Ignored
      }
    }
  }

  private dispatchToListeners(envelope: RealtimeEvent): void {
    // Dispatch to specific event listeners
    const specificListeners = this.eventListeners.get(envelope.event);
    if (specificListeners && specificListeners.size > 0) {
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
    if (wildcardListeners && wildcardListeners.size > 0) {
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
