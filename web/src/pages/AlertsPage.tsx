import { Grid, Column, Heading } from "@carbon/react";

export function AlertsPage() {
  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Alerts</Heading>
        <p className="atlas-page-caption">
          Live warnings when market or geopolitical conditions shift.
        </p>
      </Column>
    </Grid>
  );
}
