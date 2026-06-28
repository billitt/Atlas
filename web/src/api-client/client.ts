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

export interface BriefingRow {
  id: number;
  timestamp: string;
  query: string;
  briefing_type: string;
  confidence: Confidence;
  trace_id: string | null;
  duration_seconds: number | null;
  summary: string;
  delta_from_last: string | null;
}

export interface AlertRule {
  id: string;
  name: string;
  description: string;
  severity: string;
  watch_topic: string;
  cooldown_seconds: number;
}

export interface AlertRow {
  id: number;
  timestamp: string;
  rule_id: string;
  rule_name: string;
  severity: string;
  summary: string;
  evidence: string;
  context: string;
}

export interface TraceListEntry {
  path: string;
  filename: string;
  span_count: number;
  trace_ids: string[];
  exported_at: string | null;
}

export interface TraceDetail {
  trace_id: string;
  path: string;
  exported_at: string | null;
  span_count: number;
  tree: string;
}

export async function fetchBriefings(limit = 20): Promise<BriefingRow[]> {
  const data = await apiFetch<{ briefings: BriefingRow[] }>(`/api/briefings?limit=${limit}`);
  return data.briefings;
}

export async function fetchAlerts(): Promise<{ rules: AlertRule[]; recent: AlertRow[] }> {
  return apiFetch<{ rules: AlertRule[]; recent: AlertRow[] }>("/api/alerts");
}

export async function checkAlerts(): Promise<
  Array<Omit<AlertRow, "id"> & { triggered_at?: string }>
> {
  const data = await apiFetch<{
    triggered: Array<{
      rule_id: string;
      rule_name: string;
      severity: string;
      summary: string;
      triggered_at?: string;
      evidence?: string;
      context?: string;
    }>;
  }>("/api/alerts/check", { method: "POST" });
  return data.triggered.map((row) => ({
    timestamp: row.triggered_at ?? new Date().toISOString(),
    rule_id: row.rule_id,
    rule_name: row.rule_name,
    severity: row.severity,
    summary: row.summary,
    evidence: row.evidence ?? "",
    context: row.context ?? "",
  }));
}

export async function fetchAgents(): Promise<StatusAgent[]> {
  const data = await apiFetch<{ agents: StatusAgent[] }>("/api/agents");
  return data.agents;
}

export async function fetchTraces(): Promise<TraceListEntry[]> {
  const data = await apiFetch<{ traces: TraceListEntry[] }>("/api/traces");
  return data.traces;
}

export async function fetchTrace(traceId: string): Promise<TraceDetail> {
  return apiFetch<TraceDetail>(`/api/traces/${encodeURIComponent(traceId)}`);
}
