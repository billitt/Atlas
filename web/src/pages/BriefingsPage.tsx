import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchBriefings, type BriefingRow } from "@/api-client/client";
import { AtlasLoading } from "@/components/AtlasLoading";
import { ConfidenceTag } from "@/components/ConfidenceTag";
import { Alert, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
    <div className="mx-auto max-w-7xl px-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Briefings</h1>
      <p className="atlas-page-caption">
        Scheduled intelligence reports on the topics you care about.
      </p>
      {error ? (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      ) : null}
      {loading ? (
        <AtlasLoading />
      ) : rows.length === 0 ? (
        <p className="atlas-tile-body">No briefings recorded yet.</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Topic</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Trace</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.timestamp}</TableCell>
                  <TableCell>
                    <div>{row.query}</div>
                    <div className="atlas-list-sub">{row.summary}</div>
                  </TableCell>
                  <TableCell>
                    <ConfidenceTag level={row.confidence} />
                  </TableCell>
                  <TableCell>
                    {row.trace_id ? (
                      <Link
                        to={`/traces?trace_id=${encodeURIComponent(row.trace_id)}`}
                        className="text-primary hover:underline"
                      >
                        View reasoning
                      </Link>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
