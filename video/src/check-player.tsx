import "./captured.css";
import { useRef, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { Player, PlayerRef } from "@remotion/player";
import { CapturedWalkthrough } from "./CapturedWalkthrough";
declare global {
  interface Window {
    seekVideo: (frame: number) => void;
    videoFrame: number;
  }
}
function Preview() {
  const ref = useRef<PlayerRef>(null);
  useEffect(() => {
    window.seekVideo = (f) => ref.current!.seekTo(f);
    const onFrame = ({ detail }: { detail: { frame: number } }) =>
      (window.videoFrame = detail.frame);
    ref.current!.addEventListener("frameupdate", onFrame);
    window.videoFrame = 0;
    return () => ref.current?.removeEventListener("frameupdate", onFrame);
  }, []);
  return (
    <Player
      ref={ref}
      component={CapturedWalkthrough}
      durationInFrames={5100}
      fps={30}
      compositionWidth={1920}
      compositionHeight={1080}
      style={{ width: 1920, height: 1080 }}
      controls={false}
      autoPlay={false}
      acknowledgeRemotionLicense
    />
  );
}
createRoot(document.getElementById("root")!).render(<Preview />);
