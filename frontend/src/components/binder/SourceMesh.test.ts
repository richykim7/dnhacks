import { expect, test } from "vitest";
import { hasBackboneTrace, traceFragments } from "./SourceMesh";
import type { Bundle } from "./types";
const make = () =>
  ({
    structure: {
      source_sha256: "test",
      residues: [
        ["a", "A", 1],
        ["b", "A", 2],
        ["c", "A", 4],
        ["d", "B", 1],
      ].map(([id, chain, n]) => ({ id, chain, auth_seq_id: n, name: "ALA" })),
      atoms: [
        ["a", 0],
        ["b", 3.8],
        ["c", 7.6],
        ["d", 11.4],
      ].map(([id, x], i) => ({
        id: i,
        residue_id: id,
        name: "CA",
        element: "C",
        xyz: [x, 0, 0],
      })),
    },
    target_chains: ["A"],
    binder_chains: ["B"],
  }) as unknown as Bundle;
test("backbone trace breaks at missing author residues and chain boundaries", () => {
  const b = make();
  expect(
    traceFragments(b, b.structure.atoms).map((f) => f.map((a) => a.residue_id)),
  ).toEqual([["a", "b"]]);
  expect(hasBackboneTrace(b)).toBe(false);
  b.structure.atoms[1].xyz[0] = 10;
  expect(traceFragments(b, b.structure.atoms)).toEqual([]);
});
test("missing CA or nonprotein residues never create a trace segment", () => {
  const b = make();
  b.structure.residues[1].name = "HOH";
  expect(traceFragments(b, b.structure.atoms)).toEqual([]);
  b.structure.residues[1].name = "ALA";
  b.structure.atoms[1].name = "CB";
  expect(traceFragments(b, b.structure.atoms)).toEqual([]);
});
