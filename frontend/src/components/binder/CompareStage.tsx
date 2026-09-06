import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, View } from "@react-three/drei";
import type { OrbitControls as OrbitImpl } from "three-stdlib";
import { Scene, type StageHandle, type SceneInspection } from "./Stage";
import type { Bundle, SceneState, SurfaceMesh } from "./types";

export type CandidatePick = { bundle_sha256: string; residue_id: string };
export type ComparisonHandle = Omit<StageHandle, "pick"> & {
  comparisonSource: string;
  pick: (x: number, y: number) => CandidatePick | null;
};

/** Two scissored scenes share one actual camera, orbit target and WebGL context. */
export default function CompareStage({ bundle, other, sha256, otherSha256, meshes, otherMeshes,
  state, onPick, onOtherPick, onHandle }: {
  bundle: Bundle; other: Bundle; sha256: string; otherSha256: string;
  meshes: Record<string, SurfaceMesh>; otherMeshes: Record<string, SurfaceMesh>;
  state: SceneState; onPick: (id: string) => void; onOtherPick: (id: string) => void;
  onHandle: (handle: ComparisonHandle | null) => void;
}) {
  const host = useRef<HTMLDivElement>(null!);
  const controls = useRef<OrbitImpl>(null!);
  const left = useRef<StageHandle | null>(null), right = useRef<StageHandle | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize(old => old.width === width && old.height === height ? old : { width, height });
    });
    observer.observe(host.current); return () => observer.disconnect();
  }, []);
  const fitAtoms = useMemo(() => [bundle, other].flatMap(b => {
    const ids = new Set(b.metrics.contacts.filter(c => c.distance_angstrom <= 4.5)
      .flatMap(c => [c.target_residue, c.binder_residue]));
    const close = ["interface-close", "epitope", "reverse"].includes(state.preset);
    const binderIds = new Set(b.structure.residues.filter(r => b.binder_chains.includes(r.chain)).map(r => r.id));
    return b.structure.atoms.filter(a => a.element !== "H" && a.element !== "D" && (!close || ids.has(a.residue_id)))
      .map(a => state.preset === "exploded" && binderIds.has(a.residue_id)
        ? { ...a, xyz: [a.xyz[0] + 12, a.xyz[1], a.xyz[2]] as [number, number, number] } : a);
  }), [bundle, other, state.preset]);
  const leftHandle = useCallback((h: StageHandle | null) => { left.current = h; }, []);
  const rightHandle = useCallback((h: StageHandle | null) => { right.current = h; }, []);
  useEffect(() => {
    let active = true;
    const inspect = () => {
      if (!left.current || !right.current) throw Error("Comparison is still loading");
      const a = left.current.inspect(), b = right.current.inspect();
      const rect = host.current.getBoundingClientRect();
      const views = [a, b].map((view, i) => ({ ...view,
        bundle_sha256: i ? otherSha256 : sha256,
        viewport: { x: rect.width * i / 2, y: 0, width: rect.width / 2, height: rect.height,
          dpr: (view.viewport as { dpr: number }).dpr },
      }));
      return { ...a, views, comparison_bundle_sha256: otherSha256,
        atoms: a.atoms + b.atoms, triangles: a.triangles + b.triangles,
        viewport: { width: rect.width, height: rect.height, dpr: views[0].viewport.dpr } } as SceneInspection;
    };
    onHandle({
      comparisonSource: otherSha256,
      cancelMotion: () => left.current?.cancelMotion(),
      ready: async () => {
        const deadline = performance.now() + 30000;
        while (active && (!left.current || !right.current)) {
          if (performance.now() > deadline) throw Error("Comparison initialization timed out");
          await new Promise(requestAnimationFrame);
        }
        if (!active) return;
        await Promise.all([left.current!.ready(), right.current!.ready()]);
        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      },
      inspect,
      pick: (x, y) => {
        const width = host.current.getBoundingClientRect().width;
        const second = x >= width / 2;
        const id = (second ? right.current : left.current)?.pick(second ? x - width / 2 : x, y);
        return id ? { bundle_sha256: second ? otherSha256 : sha256, residue_id: id } : null;
      },
      capture: () => host.current.querySelector("canvas")!.toDataURL("image/png"),
    });
    return () => { active = false; onHandle(null); };
  }, [onHandle, sha256, otherSha256, size.width, size.height]);
  return <div ref={host} className="binder-compare-stage">
    {size.width > 0 && <>
      <View className="binder-compare-view" key={`left-${size.width}-${size.height}`} index={1}>
        <Scene bundle={bundle} state={state} meshes={meshes} onPick={onPick} onHandle={leftHandle}
          sharedControls={controls} fitAtoms={fitAtoms} />
      </View>
      <View className="binder-compare-view" key={`right-${size.width}-${size.height}`} index={2}>
        <Scene bundle={other} state={{ ...state, selected: state.comparison_selected ?? null }}
          meshes={otherMeshes} onPick={onOtherPick} onHandle={rightHandle}
          sharedControls={controls} manageCamera={false} />
      </View>
      <Canvas frameloop="demand" camera={{ fov: 38, near: .1, far: 2000 }} dpr={[1, 1.5]}
        gl={{ antialias: true, preserveDrawingBuffer: true }} eventSource={host}
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <OrbitControls ref={controls} domElement={host.current} enableDamping={false} minDistance={4}
          maxDistance={400} onStart={() => left.current?.cancelMotion()} />
        <View.Port />
      </Canvas>
    </>}
  </div>;
}
