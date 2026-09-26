import { ApiResponseEnvelope, ApiError } from '../types/incident';

export const getOperatorId = (): string => {
  return (import.meta.env.VITE_OPERATOR_ID as string) || 'console-operator';
};

const BASE_URL = (import.meta.env.VITE_API_URL as string) || '/api';

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

  const url = `${BASE_URL.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`;

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
