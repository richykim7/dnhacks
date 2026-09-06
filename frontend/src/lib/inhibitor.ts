export type Vec3 = [number, number, number];
export type Atom = {
  id: string;
  residue_id: string;
  name: string;
  element: string;
  position: Vec3;
  kind: string;
  model: number;
  altloc: string;
  radius: number;
};
export type Residue = {
  id: string;
  name: string;
  chain: string;
  sequence: string;
  model: number;
  kind: string;
  atoms: number[];
};
export type Geometry = {
  schema_version: number;
  source_hash: string;
  producer: string;
  units: string;
  coordinate_frame: string;
  atoms: Atom[];
  residues: Residue[];
  bonds: [number, number][];
  backbones: number[][];
  warnings: string[];
  model_count: number;
};
export type Recipe = {
  schema_version: 1;
  source_hash: string;
  revision: number;
  style: "matte" | "luminous" | "measurement";
  shot: "arrival" | "pocket" | "oblique";
  camera?: { position: Vec3; target: Vec3 };
  ligand: string;
  model: number;
  clip: boolean;
  selected: string[];
  frame: 0;
  pose?: string;
  bundle?: string;
  compare?: boolean;
  prepared?: boolean;
  surface?: boolean;
};
export type Pose = {
  id: string;
  positions: Vec3[];
  score?: number;
  rmsd?: number;
  seed?: number;
  rank?: number;
  label?: string;
};
export type Surface = {
  positions: Vec3[];
  triangle_atom_ids: string[];
  algorithm: string;
};
export type Bundle = {
  source_hash: string;
  ligand_residue: string;
  ligand_atom_names: string[];
  poses: Pose[];
  controls: Pose[];
  prepared_geometry: Geometry;
  original_receptor_geometry: Geometry;
  docking_geometry: Geometry;
  surface?: Surface;
  preparation: any;
  report: any;
  contacts: any;
  files: Record<string, string>;
};
export function poseGeometry(
  g: Geometry,
  b: Bundle | null,
  recipe: Recipe,
): Geometry {
  if (!b) return g;
  const pose = [...b.controls, ...b.poses].find((p) => p.id === recipe.pose);
  if (!pose) return g;
  const positions = new Map(
    b.ligand_atom_names.map((name, i) => [name, pose.positions[i]]),
  );
  return {
    ...g,
    atoms: g.atoms.map((a) =>
      a.residue_id === b.ligand_residue && positions.has(a.name)
        ? { ...a, position: positions.get(a.name)! }
        : a,
    ),
  };
}
export function distance(a: Atom, b: Atom) {
  return Math.hypot(...a.position.map((v, i) => v - b.position[i]));
}
export function center(atoms: Atom[]): Vec3 {
  return [0, 1, 2].map(
    (i) =>
      atoms.reduce((s, a) => s + a.position[i], 0) / Math.max(atoms.length, 1),
  ) as Vec3;
}
export function validateGeometry(g: Geometry, hash?: string) {
  if (
    g.schema_version !== 1 ||
    g.units !== "Å" ||
    !g.atoms?.length ||
    g.atoms.length > 100000 ||
    (hash && hash !== g.source_hash)
  )
    throw Error("Invalid geometry or immutable hash mismatch.");
  if (
    new Set(g.atoms.map((a) => a.id)).size !== g.atoms.length ||
    g.atoms.some(
      (a) =>
        a.position.length !== 3 || a.position.some((v) => !Number.isFinite(v)),
    )
  )
    throw Error("Invalid atom identity or coordinates.");
  return g;
}

// Presentation choreography is separate from the immutable molecular coordinates.
export type ActionKind =
  | "overview"
  | "focus"
  | "preparation"
  | "search"
  | "poses"
  | "measurement"
  | "capture"
  | "review";
export type ActionPresentation = {
  active: boolean;
  playing: boolean;
  sequence: number;
  kind: ActionKind;
  progress: number;
  updatedAt: number;
  speed: number;
  duration: number;
  from?: { position: Vec3; target: Vec3 };
  region?: { center: Vec3; size: Vec3 };
  removed?: Atom[];
  added?: Atom[];
  poses?: Vec3[][];
};
export function actionKind(action: any, previous?: any): ActionKind {
  if (action?.kind === "inhibitor.job")
    return action.details?.status === "completed" ? "poses" : "search";
  if (action?.kind === "scene.measurement") return "measurement";
  if (action?.kind === "scene.capture") return "capture";
  if (["scene.review", "scene.vision"].includes(action?.kind)) return "review";
  if (action?.recipe?.prepared) return "preparation";
  if (
    action?.recipe?.pose &&
    action.recipe.pose !== previous?.recipe?.pose &&
    action.recipe.pose !== "reference"
  )
    return "poses";
  if (action?.recipe?.selected?.length >= 2) return "measurement";
  return action?.recipe?.shot === "arrival" ? "overview" : "focus";
}
export const actionSeconds: Record<ActionKind, number> = {
  overview: 8,
  focus: 8,
  preparation: 10,
  search: 8,
  poses: 10,
  measurement: 8,
  capture: 6,
  review: 8,
};
export const actionPhases: Record<ActionKind, string[]> = {
  overview: [
    "Establish the structure",
    "Locate the intervention",
    "Hold the reference view",
  ],
  focus: [
    "Approach the pocket",
    "Reveal nearby contacts",
    "Inspect the local geometry",
  ],
  preparation: [
    "Compare coordinate models",
    "Reveal recorded preparation changes",
    "Inspect the prepared model",
  ],
  search: [
    "Locate the search region",
    "Show the recorded docking operation",
    "Inspect the job receipt",
  ],
  poses: [
    "Reveal the available pose",
    "Compare molecular geometry",
    "Inspect the recorded result",
  ],
  measurement: [
    "Locate the selected atoms",
    "Construct the measurement",
    "Read the coordinate result",
  ],
  capture: [
    "Frame the scene",
    "Capture the inspection view",
    "Read the capture receipt",
  ],
  review: [
    "Open the recorded evidence",
    "Inspect the captured geometry",
    "Read the recorded observation",
  ],
};
export function actionProgress(
  action: ActionPresentation,
  now = performance.now(),
) {
  return Math.max(
    0,
    Math.min(
      1,
      action.progress +
        (action.playing
          ? (((now - action.updatedAt) / 1000) * action.speed) / action.duration
          : 0),
    ),
  );
}
export function smoothPhase(p: number, start = 0, end = 1) {
  const t = Math.max(0, Math.min(1, (p - start) / (end - start)));
  return t * t * (3 - 2 * t);
}

export function sceneCamera(
  g: Geometry,
  r: Recipe,
): { position: Vec3; target: Vec3 } {
  if (r.camera) return r.camera;
  const atoms = g.atoms.filter((a) => a.model === r.model),
    ligand = atoms.filter((a) => a.residue_id === r.ligand);
  const target = center(
    r.shot === "arrival" ? atoms : ligand.length ? ligand : atoms,
  );
  const radius = Math.max(
    10,
    ...atoms.map((a) => Math.hypot(...a.position.map((v, i) => v - target[i]))),
  );
  const dist = r.shot === "arrival" ? radius * 2.8 : 25,
    offset = r.shot === "oblique" ? [0.85, 0.38, 0.9] : [0.2, 0.22, 1.3];
  return {
    target,
    position: target.map((v, i) => v + offset[i] * dist) as Vec3,
  };
}
