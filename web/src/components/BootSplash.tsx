import { Loading } from "@carbon/react";
import { useEffect, useState } from "react";

import { fetchSession } from "@/api-client/client";

interface BootSplashProps {
  onReady: () => void;
}

export function BootSplash({ onReady }: BootSplashProps) {
  const [message, setMessage] = useState("Starting Atlas…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function boot(): Promise<void> {
      // Gate only on the API being reachable (fast — just reads an env var).
      // Ollama / MCP readiness is checked per-feature on the Query page.
      const MAX_ATTEMPTS = 20; // 10 s at 500 ms
      for (let i = 0; i < MAX_ATTEMPTS; i++) {
        if (cancelled) return;
        try {
          await fetchSession();
          if (!cancelled) onReady();
          return;
        } catch {
          if (i === 0) setMessage("Starting Atlas…");
        }
        await new Promise((r) => setTimeout(r, 500));
      }
      if (!cancelled) {
        setError("Cannot reach the Atlas API. Is atlas-api running?");
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
