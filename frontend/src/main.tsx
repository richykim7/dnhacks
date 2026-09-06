import React from "react";
import ReactDOM from "react-dom/client";
import { MotionConfig } from "motion/react";
import "@fontsource-variable/ibm-plex-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "@xyflow/react/dist/style.css";
import "./styles.css";
const cinematic =
  new URLSearchParams(window.location.search).get("demo") === "cinematic";
const Entry = React.lazy(() =>
  cinematic ? import("./demo/CinematicDemo") : import("./App"),
);
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MotionConfig reducedMotion="user">
      <React.Suspense fallback={null}>
        <Entry />
      </React.Suspense>
    </MotionConfig>
  </React.StrictMode>,
);
