import { Loading } from "@carbon/react";
import { useEffect, useState } from "react";

import { fetchSession, fetchStatus } from "@/api-client/client";

function friendlyBootMessage(issues: string[]): string {
  if (issues.length === 0) {
    return "Preparing Atlas…";
  }
  const joined = issues.join(" ").toLowerCase();
  if (joined.includes("ollama") || joined.includes("model")) {
    return "Loading the local AI model…";
  }
  if (joined.includes("mcp-market") || joined.includes("market")) {
    return "Starting the market data service…";
  }
  if (joined.includes("mcp-edgar") || joined.includes("edgar")) {
    return "Starting the filings data service…";
  }
  return issues[0];
}

interface BootSplashProps {
  onReady: () => void;
}

export function BootSplash({ onReady }: BootSplashProps) {
  const [message, setMessage] = useState("Starting Atlas…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    async function boot(): Promise<void> {
      try {
        await fetchSession();
      } catch {
        if (!cancelled) {
          setError("Cannot reach the Atlas API on this machine.");
        }
        return;
      }

      while (!cancelled && attempts < 120) {
        attempts += 1;
        try {
          const status = await fetchStatus();
          if (status.ready) {
            onReady();
            return;
          }
          setMessage(friendlyBootMessage(status.issues));
        } catch {
          setMessage("Waiting for Atlas services…");
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      if (!cancelled) {
        setError("Atlas prerequisites did not become ready. Check Ollama and MCP servers.");
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, [onReady]);

  if (error) {
    return (
      <div className="atlas-boot-screen">
        <div className="atlas-boot-title">Atlas</div>
        <p className="atlas-boot-message">{error}</p>
      </div>
    );
  }

  return (
    <div className="atlas-boot-screen">
      <div className="atlas-boot-title">Atlas</div>
      <Loading withOverlay={false} small={false} description={message} />
      <p className="atlas-boot-message">{message}</p>
    </div>
  );
}
