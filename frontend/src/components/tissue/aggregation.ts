import type { Cell, Frame } from "./types";
export type Glyph = Cell & { population: number; members: number[] };
/** Presentation only: sum occupied volume and preserve every source identity. */
export function aggregateCells(cells: Cell[], limit = 2000): Glyph[] {
  if (cells.length <= limit)
    return cells.map((c) => ({ ...c, population: 1, members: [c.id] }));
  for (let width = 10; width <= 20480; width *= 2) {
    const bins = new Map<string, Cell[]>();
    for (const c of cells) {
      const key = [
        c.type,
        c.state,
        ...c.position.map((x) => Math.floor(x / width)),
      ].join(":");
      const group = bins.get(key) || [];
      group.push(c);
      bins.set(key, group);
    }
    if (bins.size > limit) continue;
    return [...bins.values()].map((group) => {
      const volume = group.reduce((s, c) => s + c.radius ** 3, 0);
      return {
        ...group[0],
        position: [0, 1, 2].map(
          (i) =>
            group.reduce((s, c) => s + c.position[i] * c.radius ** 3, 0) /
            volume,
        ) as Cell["position"],
        radius: Math.cbrt(volume),
        population: group.length,
        members: group.map((c) => c.id),
      };
    });
  }
  throw Error("Unable to aggregate the declared tissue domain");
}

export function boundedVolume(
  field: Frame["field"],
  maximum = 64,
): Frame["field"] {
  if (Math.max(...field.dimensions) <= maximum) return field;
  const steps = field.dimensions.map((n) => Math.ceil(n / maximum));
  const dimensions = field.dimensions.map((n, i) =>
    Math.ceil(n / steps[i]),
  ) as [number, number, number];
  const values = new Array(dimensions[0] * dimensions[1] * dimensions[2]).fill(
      0,
    ),
    counts = values.slice();
  const [nx, ny, nz] = field.dimensions;
  for (let z = 0; z < nz; z++)
    for (let y = 0; y < ny; y++)
      for (let x = 0; x < nx; x++) {
        const i =
          Math.floor(x / steps[0]) +
          dimensions[0] *
            (Math.floor(y / steps[1]) +
              dimensions[1] * Math.floor(z / steps[2]));
        values[i] += field.values[x + nx * (y + ny * z)];
        counts[i]++;
      }
  return { dimensions, values: values.map((v, i) => v / counts[i]) };
}
