import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const SEVERITY_VARIANTS: Record<string, string> = {
  HIGH: "bg-red-600 text-white hover:bg-red-600/90",
  MEDIUM: "bg-yellow-600 text-white hover:bg-yellow-600/90",
  LOW: "bg-green-600 text-white hover:bg-green-600/90",
};

export function SeverityTag({ severity }: { severity: string }) {
  const variant =
    SEVERITY_VARIANTS[severity.toUpperCase()] ??
    "bg-secondary text-secondary-foreground";
  return (
    <Badge className={cn(variant)}>{severity}</Badge>
  );
}
