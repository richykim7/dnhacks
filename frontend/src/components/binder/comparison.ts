import type { Bundle } from "./types";

function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
    .map(([key, item]) => `${JSON.stringify(key)}:${stable(item)}`).join(",")}}`;
  return JSON.stringify(value);
}

/** Exact alignment: never fit differing target coordinates onto each other silently. */
export function requireComparable(first: Bundle, second: Bundle) {
  const target = (b: Bundle) => {
    const residues = b.structure.residues.filter(r => b.target_chains.includes(r.chain));
    const ids = new Set(residues.map(r => r.id));
    return { residues, atoms: b.structure.atoms.filter(a => ids.has(a.residue_id)).map(a => {
      const full = a as typeof a & { altloc?: string; occupancy?: number };
      return { residue_id: a.residue_id, name: a.name, element: a.element, xyz: a.xyz,
        altloc: full.altloc, occupancy: full.occupancy };
    }) };
  };
  if (stable(first.manifest.scope) !== stable(second.manifest.scope) ||
    stable(first.metrics.protocol) !== stable(second.metrics.protocol) || stable(target(first)) !== stable(target(second)))
    throw Error("Comparison requires identical target coordinates, residue mapping, metric protocol and experiment scope.");
}
