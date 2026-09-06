"""Frozen, exploratory rigid-receptor docking. All coordinates are Angstroms.

Meeko residue templates determine the declared protonation state; no pH prediction,
missing-residue deletion, metal handling or covalent docking is implicit.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

import gemmi

from .geometry import normalize, audit_pose

VERSION = 'inhibitor-vina-v1'
STANDARD = set('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split())


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_bytes(encode(value))


def ligand_from_cif(block, residue):
    from rdkit import Chem
    rows = block.get_mmcif_category('_chem_comp_atom.')
    bonds = block.get_mmcif_category('_chem_comp_bond.')
    positions = {a.name: a for a in residue if a.element.name not in ('H', 'D')}
    rw, names = Chem.RWMol(), []
    for i, comp in enumerate(rows['comp_id']):
        name, element = rows['atom_id'][i], rows['type_symbol'][i]
        if comp != residue.name or element in ('H', 'D'):
            continue
        if name not in positions:
            raise ValueError(f'Ligand heavy atom missing: {name}')
        atom = Chem.Atom(element)
        atom.SetFormalCharge(int(rows.get('charge', ['0'] * len(rows['comp_id']))[i] or 0))
        atom.SetProp('source_atom_name', name)
        rw.AddAtom(atom)
        names.append(name)
    if set(names) != set(positions) or not 1 <= len(names) <= 128:
        raise ValueError('Ligand dictionary mismatch or heavy atom count outside 1–128')
    order = {'SING':Chem.BondType.SINGLE, 'DOUB':Chem.BondType.DOUBLE,
             'TRIP':Chem.BondType.TRIPLE, 'AROM':Chem.BondType.AROMATIC}
    for i, comp in enumerate(bonds['comp_id']):
        a, b = bonds['atom_id_1'][i], bonds['atom_id_2'][i]
        if comp == residue.name and a in names and b in names:
            rw.AddBond(names.index(a), names.index(b), order[bonds['value_order'][i].upper()])
    mol = rw.GetMol()
    Chem.SanitizeMol(mol)
    conf = Chem.Conformer(len(names))
    for i, name in enumerate(names):
        p = positions[name].pos
        conf.SetAtomPosition(i, (p.x, p.y, p.z))
    mol.AddConformer(conf)
    Chem.AssignStereochemistryFrom3D(mol)
    return mol, names


def validate_spec(spec):
    if not isinstance(spec,dict): raise ValueError('spec must be an object')
    if spec.get('spec_version') != 1:
        raise ValueError('spec_version must be 1')
    for key in ('chain', 'ligand_sequence', 'ligand_name', 'rationale'):
        if not isinstance(spec.get(key), str) or not 1 <= len(spec[key]) <= 2000:
            raise ValueError(f'{key} is required')
    if spec.get('water_policy') != 'exclude' or spec.get('cofactor_policy') != 'reject':
        raise ValueError('v1 requires explicit water_policy=exclude and cofactor_policy=reject')
    if spec.get('protonation') != 'meeko-standard-templates' or spec.get('assembly') != 'deposited-chain':
        raise ValueError('Declare meeko-standard-templates protonation and deposited-chain assembly')
    for key, low, high in [('exhaustiveness',1,32), ('pose_count',1,20), ('timeout_s',10,1800)]:
        if type(spec.get(key)) is not int or not low <= spec[key] <= high:
            raise ValueError(f'{key} outside [{low},{high}]')
    seeds = spec.get('seeds')
    if not isinstance(seeds,list) or not 1 <= len(seeds) <= 5 or len(set(seeds)) != len(seeds) or any(type(s) is not int or not 1 <= s <= 2147483647 for s in seeds):
        raise ValueError('Supply 1–5 unique positive seeds')
    margin = spec.get('margin_angstrom')
    if isinstance(margin,bool) or not isinstance(margin,(int,float)) or not math.isfinite(margin) or not 2 <= margin <= 12:
        raise ValueError('margin_angstrom outside [2,12]')
    if spec.get('altloc') not in ('A','B'):
        raise ValueError('Explicit altloc A or B required')
    if spec.get('repair_policy') not in ('reject','pdbfixer-missing-atoms'):
        raise ValueError('Explicit repair_policy reject or pdbfixer-missing-atoms required')
    additives=spec.get('exclude_additives',[])
    if not isinstance(additives,list) or len(additives)>100 or any(not isinstance(a,str) or len(a)>100 for a in additives):
        raise ValueError('Invalid additive exclusions')
    return spec


def prepare(raw: bytes, spec: dict, out: Path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from meeko import MoleculePreparation, Polymer, ResidueChemTemplates, PDBQTWriterLegacy
    validate_spec(spec)
    block = gemmi.cif.read_string(raw.decode()).sole_block()
    structure = gemmi.make_structure_from_block(block)
    if len(structure) != 1:
        raise ValueError('Select a single deposited model before preparation')
    structure.setup_entities()
    chain = structure[0].find_chain(spec['chain'])
    if chain is None:
        raise ValueError('Receptor chain absent')
    if sum(len(r) for r in chain)>20000:
        raise ValueError('Selected receptor exceeds 20,000 deposited atoms')
    for connection in structure.connections:
        if str(connection.type).endswith(('Covale','MetalC')):
            for partner in (connection.partner1,connection.partner2):
                if partner.chain_name==spec['chain'] and str(partner.res_id.seqid)==spec['ligand_sequence']:
                    raise ValueError('Covalent or metal-coordinated ligand unsupported by noncovalent protocol')
    delta, keep = [], []
    reference = None
    for r in chain:
        rid = f'{chain.name}:{r.seqid}:{r.name}'
        if r.name == spec['ligand_name'] and str(r.seqid) == spec['ligand_sequence']:
            reference = r.clone()
            delta.append({'residue':rid,'change':'extract reference ligand'})
        elif r.is_water():
            delta.append({'residue':rid,'change':'exclude water under frozen policy'})
        elif r.name not in STANDARD:
            # Exclude only explicitly named crystallization additives; default rejects.
            if rid not in spec.get('exclude_additives', []):
                raise ValueError(f'Unsupported cofactor/additive {rid}; explicitly justify exclusion or use another protocol')
            delta.append({'residue':rid,'change':'exclude declared crystallization additive','reason':spec['rationale']})
        else:
            keep.append(r.clone())
    if reference is None:
        raise ValueError('Reference ligand absent from selected chain')
    for r in [reference, *keep]:
        for i in range(len(r)-1,-1,-1):
            a = r[i]
            if a.altloc not in ('\x00',' ',spec['altloc']):
                delta.append({'residue':f'{chain.name}:{r.seqid}:{r.name}','atom':a.name,'altloc':a.altloc,'change':'remove alternate'})
                del r[i]
            elif a.altloc not in ('\x00',' '):
                a.altloc = '\x00'
    mol, names = ligand_from_cif(block, reference)
    if len(Chem.GetMolFrags(mol)) != 1 or any(a.GetAtomicNum() not in (1,6,7,8,9,15,16,17,35,53) for a in mol.GetAtoms()):
        raise ValueError('Unsupported disconnected ligand or element')
    # No crystal geometry passed to the docking initializer: seeded de novo ETKDG.
    reference_sdf = Chem.MolToMolBlock(mol) + '\n$$$$\n'
    (out/'reference.sdf').write_text(reference_sdf)
    initial = Chem.AddHs(Chem.Mol(mol))
    initial.RemoveAllConformers()
    params = AllChem.ETKDGv3()
    params.randomSeed = spec['seeds'][0]
    if AllChem.EmbedMolecule(initial, params) != 0:
        raise ValueError('Seeded ligand conformer generation failed')
    if not AllChem.MMFFHasAllMoleculeParams(initial):
        raise ValueError('Unsupported ligand MMFF parameters')
    AllChem.MMFFOptimizeMolecule(initial, maxIters=500)
    (out/'initial.sdf').write_text(Chem.MolToMolBlock(initial)+'\n$$$$\n')
    setup = MoleculePreparation().prepare(initial)
    if len(setup) != 1:
        raise ValueError('Ambiguous ligand preparation')
    ligand_qt, ok, error = PDBQTWriterLegacy.write_string(setup[0])
    if not ok:
        raise ValueError(error)
    (out/'ligand.pdbqt').write_text(ligand_qt)
    receptor = gemmi.Structure()
    model, rec_chain = gemmi.Model('1'), gemmi.Chain(chain.name)
    for r in keep:
        rec_chain.add_residue(r)
    model.add_chain(rec_chain)
    receptor.add_model(model)
    receptor_pdb = receptor.make_pdb_string()
    (out/'receptor-original.pdb').write_text(receptor_pdb)
    input_pdb = receptor_pdb
    if spec['repair_policy']=='pdbfixer-missing-atoms':
        import io
        from pdbfixer import PDBFixer
        from openmm import Platform
        from openmm.app import PDBFile
        fixer=PDBFixer(pdbfile=io.StringIO(receptor_pdb),platform=Platform.getPlatformByName('Reference'))
        fixer.findMissingResidues()
        fixer.missingResidues={}  # no implicit loop construction or sequence replacement
        fixer.findMissingAtoms()
        delta.extend({'residue':f'{r.chain.id}:{r.id}:{r.name}','change':'reconstruct missing heavy atoms',
                      'atoms':[a.name if hasattr(a,'name') else a for a in atoms]} for r,atoms in fixer.missingAtoms.items())
        fixer.addMissingAtoms(seed=spec['seeds'][0])
        stream=io.StringIO()
        PDBFile.writeFile(fixer.topology,fixer.positions,stream,keepIds=True)
        input_pdb=stream.getvalue()
        (out/'receptor-repaired.pdb').write_text(input_pdb)
    polymer = Polymer.from_pdb_string(input_pdb, ResidueChemTemplates.create_from_defaults(),
                                     MoleculePreparation(), allow_bad_res=False)
    rigid, flexible = PDBQTWriterLegacy.write_from_polymer(polymer)
    if flexible:
        raise ValueError('Unexpected flexible receptor')
    (out/'receptor.pdbqt').write_text(rigid)
    prepared_pdb = polymer.to_pdb()
    (out/'receptor-prepared.pdb').write_text(prepared_pdb)
    before = normalize(receptor_pdb.encode(),'pdb')
    after = normalize(prepared_pdb.encode(),'pdb')
    bykey = lambda a: (a['residue_id'].split(':',1)[-1],a['name'])
    previous = {bykey(a):a for a in before['atoms']}
    changes = []
    for a in after['atoms']:
        old = previous.pop(bykey(a), None)
        changes.append({'prepared_id':a['id'], 'original_id':old['id'] if old else None,
                        'change':'unchanged' if old and math.dist(old['position'],a['position'])<.01 else 'moved' if old else 'added',
                        'element':a['element']})
    if any(a['element'] != 'H' for a in previous.values()):
        raise ValueError('Preparation unexpectedly removed receptor heavy atoms')
    coords = mol.GetConformer().GetPositions()
    lo, hi = coords.min(axis=0)-spec['margin_angstrom'], coords.max(axis=0)+spec['margin_angstrom']
    box = {'center':((lo+hi)/2).tolist(),'size':(hi-lo).tolist(),'units':'Å'}
    if max(box['size']) > 40:
        raise ValueError('Docking box exceeds 40 Å cap')
    audit = {'status':'prepared','policy':spec,'changes':delta,'atom_map':changes,
             'ligand_atom_names':names,'box':box,'source_hash':digest(raw),
             'ligand_smiles':Chem.MolToSmiles(mol,isomericSmiles=True),
             'warnings':['Template protonation is a declared model, not a pH calculation.',
                         'Only the selected deposited chain is used; no biological assembly expansion.',
                         'No missing-heavy-atom deletion allowed; waters excluded by explicit protocol.']}
    write_json(out/'preparation.json', audit)
    return mol, names, before, after, audit


def dock(raw: bytes, spec: dict, out: Path, progress=lambda *_:None):
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
    from meeko import PDBQTMolecule, RDKitMolCreate
    from vina import Vina
    out.mkdir(parents=True, exist_ok=True)
    (out/'structure.cif').write_bytes(raw)
    protocol = {'adapter':VERSION, 'spec':validate_spec(spec), 'source_hash':digest(raw),
                'versions':{p:importlib.metadata.version(p) for p in ('vina','meeko','rdkit','gemmi','pdbfixer','openmm')},
                'recovery_target_angstrom':2.0, 'cpu':1, 'score_units':'kcal/mol',
                'pose_cluster_threshold_angstrom':2.0,'pose_cluster_rule':'score-ordered leader, symmetry-aware fixed receptor frame',
                'independent_unit':'none; repeated seeds are computational sensitivity, not biological replicates'}
    write_json(out/'protocol.json', protocol)  # freeze before outputs
    progress('preparation', 'Preparing receptor and de novo ligand conformer')
    ref, names, original, prepared, audit = prepare(raw,spec,out)
    poses, scores = [], []
    for seed in spec['seeds']:
        progress('docking', f'Vina seed {seed}')
        v = Vina(sf_name='vina',cpu=1,seed=seed,verbosity=0)
        v.set_receptor(str(out/'receptor.pdbqt'))
        v.set_ligand_from_file(str(out/'ligand.pdbqt'))
        v.compute_vina_maps(center=audit['box']['center'], box_size=audit['box']['size'])
        v.dock(exhaustiveness=spec['exhaustiveness'],n_poses=spec['pose_count'])
        qt = v.poses(n_poses=spec['pose_count'],energy_range=100)
        (out/f'poses-{seed}.pdbqt').write_text(qt)
        energies = v.energies(n_poses=spec['pose_count'],energy_range=100)
        molecules = RDKitMolCreate.from_pdbqt_mol(PDBQTMolecule(qt,skip_typing=True))
        if len(molecules)!=1 or molecules[0] is None:
            raise ValueError('Could not recover mapped pose molecule')
        molecule = Chem.RemoveHs(molecules[0])
        if Chem.MolToSmiles(molecule)!=Chem.MolToSmiles(ref):
            raise ValueError('Docked ligand identity/stereochemistry mismatch')
        matches = molecule.GetSubstructMatches(ref,uniquify=False,useChirality=True,maxMatches=10000)
        if not matches or len(matches)>=10000:
            raise ValueError('Unresolved ligand symmetry map')
        for rank, conf in enumerate(molecule.GetConformers()):
            # CalcRMS never aligns the ligand independently of its fixed receptor frame.
            mapping = [[(m[i],i) for i in range(len(m))] for m in matches]
            rmsd = rdMolAlign.CalcRMS(molecule,ref,prbId=conf.GetId(),map=mapping)
            pose_id = f'seed-{seed}-pose-{rank+1}'
            sdf = Chem.MolToMolBlock(molecule,confId=conf.GetId())+'\n$$$$\n'
            (out/f'{pose_id}.sdf').write_text(sdf)
            position = [list(conf.GetAtomPosition(i)) for i in matches[0]]
            row = {'id':pose_id,'seed':seed,'rank':rank+1,'score':float(energies[rank][0]),'rmsd':rmsd,'recovered':rmsd<=2}
            scores.append(row)
            poses.append({**row,'positions':position,'atom_names':names,'sdf_hash':digest(sdf.encode())})
    reference_positions = ref.GetConformer().GetPositions().tolist()
    # Deliberate geometric negative controls, never labelled measured inactives.
    displacement = [[p[0]+20,p[1],p[2]] for p in reference_positions]
    controls = [{'id':'reference','positions':reference_positions,'label':'Deposited reference'},
                {'id':'displaced-control','positions':displacement,'label':'Displaced geometry negative control'}]
    contact_geometry = normalize(raw,'cif')
    ligand_residue = next(r for r in contact_geometry['residues'] if r['chain']==spec['chain'] and r['sequence']==spec['ligand_sequence'] and r['name']==spec['ligand_name'])
    # Contacts must use the actual prepared receptor, including reconstructed atoms.
    original_residues={r['id'].split(':',1)[-1]:r for r in contact_geometry['residues']}
    mapped=__import__('copy').deepcopy(prepared)
    residue_ids={}
    for r in mapped['residues']:
        original_r=original_residues.get(r['id'].split(':',1)[-1])
        residue_ids[r['id']]=original_r['id'] if original_r else 'prepared/'+r['id']
        r['id']=residue_ids[r['id']]
    # Atom ordinals can change under repair; map by author residue + atom name.
    original_by_name={(a['residue_id'].split(':',1)[-1],a['name']):a for a in contact_geometry['atoms']}
    for a in mapped['atoms']:
        old=original_by_name.get((a['residue_id'].split(':',1)[-1],a['name']))
        a['id']=old['id'] if old else 'prepared/'+a['id']
        a['residue_id']=residue_ids[a['residue_id']]
    # A docked heavy-atom pose must not retain unmoved deposited hydrogens or
    # a second alternate conformer. Keep only the atoms in the frozen map.
    selected_raw=[(i,a) for i,a in enumerate(contact_geometry['atoms'])
                  if a['residue_id']==ligand_residue['id'] and a['name'] in names
                  and a['altloc'] in ('',spec['altloc'])]
    ligand_atoms=[a for _,a in selected_raw]
    offset=len(mapped['atoms'])
    mapped['atoms'].extend(__import__('copy').deepcopy(ligand_atoms))
    ligand_residue={**ligand_residue,'atoms':list(range(offset,offset+len(ligand_atoms)))}
    mapped['residues'].append(ligand_residue)
    raw_indices={i:offset+k for k,(i,_) in enumerate(selected_raw)}
    mapped['bonds'].extend([[raw_indices[a],raw_indices[b]] for a,b in contact_geometry['bonds'] if a in raw_indices and b in raw_indices])
    mapped['source_hash']=digest(raw)
    mapped['coordinate_frame']='Prepared receptor in deposited coordinate frame; added atoms explicitly mapped'
    contact_geometry=mapped
    docking_geometry=__import__('copy').deepcopy(mapped)
    from .surface import accessible_surface
    surface=accessible_surface(docking_geometry,ligand_residue['id'])
    write_json(out/'surface.json',surface)
    lookup = {contact_geometry['atoms'][i]['name']:i for i in ligand_residue['atoms']}
    # Force one atom onto a receptor atom as an exact clash countercheck.
    nearest = min((a for a in contact_geometry['atoms'] if a['kind']=='polymer'),key=lambda a:math.dist(a['position'],reference_positions[0]))
    clash = [list(p) for p in reference_positions]
    clash[0] = nearest['position']
    controls.append({'id':'clash-control','positions':clash,'label':'Clashing geometry negative control'})
    contacts = {}
    for pose in [*controls,*poses]:
        for name, xyz in zip(names,pose['positions']):
            contact_geometry['atoms'][lookup[name]]['position']=xyz
        contacts[pose['id']] = audit_pose(contact_geometry,ligand_residue['id'])
    top = [s for s in scores if s['rank']==1]
    import numpy as np
    symmetries=ref.GetSubstructMatches(ref,uniquify=False,useChirality=True,maxMatches=10000)
    clusters=[]
    for pose in sorted(poses,key=lambda p:(p['score'],p['seed'],p['rank'])):
        points=np.array(pose['positions'])
        assigned=None
        for cluster in clusters:
            representative=np.array(next(p['positions'] for p in poses if p['id']==cluster['representative']))
            rmsd=min(float(np.sqrt(np.mean(np.sum((points[list(mapping)]-representative)**2,axis=1)))) for mapping in symmetries)
            if rmsd<=2: assigned=cluster;break
        if assigned is None:
            assigned={'representative':pose['id'],'members':[]};clusters.append(assigned)
        assigned['members'].append(pose['id'])
    report = {'protocol_hash':digest(encode(protocol)), 'scores':scores,'score_units':'kcal/mol',
              'pose_clusters':clusters,'cluster_threshold_angstrom':2,
              'seed_score_sensitivity':{'top_score_min':min(p['score'] for p in top),'top_score_max':max(p['score'] for p in top)},
              'recovery':{'threshold_angstrom':2,'top_pose_fraction':sum(p['recovered'] for p in top)/len(top),
                          'per_seed':[{'seed':s,'any_recovered':any(p['recovered'] for p in scores if p['seed']==s)} for s in spec['seeds']]},
              'limitations':['Docking ranks are exploratory, not affinity or cellular inhibition.',
                             'Controls are deliberately invalid geometry, not measured inactive compounds.',
                             'One rigid receptor/protonation protocol; compare separate protocol branches for sensitivity.',
                             'Seed repetition does not create biological replicates.'],
              'follow_up':'Test ranked compounds experimentally; assess preparation and receptor-state sensitivity before prioritization.'}
    write_json(out/'scores.json', scores)
    write_json(out/'contacts.json', contacts)
    write_json(out/'report.json', report)
    write_json(out/'atom-map.json',audit['atom_map'])
    (out/'report.md').write_text('# Exploratory known-ligand recovery\n\n'
        +f"Source SHA-256: {digest(raw)}\n\nProtocol SHA-256: {report['protocol_hash']}\n\n"
        +f"Top-pose recovery at 2 Å: {report['recovery']['top_pose_fraction']:.0%}.\n\n"
        +'| Seed | Rank | Vina score (kcal/mol) | Fixed-frame RMSD (Å) |\n|---|---|---|---|\n'
        +'\n'.join(f"| {s['seed']} | {s['rank']} | {s['score']:.3f} | {s['rmsd']:.3f} |" for s in scores)
        +'\n\n'+'\n'.join('- '+s for s in report['limitations'])+'\n\n'+report['follow_up']+'\n')
    import pandas as pd
    pd.DataFrame(scores).to_parquet(out/'scores.parquet',index=False)
    pd.DataFrame([{'pose':p,**c} for p,a in contacts.items() for c in a['contacts']]).to_parquet(out/'contacts.parquet',index=False)
    bundle = {'schema_version':1,'kind':'inhibitor_bundle','source_hash':digest(raw), 'protocol':protocol,
              'preparation':audit, 'prepared_geometry':prepared, 'original_receptor_geometry':original,'docking_geometry':docking_geometry,
              'ligand_residue':ligand_residue['id'], 'ligand_atom_names':names,'poses':poses,'controls':controls,
              'contacts':contacts,'report':report,'surface':surface,'scientific_status':'exploratory'}
    write_json(out/'bundle.json',bundle)
    progress('completed','Docking outputs and controls ready')
    return bundle
