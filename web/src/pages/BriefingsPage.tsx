import { Grid, Column, Heading } from "@carbon/react";

export function BriefingsPage() {
  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Briefings</Heading>
        <p className="atlas-page-caption">
          Scheduled intelligence reports on the topics you care about.
        </p>
      </Column>
    </Grid>
  );
}
