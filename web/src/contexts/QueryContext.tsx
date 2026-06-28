/**
 * QueryContext — lifts query state and the SSE stream above the router so that
 * navigating away from the Query page does not abort an in-flight request and
 * does not discard results that have already arrived.
 *
 * The AbortController is recreated only on an explicit new submit, never on
 * page unmount, so the stream survives navigation.
 */

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type { Confidence } from "@/api-client/client";
import type { SpecialistPayload } from "@/api-client/query";
import { streamQuery } from "@/api-client/query";

interface QueryState {
  running: boolean;
  question: string;
  specialists: Record<string, SpecialistPayload>;
  summary: string | undefined;
  confidence: Confidence | undefined;
  passed: boolean | undefined;
  traceId: string | null;
  error: string | null;
  hasResults: boolean;
}

interface QueryContextValue extends QueryState {
  startQuery: (q: string) => void;
  cancelQuery: () => void;
}

const QueryContext = createContext<QueryContextValue | null>(null);

export function QueryProvider({ children }: { children: ReactNode }) {
  const [running, setRunning] = useState(false);
  const [question, setQuestion] = useState("");
  const [specialists, setSpecialists] = useState<Record<string, SpecialistPayload>>({});
  const [summary, setSummary] = useState<string | undefined>();
  const [confidence, setConfidence] = useState<Confidence | undefined>();
  const [passed, setPassed] = useState<boolean | undefined>();
  const [traceId, setTraceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Holds the controller for the current stream so we can abort on new submit.
  const abortRef = useRef<AbortController | null>(null);

  const cancelQuery = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
  }, []);

  const startQuery = useCallback((q: string) => {
    // Abort any in-flight stream before starting a new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // Reset result state for the new question.
    setQuestion(q);
    setSpecialists({});
    setSummary(undefined);
    setConfidence(undefined);
    setPassed(undefined);
    setTraceId(null);
    setError(null);
    setRunning(true);

    void streamQuery(
      q,
      (ev) => {
        if (controller.signal.aborted) return;

        if (ev.type === "specialist") {
          setSpecialists((prev) => ({ ...prev, [ev.data.agent]: ev.data }));
        }
        if (ev.type === "synthesize") {
          setSummary(ev.data.combined_analysis);
          setConfidence(ev.data.confidence);
        }
        if (ev.type === "guardian") {
          setPassed(ev.data.passed);
          if (ev.data.overall_confidence) setConfidence(ev.data.overall_confidence);
        }
        if (ev.type === "final") {
          const briefing = ev.data.briefing;
          setSummary(briefing?.combined_analysis ?? summary);
          setConfidence(ev.data.confidence ?? briefing?.overall_confidence);
          const verdict = ev.data.guardian_verdict ?? briefing?.guardian_verdict;
          if (verdict?.passed !== undefined) setPassed(verdict.passed);
          if (ev.data.trace_id) setTraceId(ev.data.trace_id);
          setRunning(false);
        }
        if (ev.type === "error") {
          setError(ev.message);
          setRunning(false);
        }
      },
      controller.signal,
    ).then(() => {
      if (!controller.signal.aborted) setRunning(false);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const hasResults =
    Object.keys(specialists).length > 0 || summary !== undefined || error !== null;

  return (
    <QueryContext.Provider
      value={{
        running,
        question,
        specialists,
        summary,
        confidence,
        passed,
        traceId,
        error,
        hasResults,
        startQuery,
        cancelQuery,
      }}
    >
      {children}
    </QueryContext.Provider>
  );
}

export function useQuery(): QueryContextValue {
  const ctx = useContext(QueryContext);
  if (!ctx) throw new Error("useQuery must be used within <QueryProvider>");
  return ctx;
}
