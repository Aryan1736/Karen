import { ApiResponseEnvelope, ApiError } from '../types/incident';

export const getOperatorId = (): string => {
  return (import.meta.env.VITE_OPERATOR_ID as string) || 'console-operator';
};

export const getApiBaseUrl = (): string => {
  const envUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
                 (import.meta.env.VITE_API_URL as string | undefined);
  if (!envUrl || !envUrl.trim()) {
    // If running in production on a remote host (e.g. Vercel), default to production Render backend
    if (typeof window !== 'undefined' && !window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1')) {
      return 'https://tingle-backend.onrender.com';
    }
    // Default to local development Vite proxy prefix
    return '/api';
  }

  let cleanUrl = envUrl.trim().replace(/\/+$/, '');
  // If a full HTTP/HTTPS URL is provided and accidentally ends with /api, strip it
  // because Karen backend mounts routes at root (/incidents, /reports, /health)
  if (/^https?:\/\//i.test(cleanUrl) && cleanUrl.toLowerCase().endsWith('/api')) {
    cleanUrl = cleanUrl.slice(0, -4).replace(/\/+$/, '');
  }

  return cleanUrl;
};

export class ApiRequestError extends Error {
  code: string;
  details?: unknown;
  status: number;
  requestId?: string;

  constructor(message: string, code: string, status: number, details?: unknown, requestId?: string) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = code;
    this.status = status;
    this.details = details;
    this.requestId = requestId;
  }
}

export interface RequestOptions extends RequestInit {
  includeOperatorId?: boolean;
}

export async function apiFetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { includeOperatorId = false, headers: customHeaders, ...restOptions } = options;

  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/${endpoint.replace(/^\//, '')}`;

  const headers: Record<string, string> = {
    'Accept': 'application/json',
    ...(customHeaders as Record<string, string>),
  };

  if (includeOperatorId) {
    headers['X-Operator-Id'] = getOperatorId();
  }

  if (restOptions.body && typeof restOptions.body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...restOptions,
      headers,
    });
  } catch (networkError) {
    throw new ApiRequestError(
      networkError instanceof Error ? networkError.message : 'Network transport error',
      'NETWORK_ERROR',
      0
    );
  }

  let envelope: ApiResponseEnvelope<T> | null = null;
  try {
    envelope = await response.json();
  } catch {
    throw new ApiRequestError(
      `Invalid JSON response from server (HTTP ${response.status})`,
      'PARSE_ERROR',
      response.status
    );
  }

  if (!response.ok || !envelope || !envelope.success) {
    const errorPayload: ApiError | undefined = envelope?.error ?? undefined;
    throw new ApiRequestError(
      errorPayload?.message || `API request failed with status ${response.status}`,
      errorPayload?.code || `HTTP_${response.status}`,
      response.status,
      errorPayload?.details,
      envelope?.request_id
    );
  }

  return envelope.data as T;
}
