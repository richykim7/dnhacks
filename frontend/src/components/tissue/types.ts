export type Cell = {
  id: number;
  position: [number, number, number];
  radius: number;
  type: "tumor" | "CAF";
  state: "alive" | "dead";
  parent_id: number | null;
  alanine: number;
};
export type Frame = {
  time: number;
  cells: Cell[];
  field: { dimensions: [number, number, number]; values: number[] };
};
export type Tissue = {
  schema_version: 1;
  kind: "tissue_simulation";
  category: "illustration" | "simulation";
  name: string;
  domain: {
    bounds: [number, number, number, number, number, number];
    units: "µm";
  };
  field_range: [number, number];
  conditions: { id: string; label: string; frames: Frame[] }[];
  provenance: Record<string, unknown>;
  analysis: Record<string, unknown>;
};
export type View = {
  theme: "dark" | "light";
  preset: "Exterior" | "Core" | "Neighborhood";
  frame: number;
  section: number;
  opacity: number;
  fieldMaximum: number;
  diagnosticSlice: boolean;
  comparison: boolean;
  condition: number;
  selection: number | null;
  azimuth: number;
  elevation: number;
  zoom: number;
};
export const initialView: View = {
  theme: "dark",
  preset: "Exterior",
  frame: 0,
  section: 160,
  opacity: 0,
  fieldMaximum: 1.01,
  diagnosticSlice: false,
  comparison: false,
  condition: 0,
  selection: null,
  azimuth: 0.48,
  elevation: 0.32,
  zoom: 1,
};
export function sampleField(
  frame: Frame,
  domain: Tissue["domain"],
  p: number[],
) {
  const [nx, ny, nz] = frame.field.dimensions,
    b = domain.bounds;
  const q = p.map((v, i) =>
    Math.max(
      0,
      Math.min(
        [nx, ny, nz][i] - 1,
        Math.floor((v - b[i]) / ((b[i + 3] - b[i]) / [nx, ny, nz][i])),
      ),
    ),
  );
  return frame.field.values[q[0] + nx * (q[1] + ny * q[2])];
}

export function conditionIndices(view: View): number[] {
  return view.comparison ? [0, view.condition || 1] : [view.condition];
}
