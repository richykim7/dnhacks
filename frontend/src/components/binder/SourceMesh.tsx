import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { type ThreeEvent } from "@react-three/fiber";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import type { Atom, Bundle, Style, SurfaceMesh } from "./types";

export function sourceAtomAt(hit: THREE.Intersection): Atom | null {
  const object = hit.object as THREE.Mesh;
  if (hit.instanceId !== undefined)
    return object.userData.atoms?.[hit.instanceId] ?? null;
  if (!hit.face || !object.userData.sourceAtomIds) return null;
  const positions = object.geometry.getAttribute("position");
  let nearest = hit.face.a,
    distance = Infinity;
  for (const index of [hit.face.a, hit.face.b, hit.face.c]) {
    const point = new THREE.Vector3()
      .fromBufferAttribute(positions, index)
      .applyMatrix4(object.matrixWorld);
    const d = point.distanceToSquared(hit.point);
    if (d < distance) {
      nearest = index;
      distance = d;
    }
  }
  return (
    object.userData.atomMap.get(object.userData.sourceAtomIds[nearest]) ?? null
  );
}
const amino = new Set(
  "ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL MSE SEC PYL".split(
    " ",
  ),
);
export function traceFragments(bundle: Bundle, atoms: Atom[]) {
  const eligible = new Map(
    atoms
      .filter((a) => a.name === "CA" && a.element === "C")
      .map((a) => [a.residue_id, a]),
  );
  const fragments: Atom[][] = [];
  let current: Atom[] = [];
  let chain = "";
  let previousNumber: number | null = null;
  for (const residue of bundle.structure.residues) {
    const atom = amino.has(residue.name) ? eligible.get(residue.id) : undefined;
    const prior = current.at(-1);
    const gap =
      prior && atom
        ? Math.hypot(...atom.xyz.map((v, i) => v - prior.xyz[i]))
        : Infinity;
    const numberedGap =
      previousNumber !== null && residue.auth_seq_id > previousNumber + 1;
    if (
      !atom ||
      chain !== residue.chain ||
      gap > 4.5 ||
      (gap < 2.5 && !!prior) ||
      numberedGap
    ) {
      if (current.length > 1) fragments.push(current);
      current = [];
    }
    if (atom) current.push(atom);
    chain = residue.chain;
    previousNumber = residue.auth_seq_id;
  }
  if (current.length > 1) fragments.push(current);
  return fragments;
}
export function hasBackboneTrace(bundle: Bundle) {
  const residues = new Map(bundle.structure.residues.map((r) => [r.id, r]));
  return [bundle.target_chains, bundle.binder_chains].every(
    (chains) =>
      traceFragments(
        bundle,
        bundle.structure.atoms.filter((a) =>
          chains.includes(residues.get(a.residue_id)!.chain),
        ),
      ).length > 0,
  );
}
function trace(bundle: Bundle, atoms: Atom[]) {
  const fragments = traceFragments(bundle, atoms);
  const geometries: THREE.BufferGeometry[] = [];
  const source: number[] = [];
  for (const fragment of fragments) {
    const segments = (fragment.length - 1) * 6;
    const curve = new THREE.CatmullRomCurve3(
      fragment.map((a) => new THREE.Vector3(...a.xyz)),
      false,
      "centripetal",
    );
    const geometry = new THREE.TubeGeometry(curve, segments, 0.38, 6, false);
    geometries.push(geometry);
    for (let ring = 0; ring <= segments; ring++)
      for (let side = 0; side <= 6; side++)
        source.push(
          fragment[Math.round((ring / segments) * (fragment.length - 1))].id,
        );
  }
  if (!geometries.length) return null;
  const geometry = mergeGeometries(geometries)!;
  geometries.forEach((g) => g.dispose());
  return { geometry, source: new Uint32Array(source) };
}

export default function SourceMesh({
  bundle,
  atoms,
  surface,
  representation,
  color,
  contacts,
  selected,
  offset,
  style,
  onPick,
}: {
  bundle: Bundle;
  atoms: Atom[];
  surface?: SurfaceMesh;
  representation: "surface" | "ribbon";
  color: string;
  contacts: Set<string>;
  selected: string | null;
  offset: number;
  style: Style;
  onPick: (id: string) => void;
}) {
  const mesh = useRef<THREE.Mesh>(null!);
  const prepared = useMemo(() => {
    if (representation === "ribbon") return trace(bundle, atoms);
    if (!surface) return null;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(surface.positions, 3),
    );
    geometry.setAttribute(
      "normal",
      new THREE.BufferAttribute(surface.normals, 3),
    );
    geometry.setIndex(new THREE.BufferAttribute(surface.indices, 1));
    return { geometry, source: surface.sourceAtoms };
  }, [surface, representation, bundle, atoms]);
  useEffect(
    () => () => {
      prepared?.geometry.dispose();
    },
    [prepared],
  );
  useLayoutEffect(() => {
    if (!prepared || !mesh.current) return;
    const atomMap = new Map(bundle.structure.atoms.map((a) => [a.id, a]));
    const colors = new Float32Array(prepared.source.length * 3);
    prepared.source.forEach((id, i) => {
      const residue = atomMap.get(id)!.residue_id;
      const material = new THREE.Color(
        residue === selected
          ? "#ffe69b"
          : contacts.has(residue)
            ? style === "pearl"
              ? "#e9907b"
              : "#e9be69"
            : color,
      );
      material.toArray(colors, i * 3);
    });
    prepared.geometry.setAttribute(
      "color",
      new THREE.BufferAttribute(colors, 3),
    );
    prepared.geometry.computeBoundingSphere();
    mesh.current.userData = {
      atoms,
      atomMap,
      sourceAtomIds: prepared.source,
      pickable: true,
      representation,
    };
  }, [prepared, bundle, atoms, color, contacts, selected, representation]);
  if (!prepared) return null;
  return (
    <mesh
      ref={mesh}
      geometry={prepared.geometry}
      position={[offset, 0, 0]}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        const atom = sourceAtomAt(e);
        if (atom) onPick(atom.residue_id);
      }}
    >
      <meshPhysicalMaterial
        vertexColors
        roughness={style === "pearl" ? 0.4 : 0.3}
        metalness={style === "pearl" ? 0.1 : 0.65}
        clearcoat={0.5}
      />
    </mesh>
  );
}
