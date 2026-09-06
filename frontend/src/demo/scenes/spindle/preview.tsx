import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import SpindleDemo from "./SpindleDemo";
function Preview() {
  const query = new URLSearchParams(location.search);
  const [time, setTime] = useState(Number(query.get("time") ?? 14));
  useEffect(() => {
    if (!query.has("play")) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      setTime(Math.min(18, (now - start) / 1000));
      if (now - start < 18000) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);
  return (
    <main
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <SpindleDemo time={time} reducedMotion={query.has("reducedMotion")} />
      <header
        style={{
          position: "absolute",
          top: "7%",
          left: "6%",
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            fontSize: 12,
            letterSpacing: 4,
            color: "#67e8f9",
            marginBottom: 18,
          }}
        >
          CELLULAR CHOREOGRAPHY
        </div>
        <div style={{ fontSize: 48, fontWeight: 300, letterSpacing: 9 }}>
          SPINDLE
        </div>
        <div style={{ fontSize: 15, marginTop: 17, color: "#a4bbc6" }}>
          Order emerges between two poles.
        </div>
      </header>
      <footer
        style={{
          position: "absolute",
          bottom: "6%",
          left: "6%",
          right: "6%",
          display: "flex",
          justifyContent: "space-between",
          fontSize: 12,
          letterSpacing: 2,
          color: "#a4bbc6",
          pointerEvents: "none",
        }}
      >
        <span>CURATED ILLUSTRATION / NO EXPERIMENTAL OUTPUT</span>
        <span>MICROTUBULE ORGANIZATION</span>
      </footer>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<Preview />);
