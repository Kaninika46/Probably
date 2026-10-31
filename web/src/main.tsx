/**
 * web/src/main.tsx
 * Application entry point importing self-hosted `@fontsource` fonts (offline-capable)
 * and `tokens.css` design tokens.
 */

import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/bricolage-grotesque/600.css";
import "@fontsource/figtree/400.css";
import "@fontsource/figtree/500.css";
import "@fontsource/figtree/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "./styles/tokens.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
