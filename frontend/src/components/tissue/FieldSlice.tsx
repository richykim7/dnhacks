import { useMemo } from "react";
import type { Frame, Tissue } from "./types";
export default function FieldSlice({
  frame,
  domain,
  z,
  maximum,
}: {
  frame: Frame;
  domain: Tissue["domain"];
  z: number;
  maximum: number;
}) {
  const { pixels, min, max, clipped, plane } = useMemo(() => {
    const [nx, ny, nz] = frame.field.dimensions;
    const bounds = domain.bounds;
    const iz = Math.max(
      0,
      Math.min(
        nz - 1,
        Math.floor(((z - bounds[2]) / (bounds[5] - bounds[2])) * nz),
      ),
    );
    const values = frame.field.values.slice(nx * ny * iz, nx * ny * (iz + 1));
    let min = Infinity,
      max = -Infinity,
      clipped = 0;
    const pixels = values.map((v, i) => {
      min = Math.min(min, v);
      max = Math.max(max, v);
      if (v > maximum) clipped++;
      const t = Math.min(1, Math.max(0, v / maximum));
      return (
        <rect
          key={i}
          x={i % nx}
          y={ny - 1 - Math.floor(i / nx)}
          width={1}
          height={1}
          fill={`rgb(${Math.round(9 + 30 * t)},${Math.round(20 + 210 * t)},${Math.round(35 + 205 * t)})`}
        />
      );
    });
    return {
      pixels,
      min,
      max,
      clipped,
      plane: bounds[2] + ((iz + 0.5) * (bounds[5] - bounds[2])) / nz,
    };
  }, [frame, domain, z, maximum]);
  return (
    <figure className="tissue-field-slice">
      <figcaption>Alanine · exact voxel slice</figcaption>
      <svg
        viewBox={`0 0 ${frame.field.dimensions[0]} ${frame.field.dimensions[1]}`}
        role="img"
        aria-label={`Alanine slice at z ${plane} micrometers; minimum ${min}, maximum ${max} millimolar`}
        shapeRendering="crispEdges"
      >
        {pixels}
      </svg>
      <small>
        Nearest voxel center z {plane.toFixed(1)} µm
        <br />
        to requested z {Number.isInteger(z) ? z : z.toFixed(1)} µm · x → y ↑
        <br />
        {min.toFixed(4)}–{max.toFixed(4)} mM
        <br />
        {clipped} saturated voxels · shared 0–{maximum} mM
      </small>
    </figure>
  );
}
