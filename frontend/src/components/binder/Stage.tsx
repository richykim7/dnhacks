import { useEffect, useMemo, useRef, type RefObject } from "react";
import {
  Canvas,
  useFrame,
  useThree,
  type ThreeEvent,
} from "@react-three/fiber";
import { OrbitControls, Line } from "@react-three/drei";
import * as THREE from "three";
import type { OrbitControls as OrbitImpl } from "three-stdlib";
import {
  type Atom,
  type Bundle,
  type SceneState,
  type SurfaceMesh,
} from "./types";

import SourceMesh, { sourceAtomAt, hasBackboneTrace } from "./SourceMesh";

const radius: Record<string, number> = {
  C: 1.7,
  N: 1.55,
  O: 1.52,
  S: 1.8,
  P: 1.8,
};
export type SceneInspection = {
  camera_transitioning: boolean;
  camera: unknown;
  renderer: unknown;
  visible_residue_ids: string[];
  occlusion_fractions: Record<string, number>;
  physical_to_scene: unknown;
  frame_times_ms: number[];
  triangles: number;
  atoms: number;
  viewport: unknown;
};
export type StageHandle = {
  cancelMotion: () => void;
  ready: () => Promise<void>;
  inspect: () => SceneInspection;
  pick: (x: number, y: number) => string | null;
  capture: () => string;
};

function Molecule({
  atoms,
  color,
  selected,
  onPick,
  offset = 0,
  style,
  role,
  detail = false,
}: {
  atoms: Atom[];
  color: string;
  selected: string | null;
  onPick: (id: string) => void;
  offset?: number;
  style: string;
  role: string;
  detail?: boolean;
}) {
  const mesh = useRef<THREE.InstancedMesh>(null!);
  useEffect(() => {
    const m = new THREE.Object3D();
    atoms.forEach((a, i) => {
      m.position.set(...a.xyz);
      m.position.x += offset;
      const r = (radius[a.element] || 1.7) * (detail ? 0.42 : 0.88);
      m.scale.setScalar(r);
      m.updateMatrix();
      mesh.current.setMatrixAt(i, m.matrix);
      mesh.current.setColorAt(
        i,
        new THREE.Color(a.residue_id === selected ? "#ffcb83" : color),
      );
    });
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor)
      mesh.current.instanceColor.needsUpdate = true;
    mesh.current.computeBoundingSphere();
    mesh.current.userData = { atoms, role, pickable: true };
  }, [atoms, color, selected, offset, role, detail]);
  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, atoms.length]}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        if (e.instanceId !== undefined) onPick(atoms[e.instanceId].residue_id);
      }}
    >
      <sphereGeometry args={[1, 12, 8]} />
      <meshPhysicalMaterial
        color="white"
        roughness={style === "pearl" ? 0.48 : 0.32}
        metalness={style === "pearl" ? 0.12 : 0.65}
        clearcoat={0.5}
      />
    </instancedMesh>
  );
}

export function Scene({
  bundle,
  state,
  onPick,
  onHandle,
  meshes: surfaceMeshes,
  sharedControls,
  fitAtoms: sharedFitAtoms,
  manageCamera = true,
}: {
  bundle: Bundle;
  sharedControls?: RefObject<OrbitImpl>;
  fitAtoms?: Atom[];
  manageCamera?: boolean;
  meshes: Record<string, SurfaceMesh>;
  state: SceneState;
  onPick: (id: string) => void;
  onHandle: (h: StageHandle | null) => void;
}) {
  const { camera, gl, scene, size, invalidate } = useThree();
  const ownControls = useRef<OrbitImpl>(null!);
  const controls = sharedControls ?? ownControls;
  const initialized = useRef(false);
  const transition = useRef<null | {
    started: number; from: THREE.Vector3; to: THREE.Vector3;
    fromTarget: THREE.Vector3; toTarget: THREE.Vector3;
    fromUp: THREE.Vector3; toUp: THREE.Vector3; fromFov: number; toFov: number;
  }>(null);
  const settled = useRef(0),
    frameTimes = useRef<number[]>([]);
  const parts = useMemo(() => {
    const residue = new Map(bundle.structure.residues.map((r) => [r.id, r]));
    const atoms = bundle.structure.atoms.filter(
      (a) => a.element !== "H" && a.element !== "D",
    );
    const target = atoms.filter((a) =>
      bundle.target_chains.includes(residue.get(a.residue_id)!.chain),
    );
    const binder = atoms.filter((a) =>
      bundle.binder_chains.includes(residue.get(a.residue_id)!.chain),
    );
    const selectedContacts = bundle.metrics.contacts.filter(
      (c) => c.distance_angstrom <= 4.5,
    );
    const contactIds = new Set(
      selectedContacts.flatMap((c) => [c.target_residue, c.binder_residue]),
    );
    const contactAtoms = atoms.filter((a) => contactIds.has(a.residue_id));
    const center = new THREE.Box3()
      .setFromPoints(atoms.map((a) => new THREE.Vector3(...a.xyz)))
      .getCenter(new THREE.Vector3());
    const seam = new THREE.Box3()
      .setFromPoints(
        (contactAtoms.length ? contactAtoms : atoms).map(
          (a) => new THREE.Vector3(...a.xyz),
        ),
      )
      .getCenter(new THREE.Vector3());
    return { target, binder, center, seam, contactIds, atoms };
  }, [bundle]);
  const detail = ["interface-close", "reverse"].includes(state.preset);
  const requested =
    state.representation ??
    (surfaceMeshes.target && surfaceMeshes.binder ? "surface" : "atoms");
  const traceSupported = useMemo(() => hasBackboneTrace(bundle), [bundle]);
  const representation =
    requested === "ribbon" && !traceSupported
      ? "atoms"
      : detail
        ? "atoms"
        : requested === "surface" &&
            (!surfaceMeshes.target || !surfaceMeshes.binder)
          ? "atoms"
          : requested;
  useEffect(() => {
    settled.current = 0;
    invalidate();
  }, [state.style, state.selected, representation, invalidate]);
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => { if (media.matches) { transition.current = null; invalidate(); } };
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, [invalidate]);
  useFrame((_, delta) => {
    const motion = transition.current;
    if (motion) {
      const fraction = Math.min(1, (performance.now() - motion.started) / 700);
      const t = fraction * fraction * (3 - 2 * fraction);
      const target = motion.fromTarget.clone().lerp(motion.toTarget, t);
      const a = motion.from.clone().sub(motion.fromTarget);
      const b = motion.to.clone().sub(motion.toTarget);
      const distance = THREE.MathUtils.lerp(a.length(), b.length(), t);
      const rotation = new THREE.Quaternion().setFromUnitVectors(a.normalize(), b.normalize());
      const direction = a.applyQuaternion(new THREE.Quaternion().slerp(rotation, t));
      camera.position.copy(target).addScaledVector(direction, distance);
      camera.up.copy(motion.fromUp).lerp(motion.toUp, t).normalize();
      (camera as THREE.PerspectiveCamera).fov = THREE.MathUtils.lerp(motion.fromFov, motion.toFov, t);
      camera.updateProjectionMatrix();
      controls.current.target.copy(target);
      controls.current.update();
      camera.updateMatrixWorld(true);
      if (fraction === 1) transition.current = null;
      settled.current = 0;
      invalidate();
    }
    settled.current++;
    if (settled.current < 5) invalidate();
    frameTimes.current.push(delta * 1000);
    if (frameTimes.current.length > 240) frameTimes.current.shift();
  });
  useEffect(() => {
    if (!manageCamera) return;
    const from = camera.position.clone(), fromTarget = controls.current.target.clone();
    const fromUp = camera.up.clone(), fromFov = (camera as THREE.PerspectiveCamera).fov;
    transition.current = null;
    const finishPose = () => {
      if (initialized.current && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        transition.current = { started: performance.now(), from, fromTarget, fromUp, fromFov,
          to: camera.position.clone(), toTarget: controls.current.target.clone(),
          toUp: camera.up.clone(), toFov: (camera as THREE.PerspectiveCamera).fov };
        camera.position.copy(from); camera.up.copy(fromUp);
        (camera as THREE.PerspectiveCamera).fov = fromFov;
        controls.current.target.copy(fromTarget); controls.current.update();
        camera.updateProjectionMatrix(); camera.updateMatrixWorld(true);
      }
      initialized.current = true;
      settled.current = 0;
      invalidate();
    };
    if (state.camera) {
      const c = state.camera;
      camera.position.set(...c.position);
      camera.up.set(...(c.up || [0, 1, 0]));
      camera.lookAt(...c.target);
      (camera as THREE.PerspectiveCamera).fov = c.fov || 38;
      (camera as THREE.PerspectiveCamera).aspect = size.width / size.height;
      camera.near = Math.max(0.01, c.near || 0.1);
      camera.far = Math.max(camera.near + 0.1, c.far || 2000);
      camera.updateProjectionMatrix();
      camera.updateMatrixWorld(true);
      controls.current.target.set(...c.target);
      controls.current.update();
      finishPose();
      return;
    }
    const close = ["interface-close", "epitope", "reverse"].includes(
      state.preset,
    );
    const fitAtoms = sharedFitAtoms ?? (close
      ? parts.atoms.filter((a) => parts.contactIds.has(a.residue_id))
      : parts.atoms);
    const box = new THREE.Box3().setFromPoints(
      fitAtoms.map((a) => new THREE.Vector3(...a.xyz)),
    );
    const center = sharedFitAtoms ? box.getCenter(new THREE.Vector3()) : close ? parts.seam : parts.center;
    const extent = box.getSize(new THREE.Vector3()).length();
    const aspect = size.width / size.height;
    (camera as THREE.PerspectiveCamera).aspect = aspect;
    const distance = extent * (close ? 0.82 : 1.15) * Math.max(1, 1 / aspect);

    const direction = new THREE.Vector3(
      state.preset === "reverse" ? -0.3 : 0.28,
      0.24,
      state.preset === "reverse" ? -1 : 1,
    ).normalize();
    camera.position.copy(center).addScaledVector(direction, distance);
    camera.up.set(0, 1, 0);
    camera.lookAt(center);
    camera.near = 0.1;
    camera.far = 2000;
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    // Fit the actual projected physical bounds, including atom radii, after viewport changes.
    for (let pass = 0; pass < 12; pass++) {
      const points = fitAtoms.map((a) =>
        new THREE.Vector3(...a.xyz).project(camera),
      );
      if (points.every((p) => Math.abs(p.x) < 0.78 && Math.abs(p.y) < 0.73))
        break;
      camera.position.sub(center).multiplyScalar(1.12).add(center);
      camera.updateMatrixWorld(true);
    }
    controls.current.target.copy(center);
    controls.current.update();
    finishPose();
  }, [
    state.preset,
    state.revision,
    sharedFitAtoms,
    manageCamera,
    representation,
    parts,
    camera,
    size.width,
    size.height,
    invalidate,
  ]);
  useEffect(() => {
    const meshes: THREE.Mesh[] = [];
    scene.traverse((o) => {
      if (o instanceof THREE.Mesh && o.userData.pickable) meshes.push(o);
    });
    const ray = new THREE.Raycaster();
    const visibility = () => {
      const total: Record<string, number> = {},
        visible: Record<string, number> = {};
      for (const mesh of meshes) {
        const atoms = mesh.userData.atoms as Atom[];
        if (!atoms) continue;
        atoms.forEach((a, i) => {
          if (!parts.contactIds.has(a.residue_id)) return;
          total[a.residue_id] = (total[a.residue_id] || 0) + 1;
          const p = new THREE.Vector3(...a.xyz);
          if (mesh instanceof THREE.InstancedMesh) {
            const mat = new THREE.Matrix4();
            mesh.getMatrixAt(i, mat);
            p.setFromMatrixPosition(mat);
          }
          p.applyMatrix4(mesh.matrixWorld);
          const ndc = p.clone().project(camera);
          if (Math.abs(ndc.x) > 1 || Math.abs(ndc.y) > 1 || Math.abs(ndc.z) > 1)
            return;
          ray.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), camera);
          const hit = ray.intersectObjects(meshes)[0];
          if (
            hit?.object === mesh &&
            sourceAtomAt(hit)?.residue_id === a.residue_id
          )
            visible[a.residue_id] = (visible[a.residue_id] || 0) + 1;
        });
      }
      return {
        visible_residue_ids: Object.keys(visible),
        occlusion_fractions: Object.fromEntries(
          Object.entries(total).map(([k, n]) => [k, 1 - (visible[k] || 0) / n]),
        ),
      };
    };
    let active = true;
    onHandle({
      cancelMotion: () => { transition.current = null; settled.current = 0; invalidate(); },
      ready: async () => {
        await document.fonts.ready;
        if (!active) return;
        gl.compile(scene, camera);
        await new Promise<void>((resolve) => {
          const check = () => {
            if (!active || (!transition.current && settled.current >= 4)) resolve();
            else requestAnimationFrame(check);
          };
          check();
        });
      },
      inspect: () => ({
        camera_transitioning: transition.current !== null,
        representation,
        representation_protocol:
          representation === "surface"
            ? {
                target: surfaceMeshes.target.protocol,
                binder: surfaceMeshes.binder.protocol,
              }
            : representation === "ribbon"
              ? {
                  method:
                    "Cα trace; spline interpolation, not secondary structure; sidechains omitted",
                }
              : {
                  method: detail
                    ? "contact-only atom cutaway"
                    : "instanced atoms",
                },
        picking_definition:
          representation === "atoms"
            ? "exact atom instance"
            : "source atom associated with nearest intersected triangle vertex",
        camera: {
          position: camera.position.toArray(),
          quaternion: camera.quaternion.toArray(),
          up: camera.up.toArray(),
          target: controls.current.target.toArray(),
          projection: camera.type,
          fov: (camera as THREE.PerspectiveCamera).fov,
          near: camera.near,
          far: camera.far,
        },
        renderer: {
          type: "WebGL2",
          three: THREE.REVISION,
          device: gl.getContext().getParameter(gl.getContext().RENDERER),
        },
        ...visibility(),
        physical_to_scene: {
          units: "angstrom",
          scale: 1,
          binder_offset: state.preset === "exploded" ? 12 : 0,
          illustrative: state.preset === "exploded",
        },
        frame_times_ms: frameTimes.current.slice(),
        triangles: meshes.reduce((sum, mesh) => sum +
          (mesh.geometry.index?.count ?? mesh.geometry.attributes.position?.count ?? 0) / 3 *
          (mesh instanceof THREE.InstancedMesh ? mesh.count : 1), 0),
        atoms: parts.atoms.length,
        viewport: { ...size, dpr: gl.getPixelRatio() },
      }),
      pick: (x, y) => {
        ray.setFromCamera(
          new THREE.Vector2(
            (x / size.width) * 2 - 1,
            1 - (y / size.height) * 2,
          ),
          camera,
        );
        const hit = ray.intersectObjects(meshes)[0];
        return hit ? (sourceAtomAt(hit)?.residue_id ?? null) : null;
      },
      capture: () => {
        gl.render(scene, camera);
        return gl.domElement.toDataURL("image/png");
      },
    });
    return () => {
      active = false;
      onHandle(null);
    };
  }, [
    camera,
    gl,
    scene,
    size,
    parts,
    onHandle,
    state.preset,
    representation,
    surfaceMeshes,
  ]);
  const pearl = state.style === "pearl";
  const targets = parts.target.filter(
    (a) => !parts.contactIds.has(a.residue_id),
  );
  const seam = parts.target.filter((a) => parts.contactIds.has(a.residue_id));
  return (
    <>
      <color attach="background" args={["#07111d"]} />
      <ambientLight intensity={0.55} />
      <directionalLight
        position={[35, 45, 30]}
        intensity={2.8}
        color={pearl ? "#daeaff" : "#ffdda3"}
      />
      <directionalLight
        position={[-35, 15, -15]}
        intensity={2.7}
        color={pearl ? "#70bed8" : "#807dff"}
      />
      <directionalLight position={[30, -10, 30]} intensity={0.7} />
      {representation === "atoms" ? (
        <>
          {" "}
          {!detail && (
            <Molecule
              atoms={targets}
              color={pearl ? "#c7d3db" : "#a77948"}
              selected={state.selected}
              onPick={onPick}
              style={state.style}
              role="target"
            />
          )}
          <Molecule
            detail={detail}
            atoms={seam}
            color={pearl ? "#e9907b" : "#e9be69"}
            selected={state.selected}
            onPick={onPick}
            style={state.style}
            role="interface"
          />
          <Molecule
            detail={detail}
            atoms={
              detail
                ? parts.binder.filter((a) => parts.contactIds.has(a.residue_id))
                : parts.binder
            }
            color={pearl ? "#26b8cd" : "#9193fc"}
            selected={state.selected}
            onPick={onPick}
            offset={state.preset === "exploded" ? 12 : 0}
            style={state.style}
            role="binder"
          />
        </>
      ) : (
        <>
          <SourceMesh
            bundle={bundle}
            atoms={parts.target}
            surface={surfaceMeshes.target}
            representation={representation}
            color={pearl ? "#c7d3db" : "#a77948"}
            contacts={parts.contactIds}
            selected={state.selected}
            offset={0}
            style={state.style}
            onPick={onPick}
          />
          <SourceMesh
            bundle={bundle}
            atoms={parts.binder}
            surface={surfaceMeshes.binder}
            representation={representation}
            color={pearl ? "#26b8cd" : "#9193fc"}
            contacts={new Set()}
            selected={state.selected}
            offset={state.preset === "exploded" ? 12 : 0}
            style={state.style}
            onPick={onPick}
          />
        </>
      )}
      {state.selected &&
        bundle.metrics.contacts
          .filter(
            (c) =>
              c.distance_angstrom <= 4.5 &&
              (c.target_residue === state.selected ||
                c.binder_residue === state.selected),
          )
          .slice(0, 30)
          .map((c, i) => {
            const a = bundle.structure.atoms.find(
                (a) => a.id === c.target_atom,
              )!,
              b = bundle.structure.atoms.find((a) => a.id === c.binder_atom)!;
            return (
              <Line
                key={i}
                points={[
                  a.xyz,
                  [
                    b.xyz[0] + (state.preset === "exploded" ? 12 : 0),
                    b.xyz[1],
                    b.xyz[2],
                  ],
                ]}
                color="#ffd394"
                lineWidth={1}
              />
            );
          })}
      {!sharedControls && <OrbitControls
        ref={controls}
        makeDefault
        enableDamping={false}
        onStart={() => { transition.current = null; settled.current = 0; invalidate(); }}
        minDistance={4}
        maxDistance={400}
      />}
    </>
  );
}
export default function Stage(props: {
  bundle: Bundle;
  meshes: Record<string, SurfaceMesh>;
  state: SceneState;
  onPick: (id: string) => void;
  onHandle: (h: StageHandle | null) => void;
}) {
  return (
    <Canvas
      frameloop="demand"
      camera={{ fov: 38, near: 0.1, far: 2000 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, preserveDrawingBuffer: true }}
    >
      <Scene {...props} />
    </Canvas>
  );
}
