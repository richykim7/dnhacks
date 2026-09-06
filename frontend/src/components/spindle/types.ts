export type Vec3 = [number, number, number];
export type CorticalMotor = { id: string; position: Vec3; force_pn: Vec3 | null; filament: string | null; abscissa_um: number | null };
export type SpindleFrame = {
  cortical_motors?: CorticalMotor[];
  time: number;
  poles: { id: string; position: Vec3 }[];
  filaments: { id: string; pole: string; points: Vec3[] }[];
};
export type SpindleBundle = {
  display_sampling?: { schema: "spindle_display_sampling.v1"; source_trajectory_sha256: string; source_frame_counts: number[]; source_frame_indices: number[][]; method: string };
  schema_version: 1;
  dimensionality: 2 | 3;
  category: "illustration" | "simulation";
  model_id: string;
  units: { length: "um"; time: "s" };
  radius: Vec3;
  runs: { seed: number; condition: string; frames: SpindleFrame[] }[];
};
export type SpindleRecipe = {
  frame: number;
  run: number;
  selected: string | null;
  shot: "front" | "oblique" | "detail";
  treatment: "luminous" | "fine";
  trails: boolean;
  revision: number;
  compare?: number | null;
  camera?: {
    position: Vec3;
    target: Vec3;
    fov?: number;
    near?: number;
    far?: number;
  } | null;
};
export function validateBundle(value: unknown): SpindleBundle {
  const b = value as SpindleBundle;
  if (
    b?.schema_version !== 1 ||
    ![2, 3].includes(b.dimensionality) ||
    !["illustration", "simulation"].includes(b.category) ||
    b.units?.length !== "um" ||
    b.units?.time !== "s" ||
    !Array.isArray(b.runs) ||
    !b.runs.length ||
    b.runs.length > 128
  )
    throw Error("Invalid spindle trajectory manifest");
  const vector = (p: Vec3) =>
    Array.isArray(p) && p.length === 3 && p.every(Number.isFinite);
  if (!vector(b.radius) || b.radius.some((x) => x <= 0))
    throw Error("Invalid cell geometry");
  let points = 0;
  for (const r of b.runs) {
    if (!Array.isArray(r.frames) || !r.frames.length || r.frames.length > 2000)
      throw Error("Invalid trajectory frames");
    let previous = -1;
    for (const f of r.frames) {
      if (
        !Number.isFinite(f.time) ||
        f.time <= previous ||
        !Array.isArray(f.poles) ||
        f.poles.length < 1 ||
        f.poles.length > 32 ||
        !Array.isArray(f.filaments)
      )
        throw Error("Invalid sampled frame");
      previous = f.time;
      if (f.cortical_motors != null) {
        if (!Array.isArray(f.cortical_motors) || f.cortical_motors.length > 1000) throw Error("Invalid motor field");
        const motorIds = new Set<string>();
        for (const m of f.cortical_motors) {
          if (!m.id || motorIds.has(m.id) || !vector(m.position)) throw Error("Invalid cortical motor");
          motorIds.add(m.id);
          if (m.filament == null) {
            if (m.force_pn !== null || m.abscissa_um !== null) throw Error("Unbound motor has bound measurements");
          } else if (!f.filaments.some(x => x.id === m.filament) || !vector(m.force_pn!) || !Number.isFinite(m.abscissa_um)) throw Error("Invalid bound motor");
        }
      }
      const ids = new Set(f.poles.map((p) => p.id));
      if (ids.size !== f.poles.length) throw Error("Duplicate pole identity");
      for (const p of f.poles)
        if (
          !vector(p.position) ||
          (b.dimensionality === 2 && p.position[2] !== 0)
        )
          throw Error("Invalid pole coordinates");
      const fibers = new Set<string>();
      for (const fiber of f.filaments) {
        if (
          fibers.has(fiber.id) ||
          !ids.has(fiber.pole) ||
          !Array.isArray(fiber.points) ||
          fiber.points.length < 2
        )
          throw Error("Invalid filament identity");
        fibers.add(fiber.id);
        for (const p of fiber.points) {
          if (!vector(p) || (b.dimensionality === 2 && p[2] !== 0))
            throw Error("Invalid filament coordinates");
          if (++points > 2000000)
            throw Error("Trajectory exceeds display budget");
        }
      }
    }
  }
  const sampling = b.display_sampling;
  if (sampling != null) {
    if (sampling.schema !== "spindle_display_sampling.v1" || !/^[a-f0-9]{64}$/.test(sampling.source_trajectory_sha256)
      || typeof sampling.method !== "string" || !Array.isArray(sampling.source_frame_counts)
      || !Array.isArray(sampling.source_frame_indices) || sampling.source_frame_counts.length !== b.runs.length
      || sampling.source_frame_indices.length !== b.runs.length) throw Error("Invalid display sampling manifest");
    b.runs.forEach((run, r) => {
      const count = sampling.source_frame_counts[r], indices = sampling.source_frame_indices[r];
      if (!Number.isInteger(count) || count < 1 || count > 2000 || !Array.isArray(indices)
        || indices.length !== run.frames.length || indices[0] !== 0 || indices.at(-1) !== count - 1
        || indices.some((n, i) => !Number.isInteger(n) || n < 0 || n >= count || (i > 0 && n <= indices[i - 1])))
        throw Error("Invalid source frame mapping");
    });
  }
  return b;
}
