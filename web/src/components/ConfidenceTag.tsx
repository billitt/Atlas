import { Tag } from "@carbon/react";

import type { Confidence } from "@/api-client/client";

const LABELS: Record<Confidence, string> = {
  HIGH: "High confidence",
  MEDIUM: "Medium confidence",
  LOW: "Low confidence",
};

const TYPES: Record<Confidence, "green" | "gray" | "red"> = {
  HIGH: "green",
  MEDIUM: "gray",
  LOW: "red",
};

export function ConfidenceTag({ level }: { level: Confidence | undefined }) {
  if (!level) return null;
  return <Tag type={TYPES[level]} size="md">{LABELS[level]}</Tag>;
}
