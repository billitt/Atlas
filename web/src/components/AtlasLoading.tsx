import { Loader2 } from "lucide-react";

interface AtlasLoadingProps {
  description?: string;
  /** Tighter padding for tile/card inline use. */
  compact?: boolean;
}

export function AtlasLoading({ description = "Loading…", compact = false }: AtlasLoadingProps) {
  return (
    <div
      className={compact ? "atlas-loading atlas-loading--tile" : "atlas-loading"}
      role="status"
      aria-label={description}
    >
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
    </div>
  );
}
