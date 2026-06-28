import { Tag } from "@carbon/react";

const SEVERITY_TYPES: Record<string, "red" | "gray" | "green"> = {
  HIGH: "red",
  MEDIUM: "gray",
  LOW: "green",
};

export function SeverityTag({ severity }: { severity: string }) {
  const type = SEVERITY_TYPES[severity.toUpperCase()] ?? "gray";
  return (
    <Tag type={type} size="sm">
      {severity}
    </Tag>
  );
}
