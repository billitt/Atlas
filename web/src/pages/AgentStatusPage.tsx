import { Grid, Column, Heading } from "@carbon/react";

export function AgentStatusPage() {
  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Agent Status</Heading>
        <p className="atlas-page-caption">
          The health of the system&apos;s specialists and data sources.
        </p>
      </Column>
    </Grid>
  );
}
