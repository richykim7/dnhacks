export type Vec3 = [number, number, number];
export type Atom = {id: string; residue_id: string; name: string; element: string; position: Vec3; kind: string; model: number; altloc: string; radius: number};
export type Residue = {id: string; name: string; chain: string; sequence: string; model: number; kind: string; atoms: number[]};
export type Geometry = {schema_version: number; source_hash: string; producer: string; units: string; coordinate_frame: string; atoms: Atom[]; residues: Residue[]; bonds: [number,number][]; backbones: number[][]; warnings: string[]; model_count: number};
export type Recipe = {schema_version: 1; source_hash: string; revision: number; style: 'matte'|'luminous'; shot: 'arrival'|'pocket'|'oblique'; camera?: {position: Vec3; target: Vec3}; ligand: string; model: number; clip: boolean; selected: string[]; frame: 0};
export function distance(a: Atom,b: Atom) {return Math.hypot(...a.position.map((v,i)=>v-b.position[i]));}
export function center(atoms: Atom[]): Vec3 {return [0,1,2].map(i=>atoms.reduce((s,a)=>s+a.position[i],0)/Math.max(atoms.length,1)) as Vec3;}
export function validateGeometry(g: Geometry, hash?: string) {
  if (g.schema_version!==1 || g.units!=='Å' || !g.atoms?.length || g.atoms.length>100000 || (hash && hash!==g.source_hash)) throw Error('Invalid geometry or immutable hash mismatch.');
  if (new Set(g.atoms.map(a=>a.id)).size!==g.atoms.length || g.atoms.some(a=>a.position.length!==3 || a.position.some(v=>!Number.isFinite(v)))) throw Error('Invalid atom identity or coordinates.');
  return g;
}
