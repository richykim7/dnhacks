import "./index.css";
import { Composition } from "remotion";
import { Walkthrough } from "./Composition";
import { totalFrames, pendingReveal } from "./story";
export const RemotionRoot = () => (
  <Composition
    id="ProductWalkthrough"
    component={Walkthrough}
    durationInFrames={totalFrames}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={{ reveal: pendingReveal }}
  />
);
