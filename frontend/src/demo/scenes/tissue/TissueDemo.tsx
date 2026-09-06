import { useLayoutEffect, useMemo } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { CatmullRomCurve3, Color, DoubleSide, Vector3 } from "three";

export const tissueDemoMetadata = {
  title: "A living neighborhood",
  provenance:
    "Curated illustrative animation; synthetic local geometry, not a simulated experiment result.",
  duration: 18,
  seed: 1409,
} as const;

export interface TissueDemoProps {
  time: number;
  reducedMotion?: boolean;
}
const cyan = "#67e8f9";
const coral = "#fb8c82";
const smooth = (a: number, b: number, t: number) => {
  const x = Math.max(0, Math.min(1, (t - a) / (b - a)));
  return x * x * (3 - 2 * x);
};
// Explicit local seed. Never reads the clock or a backend.
function seeded(seed: number) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}
const rand = seeded(tissueDemoMetadata.seed);
const cells = Array.from({ length: 67 }, (_, i) => {
  const angle = i * 2.39996323;
  const radius = Math.sqrt(i / 67);
  const x = Math.cos(angle) * radius * 5.8;
  const y = Math.sin(angle) * radius * 3.7;
  return {
    position: [x, y, (rand() - 0.5) * 2.6] as [number, number, number],
    radius: 0.39 + rand() * 0.18,
    phase: rand() * 6.28,
    selected: x > 0.2 && x < 3.1 && y > -0.9 && y < 1.7,
  };
});
const fibers = Array.from(
  { length: 13 },
  (_, i) =>
    new CatmullRomCurve3(
      Array.from({ length: 9 }, (_, j) => {
        const x = -7 + j * 1.75;
        return new Vector3(
          x,
          -4.4 + i * 0.73 + Math.sin(x * 0.52 + i * 0.67) * 0.5,
          -1.6 + Math.cos(x * 0.6 + i) * 0.45,
        );
      }),
    ),
);
const vertexShader = `varying vec3 vN; varying vec3 vV;
void main(){ vec4 p=modelViewMatrix*vec4(position,1.); vN=normalize(normalMatrix*normal); vV=normalize(-p.xyz); gl_Position=projectionMatrix*p; }`;
const fragmentShader = `varying vec3 vN; varying vec3 vV; uniform vec3 tint; uniform float strength;
void main(){ float rim=pow(1.-abs(dot(normalize(vN),normalize(vV))),2.5);
float light=.35+.65*max(dot(normalize(vN),normalize(vec3(-.5,.8,1.))),0.);
gl_FragColor=vec4(tint*(.65+rim*.65+light*.2),(.035+rim*.53)*strength);
#include <colorspace_fragment>
}`;
function Membrane({
  color,
  strength = 1,
}: {
  color: string;
  strength?: number;
}) {
  const uniforms = useMemo(
    () => ({
      tint: { value: new Color(color) },
      strength: { value: strength },
    }),
    [color, strength],
  );
  return (
    <shaderMaterial
      vertexShader={vertexShader}
      fragmentShader={fragmentShader}
      uniforms={uniforms}
      transparent
      depthWrite={false}
    />
  );
}
function Camera({ time, reducedMotion }: TissueDemoProps) {
  const { camera, invalidate } = useThree();
  useLayoutEffect(() => {
    const t = reducedMotion ? 15 : time;
    const approach = smooth(5, 11, t);
    const orbit = Math.min(t, 15) * 0.018 - 0.14;
    const distance = 17.8 - approach * 2.3;
    camera.position.set(
      Math.sin(orbit) * distance + approach * 0.8,
      1.8 - approach * 0.8,
      Math.cos(orbit) * distance,
    );
    camera.lookAt(approach * 0.9, approach * 0.22, 0);
    camera.updateProjectionMatrix();
    invalidate();
  }, [camera, invalidate, time, reducedMotion]);
  return null;
}
function Neighborhood({ time, reducedMotion }: TissueDemoProps) {
  const t = reducedMotion ? 15 : time;
  const highlight = smooth(8, 13, t);
  const interaction = smooth(11, 15, t);
  return (
    <>
      <Camera time={t} reducedMotion={reducedMotion} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[-4, 7, 9]} intensity={2} color="#c4f5ff" />
      <pointLight position={[6, -1, 4]} intensity={16} color={coral} />
      <group rotation={[0.07, -0.08, -0.12]}>
        {fibers.map((curve, i) => (
          <mesh key={`fiber-${i}`}>
            <tubeGeometry
              args={[curve, 64, 0.012 + (i % 3) * 0.005, 5, false]}
            />
            <meshBasicMaterial
              color={i % 4 === 0 ? coral : cyan}
              transparent
              opacity={i % 4 === 0 ? 0.21 : 0.12}
              depthWrite={false}
            />
          </mesh>
        ))}
        {cells.map((cell, i) => (
          <group
            key={i}
            position={cell.position}
            rotation={[cell.phase, cell.phase * 0.3, cell.phase * 0.5]}
            scale={[
              cell.radius,
              cell.radius * (1.1 + Math.sin(cell.phase) * 0.1),
              cell.radius,
            ]}
          >
            <mesh>
              <sphereGeometry args={[1, 28, 20]} />
              <Membrane
                color={cyan}
                strength={
                  cell.selected ? 1 + highlight * 0.75 : 0.86 - highlight * 0.15
                }
              />
            </mesh>
            <mesh scale={0.46} position={[0.07, -0.02, 0.02]}>
              <sphereGeometry args={[1, 18, 12]} />
              <meshStandardMaterial
                color={cell.selected ? cyan : "#289cae"}
                emissive={cyan}
                emissiveIntensity={
                  cell.selected ? 0.13 + highlight * 0.35 : 0.13
                }
                roughness={0.38}
                transparent
                opacity={cell.selected ? 0.4 + highlight * 0.3 : 0.4}
                depthWrite={false}
              />
            </mesh>
            <mesh scale={0.83}>
              <sphereGeometry args={[1, 20, 14]} />
              <Membrane color={cyan} strength={0.23} />
            </mesh>
          </group>
        ))}
        {Array.from({ length: 10 }, (_, i) => {
          const a = i * 2.399;
          const x = Math.cos(a) * (4.1 + (i % 2) * 0.8);
          const y = Math.sin(a) * 2.8;
          return (
            <group
              key={`stroma-${i}`}
              position={[x - interaction * 0.17, y, 0.7 + Math.sin(i) * 0.8]}
              rotation={[0, 0.2, a + 0.65]}
            >
              <mesh scale={[1.0, 0.23, 0.29]}>
                <sphereGeometry args={[1, 28, 16]} />
                <Membrane color={coral} strength={1.2} />
              </mesh>
              <mesh scale={[0.28, 0.115, 0.14]}>
                <sphereGeometry args={[1, 16, 12]} />
                <meshStandardMaterial
                  color={coral}
                  emissive={coral}
                  emissiveIntensity={0.25}
                  transparent
                  opacity={0.75}
                />
              </mesh>
            </group>
          );
        })}
        {/* A quiet translucent lens identifies a curated population, not a measured field. */}
        <mesh position={[1.55, 0.38, -0.25]} scale={[2.1, 1.65, 0.75]}>
          <sphereGeometry args={[1, 40, 24]} />
          <Membrane color={cyan} strength={highlight * 0.28} />
        </mesh>
        {[0, 1, 2].map((i) => (
          <mesh
            key={`layer-${i}`}
            position={[0, 0, -2.2 - i * 0.32]}
            scale={[7.3 - i * 0.25, 4.6 - i * 0.2, 0.5]}
          >
            <sphereGeometry args={[1, 48, 24]} />
            <meshBasicMaterial
              color={cyan}
              transparent
              opacity={0.015}
              side={DoubleSide}
              depthWrite={false}
            />
          </mesh>
        ))}
      </group>
    </>
  );
}
export default function TissueDemo({
  time,
  reducedMotion = false,
}: TissueDemoProps) {
  const t = Number.isFinite(time) ? Math.max(0, Math.min(18, time)) : 0;
  return (
    <div
      data-provenance="illustrative"
      aria-label="Illustrative tumor and stroma neighborhood"
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        background: "#061019",
        overflow: "hidden",
      }}
    >
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        camera={{ fov: 39, near: 0.1, far: 80 }}
        gl={{ antialias: true, alpha: false }}
        onCreated={({ gl }) => gl.setClearColor("#061019")}
      >
        <Neighborhood time={t} reducedMotion={reducedMotion} />
      </Canvas>
      <div
        style={{
          position: "absolute",
          left: "7%",
          bottom: "9%",
          color: "#e5f3f5",
          font: "400 clamp(12px,1vw,18px)/1.5 system-ui",
          letterSpacing: ".03em",
          pointerEvents: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              background: cyan,
              width: 5,
              height: 5,
              borderRadius: "50%",
            }}
          />
          Tumor neighborhood
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            opacity: 0.7,
            marginTop: 6,
          }}
        >
          <span
            style={{
              background: coral,
              width: 5,
              height: 5,
              borderRadius: "50%",
            }}
          />
          Surrounding stroma
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: "7%",
          bottom: "9%",
          color: "#b6d4da",
          font: "400 clamp(10px,.75vw,14px)/1.5 system-ui",
          letterSpacing: ".14em",
          opacity: 0.55,
          pointerEvents: "none",
        }}
      >
        ILLUSTRATIVE · NOT A SIMULATION
      </div>
    </div>
  );
}
