import { useLayoutEffect, useMemo } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import * as THREE from 'three';

export const binderDemoMetadata = {
  title: 'Protein–binder docking',
  provenance: 'Illustrative seeded ribbon geometry and choreographed docking. Not an experimental structure, simulation, prediction, or binding result.',
  seed: 1207,
  durationSeconds: 18,
} as const;
export interface BinderDemoProps { time: number; reducedMotion?: boolean }
const cyan = '#67e8f9';
const coral = '#fb8c82';
const smooth = (a: number, b: number, t: number) => {
  const x = THREE.MathUtils.clamp((t - a) / (b - a), 0, 1);
  return x * x * x * (x * (x * 6 - 15) + 10);
};
const v = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
const curve = (points: THREE.Vector3[]) => new THREE.CatmullRomCurve3(points, false, 'centripetal');

// A thick ribbon has lit front/side/back faces: no global transparent blob.
function ribbon(path: THREE.CatmullRomCurve3, width: number, steps = 180) {
  const frames = path.computeFrenetFrames(steps, false);
  const points = path.getPoints(steps);
  const positions: number[] = [], indices: number[] = [];
  for (let i = 0; i <= steps; i++) {
    const taper = Math.min(1, .35 + Math.min(i, steps - i) / 7);
    for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      const p = points[i].clone().addScaledVector(frames.normals[i], a * width * taper / 2)
        .addScaledVector(frames.binormals[i], b * .027);
      positions.push(p.x, p.y, p.z);
    }
    if (i < steps) for (let j = 0; j < 4; j++) {
      const a = i * 4 + j, b = i * 4 + (j + 1) % 4;
      indices.push(a, b, a + 4, b, b + 4, a + 4);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}
function helix(center: THREE.Vector3, axis: THREE.Vector3, length: number, radius: number, turns: number) {
  axis.normalize();
  const u = v(0, 1, 0).cross(axis).normalize();
  const w = axis.clone().cross(u).normalize();
  return curve(Array.from({ length: 121 }, (_, i) => {
    const f = i / 120, a = f * Math.PI * 2 * turns;
    return center.clone().addScaledVector(axis, (f - .5) * length)
      .addScaledVector(u, radius * Math.cos(a)).addScaledVector(w, radius * Math.sin(a));
  }));
}
function Ribbon({ path, color, width = .26 }: { path: THREE.CatmullRomCurve3; color: string; width?: number }) {
  const geometry = useMemo(() => ribbon(path, width), [path, width]);
  return <mesh geometry={geometry}>
    <meshStandardMaterial color={color} metalness={.36} roughness={.29} emissive={color} emissiveIntensity={.035} side={THREE.DoubleSide} />
  </mesh>;
}
function Trace({ path, color, radius = .033, glow = 0 }: { path: THREE.CatmullRomCurve3; color: string; radius?: number; glow?: number }) {
  const geometry = useMemo(() => new THREE.TubeGeometry(path, 100, radius, 7, false), [path, radius]);
  return <mesh geometry={geometry}><meshStandardMaterial color={color} emissive={color} emissiveIntensity={glow} roughness={.35} /></mesh>;
}

function Target() {
  const folds = useMemo(() => Array.from({ length: 9 }, (_, i) => {
    const a = (.29 + i * .1775) * Math.PI;
    return helix(v(1.4 * Math.cos(a), 1.65 * Math.sin(a), .16 * Math.sin(i * 1207)),
      v(-.65 * Math.sin(a), .65 * Math.cos(a), .75), 1.5, .27, 3.2);
  }), []);
  const sheets = useMemo(() => [-.48, -.12, .24].map(z => curve(Array.from({ length: 65 }, (_, i) => {
    const a = (.25 + i / 64 * 1.5) * Math.PI;
    return v(.92 * Math.cos(a), 1.02 * Math.sin(a), z + .12 * Math.cos(a * 2));
  }))), []);
  const loops = useMemo(() => folds.slice(0, -1).map((path, i) => {
    const a = path.getPoint(1), b = folds[i + 1].getPoint(0);
    return curve([a, a.clone().lerp(b, .35).add(v(-.08, .1, .30)), a.clone().lerp(b, .7).add(v(-.1, 0, -.15)), b]);
  }), [folds]);
  const lips = useMemo(() => [-1, 1].map(sign => curve([
    v(-.2, sign * .95, .48), v(.28, sign * .65, .66), v(.76, sign * .49, .56), v(1.12, sign * .70, .28),
  ])), []);
  return <group>
    {sheets.map((path, i) => <Ribbon key={`s${i}`} path={path} width={.36} color={i === 2 ? '#53d5e8' : '#14788f'} />)}
    {folds.map((path, i) => <Ribbon key={i} path={path} color={i % 3 === 0 ? '#a1f1f8' : cyan} />)}
    {loops.map((path, i) => <Trace key={`l${i}`} path={path} color="#2ba6ba" radius={.044} />)}
    {lips.map((path, i) => <Ribbon key={`p${i}`} path={path} width={.28} color="#b9faff" />)}
    {lips.flatMap((path, j) => path.getSpacedPoints(8).map((p, i) => <mesh key={`${j}-${i}`} position={p}>
      <sphereGeometry args={[.052, 12, 8]} /><meshStandardMaterial color={cyan} metalness={.2} roughness={.25} />
    </mesh>))}
  </group>;
}

function Binder() {
  const strands = useMemo(() => [-.27, 0, .27].map((y, i) => curve([
    v(-.73, y * .65, .30), v(-.42, y, .41), v(.02, y * 1.5, .17),
    v(.54, y * 1.2, .28), v(.72, y, -.02), v(.47, y, -.32), v(-.07, y, -.25),
  ].map(p => p.add(v(0, 0, i * .018))))), []);
  const spine = useMemo(() => helix(v(.12, -.06, -.38), v(.1, 1, .15), .94, .17, 2.6), []);
  return <group>
    {strands.map((path, i) => <Ribbon key={i} path={path} color={i === 1 ? '#ffb5a5' : coral} width={.19} />)}
    <Ribbon path={spine} color="#c95650" width={.16} />
    {strands.map((path, i) => <mesh key={`tip${i}`} position={path.getPoint(0)}>
      <sphereGeometry args={[.057, 12, 8]} /><meshStandardMaterial color="#ffe1ce" roughness={.22} />
    </mesh>)}
  </group>;
}

function Camera({ t }: { t: number }) {
  const { camera, size } = useThree();
  useLayoutEffect(() => {
    const dock = smooth(5, 11, t), orbit = smooth(11.4, 15, t);
    // Keep the opening separation and final complex large in a narrow shell viewport.
    const aspect = size.width / Math.max(1, size.height);
    const span = 8.8 - 3.1 * dock;
    const distance = Math.max(8.2, span / (2 * Math.tan(THREE.MathUtils.degToRad(36 / 2)) * aspect));
    const focus = v(1.4 - 1.05 * dock, .06, .15);
    const azimuth = .26 - .15 * orbit + .035 * smooth(0, 5, t);
    camera.position.set(focus.x + distance * Math.sin(azimuth), 2.5, distance * Math.cos(azimuth));
    camera.lookAt(focus);
    camera.updateProjectionMatrix();
  }, [camera, size.width, size.height, t]);
  return null;
}

function Assembly({ t }: { t: number }) {
  const approach = smooth(5, 11, t), align = smooth(5.8, 10.3, t);
  const joined = smooth(11.4, 15, t), contact = smooth(11.15, 12.8, t);
  // Cubic Bezier: travel around the front of the cleft, then seat along its open axis.
  const route = useMemo(() => new THREE.CubicBezierCurve3(v(3.9, .85, -.75), v(3.7, 1.05, 2.9), v(2.1, .05, .35), v(1.38, 0, .15)), []);
  const position = route.getPoint(approach);
  const bridges = useMemo(() => [-1, 1].map(sign => curve([v(.73, sign * .45, .55), v(.72, sign * .31, .51), v(.68, sign * .175, .45)])), []);
  return <group rotation={[.035, -.19 + .26 * smooth(0, 5, t) - .36 * joined, -.10]}>
    <Target />
    <group position={position} rotation={[.55 * (1 - align), -.95 * (1 - align), .95 * (1 - align)]}>
      <Binder />
    </group>
    <group visible={contact > 0}>
      {bridges.map((path, i) => <Trace key={i} path={path} color="#daffff" radius={.016 * contact} glow={contact * .8} />)}
      {[-1, 1].map(sign => <mesh key={sign} position={[.73, sign * .45, .55]} scale={[.18, .09, .09]}>
        <sphereGeometry args={[1, 20, 12]} /><meshBasicMaterial color={cyan} transparent opacity={contact * .26} depthWrite={false} />
      </mesh>)}
    </group>
    <pointLight position={[.9, .15, 1.0]} intensity={contact * 1.2} color="#9ffaff" distance={2} />
  </group>;
}

/** Parent owns time, selection and reset. No internal animation clock or controls. */
export default function BinderDemo({ time, reducedMotion = false }: BinderDemoProps) {
  const t = reducedMotion ? 15 : THREE.MathUtils.clamp(Number.isFinite(time) ? time : 0, 0, 18);
  return <div role="img" aria-label="Illustrative ribbon protein with an open cleft; a smaller coral binder approaches, turns, seats, and orbits with the bound complex" data-provenance="illustrative" style={{ width: '100%', height: '100%', background: '#061019', overflow: 'hidden' }}>
    <Canvas frameloop="demand" dpr={[1, 1.5]} camera={{ position: [3, 2.5, 11], fov: 36 }} gl={{ antialias: true, alpha: false, preserveDrawingBuffer: true }}>
      <color attach="background" args={['#061019']} />
      <ambientLight intensity={.26} />
      <directionalLight position={[-3, 6, 6]} intensity={3.2} color="#e1fcff" />
      <directionalLight position={[3, 1, -5]} intensity={3.5} color={cyan} />
      <directionalLight position={[4, -2, 3]} intensity={.7} color="#ffd6bf" />
      <Camera t={t} />
      <Assembly t={t} />
    </Canvas>
  </div>;
}
