"""Bounded marching-tetrahedra atom-union envelopes with source-atom associations.

These are visualization meshes, not solvent-excluded surfaces or a replacement for SASA.
The recorded field-residual bound is not a Hausdorff/topology guarantee.
"""
from __future__ import annotations

import itertools
import numpy as np

from .geometry import RADII, digest

CORNERS=np.array([(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)])
TETS=((0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6))


def options(value=None):
    value={} if value is None else value
    if not isinstance(value,dict) or set(value)-{'spacing','probe','max_grid_axis'}:
        raise ValueError('Unsupported surface options')
    resolved={'spacing':.8,'probe':1.4,'max_grid_axis':64,**value}
    if any(type(resolved[k]) not in (int,float) or not np.isfinite(resolved[k]) for k in ('spacing','probe')):
        raise ValueError('Finite surface spacing and probe required')
    if not .4<=resolved['spacing']<=2 or not 0<=resolved['probe']<=2:
        raise ValueError('Surface spacing/probe outside bounds')
    if type(resolved['max_grid_axis']) is not int or not 16<=resolved['max_grid_axis']<=64:
        raise ValueError('Surface grid axis outside 16–64 budget')
    return resolved


def envelope(structure, chains, settings=None):
    settings=options(settings)
    residues={r['id'] for r in structure['residues'] if r['chain'] in chains}
    atoms=[a for a in structure['atoms'] if a['residue_id'] in residues and a['element'] not in {'H','D'}]
    if not atoms or len(atoms)>6000:raise ValueError('Surface requires 1–6000 heavy atoms')
    if any(a['element'] not in RADII for a in atoms):raise ValueError('Surface radius unavailable for an element')
    xyz=np.array([a['xyz'] for a in atoms],dtype=float)
    radii=np.array([RADII[a['element']]+settings['probe'] for a in atoms])
    span=np.ptp(xyz,axis=0)+2*radii.max()
    spacing=max(settings['spacing'],float(span.max())/(settings['max_grid_axis']-5)*1.000001)
    origin=xyz.min(axis=0)-radii.max()-2*spacing
    shape=tuple((np.ceil(span/spacing).astype(int)+5).tolist())
    field=np.full(shape,2*spacing,dtype=float)
    for center,radius in zip(xyz,radii):
        lo=np.maximum(0,np.floor((center-radius-2*spacing-origin)/spacing).astype(int))
        hi=np.minimum(shape,np.ceil((center+radius+2*spacing-origin)/spacing).astype(int)+1)
        slices=tuple(slice(a,b) for a,b in zip(lo,hi))
        axes=[origin[k]+np.arange(lo[k],hi[k])*spacing-center[k] for k in range(3)]
        distances=np.sqrt(axes[0][:,None,None]**2+axes[1][None,:,None]**2+axes[2][None,None,:]**2)-radius
        field[slices]=np.minimum(field[slices],distances)
    blocks=[field[c[0]:shape[0]-1+c[0],c[1]:shape[1]-1+c[1],c[2]:shape[2]-1+c[2]] for c in CORNERS]
    active=np.argwhere((np.minimum.reduce(blocks)<0)&(np.maximum.reduce(blocks)>=0))
    vertices=[];faces=[];edges={}
    inverses=[np.linalg.inv((CORNERS[list(t)[1:]]-CORNERS[t[0]]).astype(float)) for t in TETS]
    for cell in active:
        grid=cell+CORNERS
        ids=np.ravel_multi_index(grid.T,shape)
        values=field[tuple(grid.T)]
        points=origin+grid*spacing
        def crossing(a,b):
            key=tuple(sorted((int(ids[a]),int(ids[b]))))
            if key not in edges:
                fraction=values[a]/(values[a]-values[b])
                edges[key]=len(vertices)
                vertices.append(points[a]+fraction*(points[b]-points[a]))
            return edges[key]
        for tet,inverse in zip(TETS,inverses):
            inside=[a for a in tet if values[a]<0];outside=[a for a in tet if values[a]>=0]
            if not inside or not outside:continue
            gradient=inverse@(values[list(tet)[1:]]-values[tet[0]])
            if len(inside)==2:
                a,b=inside;c,d=outside
                ac,ad,bc,bd=[crossing(x,y) for x,y in ((a,c),(a,d),(b,c),(b,d))]
                triangles=((ac,bc,bd),(ac,bd,ad))
            else:
                one,many=(inside[0],outside) if len(inside)==1 else (outside[0],inside)
                triangles=(tuple(crossing(one,a) for a in many),)
            for triangle in triangles:
                a,b,c=[vertices[i] for i in triangle]
                normal=np.cross(b-a,c-a)
                if np.dot(normal,normal)<1e-16:continue
                faces.append(triangle if np.dot(normal,gradient)>0 else tuple(reversed(triangle)))
            if len(faces)>120000:raise ValueError('Surface triangle budget exhausted; request coarser spacing')
    if not faces:raise ValueError('No surface resolved on requested grid')
    positions=np.round(np.array(vertices),6)
    source=[];residual=0.
    for start in range(0,len(positions),256):
        distances=np.linalg.norm(positions[start:start+256,None,:]-xyz[None,:,:],axis=2)-radii
        nearest=np.argmin(distances,axis=1)
        source.extend(atoms[int(i)]['id'] for i in nearest)
        residual=max(residual,float(np.abs(distances[np.arange(len(nearest)),nearest]).max()))
    triangles=np.array(faces)
    max_edge=max(float(np.linalg.norm(positions[triangles[:,a]]-positions[triangles[:,b]],axis=1).max()) for a,b in itertools.combinations(range(3),2))
    return {'schema':'binder_surface.v1','source_sha256':structure['source_sha256'],'chains':list(chains),
            'source_mapping':'atom minimizing distance-to-center minus declared radius at each vertex',
            'positions':positions.tolist(),'triangles':triangles.tolist(),'source_atom_ids':source,
            'protocol':{'method':'marching-tetrahedra.v1','envelope':'union of heavy-atom spheres; visualization only',
                        'radii_angstrom':RADII,'probe_angstrom':settings['probe'],'requested_spacing_angstrom':settings['spacing'],
                        'grid_spacing_angstrom':spacing,'grid_shape':list(shape),'simplification':'none',
                        'max_vertex_field_residual_angstrom':residual,
                        'whole_triangle_field_residual_bound_angstrom':residual+max_edge,
                        'hausdorff_bound':'not established','topology_guarantee':False},
            'geometry_sha256':digest({'positions':positions.tolist(),'triangles':triangles.tolist(),'source_atom_ids':source})}


def has_backbone_trace(bundle):
    """Require a contiguous source C-alpha pair on each side; never invent a missing atom."""
    amino=set('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL MSE SEC PYL'.split())
    atoms={a['residue_id']:a for a in bundle['structure']['atoms'] if a['name']=='CA' and a['element']=='C'}
    for chains in (bundle['target_chains'],bundle['binder_chains']):
        previous=None;found=False
        for residue in bundle['structure']['residues']:
            atom=atoms.get(residue['id']) if residue['name'] in amino and residue['chain'] in chains else None
            if atom and previous:
                prior,point=previous
                distance=float(np.linalg.norm(np.array(atom['xyz'])-point['xyz']))
                if prior['chain']==residue['chain'] and residue['auth_seq_id']<=prior['auth_seq_id']+1 and 2.5<=distance<=4.5:found=True
            previous=(residue,atom) if atom else None
        if not found:return False
    return True
