import type { Confidence } from "@/api-client/client";
import { getAuthToken } from "@/api-client/client";

export interface SpecialistPayload {
  agent: string;
  label: string;
  analysis?: string;
  confidence?: Confidence;
  sources?: Array<Record<string, unknown>>;
  task?: string;
}

export interface SynthesizePayload {
  status: string;
  combined_analysis?: string;
  confidence?: Confidence;
  sources?: Array<Record<string, unknown>>;
}

export interface GuardianPayload {
  status: string;
  passed?: boolean;
  overall_confidence?: Confidence;
  summary?: string;
  flags?: string[];
}

export interface FinalPayload {
  briefing?: {
    combined_analysis?: string;
    overall_confidence?: Confidence;
    per_agent_sources?: Array<Record<string, unknown>>;
    guardian_verdict?: GuardianPayload;
  };
  trace_id?: string;
  duration_seconds?: number;
  confidence?: Confidence;
  guardian_verdict?: GuardianPayload;
}

export type QueryStreamEvent =
  | { type: "started"; query: string }
  | { type: "plan"; step_count: number }
  | { type: "specialist"; data: SpecialistPayload }
  | { type: "delegate"; count: number }
  | { type: "synthesize"; data: SynthesizePayload }
  | { type: "guardian"; data: GuardianPayload }
  | { type: "final"; data: FinalPayload }
  | { type: "error"; message: string };

function parseSseChunk(buffer: string): { events: QueryStreamEvent[]; rest: string } {
  const events: QueryStreamEvent[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";

  for (const part of parts) {
    if (!part.trim()) continue;
    let eventName = "message";
    let dataLine = "";
    for (const line of part.split("\n")) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataLine = line.slice(5).trim();
    }
    if (!dataLine) continue;
    try {
      const payload = JSON.parse(dataLine) as Record<string, unknown>;
      switch (eventName) {
        case "started":
          events.push({ type: "started", query: String(payload.query ?? "") });
          break;
        case "plan":
          events.push({ type: "plan", step_count: Number(payload.step_count ?? 0) });
          break;
        case "specialist":
          events.push({ type: "specialist", data: payload as unknown as SpecialistPayload });
          break;
        case "delegate":
          events.push({ type: "delegate", count: Number(payload.count ?? 0) });
          break;
        case "synthesize":
          events.push({ type: "synthesize", data: payload as unknown as SynthesizePayload });
          break;
        case "guardian":
          events.push({ type: "guardian", data: payload as unknown as GuardianPayload });
          break;
        case "final":
          events.push({ type: "final", data: payload as unknown as FinalPayload });
          break;
        case "error":
          events.push({ type: "error", message: String(payload.message ?? "Query failed.") });
          break;
        default:
          break;
      }
    } catch {
      // ignore malformed chunks
    }
  }
  return { events, rest };
}

export async function streamQuery(
  query: string,
  onEvent: (event: QueryStreamEvent) => void,
): Promise<void> {
  const token = getAuthToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch("/api/query", {
    method: "POST",
    headers,
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    onEvent({ type: "error", message: "Query failed." });
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onEvent({ type: "error", message: "Query failed." });
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) {
      onEvent(event);
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      onEvent(event);
    }
  }
}
