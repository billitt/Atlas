import { Moon, Sun } from "lucide-react";
import { Link, Outlet, useLocation } from "react-router-dom";

import type { AtlasTheme } from "@/App";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Query", path: "/" },
  { label: "Briefings", path: "/briefings" },
  { label: "Alerts", path: "/alerts" },
  { label: "Agent Status", path: "/agent-status" },
  { label: "Trace Viewer", path: "/traces" },
] as const;

interface AppShellProps {
  theme: AtlasTheme;
  onToggleTheme: () => void;
}

export function AppShell({ theme, onToggleTheme }: AppShellProps) {
  const location = useLocation();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link to="/" className="font-semibold tracking-tight">
            Atlas
          </Link>
          <nav className="flex flex-1 gap-1" aria-label="Primary navigation">
            {NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                    isActive && "bg-primary/10 text-primary",
                  )}
                  aria-current={isActive ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleTheme}
            aria-label={theme === "g100" ? "Switch to light theme" : "Switch to dark theme"}
          >
            {theme === "g100" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </div>
      </header>
      <main id="main-content" className="flex-1" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
