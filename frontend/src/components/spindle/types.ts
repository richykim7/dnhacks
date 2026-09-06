export type Vec3 = [number, number, number];
export type SpindleFrame = {
  time: number;
  poles: { id: string; position: Vec3 }[];
  filaments: { id: string; pole: string; points: Vec3[] }[];
};
export type SpindleBundle = {
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
  camera?: { position: Vec3; target: Vec3 };
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
  return b;
}
