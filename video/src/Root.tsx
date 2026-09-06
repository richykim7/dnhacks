import "./captured.css";
import { Composition } from "remotion";
import { CapturedWalkthrough } from "./CapturedWalkthrough";
export const RemotionRoot = () => (
  <Composition
    id="ProductWalkthrough"
    component={CapturedWalkthrough}
    durationInFrames={5100}
    fps={30}
    width={1920}
    height={1080}
  />
);
