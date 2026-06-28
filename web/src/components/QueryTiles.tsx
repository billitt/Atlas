import { Link } from "react-router-dom";

import type { SourceItem, SpecialistPayload } from "@/api-client/query";
import { AtlasLoading } from "@/components/AtlasLoading";
import { ConfidenceTag } from "@/components/ConfidenceTag";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface SpecialistTileProps {
  label: string;
  data: SpecialistPayload | null;
  loading: boolean;
}

function SourceList({ sources }: { sources?: SourceItem[] }) {
  if (!sources || sources.length === 0) {
    return <p className="atlas-sources-empty">No sources for this query.</p>;
  }
  return (
    <div className="atlas-sources">
      <span className="atlas-sources-label">Sources</span>
      <ul>
        {sources.slice(0, 6).map((source, index) => (
          <li key={index}>
            {source.url ? (
              <a href={source.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                {source.label}
              </a>
            ) : (
              source.label
            )}
            {source.detail ? (
              <span className="atlas-source-detail"> · {source.detail}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SpecialistTile({ label, data, loading }: SpecialistTileProps) {
  const showSkeleton = loading && !data;

  return (
    <Card className="atlas-specialist-tile">
      <CardHeader className="atlas-tile-header pb-2">
        <h3 className="atlas-tile-title">{label}</h3>
        {data?.confidence ? <ConfidenceTag level={data.confidence} /> : null}
      </CardHeader>
      <CardContent>
        {showSkeleton ? (
          <AtlasLoading compact />
        ) : (
          <>
            <p className="atlas-tile-body">{data?.analysis ?? "No analysis returned."}</p>
            {data ? <SourceList sources={data.sources} /> : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface SummaryTileProps {
  loading: boolean;
  analysis?: string;
  confidence?: SpecialistPayload["confidence"];
  passed?: boolean;
  traceId?: string | null;
}

export function SummaryTile({
  loading,
  analysis,
  confidence,
  passed,
  traceId,
}: SummaryTileProps) {
  const showSkeleton = loading && !analysis;

  return (
    <Card className="atlas-summary-tile">
      <CardHeader className="atlas-tile-header pb-2">
        <h3 className="atlas-tile-title">Summary</h3>
        <div className="atlas-tile-tags">
          {confidence ? <ConfidenceTag level={confidence} /> : null}
          {passed !== undefined ? (
            <Badge className={cn(passed ? "bg-green-600 text-white" : "bg-red-600 text-white")}>
              {passed ? "Fact-check passed" : "Fact-check flagged"}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {showSkeleton ? (
          <AtlasLoading compact />
        ) : (
          <>
            <p className="atlas-tile-body">{analysis ?? "Summary will appear here."}</p>
            {traceId ? (
              <Link
                to={`/traces?trace_id=${encodeURIComponent(traceId)}`}
                className="atlas-reasoning-link text-primary hover:underline"
              >
                View reasoning
              </Link>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
