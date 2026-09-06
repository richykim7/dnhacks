#!/usr/bin/env python3
"""Audit clinical annotations; protein values are not retained or analyzed."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

CLINICAL_FIELDS = ('PatientID', 'Grade', 'Histology', 'T_or_N')
APGI_MATRIX_URL = 'https://ftp.pride.ebi.ac.uk/pride/data/archive/2025/09/PXD059074/protein_matrix.csv'


def fetch_apgi_annotations():
    checksum=hashlib.sha256();size=0
    with urllib.request.urlopen(APGI_MATRIX_URL,timeout=90) as source:
        def lines():
            nonlocal size
            for line in source:
                size+=len(line)
                if size>100*1024**2:raise ValueError('Clinical projection source exceeds byte budget')
                checksum.update(line)
                yield line.decode('utf-8-sig')
        rows=clinical_projection(lines())
    return {'url':APGI_MATRIX_URL,'bytes':size,'sha256':checksum.hexdigest(),'rows':rows}


def clinical_projection(lines):
    """Project embedded clinical columns and hash identifiers before retaining rows."""
    reader=csv.DictReader(lines)
    if not reader.fieldnames or not set(CLINICAL_FIELDS)<=set(reader.fieldnames):
        raise ValueError('Required embedded clinical columns missing')
    if len(reader.fieldnames)!=len(set(reader.fieldnames)):
        raise ValueError('Duplicated matrix columns')
    out=[]
    for i,row in enumerate(reader):
        patient=row['PatientID']
        if not isinstance(patient,str) or not patient.strip() or patient.strip() in {'NA','nan'}:
            raise ValueError('Missing patient identifier')
        projected={k:row[k] for k in CLINICAL_FIELDS}
        projected['PatientID']=hashlib.sha256(('APGI/PXD059074/'+patient).encode()).hexdigest()
        projected['source_row']=i
        out.append(projected)
    return out


def embedded_counts(rows):
    by_patient=defaultdict(list)
    for row in rows:
        if row['T_or_N'] not in {'Tumour','Normal'}:raise ValueError('Unknown specimen type')
        by_patient[row['PatientID']].append(row)
    for observations in by_patient.values():
        if any(len({r[key] for r in observations})!=1 for key in ('Grade','Histology')):
            raise ValueError('Conflicting patient annotations')
    tumors=[r for r in rows if r['T_or_N']=='Tumour']
    if len(tumors)!=len({r['PatientID'] for r in tumors}):raise ValueError('Repeated tumor patient')
    ductal=[r for r in tumors if r['Histology']=='Pancreatic Ductal Adenocarcinoma']
    crosswalk={'Well/Moderate differentiation':'G1_G2','3 - Poorly differentiated':'G3','Undifferentiated/unknown':'excluded'}
    if any(r['Grade'] not in crosswalk for r in tumors):raise ValueError('Unreviewed grade label')
    counts=Counter(crosswalk[r['Grade']] for r in ductal)
    return {'all_specimen_rows':len(rows),'unique_patients':len(by_patient),'unique_tumor_patients':len(tumors),
            'strict_ductal_patients':len(ductal),'strict_ductal_grades':dict(counts),
            'clinical_grade_pairs':min(counts['G1_G2'],counts['G3']),
            'verified_confirmation_pairs':None,
            'remaining':'Assay/coverage, cross-study identity, independent processing and release reviews'}


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
    source=p.add_mutually_exclusive_group()
    source.add_argument('--embedded-clinical',help='Saved metadata-only APGI projection JSON')
    source.add_argument('--fetch-embedded',action='store_true',help='Stream the published matrix and retain clinical columns only')
    a=p.parse_args()
    report={'schema':'ProteinConfirmationSourceAudit-v1','apgi':apgi_counts(a.article),'atlas2026':atlas_counts(a.atlas),
            'confirmation_release':False,'note':'Patient ceilings are not verified independent confirmation units'}
    if a.embedded_clinical or a.fetch_embedded:
        source=fetch_apgi_annotations() if a.fetch_embedded else json.loads(Path(a.embedded_clinical).read_text())
        report['apgi']['embedded']=embedded_counts(source['rows'])
        report['apgi']['embedded_source_sha256']=source['sha256']
        report['apgi']['missing']='Individual clinical intersection resolved; confirmation processing/reviews still required'
    with open(a.output,'x') as f:json.dump(report,f,indent=2,allow_nan=False)
