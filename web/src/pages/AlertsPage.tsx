import { useCallback, useEffect, useState } from "react";

import {
  checkAlerts,
  fetchAlerts,
  type AlertRule,
  type AlertRow,
} from "@/api-client/client";
import { AtlasLoading } from "@/components/AtlasLoading";
import { SeverityTag } from "@/components/SeverityTag";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [recent, setRecent] = useState<AlertRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkMessage, setCheckMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchAlerts()
      .then((data) => {
        setRules(data.rules);
        setRecent(data.recent);
        setError(null);
      })
      .catch(() => setError("Could not load alerts."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCheck = async () => {
    setChecking(true);
    setCheckMessage(null);
    try {
      const triggered = await checkAlerts();
      setCheckMessage(
        triggered.length
          ? `${triggered.length} alert(s) triggered.`
          : "No alerts triggered.",
      );
      load();
    } catch {
      setCheckMessage("Alert check failed.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
      <p className="atlas-page-caption">
        Live warnings when market or geopolitical conditions shift.
      </p>
      <div className="atlas-inline-actions">
        <Button onClick={handleCheck} disabled={checking}>
          {checking ? "Checking…" : "Check now"}
        </Button>
      </div>
      {checkMessage ? (
        <Alert className="mb-4">
          <AlertTitle>{checkMessage}</AlertTitle>
        </Alert>
      ) : null}
      {error ? (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      ) : null}
      {loading ? (
        <AtlasLoading />
      ) : (
        <>
          <Card className="atlas-section-tile mb-4">
            <CardHeader className="pb-2">
              <h3 className="atlas-tile-title">Active rules</h3>
            </CardHeader>
            <CardContent className="divide-y">
              {rules.map((rule) => (
                <div key={rule.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="atlas-alert-rule">
                    <SeverityTag severity={rule.severity} />
                    <strong>{rule.name}</strong>
                  </div>
                  <div className="atlas-list-sub">{rule.description}</div>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card className="atlas-section-tile">
            <CardHeader className="pb-2">
              <h3 className="atlas-tile-title">Recent alerts</h3>
            </CardHeader>
            <CardContent>
              {recent.length === 0 ? (
                <p className="atlas-tile-body">No recent alerts.</p>
              ) : (
                <div className="divide-y">
                  {recent.map((row) => (
                    <div key={row.id} className="py-3 first:pt-0 last:pb-0">
                      <div className="atlas-alert-rule">
                        <SeverityTag severity={row.severity} />
                        <span>{row.timestamp}</span>
                      </div>
                      <div>{row.rule_name}</div>
                      <div className="atlas-list-sub">{row.summary}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
