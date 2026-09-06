import "./index.css";
import { useRef, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { Player, PlayerRef } from "@remotion/player";
import { Walkthrough } from "./Composition";
import { totalFrames, pendingReveal } from "./story";
declare global {
  interface Window {
    seekVideo: (frame: number) => void;
    videoFrame: number;
  }
}
function Preview() {
  const ref = useRef<PlayerRef>(null);
  useEffect(() => {
    window.seekVideo = (frame) => ref.current!.seekTo(frame);
    const onFrame = ({ detail }: { detail: { frame: number } }) => {
      window.videoFrame = detail.frame;
    };
    ref.current!.addEventListener("frameupdate", onFrame);
    window.videoFrame = 0;
    return () => ref.current?.removeEventListener("frameupdate", onFrame);
  }, []);
  return (
    <Player
      ref={ref}
      component={Walkthrough}
      inputProps={{ reveal: pendingReveal }}
      durationInFrames={totalFrames}
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
