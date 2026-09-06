#!/usr/bin/env python3
"""Audit published cohort metadata without reading protein outcome matrices."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def apgi_counts(path):
    root=ET.parse(path).getroot()
    tables=[t for t in root.findall('.//table-wrap') if 'Clinical characteristics of the study cohort' in ''.join(t.itertext())]
    if len(tables)!=1:raise ValueError('Unique clinical table required')
    wanted={'Poorly differentiated','Undifferentiated','Well/moderately differentiated','PDA','Mucinous','Others'}
    counts={}
    for row in tables[0].findall('.//tr'):
        cells=[' '.join(''.join(c.itertext()).split()) for c in row if c.tag in {'td','th'}]
        if cells and cells[0] in wanted:
            if cells[0] in counts:raise ValueError('Duplicated clinical category')
            match=re.match(r'^(\d+)\b',cells[1])
            if not match:raise ValueError('Unparseable clinical count')
            counts[cells[0]]=int(match[1])
    if set(counts)!=wanted:raise ValueError('Incomplete grade/histology table')
    total=sum(counts[k] for k in ('PDA','Mucinous','Others'))
    if total!=sum(counts[k] for k in ('Poorly differentiated','Undifferentiated','Well/moderately differentiated')):
        raise ValueError('Grade/histology totals disagree')
    return {'analyzed_patients':total,'grades_and_histologies':counts,
            'grade_pair_upper_bound':min(counts['Poorly differentiated'],counts['Well/moderately differentiated']),
            'verified_eligible_pairs':None,
            'missing':'Patient-level grade/histology/assay crosswalk; aggregate categories cannot be intersected exactly',
            'article_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def atlas_counts(path):
    import openpyxl
    w=openpyxl.load_workbook(path,read_only=True,data_only=True)
    rows=list(w['B.Cancer.patient.information'].values);header=rows[0]
    selected=[dict(zip(header,r)) for r in rows[1:] if 'pancrea' in str(r).lower()]
    ids=[r['PatientID'] for r in selected]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicated atlas patient')
    w.close()
    return {'pancreatic_patients':len(ids),'diagnosis_labels':sorted(set(r['TissueName'] for r in selected)),
            'unconditional_pair_ceiling':len(ids)//2,'verified_eligible_pairs':None,
            'missing':'Histological grade, confirmed ductal histology and prior-treatment status not provided in patient sheet',
            'metadata_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('article','atlas','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args()
    report={'schema':'ProteinConfirmationSourceAudit-v1','apgi':apgi_counts(a.article),'atlas2026':atlas_counts(a.atlas),
            'confirmation_release':False,'note':'Patient ceilings are not verified independent confirmation units'}
    with open(a.output,'x') as f:json.dump(report,f,indent=2,allow_nan=False)
