import { Loader2 } from "lucide-react";
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
      const MAX_ATTEMPTS = 20;
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
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-8">
        <div className="text-3xl font-semibold tracking-tight">Atlas</div>
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-8">
      <div className="text-3xl font-semibold tracking-tight">Atlas</div>
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-label={message} />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
