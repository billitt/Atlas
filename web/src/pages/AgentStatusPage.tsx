import {
  Column,
  Grid,
  Heading,
  InlineNotification,
  SkeletonText,
  Tag,
  Tile,
} from "@carbon/react";
import { useEffect, useState } from "react";

import { fetchAgents, fetchStatus, type StatusAgent, type StatusResponse } from "@/api-client/client";

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
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Agent Status</Heading>
        <p className="atlas-page-caption">
          The health of the system&apos;s specialists and data sources.
        </p>
        {error ? (
          <InlineNotification kind="error" title={error} lowContrast hideCloseButton />
        ) : null}
        {loading ? (
          <SkeletonText heading={false} lineCount={8} />
        ) : (
          <>
            <div className="atlas-status-grid">
              <Tile>
                <h3 className="atlas-tile-title">Local AI model</h3>
                <Tag type={status?.ollama.model_loaded ? "green" : "red"} size="md">
                  {status?.ollama.model_loaded ? "Ready" : "Not loaded"}
                </Tag>
                <p className="atlas-list-sub">{status?.ollama.model}</p>
              </Tile>
              {status?.mcp_servers.map((server) => (
                <Tile key={server.name}>
                  <h3 className="atlas-tile-title">{server.name}</h3>
                  <Tag type={server.reachable ? "green" : "red"} size="md">
                    {server.reachable ? "Online" : "Offline"}
                  </Tag>
                </Tile>
              ))}
            </div>
            <div className="atlas-status-grid">
              {agents.map((agent) => (
                <Tile key={agent.name}>
                  <h3 className="atlas-tile-title">{agent.name}</h3>
                  <Tag type={agent.reachable ? "green" : "red"} size="md">
                    {agent.reachable ? "Online" : "Offline"}
                  </Tag>
                  {agent.skills.length > 0 ? (
                    <p className="atlas-list-sub">
                      Capabilities: {agent.skills.slice(0, 3).join(", ")}
                    </p>
                  ) : null}
                </Tile>
              ))}
            </div>
          </>
        )}
      </Column>
    </Grid>
  );
}
