import { useEffect, useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import SceneInteraction from "../../SceneInteraction";
import * as THREE from "three";

export const spindleMetadata = {
  title: "SPINDLE",
  duration: 18,
  provenance:
    "Curated illustrative animation. No simulated or measured experiment results.",
  seed: 1511,
} as const;

const CYAN = "#67e8f9";
const CORAL = "#fb8c82";
const ease = (a: number, b: number, t: number) => {
  const p = THREE.MathUtils.clamp((t - a) / (b - a), 0, 1);
  return p * p * (3 - 2 * p);
};
const rimVertex = `varying vec3 n; varying vec3 v;
void main(){ vec4 p=modelViewMatrix*vec4(position,1.); n=normalize(normalMatrix*normal); v=normalize(-p.xyz); gl_Position=projectionMatrix*p; }`;
const rimFragment = `varying vec3 n; varying vec3 v; uniform vec3 tint; uniform float strength;
void main(){ float rim=pow(1.-abs(dot(normalize(n),normalize(v))),3.5);
 gl_FragColor=vec4(tint,(.012+rim*.42)*strength); }`;

function Membrane({
  scale,
  strength,
}: {
  scale: [number, number, number];
  strength: number;
}) {
  return (
    <mesh scale={scale} renderOrder={3}>
      <sphereGeometry args={[1, 96, 64]} />
      <shaderMaterial
        transparent
        depthWrite={false}
        vertexShader={rimVertex}
        fragmentShader={rimFragment}
        uniforms={{
          tint: { value: new THREE.Color(CYAN) },
          strength: { value: strength },
        }}
      />
    </mesh>
  );
}

function Spindle({
  time,
  reducedMotion,
}: {
  time: number;
  reducedMotion: boolean;
}) {
  const t = reducedMotion
    ? 15
    : Math.min(18, Math.max(0, Number.isFinite(time) ? time : 0));
  const organize = ease(5, 11, t);
  const highlight = ease(11, 14, t);
  const turn = ease(0, 15, t);
  const glow = useMemo(() => {
    const pixels = new Uint8Array(64 * 64 * 4);
    for (let y = 0; y < 64; y++)
      for (let x = 0; x < 64; x++) {
        const i = (y * 64 + x) * 4;
        const r = Math.hypot((x - 31.5) / 31.5, (y - 31.5) / 31.5);
        pixels[i] = pixels[i + 1] = pixels[i + 2] = 255;
        pixels[i + 3] = Math.round(Math.pow(Math.max(0, 1 - r), 3) * 120);
      }
    const texture = new THREE.DataTexture(pixels, 64, 64);
    texture.needsUpdate = true;
    return texture;
  }, []);
  useEffect(() => () => glow.dispose(), [glow]);
  const fibers = useMemo(() => {
    // Fixed analytic seed: deliberately composed paths, never Cytosim output.
    const result: {
      geometry: THREE.TubeGeometry;
      angle: number;
      side: number;
      index: number;
    }[] = [];
    for (const side of [-1, 1])
      for (let i = 0; i < 34; i++) {
        const angle = i * 2.399963229728653 + 0.1511;
        const radius = 0.48 + (i % 8) * 0.135;
        const y = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius;
        const curve = new THREE.CatmullRomCurve3([
          new THREE.Vector3(side * 2.65, 0, 0),
          new THREE.Vector3(side * 2.04, y * 0.78, z * 0.78),
          new THREE.Vector3(side * 1.06, y * 1.23, z * 1.23),
          new THREE.Vector3(-side * 0.16, y * 0.78, z * 0.78),
        ]);
        result.push({
          geometry: new THREE.TubeGeometry(
            curve,
            48,
            i % 5 === 0 ? 0.017 : 0.009,
            5,
            false,
          ),
          angle,
          side,
          index: i,
        });
      }
    return result;
  }, []);
  useEffect(() => () => fibers.forEach((f) => f.geometry.dispose()), [fibers]);
  return (
    <>
      <ambientLight intensity={0.8} />
      <directionalLight position={[2, 5, 6]} intensity={2.5} color="#c9f6ff" />
      <pointLight position={[0, 0, 3]} intensity={5} color={CORAL} />
      <group rotation={[0.12 + 0.08 * turn, -0.27 + 0.48 * turn, -0.16]}>
        <Membrane scale={[3.88, 2.46, 2.2]} strength={0.68} />
        <Membrane scale={[3.79, 2.39, 2.13]} strength={0.26} />
        <group scale={[0.89 + 0.11 * organize, 1, 1]}>
          {fibers.map((f, i) => (
            <group key={i} rotation={[f.side * (1 - organize) * 0.23, 0, 0]}>
              <mesh geometry={f.geometry} dispose={null}>
                <meshBasicMaterial
                  color={CYAN}
                  transparent
                  opacity={f.index % 5 === 0 ? 0.84 : 0.31 + 0.14 * organize}
                  depthWrite={false}
                />
              </mesh>
              {f.index % 5 === 0 && (
                <mesh
                  geometry={f.geometry}
                  dispose={null}
                  scale={[1, 1.009, 1.009]}
                >
                  <meshBasicMaterial
                    color={CYAN}
                    transparent
                    opacity={0.09 * highlight}
                    blending={THREE.AdditiveBlending}
                    depthWrite={false}
                  />
                </mesh>
              )}
            </group>
          ))}
          {[-1, 1].map((side) => (
            <group key={side} position={[side * 2.65, 0, 0]}>
              <sprite scale={[1.05, 1.05, 1]}>
                <spriteMaterial
                  map={glow}
                  color={CYAN}
                  transparent
                  depthWrite={false}
                  blending={THREE.AdditiveBlending}
                />
              </sprite>
              <mesh>
                <sphereGeometry args={[0.105, 24, 16]} />
                <meshBasicMaterial color="#e2fbff" />
              </mesh>
              {[0.19, 0.29, 0.42].map((r, i) => (
                <mesh key={r}>
                  <sphereGeometry args={[r, 24, 16]} />
                  <shaderMaterial
                    transparent
                    depthWrite={false}
                    blending={THREE.AdditiveBlending}
                    vertexShader={rimVertex}
                    fragmentShader={rimFragment}
                    uniforms={{
                      tint: { value: new THREE.Color(CYAN) },
                      strength: { value: 0.8 / (i + 1) },
                    }}
                  />
                </mesh>
              ))}
              {Array.from({ length: 14 }, (_, i) => {
                const a = i * 2.39996;
                const end = new THREE.Vector3(
                  side * (0.45 + 0.18 * Math.sin(i)),
                  Math.cos(a) * 0.58,
                  Math.sin(a) * 0.58,
                );
                const q = new THREE.Quaternion().setFromUnitVectors(
                  new THREE.Vector3(0, 1, 0),
                  end.clone().normalize(),
                );
                return (
                  <mesh
                    key={i}
                    position={end.clone().multiplyScalar(0.5)}
                    quaternion={q}
                  >
                    <cylinderGeometry args={[0.003, 0.008, end.length(), 5]} />
                    <meshBasicMaterial
                      color={CYAN}
                      transparent
                      opacity={0.26}
                    />
                  </mesh>
                );
              })}
            </group>
          ))}
        </group>
        {Array.from({ length: 7 }, (_, i) => {
          const a = i * 2.39996;
          const y = (i - 3) * 0.28;
          const x = (1 - organize) * Math.sin(i * 3.7) * 1.05;
          return (
            <group
              key={i}
              position={[x, y, Math.sin(a) * 0.37]}
              rotation={[
                0.1 * Math.sin(a),
                0.18 * Math.sin(i),
                0.13 * Math.cos(i),
              ]}
            >
              <sprite scale={[0.8, 0.8, 1]}>
                <spriteMaterial
                  map={glow}
                  color={CORAL}
                  opacity={highlight * 0.65}
                  transparent
                  depthWrite={false}
                  blending={THREE.AdditiveBlending}
                />
              </sprite>
              {[-1, 1].map((side) => (
                <mesh key={side} rotation={[0, 0, side * 0.42]}>
                  <capsuleGeometry args={[0.046, 0.3, 5, 10]} />
                  <meshStandardMaterial
                    color={CORAL}
                    emissive={CORAL}
                    emissiveIntensity={0.22 + 0.5 * highlight}
                    roughness={0.35}
                    metalness={0.12}
                  />
                </mesh>
              ))}
              {[-1, 1].map((side) => (
                <mesh key={side} position={[side * 0.125, 0, 0]}>
                  <sphereGeometry args={[0.029 + 0.012 * highlight, 12, 8]} />
                  <meshBasicMaterial color="#ffe8d9" />
                </mesh>
              ))}
            </group>
          );
        })}
      </group>
    </>
  );
}

/** Parent supplies elapsed seconds; seeking is stateless, reduced motion holds the final tableau. */
export default function SpindleDemo({
  time,
  reducedMotion = false,
  interactive = false,
}: {
  time: number;
  reducedMotion?: boolean;
  interactive?: boolean;
}) {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: interactive ? "transparent" : "#061019",
        position: "relative",
      }}
      role="img"
      aria-label={interactive ? "Spindle assembly simulation" : "Illustrative spindle: cyan microtubules connect two luminous poles around coral chromosomes inside a translucent cell. No experimental result."}
    >
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 11.5], fov: 42 }}
        gl={{ antialias: true, alpha: interactive, preserveDrawingBuffer: true }}
      >
        {!interactive && <color attach="background" args={["#061019"]} />}
        <Spindle time={time} reducedMotion={reducedMotion} />
        {interactive && <SceneInteraction />}
      </Canvas>
    </div>
  );
}
