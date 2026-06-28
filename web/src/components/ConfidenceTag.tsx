import type { Confidence } from "@/api-client/client";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const LABELS: Record<Confidence, string> = {
  HIGH: "High confidence",
  MEDIUM: "Medium confidence",
  LOW: "Low confidence",
};

const VARIANTS: Record<Confidence, string> = {
  HIGH: "bg-green-600 text-white hover:bg-green-600/90",
  MEDIUM: "bg-yellow-600 text-white hover:bg-yellow-600/90",
  LOW: "bg-red-600 text-white hover:bg-red-600/90",
};

export function ConfidenceTag({ level }: { level: Confidence | undefined }) {
  if (!level) return null;
  return (
    <Badge className={cn(VARIANTS[level])}>{LABELS[level]}</Badge>
  );
}
