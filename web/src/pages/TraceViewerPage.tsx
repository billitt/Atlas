import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  fetchTrace,
  fetchTraces,
  type TraceDetail,
  type TraceListEntry,
} from "@/api-client/client";
import { AtlasLoading } from "@/components/AtlasLoading";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export function TraceViewerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("trace_id") ?? "";

  const [traces, setTraces] = useState<TraceListEntry[]>([]);
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTraces()
      .then((data) => {
        if (!cancelled) setTraces(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load traces.");
      })
      .finally(() => {
        if (!cancelled) setLoadingList(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    setError(null);
    fetchTrace(selectedId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Trace not found or unavailable.");
          setDetail(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const traceOptions = traces.flatMap((entry) =>
    (entry.trace_ids ?? []).map((id) => ({ id, label: `${id} (${entry.filename})` })),
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Trace Viewer</h1>
      <p className="atlas-page-caption">
        See exactly how any answer was reached, step by step.
      </p>
      {loadingList ? (
        <AtlasLoading />
      ) : (
        <div className="mb-4 grid max-w-xl gap-2">
          <Label htmlFor="trace-select">Select a trace</Label>
          <Select
            value={selectedId || undefined}
            onValueChange={(value) => setSearchParams({ trace_id: value })}
          >
            <SelectTrigger id="trace-select" className="w-full">
              <SelectValue placeholder="Choose a trace…" />
            </SelectTrigger>
            <SelectContent>
              {traceOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {error ? (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      ) : null}
      {loadingDetail ? (
        <AtlasLoading />
      ) : detail ? (
        <div className="grid max-w-4xl gap-2">
          <Label htmlFor="trace-tree">Execution steps</Label>
          <Textarea
            id="trace-tree"
            readOnly
            value={detail.tree}
            rows={18}
            className="atlas-trace-output font-mono text-sm"
          />
        </div>
      ) : null}
    </div>
  );
}
