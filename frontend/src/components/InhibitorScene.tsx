import { memo, useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import * as T from "three";
import { Html, Line } from "@react-three/drei";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  center,
  distance,
  type Atom,
  type Geometry,
  type Recipe,
  type Surface,
  type Vec3,
} from "@/lib/inhibitor";

function Instances({
  atoms,
  color,
  scale,
  pick,
  opacity = 1,
  clip,
}: {
  atoms: Atom[];
  color: string;
  scale: number;
  pick: (id: string) => void;
  opacity?: number;
  clip: T.Plane[];
}) {
  const ref = useRef<T.InstancedMesh>(null);
  useLayoutEffect(() => {
    const obj = new T.Object3D();
    atoms.forEach((a, i) => {
      obj.position.fromArray(a.position);
      obj.scale.setScalar(scale * (a.element === "H" ? 0.6 : 1));
      obj.updateMatrix();
      ref.current!.setMatrixAt(i, obj.matrix);
      const c =
        a.element === "N"
          ? "#759ee6"
          : a.element === "O"
            ? "#ef908b"
            : a.element === "S"
              ? "#ecd282"
              : color;
      ref.current!.setColorAt(i, new T.Color(c));
    });
    if (ref.current) {
      ref.current.instanceMatrix.needsUpdate = true;
      ref.current.computeBoundingSphere();
    }
  }, [atoms, scale, color]);
  return (
    <instancedMesh
      ref={ref}
      args={[undefined, undefined, atoms.length]}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        if (e.instanceId !== undefined) pick(atoms[e.instanceId].id);
      }}
    >
      <sphereGeometry args={[1, 16, 12]} />
      <meshStandardMaterial
        color="white"
        roughness={0.32}
        metalness={0.16}
        transparent={opacity < 1}
        opacity={opacity}
        depthWrite={opacity === 1}
        clippingPlanes={clip}
      />
    </instancedMesh>
  );
}
function Bonds({
  g,
  indices,
  color,
  radius = 0.12,
  clip,
}: {
  g: Geometry;
  indices: Set<number>;
  color: string;
  radius?: number;
  clip: T.Plane[];
}) {
  const bonds = useMemo(
    () => g.bonds.filter(([a, b]) => indices.has(a) && indices.has(b)),
    [g, indices],
  );
  const ref = useRef<T.InstancedMesh>(null);
  useLayoutEffect(() => {
    const obj = new T.Object3D(),
      up = new T.Vector3(0, 1, 0);
    bonds.forEach(([a, b], i) => {
      const start = new T.Vector3(...g.atoms[a].position),
        end = new T.Vector3(...g.atoms[b].position);
      const delta = end.clone().sub(start);
      obj.position.copy(start).add(end).multiplyScalar(0.5);
      obj.quaternion.setFromUnitVectors(up, delta.clone().normalize());
      obj.scale.set(radius, delta.length(), radius);
      obj.updateMatrix();
      ref.current!.setMatrixAt(i, obj.matrix);
    });
    ref.current!.instanceMatrix.needsUpdate = true;
    ref.current!.computeBoundingSphere();
  }, [g, bonds, radius]);
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, bonds.length]}>
      <cylinderGeometry args={[1, 1, 1, 10]} />
      <meshStandardMaterial
        color={color}
        roughness={0.5}
        clippingPlanes={clip}
      />
    </instancedMesh>
  );
}
function Trace({
  g,
  path,
  clip,
  overview,
}: {
  overview: boolean;
  g: Geometry;
  path: number[];
  clip: T.Plane[];
}) {
  const geometry = useMemo(
    () =>
      new T.TubeGeometry(
        new T.CatmullRomCurve3(
          path.map((i) => new T.Vector3(...g.atoms[i].position)),
        ),
        path.length * 5,
        0.13,
        7,
        false,
      ),
    [g, path],
  );
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial
        color="#4b6b78"
        transparent={!overview}
        opacity={overview ? 1 : 0.12}
        depthWrite={overview}
        roughness={0.65}
        metalness={0.05}
        clippingPlanes={clip}
      />
    </mesh>
  );
}
function PocketSurface({
  surface,
  clip,
  pick,
}: {
  surface: Surface;
  clip: T.Plane[];
  pick: (id: string) => void;
}) {
  const geometry = useMemo(() => {
    const g = new T.BufferGeometry();
    g.setAttribute(
      "position",
      new T.Float32BufferAttribute(surface.positions.flat(), 3),
    );
    g.computeVertexNormals();
    return g;
  }, [surface]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh
      geometry={geometry}
      onClick={(e) => {
        e.stopPropagation();
        if (e.faceIndex != null) pick(surface.triangle_atom_ids[e.faceIndex]);
      }}
    >
      <meshStandardMaterial
        color="#67aeb9"
        transparent
        opacity={0.22}
        depthWrite={false}
        side={T.DoubleSide}
        clippingPlanes={clip}
      />
    </mesh>
  );
}
function Scene({
  g,
  recipe,
  pick,
  ack,
  onCamera,
  surface,
}: {
  g: Geometry;
  surface?: Surface;
  recipe: Recipe;
  pick: (id: string) => void;
  ack: (revision: number, canvas: HTMLCanvasElement) => void;
  onCamera: (position: Vec3, target: Vec3) => void;
}) {
  const { gl, scene, camera, invalidate, size } = useThree();
  const orbit = useRef<OrbitControls>(null);
  const motion = useRef<number | null>(null);
  const initialized = useRef(false);
  const atomSet = useMemo(
    () => g.atoms.filter((a) => a.model === recipe.model),
    [g, recipe.model],
  );
  const ligand = useMemo(
    () => atomSet.filter((a) => a.residue_id === recipe.ligand),
    [atomSet, recipe.ligand],
  );
  const focus = useMemo(
    () => center(ligand.length ? ligand : atomSet),
    [ligand, atomSet],
  );
  const context = useMemo(() => {
    const residues = new Set(
      atomSet
        .filter(
          (a) =>
            a.kind === "polymer" &&
            !["H", "D"].includes(a.element) &&
            ligand.some((b) => distance(a, b) < 4),
        )
        .map((a) => a.residue_id),
    );
    return atomSet.filter(
      (a) => residues.has(a.residue_id) && !["H", "D"].includes(a.element),
    );
  }, [atomSet, ligand]);
  const contextIndices = useMemo(() => {
    const ids = new Set(context.map((a) => a.id));
    return new Set(g.atoms.flatMap((a, i) => (ids.has(a.id) ? [i] : [])));
  }, [g, context]);
  const selected = g.atoms.filter((a) => recipe.selected.includes(a.id));
  const ligandIndices = useMemo(
    () =>
      new Set(
        g.atoms.flatMap((a, i) => (a.residue_id === recipe.ligand ? [i] : [])),
      ),
    [g, recipe.ligand],
  );
  const clip = useMemo(
    () =>
      recipe.clip ? [new T.Plane(new T.Vector3(0, 0, -1), focus[2] + 3)] : [],
    [recipe.clip, focus],
  );
  useLayoutEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    orbit.current = controls;
    controls.enableDamping = false;
    controls.addEventListener("change", () => invalidate());
    let startPosition = camera.position.clone(),
      startTarget = controls.target.clone();
    controls.addEventListener("start", () => {
      if (motion.current !== null) cancelAnimationFrame(motion.current);
      motion.current = null;
      startPosition = camera.position.clone();
      startTarget = controls.target.clone();
    });
    const end = () => {
      if (
        startPosition.distanceTo(camera.position) +
          startTarget.distanceTo(controls.target) <
        0.0001
      )
        return;
      onCamera(
        camera.position.toArray() as Vec3,
        controls.target.toArray() as Vec3,
      );
    };
    controls.addEventListener("end", end);
    return () => controls.dispose();
  }, [camera, gl, invalidate, onCamera]);
  useLayoutEffect(() => {
    const target =
      recipe.camera?.target ||
      (recipe.shot === "arrival" ? center(atomSet) : focus);
    const radius = Math.max(
      10,
      ...atomSet.map((a) =>
        Math.hypot(...a.position.map((v, i) => v - target[i])),
      ),
    );
    const dist = recipe.shot === "arrival" ? radius * 2.8 : 25;
    const offset =
      recipe.shot === "oblique" ? [0.85, 0.38, 0.9] : [0.2, 0.22, 1.3];
    const destination = new T.Vector3(
      ...(recipe.camera?.position ||
        (target.map((v, i) => v + offset[i] * dist) as Vec3)),
    );
    const destinationTarget = new T.Vector3(...target);
    const from = camera.position.clone(),
      fromTarget = orbit.current!.target.clone();
    const duration =
      initialized.current &&
      !matchMedia("(prefers-reduced-motion: reduce)").matches
        ? 700
        : 0;
    initialized.current = true;
    const started = performance.now();
    function step(now: number) {
      const t = duration ? Math.min(1, (now - started) / duration) : 1;
      const smooth = t * t * (3 - 2 * t);
      camera.position.lerpVectors(from, destination, smooth);
      orbit.current!.target.lerpVectors(fromTarget, destinationTarget, smooth);
      camera.up.set(0, 1, 0);
      orbit.current!.update();
      camera.updateProjectionMatrix();
      invalidate();
      motion.current = t < 1 ? requestAnimationFrame(step) : null;
    }
    step(started);
    return () => {
      if (motion.current !== null) cancelAnimationFrame(motion.current);
      motion.current = null;
    };
  }, [
    recipe.camera,
    recipe.shot,
    recipe.ligand,
    recipe.model,
    camera,
    atomSet,
    focus,
    invalidate,
  ]);
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await document.fonts.ready;
      while (motion.current !== null && !cancelled)
        await new Promise(requestAnimationFrame);
      if (cancelled) return;
      gl.compile(scene, camera);
      gl.render(scene, camera);
      gl.getContext().finish();
      if (!cancelled) ack(recipe.revision, gl.domElement);
    })();
    return () => {
      cancelled = true;
    };
  }, [recipe, gl, scene, camera, ack, size]);
  return (
    <>
      <color attach="background" args={["#09131d"]} />
      <ambientLight intensity={0.7} />
      <directionalLight
        position={[20, 45, 70]}
        intensity={2.6}
        color="#e2efff"
      />
      <directionalLight
        position={[-40, 5, -20]}
        intensity={2}
        color="#54ccd8"
      />
      <pointLight
        position={[focus[0], focus[1] + 8, focus[2] + 12]}
        intensity={120}
        color="#ffcd87"
      />
      {g.backbones
        .filter((p) => g.atoms[p[0]].model === recipe.model)
        .map((p, i) => (
          <Trace
            key={i}
            g={g}
            path={p}
            clip={clip}
            overview={recipe.shot === "arrival"}
          />
        ))}
      {recipe.surface && surface && (
        <PocketSurface surface={surface} clip={clip} pick={pick} />
      )}
      {recipe.style === "luminous" && (
        <Instances
          atoms={context}
          color="#77b7b6"
          scale={1.25}
          opacity={0.13}
          pick={pick}
          clip={clip}
        />
      )}
      {recipe.style !== "luminous" && (
        <Instances
          atoms={context}
          color="#a4c4c6"
          scale={0.23}
          pick={pick}
          clip={clip}
        />
      )}
      <Bonds
        g={g}
        indices={contextIndices}
        color="#728e9d"
        radius={0.075}
        clip={clip}
      />
      <Bonds
        g={g}
        indices={ligandIndices}
        color="#efb561"
        radius={0.17}
        clip={[]}
      />
      <Instances
        atoms={ligand}
        color="#ffbe67"
        scale={0.36}
        pick={pick}
        clip={[]}
      />
      {selected.map((a) => (
        <group key={a.id} position={a.position}>
          <mesh>
            <sphereGeometry args={[0.49, 20, 16]} />
            <meshBasicMaterial
              color="#b9ffff"
              wireframe
              transparent
              opacity={0.55}
            />
          </mesh>
          <Html center position={[0, 0.8, 0]} style={{ pointerEvents: "none" }}>
            <span className="pocket-atom-label">
              {a.name} · {g.residues.find((r) => r.id === a.residue_id)?.name}
            </span>
          </Html>
        </group>
      ))}
      {selected.length >= 2 && (
        <Line
          points={recipe.selected.map(
            (id) => g.atoms.find((a) => a.id === id)!.position,
          )}
          color="#b9ffff"
          lineWidth={1.5}
          dashed
          dashSize={0.18}
          gapSize={0.12}
        />
      )}
      {selected.length === 2 && (
        <Html
          center
          position={center(selected)}
          style={{ pointerEvents: "none" }}
        >
          <span className="pocket-distance-label">
            {distance(selected[0], selected[1]).toFixed(2)} Å
          </span>
        </Html>
      )}
    </>
  );
}
export default memo(function InhibitorScene(
  props: Parameters<typeof Scene>[0],
) {
  return (
    <Canvas
      frameloop="demand"
      dpr={[1, 1.5]}
      camera={{ fov: 38, near: 0.1, far: 10000 }}
      gl={{
        antialias: true,
        preserveDrawingBuffer: true,
        localClippingEnabled: true,
      }}
      onCreated={({ gl }) => {
        gl.domElement.setAttribute(
          "aria-label",
          "Interactive inhibitor geometry",
        );
        gl.domElement.addEventListener("webglcontextlost", (e) =>
          e.preventDefault(),
        );
      }}
    >
      <Scene {...props} />
    </Canvas>
  );
});
