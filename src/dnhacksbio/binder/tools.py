"""Scientist-facing exploratory operations, independent of any statistical verdict."""
from .geometry import canonical, digest, parse_structure, select_chains


def prepare_target(raw,fmt,*,structure_sha256,chains,source_evidence,construct_policy,assembly='context unavailable'):
    if digest(raw)!=structure_sha256:raise ValueError('Stale target artifact hash')
    if not source_evidence or not construct_policy.strip():raise ValueError('Evidence and explicit construct policy required')
    for source in source_evidence:
        if any(not source.get(k) for k in ('doi','quote','context')):raise ValueError('Incomplete source evidence')
    s=parse_structure(raw,fmt)
    if assembly!='context unavailable':
        raise ValueError('Assembly expansion is not supported; import explicitly expanded coordinates with evidence')
    target=select_chains(s,chains)
    return {**target,'source_evidence':source_evidence,'construct_policy':construct_policy,'context':assembly}


def compare(bundles):
    if not 2<=len(bundles)<=8:raise ValueError('Compare 2–8 candidates')
    from .bundle import validate_bundle
    bundles=[validate_bundle(canonical(b)) for b in bundles]
    if len({digest(b) for b in bundles})!=len(bundles):raise ValueError('Comparison requires distinct candidates')
    first=bundles[0]
    protocol=first['metrics']['protocol']
    # Exact target coordinate alignment only; never assume differing predictions share a pose.
    def target(b):
        ids={r['id'] for r in b['structure']['residues'] if r['chain'] in b['target_chains']}
        return {'residues':[r for r in b['structure']['residues'] if r['id'] in ids],
                'atoms':[{k:a[k] for k in ('residue_id','name','element','xyz','altloc','occupancy')}
                         for a in b['structure']['atoms'] if a['residue_id'] in ids]}
    target_hash=digest(target(first))
    rows=[]
    for b in bundles:
        if b['manifest']['scope']!=first['manifest']['scope']:
            raise ValueError('Comparison requires one experiment scope')
        if b['metrics']['protocol']!=protocol or digest(target(b))!=target_hash:
            raise ValueError('Comparison requires identical metric protocol and target coordinates/mapping')
        m=b['metrics'];rows.append({'candidate_id':b['manifest']['candidate_id'],'bundle_sha256':digest(b),
                                  'contacts':m['counts']['4.5'],'clashes':m['clash_count'],
                                  'buried_area_angstrom2':m['total_buried_area_angstrom2'],
                                  'affinity':None,'confidence':m['confidence'],'missingness':m['missingness']})
    for r in rows:
        # Engineering Pareto display, not an affinity ranking.
        r['pareto']=not any(o['contacts']>=r['contacts'] and o['clashes']<=r['clashes'] and
                           (o['contacts']>r['contacts'] or o['clashes']<r['clashes']) for o in rows)
    return {'rows':rows,'recipe':{'alignment':'identical-target-coordinates','scale':'angstrom','synchronized_cameras':True},
            'pareto_axes':{'contacts':'maximize','clashes':'minimize'},'status':'exploratory'}


def propose_followup(bundles,*,question,evidence):
    if not bundles or not question.strip() or not evidence:raise ValueError('Candidates, question and evidence required')
    return {'question':question,'candidate_hashes':[digest(b) for b in bundles],'evidence':evidence,
            'status':'human-review-required','proposed_assays':['Direct binding with concentration series and reference target',
            'Competition with the declared biological ligand','Selectivity against related integrin complexes',
            'PDAC functional readout with matched viability control'],
            'controls':['Known positive binding control','Matched negative binder','Target-free background',
                        'Independent protein preparations and biological repeats'],
            'limitations':['Structural contacts do not establish affinity, competition or PDAC efficacy'],
            'execution':'No molecules ordered; no wet-lab action performed'}
