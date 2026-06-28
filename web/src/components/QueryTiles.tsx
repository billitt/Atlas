import { SkeletonText, Tag, Tile } from "@carbon/react";
import { Link } from "react-router-dom";

import type { SpecialistPayload } from "@/api-client/query";
import { ConfidenceTag } from "@/components/ConfidenceTag";

interface SpecialistTileProps {
  label: string;
  data: SpecialistPayload | null;
  loading: boolean;
}

function formatSource(source: Record<string, unknown>): string {
  const title = source.title ?? source.name ?? source.symbol ?? source.url;
  if (typeof title === "string") return title;
  return "Source";
}

export function SpecialistTile({ label, data, loading }: SpecialistTileProps) {
  const showSkeleton = loading && !data;

  return (
    <Tile className="atlas-specialist-tile">
      <div className="atlas-tile-header">
        <h3 className="atlas-tile-title">{label}</h3>
        {data?.confidence ? <ConfidenceTag level={data.confidence} /> : null}
      </div>
      {showSkeleton ? (
        <SkeletonText heading={false} lineCount={4} />
      ) : (
        <>
          <p className="atlas-tile-body">{data?.analysis ?? "No analysis returned."}</p>
          {data?.sources && data.sources.length > 0 ? (
            <div className="atlas-sources">
              <span className="atlas-sources-label">Sources</span>
              <ul>
                {data.sources.slice(0, 5).map((source, index) => (
                  <li key={index}>{formatSource(source)}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </Tile>
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
    <Tile className="atlas-summary-tile">
      <div className="atlas-tile-header">
        <h3 className="atlas-tile-title">Summary</h3>
        <div className="atlas-tile-tags">
          {confidence ? <ConfidenceTag level={confidence} /> : null}
          {passed !== undefined ? (
            <Tag type={passed ? "green" : "red"} size="md">
              {passed ? "Fact-check passed" : "Fact-check flagged"}
            </Tag>
          ) : null}
        </div>
      </div>
      {showSkeleton ? (
        <SkeletonText heading={false} lineCount={6} />
      ) : (
        <>
          <p className="atlas-tile-body">{analysis ?? "Summary will appear here."}</p>
          {traceId ? (
            <Link to={`/traces?trace_id=${encodeURIComponent(traceId)}`} className="atlas-reasoning-link">
              View reasoning
            </Link>
          ) : null}
        </>
      )}
    </Tile>
  );
}
