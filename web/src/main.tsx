import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Theme } from "@carbon/react";

import "@carbon/styles/css/styles.css";
import "@ibm/plex/css/ibm-plex.min.css";

import App from "./App";
import "./theme/index.scss";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Theme theme="g100">
      <App />
    </Theme>
  </StrictMode>,
);
