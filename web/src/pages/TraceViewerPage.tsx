import {
  Column,
  Grid,
  Heading,
  InlineNotification,
  Select,
  SelectItem,
  SkeletonText,
  TextArea,
} from "@carbon/react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  fetchTrace,
  fetchTraces,
  type TraceDetail,
  type TraceListEntry,
} from "@/api-client/client";

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
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Trace Viewer</Heading>
        <p className="atlas-page-caption">
          See exactly how any answer was reached, step by step.
        </p>
        {loadingList ? (
          <SkeletonText heading={false} lineCount={2} />
        ) : (
          <Select
            id="trace-select"
            labelText="Select a trace"
            value={selectedId}
            onChange={(event) => {
              const value = event.target.value;
              if (value) setSearchParams({ trace_id: value });
              else setSearchParams({});
            }}
          >
            <SelectItem value="" text="Choose a trace…" />
            {traceOptions.map((option) => (
              <SelectItem key={option.id} value={option.id} text={option.label} />
            ))}
          </Select>
        )}
        {error ? (
          <InlineNotification kind="error" title={error} hideCloseButton />
        ) : null}
        {loadingDetail ? (
          <SkeletonText heading={false} lineCount={10} className="atlas-trace-skeleton" />
        ) : detail ? (
          <TextArea
            id="trace-tree"
            labelText="Execution steps"
            readOnly
            value={detail.tree}
            rows={18}
            className="atlas-trace-output"
          />
        ) : null}
      </Column>
    </Grid>
  );
}
