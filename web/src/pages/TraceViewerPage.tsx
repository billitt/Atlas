import { Grid, Column, Heading } from "@carbon/react";

export function TraceViewerPage() {
  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Trace Viewer</Heading>
        <p className="atlas-page-caption">
          See exactly how any answer was reached, step by step.
        </p>
      </Column>
    </Grid>
  );
}
