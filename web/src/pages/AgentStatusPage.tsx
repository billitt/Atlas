import { useEffect, useState } from "react";

import { fetchAgents, fetchStatus, type StatusAgent, type StatusResponse } from "@/api-client/client";
import { AtlasLoading } from "@/components/AtlasLoading";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge className={cn(ok ? "bg-green-600 text-white" : "bg-red-600 text-white")}>
      {label}
    </Badge>
  );
}

export function AgentStatusPage() {
  const [agents, setAgents] = useState<StatusAgent[]>([]);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const [agentData, statusData] = await Promise.all([fetchAgents(), fetchStatus()]);
        if (!cancelled) {
          setAgents(agentData);
          setStatus(statusData);
          setError(null);
        }
      } catch {
        if (!cancelled) setError("Could not load system status.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    poll();
    const timer = window.setInterval(poll, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Agent Status</h1>
      <p className="atlas-page-caption">
        The health of the system&apos;s specialists and data sources.
      </p>
      {error ? (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      ) : null}
      {loading ? (
        <AtlasLoading />
      ) : (
        <>
          <div className="atlas-status-grid">
            <Card>
              <CardHeader className="pb-2">
                <h3 className="atlas-tile-title">Local AI model</h3>
              </CardHeader>
              <CardContent>
                <StatusBadge
                  ok={status?.ollama.model_loaded ?? false}
                  label={status?.ollama.model_loaded ? "Ready" : "Not loaded"}
                />
                <p className="atlas-list-sub">{status?.ollama.model}</p>
              </CardContent>
            </Card>
            {status?.mcp_servers.map((server) => (
              <Card key={server.name}>
                <CardHeader className="pb-2">
                  <h3 className="atlas-tile-title">{server.name}</h3>
                </CardHeader>
                <CardContent>
                  <StatusBadge
                    ok={server.reachable}
                    label={server.reachable ? "Online" : "Offline"}
                  />
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="atlas-status-grid">
            {agents.map((agent) => (
              <Card key={agent.name}>
                <CardHeader className="pb-2">
                  <h3 className="atlas-tile-title">{agent.name}</h3>
                </CardHeader>
                <CardContent>
                  <StatusBadge
                    ok={agent.reachable}
                    label={agent.reachable ? "Online" : "Offline"}
                  />
                  {agent.skills.length > 0 ? (
                    <p className="atlas-list-sub">
                      Capabilities: {agent.skills.slice(0, 3).join(", ")}
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
