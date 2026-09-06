export type Atom = {
  id: number;
  residue_id: string;
  name: string;
  element: string;
  xyz: [number, number, number];
};
export type Residue = {
  id: string;
  chain: string;
  auth_seq_id: number;
  insertion_code: string;
  name: string;
  label_seq_id: number | null;
  label_asym_id: string;
};
export type Contact = {
  target_residue: string;
  binder_residue: string;
  target_atom: number;
  binder_atom: number;
  distance_angstrom: number;
};
export type Bundle = {
  schema: "binder_bundle.v1";
  manifest: {
    candidate_id: string;
    assembly: string;
    provenance: { category: string; source_ids: string[] };
    scope: Record<string, string>;
  };
  structure: { atoms: Atom[]; residues: Residue[]; source_sha256: string };
  surface_options?: Record<string, number>;
  target_chains: string[];
  binder_chains: string[];
  metrics: {
    protocol: Record<string, unknown>;
    contacts: Contact[];
    counts: Record<string, number>;
    clash_count: number;
    total_buried_area_angstrom2: number | null;
    context: string;
    missingness: string[];
  };
  files: Record<string, { base64: string; sha256: string }>;
};
export type SurfaceMesh = {
  positions: Float32Array;
  indices: Uint32Array;
  normals: Float32Array;
  sourceAtoms: Uint32Array;
  protocol: Record<string, unknown>;
};
export type Representation = "atoms" | "surface" | "ribbon";
export type Preset =
  | "hero"
  | "epitope"
  | "interface-close"
  | "reverse"
  | "exploded"
  | "candidate-compare"
  | "small-screen";
export type Style = "pearl" | "copper";
export type CameraRecipe = {
  position: [number, number, number];
  target: [number, number, number];
  up?: [number, number, number];
  fov?: number;
  near?: number;
  far?: number;
  projection?: string;
  height?: number;
  zoom?: number;
};
export type SceneAction = {
  sequence: number;
  note: string;
  recipe_sha256: string;
  view: Omit<SceneState, "revision">;
};
export type SceneState = {
  preset: Preset;
  style: Style;
  selected: string | null;
  revision: number;
  comparison_bundle_sha256?: string | null;
  comparison_selected?: string | null;
  camera?: CameraRecipe | null;
  representation?: Representation;
};
export const label = (r: Residue) =>
  `${r.chain} · ${r.name} ${r.auth_seq_id}${r.insertion_code}`;
