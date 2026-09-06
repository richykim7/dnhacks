import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { requireComparable } from "./comparison";
import type { Bundle } from "./types";
const first: Bundle = JSON.parse(readFileSync(new URL("../../../e2e/binder-fixture.json", import.meta.url), "utf8"));
const second: Bundle = JSON.parse(readFileSync(new URL("../../../e2e/binder-comparison-fixture.json", import.meta.url), "utf8"));

describe("source-aligned candidate comparison", () => {
  it("allows the rebuilt translated binder while preserving identical target geometry", () => {
    expect(second.metrics.counts["4.5"]).not.toBe(first.metrics.counts["4.5"]);
    expect(second.metrics.clash_count).not.toBe(first.metrics.clash_count);
    expect(() => requireComparable(first, second)).not.toThrow();
  });
  it.each(["coordinate", "residue", "protocol", "scope"])("rejects a changed %s", change => {
    const altered = structuredClone(second);
    if (change === "coordinate") altered.structure.atoms[0].xyz[0] += .01;
    if (change === "residue") altered.structure.residues[0].name = "GLY";
    if (change === "protocol") altered.metrics.protocol.probe_angstrom = 3;
    if (change === "scope") altered.manifest.scope.experiment_id = "other";
    expect(() => requireComparable(first, altered)).toThrow("identical target");
  });
});
