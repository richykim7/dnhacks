import { createRoot } from "react-dom/client";
import { useEffect, useState } from "react";
import TissueDemo from "./TissueDemo";
declare global {
  interface Window {
    setTissueTime: (seconds: number) => void;
  }
}
function Preview() {
  const query = new URLSearchParams(location.search);
  const [time, setTime] = useState(Number(query.get("time") ?? 13));
  useEffect(() => {
    window.setTissueTime = setTime;
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
  return <TissueDemo time={time} reducedMotion={query.has("reducedMotion")} />;
}
createRoot(document.getElementById("root")!).render(<Preview />);
