import {
  Button,
  Column,
  Grid,
  Heading,
  InlineNotification,
  SkeletonText,
  StructuredListBody,
  StructuredListCell,
  StructuredListRow,
  StructuredListWrapper,
  Tag,
  Tile,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  checkAlerts,
  fetchAlerts,
  type AlertRule,
  type AlertRow,
} from "@/api-client/client";

function severityTag(severity: string) {
  const type = severity === "HIGH" ? "red" : severity === "MEDIUM" ? "gray" : "green";
  return <Tag type={type} size="sm">{severity}</Tag>;
}

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
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Alerts</Heading>
        <p className="atlas-page-caption">
          Live warnings when market or geopolitical conditions shift.
        </p>
        <div className="atlas-inline-actions">
          <Button kind="primary" onClick={handleCheck} disabled={checking}>
            {checking ? "Checking…" : "Check now"}
          </Button>
        </div>
        {checkMessage ? (
          <InlineNotification
            kind="info"
            title={checkMessage}
            lowContrast
            hideCloseButton
          />
        ) : null}
        {error ? (
          <InlineNotification kind="error" title={error} lowContrast hideCloseButton />
        ) : null}
        {loading ? (
          <SkeletonText heading={false} lineCount={6} />
        ) : (
          <>
            <Tile className="atlas-section-tile">
              <h3 className="atlas-tile-title">Active rules</h3>
              <StructuredListWrapper>
                <StructuredListBody>
                  {rules.map((rule) => (
                    <StructuredListRow key={rule.id}>
                      <StructuredListCell>
                        <div className="atlas-alert-rule">
                          {severityTag(rule.severity)}
                          <strong>{rule.name}</strong>
                        </div>
                        <div className="atlas-list-sub">{rule.description}</div>
                      </StructuredListCell>
                    </StructuredListRow>
                  ))}
                </StructuredListBody>
              </StructuredListWrapper>
            </Tile>
            <Tile className="atlas-section-tile">
              <h3 className="atlas-tile-title">Recent alerts</h3>
              {recent.length === 0 ? (
                <p className="atlas-tile-body">No recent alerts.</p>
              ) : (
                <StructuredListWrapper>
                  <StructuredListBody>
                    {recent.map((row) => (
                      <StructuredListRow key={row.id}>
                        <StructuredListCell>
                          <div className="atlas-alert-rule">
                            {severityTag(row.severity)}
                            <span>{row.timestamp}</span>
                          </div>
                          <div>{row.rule_name}</div>
                          <div className="atlas-list-sub">{row.summary}</div>
                        </StructuredListCell>
                      </StructuredListRow>
                    ))}
                  </StructuredListBody>
                </StructuredListWrapper>
              )}
            </Tile>
          </>
        )}
      </Column>
    </Grid>
  );
}
