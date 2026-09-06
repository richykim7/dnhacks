import type { Bundle, SurfaceMesh } from "./types";

async function sha(bytes: Uint8Array) {
  return Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", bytes as BufferSource),
    ),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
}
const finite3 = (v: unknown): v is number[] =>
  Array.isArray(v) &&
  v.length === 3 &&
  v.every((x) => typeof x === "number" && Number.isFinite(x));
self.onmessage = async ({
  data,
}: {
  data: { text: string; sha256: string };
}) => {
  try {
    const bytes = new TextEncoder().encode(data.text);
    if (bytes.length > 20 * 1024 * 1024 || (await sha(bytes)) !== data.sha256)
      throw Error("Candidate artifact hash mismatch");
    const bundle = JSON.parse(data.text) as Bundle;
    if (
      bundle.schema !== "binder_bundle.v1" ||
      !bundle.structure.atoms.length ||
      bundle.structure.atoms.length > 6000
    )
      throw Error("Unsupported binder bundle");
    const meshes: Record<string, SurfaceMesh> = {};
    const transfers: ArrayBuffer[] = [];
    for (const role of ["target", "binder"]) {
      const ref = bundle.files["surface-" + role + ".json"];
      if (!ref) continue;
      const raw = Uint8Array.from(atob(ref.base64), (c) => c.charCodeAt(0));
      if ((await sha(raw)) !== ref.sha256)
        throw Error("Surface member hash mismatch");
      const mesh = JSON.parse(new TextDecoder().decode(raw));
      const atoms = new Set(bundle.structure.atoms.map((a) => a.id));
      if (
        mesh.schema !== "binder_surface.v1" ||
        mesh.source_sha256 !== bundle.structure.source_sha256 ||
        !Array.isArray(mesh.positions) ||
        !mesh.positions.length ||
        mesh.positions.length > 360000 ||
        !mesh.positions.every(finite3) ||
        !Array.isArray(mesh.triangles) ||
        mesh.triangles.length > 120000 ||
        !mesh.triangles.every(
          (t: unknown) =>
            finite3(t) &&
            t.every(
              (i) => Number.isInteger(i) && i >= 0 && i < mesh.positions.length,
            ),
        ) ||
        mesh.source_atom_ids.length !== mesh.positions.length ||
        !mesh.source_atom_ids.every(
          (id: number) => Number.isInteger(id) && atoms.has(id),
        )
      )
        throw Error("Invalid source-mapped surface");
      const positions = new Float32Array(mesh.positions.flat());
      const indices = new Uint32Array(mesh.triangles.flat());
      const sourceAtoms = new Uint32Array(mesh.source_atom_ids);
      const normals = new Float32Array(positions.length);
      const atomMap = new Map(bundle.structure.atoms.map((a) => [a.id, a]));
      const residueMap = new Map(
        bundle.structure.residues.map((r) => [r.id, r]),
      );
      const localAtoms = bundle.structure.atoms.filter(
        (a) =>
          mesh.chains.includes(residueMap.get(a.residue_id)!.chain) &&
          !["H", "D"].includes(a.element),
      );
      const width = 0.6,
        probe = mesh.protocol.probe_angstrom;
      const radii = mesh.protocol.radii_angstrom as Record<string, number>;
      const cellSize =
        Math.max(...localAtoms.map((a) => radii[a.element] + probe)) +
        mesh.protocol.max_vertex_field_residual_angstrom +
        3 * width;
      const buckets = new Map<string, typeof localAtoms>();
      for (const atom of localAtoms) {
        const key = atom.xyz.map((v) => Math.floor(v / cellSize)).join(",");
        const bucket = buckets.get(key) || [];
        bucket.push(atom);
        buckets.set(key, bucket);
      }
      for (let vertex = 0; vertex < sourceAtoms.length; vertex++) {
        const point = [0, 1, 2].map((axis) => positions[vertex * 3 + axis]);
        const witness = atomMap.get(sourceAtoms[vertex])!;
        const minimum =
          Math.hypot(...point.map((v, i) => v - witness.xyz[i])) -
          radii[witness.element] -
          probe;
        const cell = point.map((v) => Math.floor(v / cellSize));
        const normal = [0, 0, 0];
        for (let dx = -1; dx <= 1; dx++)
          for (let dy = -1; dy <= 1; dy++)
            for (let dz = -1; dz <= 1; dz++) {
              const bucket = buckets.get(
                [cell[0] + dx, cell[1] + dy, cell[2] + dz].join(","),
              );
              if (!bucket) continue;
              for (const atom of bucket) {
                const delta = point.map((v, i) => v - atom.xyz[i]);
                const length = Math.hypot(...delta);
                const difference =
                  length - radii[atom.element] - probe - minimum;
                if (difference > 3 * width || length < 1e-8) continue;
                const weight = Math.exp(-((difference / width) ** 2));
                for (let axis = 0; axis < 3; axis++)
                  normal[axis] += (weight * delta[axis]) / length;
              }
            }
        const length = Math.hypot(...normal) || 1;
        for (let axis = 0; axis < 3; axis++)
          normals[vertex * 3 + axis] = normal[axis] / length;
      }
      meshes[role] = {
        positions,
        indices,
        normals,
        sourceAtoms,
        protocol: {
          ...mesh.protocol,
          shading:
            "Gaussian blend of source sphere normals, width0.6Å; mesh coordinates unchanged",
          gpu_position_precision: "float32",
        },
      };
      transfers.push(
        positions.buffer,
        indices.buffer,
        normals.buffer,
        sourceAtoms.buffer,
      );
    }
    self.postMessage({ bundle, meshes }, { transfer: transfers });
  } catch (error) {
    self.postMessage({
      error: error instanceof Error ? error.message : String(error),
    });
  }
};
