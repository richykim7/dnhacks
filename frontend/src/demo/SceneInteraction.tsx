import { OrbitControls } from "@react-three/drei";

/** Camera interaction is opt-in; the caller suspends choreography on first input. */
export default function SceneInteraction({
  onStart,
}: {
  onStart?: () => void;
}) {
  return (
    <OrbitControls
      makeDefault
      enablePan
      enableZoom
      enableRotate
      enableDamping={false}
      minDistance={2}
      maxDistance={80}
      onStart={onStart}
    />
  );
}
