import {
  Button,
  Column,
  Form,
  Grid,
  Heading,
  InlineNotification,
  TextArea,
} from "@carbon/react";
import { useCallback, useState } from "react";

import type { SpecialistPayload } from "@/api-client/query";
import { streamQuery } from "@/api-client/query";
import { SpecialistTile, SummaryTile } from "@/components/QueryTiles";

const SPECIALIST_ORDER: Array<{ key: string; label: string }> = [
  { key: "market", label: "Market" },
  { key: "geopolitical", label: "Geopolitical" },
  { key: "supply_chain", label: "Supply Chain" },
  { key: "research", label: "Filings" },
];

export function QueryPage() {
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [specialists, setSpecialists] = useState<Record<string, SpecialistPayload | null>>({});
  const [summary, setSummary] = useState<string | undefined>();
  const [confidence, setConfidence] = useState<SpecialistPayload["confidence"]>();
  const [passed, setPassed] = useState<boolean | undefined>();
  const [traceId, setTraceId] = useState<string | null>(null);

  const resetResults = useCallback(() => {
    setSpecialists({});
    setSummary(undefined);
    setConfidence(undefined);
    setPassed(undefined);
    setTraceId(null);
    setError(null);
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || running) return;

    resetResults();
    setRunning(true);

    await streamQuery(trimmed, (streamEvent) => {
      if (streamEvent.type === "specialist") {
        const agent = streamEvent.data.agent;
        setSpecialists((prev) => ({ ...prev, [agent]: streamEvent.data }));
      }
      if (streamEvent.type === "synthesize") {
        setSummary(streamEvent.data.combined_analysis);
        setConfidence(streamEvent.data.confidence);
      }
      if (streamEvent.type === "guardian") {
        setPassed(streamEvent.data.passed);
        if (streamEvent.data.overall_confidence) {
          setConfidence(streamEvent.data.overall_confidence);
        }
      }
      if (streamEvent.type === "final") {
        const briefing = streamEvent.data.briefing;
        setSummary(briefing?.combined_analysis);
        setConfidence(streamEvent.data.confidence ?? briefing?.overall_confidence);
        const verdict = streamEvent.data.guardian_verdict ?? briefing?.guardian_verdict;
        if (verdict?.passed !== undefined) setPassed(verdict.passed);
        if (streamEvent.data.trace_id) setTraceId(streamEvent.data.trace_id);
        setRunning(false);
      }
      if (streamEvent.type === "error") {
        setError(streamEvent.message);
        setRunning(false);
      }
    });

    setRunning(false);
  };

  const showResults = running || Object.keys(specialists).length > 0 || summary || error;

  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Query</Heading>
        <p className="atlas-page-caption">
          Ask a question about global risk and get a sourced, fact-checked answer.
        </p>

        <Form onSubmit={handleSubmit} className="atlas-query-form">
          <TextArea
            id="atlas-query-input"
            labelText="Your question"
            placeholder="What is the semiconductor supply risk if tensions rise in the Taiwan Strait?"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={3}
            disabled={running}
          />
          <Button type="submit" disabled={running || !question.trim()}>
            {running ? "Analyzing…" : "Get answer"}
          </Button>
        </Form>

        {error ? (
          <InlineNotification
            kind="error"
            title="Could not complete query"
            subtitle={error}
            lowContrast
            hideCloseButton
          />
        ) : null}

        {showResults ? (
          <div className="atlas-results-grid">
            {SPECIALIST_ORDER.map((spec) => (
              <SpecialistTile
                key={spec.key}
                label={spec.label}
                data={specialists[spec.key] ?? null}
                loading={running}
              />
            ))}
            <SummaryTile
              loading={running}
              analysis={summary}
              confidence={confidence}
              passed={passed}
              traceId={traceId}
            />
          </div>
        ) : null}
      </Column>
    </Grid>
  );
}
