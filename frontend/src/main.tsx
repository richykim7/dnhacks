import React from "react";
import ReactDOM from "react-dom/client";
import { MotionConfig } from "motion/react";
import "@fontsource-variable/ibm-plex-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import App from "./App";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </React.StrictMode>,
);
