import {
  Column,
  Grid,
  Heading,
  InlineNotification,
  SkeletonText,
  StructuredListBody,
  StructuredListCell,
  StructuredListHead,
  StructuredListRow,
  StructuredListWrapper,
} from "@carbon/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchBriefings, type BriefingRow } from "@/api-client/client";
import { ConfidenceTag } from "@/components/ConfidenceTag";

export function BriefingsPage() {
  const [rows, setRows] = useState<BriefingRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchBriefings()
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load briefings.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Briefings</Heading>
        <p className="atlas-page-caption">
          Scheduled intelligence reports on the topics you care about.
        </p>
        {error ? (
          <InlineNotification kind="error" title={error} hideCloseButton />
        ) : null}
        {loading ? (
          <SkeletonText heading={false} lineCount={6} />
        ) : rows.length === 0 ? (
          <p className="atlas-tile-body">No briefings recorded yet.</p>
        ) : (
          <StructuredListWrapper>
            <StructuredListHead>
              <StructuredListRow head>
                <StructuredListCell head>When</StructuredListCell>
                <StructuredListCell head>Topic</StructuredListCell>
                <StructuredListCell head>Confidence</StructuredListCell>
                <StructuredListCell head>Trace</StructuredListCell>
              </StructuredListRow>
            </StructuredListHead>
            <StructuredListBody>
              {rows.map((row) => (
                <StructuredListRow key={row.id}>
                  <StructuredListCell>{row.timestamp}</StructuredListCell>
                  <StructuredListCell>
                    <div>{row.query}</div>
                    <div className="atlas-list-sub">{row.summary}</div>
                  </StructuredListCell>
                  <StructuredListCell>
                    <ConfidenceTag level={row.confidence} />
                  </StructuredListCell>
                  <StructuredListCell>
                    {row.trace_id ? (
                      <Link to={`/traces?trace_id=${encodeURIComponent(row.trace_id)}`}>
                        View reasoning
                      </Link>
                    ) : (
                      "—"
                    )}
                  </StructuredListCell>
                </StructuredListRow>
              ))}
            </StructuredListBody>
          </StructuredListWrapper>
        )}
      </Column>
    </Grid>
  );
}
