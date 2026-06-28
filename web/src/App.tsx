import { useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { BootSplash } from "@/components/BootSplash";
import { AgentStatusPage } from "@/pages/AgentStatusPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { BriefingsPage } from "@/pages/BriefingsPage";
import { QueryPage } from "@/pages/QueryPage";
import { TraceViewerPage } from "@/pages/TraceViewerPage";

export default function App() {
  const [booted, setBooted] = useState(false);

  if (!booted) {
    return <BootSplash onReady={() => setBooted(true)} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<QueryPage />} />
          <Route path="briefings" element={<BriefingsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="agent-status" element={<AgentStatusPage />} />
          <Route path="traces" element={<TraceViewerPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
