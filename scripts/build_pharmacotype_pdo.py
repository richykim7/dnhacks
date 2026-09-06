"""Audit public Shi PDO RNA/AUC pairs; never invent dose-level observations."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
from dnhacksbio.pharmacotype_data import digest

PANEL={'GEM':'gemcitabine','5-FU':'fluorouracil','PTX':'paclitaxel','OXA':'oxaliplatin','IRI':'irinotecan'}


def worksheet(path, number=1):
    """Read cached literal XLSX cells without executing formulas or external links."""
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as archive:
        strings=[''.join(t.itertext()) for t in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        root=ET.fromstring(archive.read(f'xl/worksheets/sheet{number}.xml'))
        rows=[]
        for row in root.findall('s:sheetData/s:row',ns):
            values={}
            for cell in row.findall('s:c',ns):
                value=cell.find('s:v',ns)
                if value is None:continue
                column=''.join(c for c in cell.get('r') if c.isalpha())
                values[column]=strings[int(value.text)] if cell.get('t')=='s' else value.text
            rows.append(values)
        return rows


def build(raw,output):
    raw,output=Path(raw),Path(output);output.mkdir(parents=True,exist_ok=True)
    metadata=worksheet(raw/'metadata.xlsx')[2:]
    # Read only donor identity, sampling multiplicity and RNA availability.
    records=[r for r in metadata if r.get('B','').startswith('CAS-DAC-')]
    origins={r['B']:r for r in records}
    if len(origins)!=len(records):raise ValueError('Duplicate source organoid identities')
    columns=pd.read_csv(raw/'drug_screening.txt.gz',sep='\t',nrows=0).columns[1:]
    expression=pd.read_csv(raw/'expression.txt.gz',sep='\t',index_col=0)
    if expression.index.has_duplicates:raise ValueError('Duplicate gene symbols require an explicit rule')
    eligible=sorted(d for d in columns if d in expression.columns and d in origins and origins[d].get('F')=='1' and origins[d].get('K')=='Yes')
    splits={k:[] for k in ('train','validation','test')}
    for donor in eligible:
        bucket=int(hashlib.sha256(donor.encode()).hexdigest()[:8],16)%100
        splits['train' if bucket<60 else 'validation' if bucket<80 else 'test'].append(donor)
    design=dict(endpoint='five-drug normalized AUC, not dose curves',panel=PANEL,
                split_rule='SHA256 canonical source organoid ID: <60 train, <80 validation, else test',
                donor_rule='PDAC only, one sample per patient confirmed in Supplementary Data 1',
                feature_rule='top 1000 variance after log2(FPKM+1), selected on GPU using training donors only',
                source_doses_available=False)
    (output/'locked-design.json').write_text(json.dumps(design,indent=2))
    # Outcome values are loaded only after design and donor splits are fixed.
    response=pd.read_csv(raw/'drug_screening.txt.gz',sep='\t',index_col=0)
    if response.index.has_duplicates:raise ValueError('Duplicate source compound identities')
    x=expression[eligible].T.to_numpy(float);y=response.loc[list(PANEL),eligible].T.to_numpy(float)
    if not np.isfinite(x).all() or (x<0).any() or not np.isfinite(y).all():raise ValueError('Incomplete declared PDO data; no outcome-dependent repair')
    if any(len(v)<2 for v in splits.values()):raise ValueError('Insufficient split counts')
    sources={name:hashlib.sha256((raw/name).read_bytes()).hexdigest() for name in ('metadata.xlsx','expression.txt.gz','drug_screening.txt.gz')}
    data=dict(schema='pharmacotype.auc-development.v1',role='development',donors=eligible,
              genes=expression.index.tolist(),x=x.tolist(),y=y.tolist(),splits=splits,
              panel=[dict(compound=k,name=v,measurement='source normalized AUC') for k,v in PANEL.items()],
              contract_hash=digest(design),source_hash=digest(sources))
    data['integrity_sha256']=digest(data)
    (output/'auc-development.json').write_text(json.dumps(data,allow_nan=False))
    audit=dict(schema='pharmacotype.pdo-audit.v1',sources=sources,design=design,
               expression_models=len(expression.columns),screened_models=len(columns),eligible_pdac=len(eligible),
               split_counts={k:len(v) for k,v in splits.items()},confirmation_enabled=False,
               source_urls=['https://www.nature.com/articles/s41467-022-29857-6',
                            'https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-022-29857-6/MediaObjects/41467_2022_29857_MOESM4_ESM.xlsx',
                            'https://ftp.ncbi.nlm.nih.gov/geo/series/GSE194nnn/GSE194249/suppl/GSE194249_PDPCOs_FPKM.txt.gz',
                            'https://ftp.ncbi.nlm.nih.gov/geo/series/GSE195nnn/GSE195623/suppl/GSE195623_PDPCO_drug_screening.txt.gz'],
               limitations=['AUC loses curve shape and cannot fulfill the dose-level endpoint.',
                            'Publisher sample-per-patient metadata is not independent identity revalidation.',
                            'Published inspected development data; no untouched confirmation claim.'])
    (output/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    return audit


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(build(a.raw,a.output)['split_counts']))
