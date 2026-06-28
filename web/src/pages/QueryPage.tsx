import {
  Button,
  Column,
  Form,
  Grid,
  Heading,
  InlineNotification,
  TextArea,
} from "@carbon/react";
import { useEffect, useState } from "react";

import { fetchStatus } from "@/api-client/client";
import { SpecialistTile, SummaryTile } from "@/components/QueryTiles";
import { useQuery } from "@/contexts/QueryContext";

const SPECIALIST_ORDER: Array<{ key: string; label: string }> = [
  { key: "market", label: "Market" },
  { key: "geopolitical", label: "Geopolitical" },
  { key: "supply_chain", label: "Supply Chain" },
  { key: "research", label: "Filings" },
];

export function QueryPage() {
  // Text area value stays local — the user may edit it while a query runs.
  const [inputValue, setInputValue] = useState("");
  const [prereqIssues, setPrereqIssues] = useState<string[]>([]);

  const { running, specialists, summary, confidence, passed, traceId, error, hasResults, startQuery } =
    useQuery();

  // Non-blocking prereq check — only the Query page needs Ollama + MCP.
  useEffect(() => {
    fetchStatus()
      .then((s) => setPrereqIssues(s.ready ? [] : (s.issues ?? [])))
      .catch(() => {});
  }, []);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || running) return;
    startQuery(trimmed);
  };

  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Query</Heading>
        <p className="atlas-page-caption">
          Ask a question about global risk and get a sourced, fact-checked answer.
        </p>

        {prereqIssues.length > 0 ? (
          <InlineNotification
            kind="warning"
            title="Some services are not ready — "
            subtitle={prereqIssues.join("; ")}
            hideCloseButton
          />
        ) : null}

        <Form onSubmit={handleSubmit} className="atlas-query-form">
          <TextArea
            id="atlas-query-input"
            labelText="Your question"
            placeholder="What is the semiconductor supply risk if tensions rise in the Taiwan Strait?"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={(event: React.KeyboardEvent<HTMLTextAreaElement>) => {
              // Enter submits; Shift+Enter inserts a newline; skip during IME
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={3}
            disabled={running}
          />
          <Button type="submit" disabled={running || !inputValue.trim()}>
            {running ? "Analyzing…" : "Get answer"}
          </Button>
        </Form>

        {error ? (
          <InlineNotification
            kind="error"
            title="Could not complete query"
            subtitle={error}
            hideCloseButton
          />
        ) : null}

        {hasResults || running ? (
          <div className="atlas-results-grid">
            {SPECIALIST_ORDER.map((spec) => (
              <SpecialistTile
                key={spec.key}
                label={spec.label}
                data={specialists[spec.key] ?? null}
                loading={running && !specialists[spec.key]}
              />
            ))}
            <SummaryTile
              loading={running && !summary}
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
