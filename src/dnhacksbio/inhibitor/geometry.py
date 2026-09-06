"""Canonical, immutable molecular identities from Gemmi, in Angstroms.

Display bonds are distance-inferred guides, not chemical bond-order assignments.
No assembly expansion, alternate-location choice, protonation or repair is implicit.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from itertools import product
import math
from urllib.parse import quote

import gemmi

VERSION = 'gemmi-geometry-v1'
MAX_BYTES = 20 * 1024 * 1024
MAX_ATOMS = 100_000


def normalize(raw: bytes, fmt: str, expected_hash: str | None = None) -> dict:
    digest = sha256(raw).hexdigest()
    if expected_hash is not None and digest != expected_hash:
        raise ValueError('Structure hash mismatch')
    if len(raw) > MAX_BYTES:
        raise ValueError('Structure exceeds 20 MB limit')
    text = raw.decode('utf-8')
    if fmt == 'pdb':
        structure = gemmi.read_pdb_string(text)
    elif fmt == 'cif':
        structure = gemmi.make_structure_from_block(gemmi.cif.read_string(text).sole_block())
    else:
        raise ValueError('Unsupported molecular format')
    structure.setup_entities()
    atoms, residues, backbones = [], [], []
    for mi, model in enumerate(structure):
        for ci, chain in enumerate(model):
            backbone = []
            for ri, residue in enumerate(chain):
                # Ordinals disambiguate duplicate chain/residue names while preserving author IDs.
                rid = f'{mi}/{ci}/{ri}:{quote(chain.name, safe="")}:{residue.seqid}:{residue.name}'
                water = residue.is_water()
                polymer = residue.entity_type == gemmi.EntityType.Polymer
                kind = 'water' if water else 'polymer' if polymer else 'ligand'
                r = dict(id=rid, name=residue.name, chain=chain.name, sequence=str(residue.seqid),
                         model=mi, kind=kind, atoms=[])
                for ai, atom in enumerate(residue):
                    xyz = [atom.pos.x, atom.pos.y, atom.pos.z]
                    if not all(math.isfinite(v) and abs(v) <= 1e6 for v in xyz):
                        raise ValueError('Invalid atomic coordinates')
                    if len(atoms) >= MAX_ATOMS:
                        raise ValueError('Structure exceeds atom limit')
                    index = len(atoms)
                    alt = atom.altloc.strip('\x00 ')
                    atoms.append(dict(id=f'{rid}/{ai}:{quote(atom.name, safe="")}:{alt}',
                                      residue_id=rid, name=atom.name, element=atom.element.name,
                                      position=xyz, occupancy=atom.occ, altloc=alt,
                                      model=mi, kind=kind, radius=atom.element.vdw_r,
                                      covalent_radius=atom.element.covalent_r))
                    r['atoms'].append(index)
                    if polymer and atom.name == 'CA' and alt in ('', 'A'):
                        if backbone and math.dist(atoms[backbone[-1]]['position'], xyz) > 4.5:
                            if len(backbone) > 1:
                                backbones.append(backbone)
                            backbone = []
                        backbone.append(index)
                residues.append(r)
            if len(backbone) > 1:
                backbones.append(backbone)
    if not atoms:
        raise ValueError('No atoms could be read from structure')
    # Bounded spatial neighborhood instead of quadratic all-pairs for a large protein.
    cells, bonds = defaultdict(list), []
    for i, a in enumerate(atoms):
        cell = tuple(math.floor(v / 3) for v in a['position'])
        for delta in product((-1, 0, 1), repeat=3):
            for k in cells[(a['model'], *(cell[d] + delta[d] for d in range(3)))]:
                b = atoms[k]
                if a['altloc'] and b['altloc'] and a['altloc'] != b['altloc']:
                    continue
                if a['kind'] != b['kind'] or a['kind'] == 'water':
                    continue
                if a['kind'] == 'ligand' and a['residue_id'] != b['residue_id']:
                    continue
                dist = math.dist(a['position'], b['position'])
                if 0.4 < dist < min(2.7, a['covalent_radius'] + b['covalent_radius'] + 0.4):
                    bonds.append([k, i])
                    if len(bonds) > MAX_ATOMS * 8:
                        raise ValueError('Geometry too dense')
        cells[(a['model'], *cell)].append(i)
    return dict(schema_version=1, adapter=VERSION, producer=f'Gemmi {gemmi.__version__}',
                source_hash=digest, units='Å', coordinate_frame='deposited coordinates; no assembly expansion',
                atoms=atoms, residues=residues, backbones=backbones, bonds=bonds,
                model_count=len(structure),
                warnings=['Display bonds are inferred by covalent radii + 0.4 Å; bond orders are unassigned.',
                          'Alternate locations, waters and cofactors retained. Models are separate conformations.',
                          'CA traces and atom radii are illustrative representations; no solvent surface calculated.'])


def _selection(geometry, ids):
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Select unique grounded atom IDs')
    lookup = {a['id']: a for a in geometry['atoms']}
    try:
        atoms = [lookup[i] for i in ids]
    except (KeyError, TypeError) as exc:
        raise ValueError('Unknown atom identity') from exc
    if len({a['model'] for a in atoms}) != 1:
        raise ValueError('Cannot measure across separate models')
    if len({a['altloc'] for a in atoms if a['altloc']}) > 1:
        raise ValueError('Cannot combine incompatible alternate locations')
    return atoms


def measure(geometry, ids):
    if len(ids) not in (2, 3):
        raise ValueError('A distance needs two atoms; an angle needs three')
    atoms = _selection(geometry, ids)
    p = [a['position'] for a in atoms]
    if len(p) == 2:
        value, units = math.dist(*p), 'Å'
    else:
        u, v = [[x-y for x,y in zip(p[i], p[1])] for i in (0, 2)]
        norm = math.sqrt(sum(x*x for x in u) * sum(x*x for x in v))
        if norm == 0:
            raise ValueError('Angle undefined for coincident atoms')
        value, units = math.degrees(math.acos(max(-1, min(1, sum(x*y for x,y in zip(u,v))/norm)))), 'degrees'
    return dict(atom_ids=ids, value=value, units=units, coordinate_frame='canonical', source_hash=geometry['source_hash'])


def define_pocket(geometry, residue_id, margin=5.0):
    if isinstance(margin, bool) or not math.isfinite(margin) or not 0 < margin <= 20:
        raise ValueError('Pocket margin must be in (0, 20] Å')
    selected = [a for a in geometry['atoms'] if a['residue_id'] == residue_id]
    if not selected:
        raise ValueError('Unknown residue identity')
    low = [min(a['position'][i] for a in selected)-margin for i in range(3)]
    high = [max(a['position'][i] for a in selected)+margin for i in range(3)]
    return dict(source_hash=geometry['source_hash'], residue_id=residue_id, margin=margin, units='Å',
                center=[(x+y)/2 for x,y in zip(low,high)], size=[y-x for x,y in zip(low,high)],
                rationale='Axis-aligned box around selected deposited residue plus declared margin')


def audit_pose(geometry, residue_id, cutoff=4.0):
    if not math.isfinite(cutoff) or not 0 < cutoff <= 8:
        raise ValueError('Contact cutoff must be in (0, 8] Å')
    ligand = [a for a in geometry['atoms'] if a['residue_id'] == residue_id and a['element'] != 'H']
    if not ligand or len(ligand) > 512:
        raise ValueError('Select a residue with 1–512 heavy atoms')
    contacts = []
    for b in geometry['atoms']:
        if b['residue_id'] == residue_id or b['model'] != ligand[0]['model'] or b['element'] == 'H':
            continue
        for a in ligand:
            if a['altloc'] and b['altloc'] and a['altloc'] != b['altloc']:
                continue
            d = math.dist(a['position'], b['position'])
            if d <= cutoff:
                contacts.append(dict(atom_ids=[a['id'], b['id']], residue_id=b['residue_id'],
                                     distance=d, kind='severe_overlap' if d < 1.2 else 'proximity'))
                if len(contacts) > 20000:
                    raise ValueError('Too many contacts; narrow selection')
    return dict(source_hash=geometry['source_hash'], rule='heavy-atom-proximity-v1', cutoff=cutoff,
                units='Å', contacts=sorted(contacts, key=lambda c:c['distance']),
                limitations=['Proximity is not an assigned hydrogen bond.',
                             'Severe overlap is a <1.2 Å geometric flag, not a force-field clash energy.',
                             'No crystal symmetry contacts or periodic images included.'])


def preparation_audit(geometry):
    atoms = geometry['atoms']
    return dict(status='blocked', changes=[], source_hash=geometry['source_hash'],
                retained=dict(waters=sum(r['kind']=='water' for r in geometry['residues']),
                              alternate_atoms=sum(bool(a['altloc']) for a in atoms),
                              hydrogens=sum(a['element']=='H' for a in atoms)),
                reason='No frozen receptor protonation/repair policy, ligand stereochemistry and charge assignment, '
                       'or validated PDBQT preparation is registered. Deposited coordinates remain unchanged; docking unavailable.')
