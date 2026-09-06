import { useEffect, useMemo, useRef, type RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as T from "three";
import {
  actionProgress,
  center,
  distance,
  smoothPhase,
  type ActionPresentation,
  type Atom,
  type Geometry,
  type Recipe,
} from "@/lib/inhibitor";

// Animated rulers and region outlines are annotations, never intermediate molecular poses.
export default function InhibitorAction({
  g,
  recipe,
  presentation,
}: {
  g: Geometry;
  recipe: Recipe;
  presentation: RefObject<ActionPresentation>;
}) {
  const halo = useRef<T.Mesh>(null),
    scan = useRef<T.Mesh>(null),
    box = useRef<T.LineSegments>(null);
  const traces = useRef<T.LineSegments>(null),
    ruler = useRef<T.Line>(null);
  const removed = useRef<T.InstancedMesh>(null),
    added = useRef<T.InstancedMesh>(null),
    poses = useRef<T.InstancedMesh>(null);
  const data = useMemo(() => {
    const ligand = g.atoms.filter((a) => a.model === recipe.model && a.residue_id === recipe.ligand);
    const focus = center(ligand),
      radius = Math.max(
        2,
        ...ligand.map((a) =>
          Math.hypot(...a.position.map((x, i) => x - focus[i])),
        ),
      );
    const pairs = new Map<string, { a: Atom; b: Atom; distance: number }>();
    for (const a of g.atoms) {
      if (a.model !== recipe.model || a.kind !== "polymer" || ["H", "D"].includes(a.element)) continue;
      for (const b of ligand) {
        const d = distance(a, b),
          old = pairs.get(a.residue_id);
        if (d < 4 && (!old || d < old.distance))
          pairs.set(a.residue_id, { a, b, distance: d });
      }
    }
    const contacts = [...pairs.values()]
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 12);
    const selected = recipe.selected
      .map((id) => g.atoms.find((a) => a.id === id))
      .filter((a): a is Atom => !!a);
    const contactGeometry = new T.BufferGeometry().setAttribute(
      "position",
      new T.Float32BufferAttribute(new Float32Array(contacts.length * 6), 3),
    );
    const rulerGeometry = new T.BufferGeometry().setAttribute(
      "position",
      new T.Float32BufferAttribute(
        new Float32Array(Math.max(2, selected.length) * 3),
        3,
      ),
    );
    const region = new T.EdgesGeometry(new T.BoxGeometry(1, 1, 1));
    return {
      focus,
      radius,
      contacts,
      selected,
      contactGeometry,
      rulerGeometry,
      region,
    };
  }, [g, recipe.model, recipe.ligand, recipe.selected]);
  const rulerObject = useMemo(
    () =>
      new T.Line(
        data.rulerGeometry,
        new T.LineBasicMaterial({ color: "#c8ffff", depthTest: false }),
      ),
    [data],
  );
  useEffect(() => () => rulerObject.material.dispose(), [rulerObject]);
  useEffect(
    () => () => {
      data.contactGeometry.dispose();
      data.rulerGeometry.dispose();
      data.region.dispose();
    },
    [data],
  );
  useFrame(({ invalidate, gl }) => {
    const a = presentation.current,
      p = actionProgress(a);
    if (
      !halo.current ||
      !scan.current ||
      !box.current ||
      !traces.current ||
      !ruler.current
    )
      return;
    const active =
      a.active && !matchMedia("(prefers-reduced-motion: reduce)").matches;
    const approach = smoothPhase(p, 0, 0.35),
      reveal = smoothPhase(p, 0.2, 0.8);
    halo.current.visible = active;
    halo.current.scale.setScalar(data.radius * (1.65 - 0.65 * approach));
    halo.current.rotation.set(
      Math.PI / 2 + 0.25 * Math.sin(p * Math.PI),
      p * Math.PI * 0.35,
      0,
    );
    (halo.current.material as T.MeshBasicMaterial).opacity = active
      ? 0.25 * (1 - smoothPhase(p, 0.8, 1))
      : 0;
    const search = active && a.kind === "search" && !!a.region;
    scan.current.visible = box.current.visible = search;
    if (a.region) {
      box.current.position.fromArray(a.region.center);
      box.current.scale.fromArray(a.region.size);
      scan.current.position.set(
        a.region.center[0],
        a.region.center[1] + (p - 0.5) * a.region.size[1],
        a.region.center[2],
      );
      scan.current.scale.set(a.region.size[0], a.region.size[2], 1);
    }
    const object = new T.Object3D();
    for (const [mesh, atoms, isAdded] of [
      [removed.current, a.removed || [], false],
      [added.current, a.added || [], true],
    ] as const) {
      if (!mesh) continue;
      mesh.visible = active && a.kind === "preparation";
      mesh.count = Math.min(2000, atoms.length);
      atoms.slice(0, 2000).forEach((atom, i) => {
        object.position.fromArray(atom.position);
        object.scale.setScalar(0.45);
        object.updateMatrix();
        mesh.setMatrixAt(i, object.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
      (mesh.material as T.MeshBasicMaterial).opacity =
        (isAdded ? reveal : 1 - reveal) * (1 - smoothPhase(p, 0.85, 1)) * 0.65;
    }
    if (poses.current) {
      const points = (a.poses || []).slice(0, 5).flat();
      poses.current.count = Math.min(640, points.length);
      poses.current.visible = active && a.kind === "poses";
      points.slice(0, 640).forEach((point, i) => {
        object.position.fromArray(point);
        object.scale.setScalar(0.22);
        object.updateMatrix();
        poses.current!.setMatrixAt(i, object.matrix);
      });
      poses.current.instanceMatrix.needsUpdate = true;
      (poses.current.material as T.MeshBasicMaterial).opacity =
        smoothPhase(p, 0.12, 0.4) * (1 - smoothPhase(p, 0.65, 0.95)) * 0.35;
    }
    (scan.current.material as T.MeshBasicMaterial).opacity =
      0.1 + 0.08 * Math.sin(p * Math.PI);
    const contactView =
      active && ["focus", "poses", "review", "preparation"].includes(a.kind);
    traces.current.visible = contactView;
    const attr = data.contactGeometry.getAttribute("position");
    data.contacts.forEach(({ a, b }, i) => {
      const t = smoothPhase(p, 0.2 + i * 0.025, 0.5 + i * 0.025);
      attr.setXYZ(i * 2, ...b.position);
      attr.setXYZ(
        i * 2 + 1,
        ...(b.position.map((v, k) => v + (a.position[k] - v) * t) as [
          number,
          number,
          number,
        ]),
      );
    });
    attr.needsUpdate = true;
    (traces.current.material as T.LineBasicMaterial).opacity = 0.6 * reveal;
    ruler.current.visible =
      active && a.kind === "measurement" && data.selected.length >= 2;
    const r = data.rulerGeometry.getAttribute("position");
    const t = smoothPhase(p, 0.2, 0.72);
    data.selected.forEach((atom, i) => {
      const before = data.selected[Math.max(0, i - 1)];
      const f = Math.max(
        0,
        Math.min(1, t * (data.selected.length - 1) - Math.max(0, i - 1)),
      );
      r.setXYZ(
        i,
        ...(atom.position.map((v, k) =>
          i === 0 ? v : before.position[k] + (v - before.position[k]) * f,
        ) as [number, number, number]),
      );
    });
    r.needsUpdate = true;
    gl.domElement.dataset.annotationProgress = String(t);
    gl.domElement.dataset.actionKind = a.active ? a.kind : "explore";
    if (a.active && a.playing && p < 1) invalidate();
  });
  return (
    <group>
      <instancedMesh
        ref={removed}
        args={[undefined, undefined, 2000]}
        frustumCulled={false}
        raycast={() => null}
      >
        <sphereGeometry args={[1, 8, 6]} />
        <meshBasicMaterial
          color="#eda78b"
          wireframe
          transparent
          depthWrite={false}
        />
      </instancedMesh>
      <instancedMesh
        ref={added}
        args={[undefined, undefined, 2000]}
        frustumCulled={false}
        raycast={() => null}
      >
        <sphereGeometry args={[1, 8, 6]} />
        <meshBasicMaterial
          color="#9cebf8"
          wireframe
          transparent
          depthWrite={false}
        />
      </instancedMesh>
      <instancedMesh
        ref={poses}
        args={[undefined, undefined, 640]}
        frustumCulled={false}
        raycast={() => null}
      >
        <sphereGeometry args={[1, 8, 6]} />
        <meshBasicMaterial
          color="#c5d7ff"
          wireframe
          transparent
          depthWrite={false}
        />
      </instancedMesh>
      <mesh ref={halo} position={data.focus} raycast={() => null}>
        <torusGeometry args={[1, 0.012, 6, 100]} />
        <meshBasicMaterial color="#a2edff" transparent depthWrite={false} />
      </mesh>
      <lineSegments
        ref={box}
        geometry={data.region}
        position={data.focus}
        raycast={() => null}
      >
        <lineBasicMaterial color="#efc481" transparent opacity={0.35} />
      </lineSegments>
      <mesh ref={scan} rotation={[-Math.PI / 2, 0, 0]} raycast={() => null}>
        <planeGeometry args={[1, 1]} />
        <meshBasicMaterial
          color="#92dff6"
          transparent
          depthWrite={false}
          side={T.DoubleSide}
        />
      </mesh>
      <lineSegments
        ref={traces}
        geometry={data.contactGeometry}
        raycast={() => null}
      >
        <lineBasicMaterial color="#8fdce9" transparent depthWrite={false} />
      </lineSegments>
      <primitive object={rulerObject} ref={ruler} />
    </group>
  );
}
