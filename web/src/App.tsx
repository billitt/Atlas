import { useCallback, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Theme } from "@carbon/react";

import { AppShell } from "@/components/AppShell";
import { BootSplash } from "@/components/BootSplash";
import { AgentStatusPage } from "@/pages/AgentStatusPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { BriefingsPage } from "@/pages/BriefingsPage";
import { QueryPage } from "@/pages/QueryPage";
import { TraceViewerPage } from "@/pages/TraceViewerPage";

export type AtlasTheme = "g100" | "g10";

function readStoredTheme(): AtlasTheme {
  const stored = localStorage.getItem("atlas-theme");
  return stored === "g10" ? "g10" : "g100";
}

export default function App() {
  const [booted, setBooted] = useState(false);
  const [theme, setTheme] = useState<AtlasTheme>(readStoredTheme);

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next: AtlasTheme = current === "g100" ? "g10" : "g100";
      localStorage.setItem("atlas-theme", next);
      return next;
    });
  }, []);

  if (!booted) {
    return (
      <Theme theme="g100">
        <BootSplash onReady={() => setBooted(true)} />
      </Theme>
    );
  }

  return (
    <Theme theme={theme}>
      <a href="#main-content" className="atlas-skip-link">
        Skip to main content
      </a>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell theme={theme} onToggleTheme={toggleTheme} />}>
            <Route index element={<QueryPage />} />
            <Route path="briefings" element={<BriefingsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="agent-status" element={<AgentStatusPage />} />
            <Route path="traces" element={<TraceViewerPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </Theme>
  );
}
