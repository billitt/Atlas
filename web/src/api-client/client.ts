export type Confidence = "HIGH" | "MEDIUM" | "LOW";

export interface SessionResponse {
  token: string | null;
  auth_required: boolean;
}

export interface StatusAgent {
  name: string;
  url: string;
  port: string;
  reachable: boolean;
  skills: string[];
}

export interface StatusResponse {
  ready: boolean;
  issues: string[];
  api_auth_required: boolean;
  ollama: {
    reachable: boolean;
    model: string;
    model_loaded: boolean;
    base_url: string;
  };
  mcp_servers: Array<{ name: string; url: string; reachable: boolean }>;
  agents: StatusAgent[];
  memory: {
    semantic_docs: number;
    episodic_briefings: number;
    episodic_alerts: number;
  };
}

let cachedToken: string | null = null;

export function setAuthToken(token: string | null): void {
  cachedToken = token;
}

export function getAuthToken(): string | null {
  return cachedToken;
}

function authHeaders(): HeadersInit {
  const token = getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function fetchSession(): Promise<SessionResponse> {
  const session = await apiFetch<SessionResponse>("/api/session");
  setAuthToken(session.token);
  return session;
}

export async function fetchStatus(): Promise<StatusResponse> {
  return apiFetch<StatusResponse>("/api/status");
}
