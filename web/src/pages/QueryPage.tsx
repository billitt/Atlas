import { Grid, Column, Heading } from "@carbon/react";

export function QueryPage() {
  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <Heading>Query</Heading>
        <p className="atlas-page-caption">
          Ask a question about global risk and get a sourced, fact-checked answer.
        </p>
      </Column>
    </Grid>
  );
}
