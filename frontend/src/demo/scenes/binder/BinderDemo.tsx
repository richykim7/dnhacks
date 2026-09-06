import { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import * as THREE from 'three';

export const binderDemoMetadata = {
  title: 'A meeting at the molecular surface',
  provenance: 'Illustrative seeded geometry and choreographed docking. Not an experimental structure, simulation, prediction, or binding result.',
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

// Fixed local illustrative fold: helical segments connected by continuous loops.
function fold(small: boolean) {
  let seed = small ? 1211 : 1207;
  const random = () => ((seed = (1664525 * seed + 1013904223) >>> 0) / 4294967296);
  const points: THREE.Vector3[] = [];
  const count = small ? 5 : 13;
  for (let h = 0; h < count; h++) {
    const phi = h * 2.399963;
    const z = 1 - 2 * (h + .5) / count;
    const radius = Math.sqrt(1 - z * z);
    const center = new THREE.Vector3(radius * Math.cos(phi), z, radius * Math.sin(phi)).multiplyScalar(small ? .48 : 1.15);
    const axis = new THREE.Vector3(.25 * Math.sin(phi), 1, .3 * Math.cos(phi)).normalize();
    const u = new THREE.Vector3().crossVectors(axis, new THREE.Vector3(0, 0, 1)).normalize();
    const v = new THREE.Vector3().crossVectors(axis, u);
    const length = (small ? .9 : 1.45) + random() * .25;
    for (let j = 0; j <= 58; j++) {
      const f = j / 58;
      const angle = f * Math.PI * 2 * (small ? 2.8 : 3.7) + phi;
      points.push(center.clone().addScaledVector(axis, (f - .5) * length)
        .addScaledVector(u, Math.cos(angle) * .19).addScaledVector(v, Math.sin(angle) * .19));
    }
  }
  return new THREE.CatmullRomCurve3(points, false, 'centripetal');
}

function envelope(small: boolean) {
  const geometry = new THREE.SphereGeometry(1, 72, 48);
  const positions = geometry.attributes.position;
  const p = new THREE.Vector3();
  for (let i = 0; i < positions.count; i++) {
    p.fromBufferAttribute(positions, i);
    const ripple = .10 * Math.sin(p.x * 9 + p.y * 4) * Math.cos(p.z * 8)
      + .08 * Math.sin(p.y * 11 + p.z * 6) + .045 * Math.cos(p.x * 19 - p.z * 12);
    const pocket = small ? 0 : .28 * Math.exp(-((p.y - .12) ** 2 + (p.z - .6) ** 2) / .15) * Math.max(0, p.x);
    p.multiplyScalar((small ? .83 : 1.96) * (1 + ripple - pocket));
    p.y *= small ? 1.14 : 1.05;
    positions.setXYZ(i, p.x, p.y, p.z);
  }
  geometry.computeVertexNormals();
  return geometry;
}

function Molecule({ small = false }: { small?: boolean }) {
  const curve = useMemo(() => fold(small), [small]);
  const shell = useMemo(() => envelope(small), [small]);
  const tube = useMemo(() => new THREE.TubeGeometry(curve, small ? 800 : 1900, small ? .047 : .051, 6, false), [curve, small]);
  const atoms = useMemo(() => curve.getSpacedPoints(small ? 38 : 96), [curve, small]);
  const color = small ? coral : cyan;
  return <group>
    <mesh geometry={tube}>
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={.33} roughness={.3} metalness={.28} />
    </mesh>
    {atoms.map((p, i) => <mesh key={i} position={p}>
      <sphereGeometry args={[small ? .061 : .07, 8, 6]} />
      <meshStandardMaterial color={i % 7 === 0 ? '#eafcff' : color} emissive={color} emissiveIntensity={.18} roughness={.35} />
    </mesh>)}
    <mesh geometry={shell} renderOrder={2}>
      <meshPhysicalMaterial color={color} transparent opacity={small ? .12 : .10} roughness={.28} metalness={.1} side={THREE.FrontSide} depthWrite={false} />
    </mesh>
    <mesh geometry={shell} scale={1.012} renderOrder={3}>
      <shaderMaterial transparent depthWrite={false} uniforms={{ tint: { value: new THREE.Color(color) } }}
        vertexShader={'varying vec3 n; varying vec3 v; void main(){vec4 p=modelViewMatrix*vec4(position,1.); n=normalize(normalMatrix*normal); v=normalize(-p.xyz); gl_Position=projectionMatrix*p;}'}
        fragmentShader={'uniform vec3 tint; varying vec3 n; varying vec3 v; void main(){float rim=pow(1.-abs(dot(normalize(n),normalize(v))),3.); gl_FragColor=vec4(tint, rim*.25);}'} />
    </mesh>
  </group>;
}

function Assembly({ time, reducedMotion }: BinderDemoProps) {
  const t = reducedMotion ? 15 : THREE.MathUtils.clamp(Number.isFinite(time) ? time : 0, 0, 18);
  const approach = smooth(5, 11, t);
  const contact = smooth(11, 14, t);
  const rotation = -.22 + .30 * smooth(0, 15, t);
  return <group position={[-.85, -.12, 0]} rotation={[.08, rotation, -.09]}>
    <Molecule />
    <group position={[5.1 - 2.48 * approach, .55 - .27 * approach, .65]}
      rotation={[.12, -.45 + .35 * approach, -.55 + .25 * approach]}>
      <Molecule small />
    </group>
    <group visible={contact > 0} position={[1.73, .22, .69]} rotation={[0, Math.PI / 2 - .22, 0]}>
      <mesh scale={[.70, .82, .12]}>
        <sphereGeometry args={[1, 32, 24]} />
        <meshBasicMaterial color="#bcffff" transparent opacity={contact * .12} depthWrite={false} />
      </mesh>
      {[0, 1, 2].map(i => <mesh key={i} scale={[.50 + i * .10, .62 + i * .09, 1]} position={[0, 0, i * .018]}>
        <ringGeometry args={[.98, 1, 80]} />
        <meshBasicMaterial color={cyan} transparent opacity={contact * (.24 - i * .06)} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>)}
      {Array.from({ length: 9 }, (_, i) => {
        const a = i * 2.399963;
        return <mesh key={i} position={[Math.cos(a) * .37, Math.sin(a) * .48, .05]}>
          <sphereGeometry args={[.035, 10, 8]} />
          <meshBasicMaterial color="#dbffff" transparent opacity={contact * .85} depthWrite={false} />
        </mesh>;
      })}
    </group>
    <pointLight position={[1.8, .4, 1.4]} color={cyan} intensity={contact * 2.3} distance={3} />
  </group>;
}

/** The parent owns selection, playback and reset. This scene never advances its own clock. */
export default function BinderDemo({ time, reducedMotion = false }: BinderDemoProps) {
  return <div role="img" aria-label="Illustrative holographic protein and coral binder approaching a softly illuminated contact region" data-provenance="illustrative" style={{ width: '100%', height: '100%', background: '#061019', overflow: 'hidden' }}>
    <Canvas frameloop="demand" dpr={[1, 1.5]} camera={{ position: [0, .6, 12.8], fov: 37 }} gl={{ antialias: true, alpha: false, preserveDrawingBuffer: true }}>
      <color attach="background" args={['#061019']} />
      <ambientLight intensity={.65} />
      <directionalLight position={[-3, 6, 7]} intensity={2.5} color="#d8faff" />
      <directionalLight position={[4, -2, -3]} intensity={1.8} color={cyan} />
      <Assembly time={time} reducedMotion={reducedMotion} />
    </Canvas>
  </div>;
}
