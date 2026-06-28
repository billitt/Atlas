import {
  Content,
  Header,
  HeaderContainer,
  HeaderMenuItem,
  HeaderName,
  HeaderNavigation,
} from "@carbon/react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

const NAV_ITEMS = [
  { label: "Query", path: "/" },
  { label: "Briefings", path: "/briefings" },
  { label: "Alerts", path: "/alerts" },
  { label: "Agent Status", path: "/agent-status" },
  { label: "Trace Viewer", path: "/traces" },
] as const;

export function AppShell() {
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
            <HeaderNavigation aria-label="Atlas">
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
          </Header>
          <Content id="main-content">
            <Outlet />
          </Content>
        </>
      )}
    />
  );
}
