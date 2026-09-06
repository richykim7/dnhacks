import { describe, it, expect } from "vitest";
import { aggregateCells, boundedVolume } from "./aggregation";
import { sampleField, conditionIndices, initialView, type Cell } from "./types";
describe("source coordinate and population invariants", () => {
  it("bounds mobile volume textures using voxel means", () => {
    const field = {
      dimensions: [128, 2, 2] as [number, number, number],
      values: Array.from({ length: 512 }, (_, i) => i % 128),
    };
    const display = boundedVolume(field);
    expect(display.dimensions).toEqual([64, 2, 2]);
    expect(display.values[0]).toBe(0.5);
    expect(display.values[63]).toBe(126.5);
    expect(field.values[0]).toBe(0);
  });
  it("samples x-fastest voxels in a noncubic translated domain", () => {
    const frame = {
      time: 0,
      cells: [],
      field: {
        dimensions: [2, 3, 4] as [number, number, number],
        values: Array.from({ length: 24 }, (_, i) => i),
      },
    };
    const domain = {
      bounds: [10, 20, 30, 14, 26, 38] as [
        number,
        number,
        number,
        number,
        number,
        number,
      ],
      units: "µm" as const,
    };
    expect(sampleField(frame, domain, [13, 23, 37])).toBe(21);
    expect(sampleField(frame, domain, [10, 20, 30])).toBe(0);
  });
  it("retains full population and occupied volume across mobile bins", () => {
    const cells: Cell[] = Array.from({ length: 10000 }, (_, i) => ({
      id: i,
      position: [i % 50, (i % 200) / 4, Math.floor(i / 200)],
      radius: 1 + (i % 3),
      type: i % 7 ? "tumor" : "CAF",
      state: i % 5 ? "alive" : "dead",
      parent_id: null,
      alanine: 0,
    }));
    const glyphs = aggregateCells(cells);
    expect(glyphs.length).toBeLessThanOrEqual(2000);
    expect(glyphs.reduce((s, c) => s + c.population, 0)).toBe(10000);
    expect(new Set(glyphs.flatMap((c) => c.members)).size).toBe(10000);
    expect(glyphs.reduce((s, c) => s + c.radius ** 3, 0)).toBeCloseTo(
      cells.reduce((s, c) => s + c.radius ** 3, 0),
      6,
    );
  });
  it("compares the selected control against baseline", () => {
    expect(
      conditionIndices({ ...initialView, comparison: true, condition: 3 }),
    ).toEqual([0, 3]);
  });
});
