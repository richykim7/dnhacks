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
  structure: { atoms: Atom[]; residues: Residue[] };
  target_chains: string[];
  binder_chains: string[];
  metrics: {
    contacts: Contact[];
    counts: Record<string, number>;
    clash_count: number;
    total_buried_area_angstrom2: number | null;
    context: string;
    missingness: string[];
  };
  files: Record<string, { base64: string; sha256: string }>;
};
export type Preset =
  | "hero"
  | "epitope"
  | "interface-close"
  | "reverse"
  | "exploded"
  | "candidate-compare"
  | "small-screen";
export type Style = "pearl" | "copper";
export type SceneState = {
  preset: Preset;
  style: Style;
  selected: string | null;
  revision: number;
};
export const label = (r: Residue) =>
  `${r.chain} · ${r.name} ${r.auth_seq_id}${r.insertion_code}`;
