import {
  Content,
  Header,
  HeaderContainer,
  HeaderGlobalAction,
  HeaderMenuItem,
  HeaderName,
  HeaderNavigation,
} from "@carbon/react";
import { Asleep, Light } from "@carbon/icons-react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import type { AtlasTheme } from "@/App";

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
  const navigate = useNavigate();

  return (
    <HeaderContainer
      render={() => (
        <>
          <Header aria-label="Atlas">
            <HeaderName href="/" prefix="">
              Atlas
            </HeaderName>
            <HeaderNavigation aria-label="Primary navigation">
              {NAV_ITEMS.map((item) => (
                <HeaderMenuItem
                  key={item.path}
                  isActive={location.pathname === item.path}
                  onClick={() => navigate(item.path)}
                >
                  {item.label}
                </HeaderMenuItem>
              ))}
            </HeaderNavigation>
            <HeaderGlobalAction
              aria-label={theme === "g100" ? "Switch to light theme" : "Switch to dark theme"}
              onClick={onToggleTheme}
              tooltipAlignment="end"
            >
              {theme === "g100" ? <Light size={20} /> : <Asleep size={20} />}
            </HeaderGlobalAction>
          </Header>
          <Content id="main-content" tabIndex={-1}>
            <Outlet />
          </Content>
        </>
      )}
    />
  );
}
