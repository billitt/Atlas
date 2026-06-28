import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchStatus } from "@/api-client/client";
import { SpecialistTile, SummaryTile } from "@/components/QueryTiles";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useQuery } from "@/contexts/QueryContext";

const SPECIALIST_ORDER: Array<{ key: string; label: string }> = [
  { key: "market", label: "Market" },
  { key: "geopolitical", label: "Geopolitical" },
  { key: "supply_chain", label: "Supply Chain" },
  { key: "research", label: "Filings" },
];

export function QueryPage() {
  const [inputValue, setInputValue] = useState("");
  const [prereqIssues, setPrereqIssues] = useState<string[]>([]);

  const {
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
  } = useQuery();

  useEffect(() => {
    fetchStatus()
      .then((s) => setPrereqIssues(s.ready ? [] : (s.issues ?? [])))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (question) setInputValue(question);
  }, [question]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || running) return;
    startQuery(trimmed);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Query</h1>
      <p className="atlas-page-caption">
      Global business intelligence built to be audited: ask, watch the reasoning, verify the sources.
      </p>

      {prereqIssues.length > 0 ? (
        <Alert className="mb-4 border-amber-600/50">
          <AlertTriangle className="text-amber-500" />
          <AlertTitle>Some services are not ready</AlertTitle>
          <AlertDescription>{prereqIssues.join("; ")}</AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit} className="atlas-query-form">
        <div className="grid gap-2">
          <Label htmlFor="atlas-query-input">Your question</Label>
          <Textarea
            id="atlas-query-input"
            placeholder="What is the semiconductor supply risk if tensions rise in the Taiwan Strait?"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={(event: React.KeyboardEvent<HTMLTextAreaElement>) => {
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
            readOnly={running}
          />
        </div>
        <Button type="submit" disabled={running || !inputValue.trim()}>
          {running ? "Analyzing…" : "Get answer"}
        </Button>
      </form>

      {error ? (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>Could not complete query</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {question && (running || hasResults) ? (
        <div className="mb-4 rounded-md border border-border bg-muted/40 px-4 py-3 text-sm">
          <span className="font-medium text-muted-foreground">Asked: </span>
          <span>{question}</span>
        </div>
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
    </div>
  );
}
