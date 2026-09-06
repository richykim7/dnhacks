"""Pocket-local solvent-accessible surface via marching tetrahedra.

The scalar field is min(distance-to-atom minus vdW radius minus probe).
The zero isosurface approximates the union of inflated atom spheres (SAS),
not a solvent-excluded surface. Coordinates are never independently fitted.
"""
import math


def accessible_surface(geometry, ligand_id, probe=1.4, cutoff=8.0, spacing=.6):
    import numpy as np
    from scipy.spatial import cKDTree
    ligand=[a for a in geometry['atoms'] if a['residue_id']==ligand_id and a['element'] not in ('H','D')]
    receptor=[a for a in geometry['atoms'] if a['kind']=='polymer' and a['element'] not in ('H','D')]
    local=[a for a in receptor if any(math.dist(a['position'],b['position'])<=cutoff for b in ligand)]
    if not local or len(local)>2000: raise ValueError('Surface selection outside 1–2000 atoms')
    centers=np.array([a['position'] for a in local]);radii=np.array([a['radius']+probe for a in local])
    origin=np.min(centers-radii[:,None],axis=0)-spacing
    high=np.max(centers+radii[:,None],axis=0)+spacing
    shape=np.ceil((high-origin)/spacing).astype(int)+1
    if int(np.prod(shape))>2_000_000: raise ValueError('Surface exceeds two-million-cell budget')
    field=np.full(tuple(shape),float(radii.max()+spacing),dtype=np.float32)
    for position,radius in zip(centers,radii):
        lo=np.maximum(0,np.floor((position-radius-spacing-origin)/spacing).astype(int))
        hi=np.minimum(shape,np.ceil((position+radius+spacing-origin)/spacing).astype(int)+1)
        sl=tuple(slice(int(a),int(b)) for a,b in zip(lo,hi))
        grid=np.stack(np.meshgrid(*(origin[i]+np.arange(lo[i],hi[i])*spacing for i in range(3)),indexing='ij'),axis=-1)
        field[sl]=np.minimum(field[sl],np.linalg.norm(grid-position,axis=-1)-radius)
    corners=np.array([(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)])
    values=np.stack([field[x:shape[0]-1+x,y:shape[1]-1+y,z:shape[2]-1+z] for x,y,z in corners],axis=-1)
    cells=np.argwhere((values.min(axis=-1)<0)&(values.max(axis=-1)>=0))
    tetrahedra=[(0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6)]
    positions=[]
    for cell in cells:
        points=origin+(cell+corners)*spacing
        vals=values[tuple(cell)]
        for tetra in tetrahedra:
            inside=[i for i in tetra if vals[i]<0];outside=[i for i in tetra if vals[i]>=0]
            if not inside or not outside: continue
            def edge(i,j): return points[i]+(points[j]-points[i])*(-vals[i])/(vals[j]-vals[i])
            if len(inside)==1 or len(outside)==1:
                singleton,others=(inside[0],outside) if len(inside)==1 else (outside[0],inside)
                positions.extend([edge(singleton,i) for i in others])
            else:
                a,b=inside;c,d=outside
                ac,ad,bc,bd=edge(a,c),edge(a,d),edge(b,c),edge(b,d)
                positions.extend([ac,ad,bc,ad,bd,bc])
    points=np.array(positions)
    if len(points)>600000: raise ValueError('Surface exceeds 200,000 triangle budget')
    centroids=points.reshape(-1,3,3).mean(axis=1)
    tree=cKDTree(centers);_,neighbors=tree.query(centroids,k=min(8,len(local)))
    neighbors=np.asarray(neighbors).reshape(len(centroids),-1)
    distance=np.abs(np.linalg.norm(centroids[:,None,:]-centers[neighbors],axis=-1)-radii[neighbors])
    owners=neighbors[np.arange(len(neighbors)),distance.argmin(axis=1)]
    return {'algorithm':'inflated-vdW-union-marching-tetrahedra-v1','surface_type':'approximate solvent-accessible surface (SAS), not SES',
            'probe_radius_angstrom':probe,'selection_cutoff_angstrom':cutoff,'grid_spacing_angstrom':spacing,
            'units':'Å','coordinate_frame':geometry['coordinate_frame'],'source_hash':geometry['source_hash'],
            'positions':points.round(5).tolist(),'triangle_atom_ids':[local[i]['id'] for i in owners],
            'selection':[a['id'] for a in local],
            'warnings':['Finite grid discretization; boundary belongs to the declared pocket-local atom subset, not the full protein.']}
