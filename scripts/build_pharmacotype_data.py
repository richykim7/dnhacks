"""Reproduce the PRISM/CCLE development join; never prepares confirmation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dnhacksbio.pharmacotype_data import digest

PANEL = ('gemcitabine', 'irinotecan', 'oxaliplatin', 'paclitaxel')


def acquire(raw):
    """Fetch only named public development releases; no confirmation sources."""
    import requests
    raw=Path(raw);raw.mkdir(parents=True,exist_ok=True)
    wanted={9393293:{'secondary-screen-readme.txt','secondary-screen-cell-line-info.csv',
                    'secondary-screen-pooling-info.csv','secondary-screen-replicate-collapsed-treatment-info.csv',
                    'secondary-screen-replicate-collapsed-logfold-change.csv'},
            11384241:{'CCLE_expression.csv','sample_info.csv','README'},27993248:{'Model.csv'}}
    for article,names in wanted.items():
        response=requests.get(f'https://api.figshare.com/v2/articles/{article}',timeout=60)
        response.raise_for_status();metadata=response.json()
        (raw/f'article-{article}.json').write_text(json.dumps(metadata,indent=2))
        for item in metadata['files']:
            if item['name'] not in names:continue
            path=raw/item['name']
            if path.exists() and hashlib.md5(path.read_bytes()).hexdigest()==item['computed_md5']:continue
            response=requests.get(item['download_url'],timeout=(30,120),stream=True)
            response.raise_for_status()
            temporary=path.with_suffix(path.suffix+'.partial')
            with temporary.open('wb') as stream:
                for block in response.iter_content(1024*1024):stream.write(block)
            if hashlib.md5(temporary.read_bytes()).hexdigest()!=item['computed_md5']:
                raise ValueError('Download checksum mismatch')
            temporary.replace(path)


def build(raw, output, *, genes=1000):
    raw, output = Path(raw), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    sources = []
    for article in (9393293, 11384241, 27993248):
        metadata = json.loads((raw/f'article-{article}.json').read_text())
        for item in metadata['files']:
            path = raw/item['name']
            if path.exists() and path.name != 'README.txt':
                blob = path.read_bytes()
                if hashlib.md5(blob).hexdigest() != item['computed_md5']:
                    raise ValueError(f'Source integrity mismatch: {path.name}')
                sources.append(dict(article=article, name=path.name, url=item['download_url'],
                                    sha256=hashlib.sha256(blob).hexdigest(), license=metadata['license']['name']))
    treatments = pd.read_csv(raw/'secondary-screen-replicate-collapsed-treatment-info.csv')
    cells = pd.read_csv(raw/'secondary-screen-cell-line-info.csv').set_index('row_name')
    models = pd.read_csv(raw/'Model.csv').set_index('ModelID')
    columns, panel = [], []
    for name in PANEL:
        selected = treatments[treatments.name == name]
        screen = 'MTS010' if 'MTS010' in set(selected.screen_id) else 'HTS002'
        selected = selected[selected.screen_id == screen].sort_values('dose')
        if len(selected) != 8 or selected.broad_id.nunique() != 1 or selected.dose.nunique() != 8:
            raise ValueError(f'Ambiguous eight-dose panel: {name}')
        panel.append(dict(name=name, compound=selected.broad_id.iloc[0],
                          formulation=selected.broad_id.iloc[0], screen=screen,
                          doses=(selected.dose.to_numpy()*1e-6).tolist()))
        columns.extend(selected.column_name.tolist())
    # This order and panel are fixed using metadata, before reading response numbers.
    locked = dict(panel=panel, columns=columns, feature_rule=f'top {genes} TRAIN variance',
                  split_rule='SHA256 canonical PatientID: <70 TRAIN, <85 VALIDATION, else TEST; pancreas always TEST',
                  culture_rule='lexicographically first STR-passing model per resolved PatientID')
    (output/'locked-design.json').write_text(json.dumps(locked, indent=2))
    response = pd.read_csv(raw/'secondary-screen-replicate-collapsed-logfold-change.csv', index_col=0, usecols=lambda c: c == '' or c == 'Unnamed: 0' or c in columns)
    # Pandas names the otherwise blank row-id header Unnamed: 0.
    expression = pd.read_csv(raw/'CCLE_expression.csv', index_col=0)
    exclusions, candidates = [], []
    for model_id in sorted(set(cells.index) & set(expression.index)):
        if model_id not in models.index or pd.isna(models.loc[model_id, 'PatientID']):
            exclusions.append(dict(model=model_id, reason='unresolved_patient_origin')); continue
        if cells.loc[model_id, 'passed_str_profiling'] != True:
            exclusions.append(dict(model=model_id, reason='STR_not_passed')); continue
        candidates.append((str(models.loc[model_id, 'PatientID']), model_id))
    seen, selected = set(), []
    for donor, model_id in sorted(candidates):
        if donor in seen:
            exclusions.append(dict(model=model_id, reason='same_patient_derivative')); continue
        seen.add(donor)
        if model_id not in response.index or not np.isfinite(response.loc[model_id, columns].to_numpy(float)).all():
            exclusions.append(dict(model=model_id, reason='incomplete_registered_panel')); continue
        selected.append((donor, model_id))
    splits = {'train': [], 'validation': [], 'test': []}
    pdac = []
    for donor, model_id in selected:
        bucket = int(hashlib.sha256(donor.encode()).hexdigest()[:8],16) % 100
        pancreatic = str(cells.loc[model_id,'primary_tissue']) == 'pancreas'
        split = 'test' if pancreatic or bucket >= 85 else ('validation' if bucket >= 70 else 'train')
        splits[split].append(donor)
        if pancreatic: pdac.append(donor)
    train_models = [m for d,m in selected if d in splits['train']]
    train_x = expression.loc[train_models]
    finite_genes = train_x.columns[np.isfinite(train_x.to_numpy(float)).all(axis=0)]
    feature_order = train_x[finite_genes].var().sort_values(ascending=False,kind='stable').index[:genes].tolist()
    if len(feature_order) != genes: raise ValueError('Insufficient finite TRAIN features')
    x = expression.loc[[m for _,m in selected], feature_order].to_numpy(float)
    y = response.loc[[m for _,m in selected], columns].to_numpy(float)
    if not np.isfinite(x).all(): raise ValueError('Unexpected missing held-out selected features')
    data = dict(schema='pharmacotype.prepared.v1', role='development', donors=[d for d,_ in selected],
                x=x.tolist(), y=y.tolist(), genes=feature_order, panel=panel,
                assay=dict(version='PRISM-19Q4-secondary', scale='ComBat-adjusted log2 fold change versus DMSO',
                           exposure_hours=120, dose_unit='M', population='STR-passing established cancer cell lines',
                           aggregation='source median collapsed technical replicates; prefer MTS010 redos'),
                source_hash=digest(sources), contract_hash=digest(locked), exclusions=exclusions,
                replicate_sd=None, pdac_donors=pdac, model_crosswalk=dict(selected))
    data['integrity_sha256']=digest(data)
    audit = dict(schema='pharmacotype.source-audit.v1', sources=sources, locked_design=locked,
                 counts=dict(prism_rows=len(cells), expression_rows=len(expression), eligible_donors=len(selected),
                             splits={k:len(v) for k,v in splits.items()}, pdac_test=len(pdac), features=genes),
                 exclusions=exclusions, confirmation_eligible=False,
                 limitations=['Pooled cell lines and cohort-level ComBat prevent confirmation use.',
                              'PatientID crosswalk is publisher metadata, not independently reverified identity.',
                              'Complete-case population and source median collapse can bias development performance.',
                              'Established cell-line RNA is not a matched PDO baseline biopsy; transfer requires separate evaluation.'])
    for name, value in [('development.json',data),('splits.json',splits),('audit.json',audit)]:
        (output/name).write_text(json.dumps(value, indent=2, allow_nan=False))
    return audit['counts']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--genes',type=int,default=1000)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--public-audit',help='Write source hashes and aggregate exclusions without donor identifiers')
    args=parser.parse_args()
    if args.download:acquire(args.raw)
    print(json.dumps(build(args.raw,args.output,genes=args.genes)))
    if args.public_audit:
        from collections import Counter
        audit=json.loads((Path(args.output)/'audit.json').read_text())
        audit['exclusion_counts']=dict(Counter(e['reason'] for e in audit.pop('exclusions')))
        Path(args.public_audit).write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n')
