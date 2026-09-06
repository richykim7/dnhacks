"""Reproducible development-only Peng count preparation from original GSA files."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from .ecosystem_design import CountData, digest

PROGRAMS = {
    'malignant': {
        'stress-program': ['DDIT3','HSPA5','ATF4','XBP1'],
        'transport-program': ['SLC1A5','SLC38A2','SLC7A5','SLC16A1'],
        'antigen-program': ['B2M','HLA-A','HLA-B','HLA-C','TAP1'],
    },
    'fibroblast': {
        'contractile-program': ['ACTA2','TAGLN','MYL9','COL1A1','COL1A2'],
        'inflammatory-program': ['CXCL12','IL6','CXCL14','CFD','DPT'],
        'antigen-program': ['CD74','HLA-DRA','HLA-DPA1','HLA-DPB1'],
        'metabolic-program': ['SLC16A1','LDHA','SLC38A2','GOT1','PSAT1'],
    },
}
LABELS = {'Ductal cell type 2':'malignant', 'Fibroblast cell':'fibroblast'}


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''): h.update(chunk)
    return h.hexdigest()


def count_rows(path):
    with Path(path).open() as stream:
        header=stream.readline().strip().split()
        cells=[v.strip('"') for v in header]
        for line in stream:
            gene, values=line.split(' ',1)
            if re.fullmatch(r'[0-9\s]+', values) is None:
                raise ValueError('Counts must be nonnegative integers')
            counts=np.fromstring(values,sep=' ',dtype=np.int64)
            if len(counts)!=len(cells) or np.any(counts<0):
                raise ValueError('Incomplete count row')
            yield gene.strip('"'), counts


def prepare_peng(root, *, genes_per_compartment=2000, selection_cells=32, seed=1701):
    """Three streaming passes: library totals, TRAIN-only selection, sparse panel.

    No complete cell-by-gene dense array is constructed. Published labels define
    development compartments; type-2 ductal is explicitly malignant-enriched.
    """
    from scipy import sparse
    root=Path(root); audit=root/'source-audit'; output=root/'prepared';output.mkdir(exist_ok=True)
    partition=json.loads((audit/'peng-partition.json').read_text())
    path=root/'raw/peng-count-matrix.txt'
    if path.stat().st_size != 2771872913:
        raise ValueError('Original count download is incomplete or source changed')
    annotation={}
    with (audit/'peng-celltypes.txt').open() as stream:
        next(stream)
        for line in stream:
            cell,label=line.rstrip('\n').split('\t');annotation[cell]=label
    with path.open() as stream: cells=[v.strip('"') for v in stream.readline().split()]
    if len(set(cells))!=len(cells) or set(cells)!=set(annotation):
        raise ValueError('Original count/annotation cell identity mismatch')
    donors=np.asarray([c.split('_')[0] for c in cells])
    labels=np.asarray([LABELS.get(annotation[c],'excluded') for c in cells])
    # Use only exact symbols measured by every external assay, from feature
    # metadata alone. This is frozen before fitting, not test-value imputation.
    import gzip
    feature_paths=list((root/'raw/lin').glob('*genes.tsv.gz'))+list((root/'raw/lin').glob('*features.tsv.gz'))
    allowed_genes=None
    if feature_paths:
        for feature_path in feature_paths:
            with gzip.open(feature_path,'rt') as stream:
                measured={line.strip().split('\t')[1] for line in stream}
            allowed_genes=measured if allowed_genes is None else allowed_genes & measured
    train=set(partition['training']);dev=set(partition['development'])
    if train&dev or len(train)!=16 or len(dev)!=8:
        raise ValueError('Frozen donor partition changed')
    totals=np.zeros(len(cells),dtype=np.int64)
    gene_names=[]
    print('Pass 1: measured all-gene library sizes',flush=True)
    for gene,counts in count_rows(path):
        totals+=counts;gene_names.append(gene)
    if len(set(gene_names))!=len(gene_names) or np.any(totals<=0):
        raise ValueError('Duplicate genes or empty measured library')
    selections={}; coverage={}
    for compartment in PROGRAMS:
        chosen=[];coverage[compartment]={}
        for donor in partition['training']+partition['development']:
            rows=np.flatnonzero((donors==donor)&(labels==compartment))
            coverage[compartment][donor]=len(rows)
            if donor in train and len(rows)>=selection_cells:
                local=int(digest([seed,donor,compartment])[:16],16)
                chosen.extend(np.random.default_rng(local).choice(rows,selection_cells,replace=False))
        if not chosen: raise ValueError('No training compartment coverage')
        selections[compartment]=np.asarray(chosen)
    stats={c:{} for c in PROGRAMS}
    print('Pass 2: separate training-only gene and state references',flush=True)
    for gene,counts in count_rows(path):
        for compartment,rows in selections.items():
            values=np.log1p(counts[rows]/totals[rows]*10000)
            stats[compartment][gene]=(float(values.mean()),float(values.std()),float(np.mean(counts[rows]>0)))
    panels={};state_refs={}
    for compartment in PROGRAMS:
        ranked=sorted((g for g in gene_names if stats[compartment][g][2]>=.05 and (allowed_genes is None or g in allowed_genes)),key=lambda g:(-stats[compartment][g][1],g))
        forced={g for panel in PROGRAMS[compartment].values() for g in panel if g in stats[compartment] and (allowed_genes is None or g in allowed_genes)}
        genes=sorted(forced|set([g for g in ranked if g not in forced][:genes_per_compartment-len(forced)]))
        panels[compartment]=genes
        state_refs[compartment]=dict(genes=genes,mean=[stats[compartment][g][0] for g in genes],
             scale=[max(stats[compartment][g][1],.1) for g in genes],programs=PROGRAMS[compartment],
             assignment='argmax of mean training-standardized gene expression per predefined program',
             selection_donors=sorted(set(donors[selections[compartment]])),selection_cells=selection_cells,
             feature_availability='exact symbol intersection of original Lin 10x feature metadata' if feature_paths else 'original Peng features')
    # Sparse selected panels only; values for unselected genes are never retained.
    collected={c:{'rows':[],'cols':[],'values':[]} for c in PROGRAMS}
    cell_rows={c:np.flatnonzero(np.isin(donors,list(train|dev))&(labels==c)) for c in PROGRAMS}
    gene_maps={c:{g:i for i,g in enumerate(panel)} for c,panel in panels.items()}
    print('Pass 3: selected sparse count panels',flush=True)
    for gene,counts in count_rows(path):
        for compartment in PROGRAMS:
            if gene not in gene_maps[compartment]:continue
            values=counts[cell_rows[compartment]];nonzero=np.flatnonzero(values)
            collected[compartment]['rows'].append(nonzero)
            collected[compartment]['cols'].append(np.full(len(nonzero),gene_maps[compartment][gene],dtype=np.int32))
            collected[compartment]['values'].append(values[nonzero])
    count_hash=sha256(path);label_hash=sha256(audit/'peng-celltypes.txt')
    artifacts={}
    for compartment in PROGRAMS:
        columns=collected[compartment]; indices=cell_rows[compartment]
        matrix=sparse.coo_matrix((np.concatenate(columns['values']),
                  (np.concatenate(columns['rows']),np.concatenate(columns['cols']))),shape=(len(indices),len(panels[compartment]))).tocsr()
        ref=state_refs[compartment]; state_ids=list(ref['programs']);assignments=[]
        for start in range(0,len(indices),256):
            raw=matrix[start:start+256].toarray()
            x=np.log1p(raw/totals[indices[start:start+256],None]*10000)
            z=(x-np.asarray(ref['mean']))/np.asarray(ref['scale'])
            program_scores=np.column_stack([z[:,[gene_maps[compartment][g] for g in ref['programs'][state] if g in gene_maps[compartment]]].mean(1) for state in state_ids])
            assignments.extend(state_ids[i] for i in program_scores.argmax(1))
        for role,allowed in [('training',train),('development',dev)]:
            keep=np.isin(donors[indices],list(allowed)); selected=matrix[keep].tocsr();selected.sort_indices()
            metadata=[]
            for i in np.flatnonzero(keep):
                idx=indices[i];donor=str(donors[idx])
                metadata.append(dict(cell_id=cells[idx],accession='CRA001160',specimen=donor,
                                     compartment=compartment,state=assignments[i],library_size=int(totals[idx])))
            manifest=dict(schema='ecosystem-counts-v1',scale='UMI counts',library_size_rule='measured-all-genes',
                population='untreated-primary-human-PDAC-development',organism='human',tissue='pancreas',assay='scRNA',
                ontology='Peng2019-published-compartments-v1',state_dictionary='ecosystem-development-programs-v1',
                sampling_justification='One original tumor specimen per published individual T1-T24; development only; no independence certificate',
                specimen_rule='one-preselected-specimen-per-donor',
                sources=[dict(accession='CRA001160',license='public-GSA-research-data; source citation retained; no redistribution',
                              access_status='verified-local',role=role,sha256=count_hash)],
                crosswalk=[dict(accession='CRA001160',specimen=d,donor='CRA001160:'+d,timepoint='untreated-resection',identity_reviewed=True) for d in sorted(allowed)],
                annotation_sha256=label_hash,source_aliases=partition['source_aliases'],partition_sha256=sha256(audit/'peng-partition.json'),
                state_reference_hash=digest(ref),gene_selection_role='training-only',
                interpretation='Type-2 ductal cells are a published malignant-enriched proxy; no independent CNA validation',
                reserved_studies=partition['reserved_studies'])
            dataset=CountData(selected.data.astype(np.int64),selected.indices.astype(np.int64),selected.indptr.astype(np.int64),tuple(panels[compartment]),metadata,manifest)
            destination=output/f'peng-{compartment}-{role}.npz';dataset.save(destination)
            artifacts[f'{compartment}-{role}']=dict(path=str(destination),sha256=sha256(destination),data_hash=dataset.identity(),cells=len(metadata),donors=len(allowed))
        (output/f'{compartment}-state-reference.json').write_text(json.dumps(ref,indent=2)+'\n')
    report=dict(schema='ecosystem-real-preparation-v1',source='https://download.cncb.ac.cn/gsa/CRA001160/',
                count_sha256=count_hash,annotation_sha256=label_hash,training_donors=partition['training'],development_donors=partition['development'],
                coverage=coverage,artifacts=artifacts,confirmation='unavailable',selection_cells=selection_cells,
                treatment_audit='Original Peng Results states all samples without any treatment; publication-level attestation',
                limitations=['Published compartment labels are development proxies','Cross-study aliases require audit before any confirmation'])
    (output/'preparation-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def prepare_lin(root):
    """Transfer-only primary Lin donors, original 10x counts and frozen references.

    Feature availability is audited before training. Missing measured genes fail
    rather than becoming artificial zeros. No metastasis or Hwang data loaded.
    """
    import csv
    import gzip
    from scipy import io, sparse
    root=Path(root);audit=root/'source-audit';output=root/'prepared'
    partition=json.loads((audit/'lin-partition.json').read_text())
    with (audit/'lin-celltypes.tsv').open() as stream:
        rows=list(csv.DictReader(stream,delimiter='\t'))
    annotation={r['Cell']:r for r in rows if r['Tissue']=='Primary'}
    refs={c:json.loads((output/f'{c}-state-reference.json').read_text()) for c in PROGRAMS}
    mapping={'Malignant':'malignant','Fibroblasts':'fibroblast'}
    matrices={c:[] for c in PROGRAMS}; metadata={c:[] for c in PROGRAMS};missing_genes={c:set() for c in PROGRAMS}
    inputs=[]; crosswalk=[]
    for sample in partition['samples']:
        gsm=sample['sample'];donor=sample['title'].split(':')[0]
        crosswalk.append(dict(accession='GSE154778',specimen=gsm,donor='GSE154778:'+donor,timepoint='resection-treatment-unresolved',identity_reviewed=True))
        paths=[root/'raw/lin'/u.strip().rsplit('/',1)[1] for u in sample['files']]
        barcode=next(p for p in paths if 'barcodes' in p.name)
        feature=next(p for p in paths if 'genes' in p.name or 'features' in p.name)
        matrix_path=next(p for p in paths if 'matrix.mtx' in p.name)
        with gzip.open(barcode,'rt') as stream:barcodes=[line.strip() for line in stream]
        with gzip.open(feature,'rt') as stream:genes=[line.strip().split('\t')[1] for line in stream]
        with gzip.open(matrix_path,'rb') as stream:matrix=io.mmread(stream).T.tocsr()
        if matrix.shape!=(len(barcodes),len(genes)) or np.any(matrix.data<0) or np.any(matrix.data!=np.floor(matrix.data)):
            raise ValueError('Invalid original 10x count shape/units')
        totals=np.asarray(matrix.sum(axis=1)).ravel()
        gene_columns={}
        for i,gene in enumerate(genes):gene_columns.setdefault(gene,[]).append(i)
        for compartment,ref in refs.items():
            absent=set(ref['genes'])-set(genes);missing_genes[compartment].update(absent)
            if absent:continue
            # Some Ensembl entries share a symbol: sum those measured counts,
            # never duplicate library contributions or select a data-driven alias.
            projection=sparse.coo_matrix(([1 for g in ref['genes'] for i in gene_columns[g]],
                ([i for g in ref['genes'] for i in gene_columns[g]],
                 [j for j,g in enumerate(ref['genes']) for i in gene_columns[g]])),shape=(len(genes),len(ref['genes']))).tocsr()
            selected=[]
            for i,b in enumerate(barcodes):
                info=annotation.get(gsm+'@'+b)
                if info and info['Patient']!=donor:raise ValueError('Lin canonical donor mapping conflict')
                if info and mapping.get(info['Celltype (major-lineage)'])==compartment:selected.append(i)
            counts=(matrix[selected]@projection).tocsr();counts.sort_indices()
            lookup={g:i for i,g in enumerate(ref['genes'])};state_ids=list(ref['programs'])
            for start in range(0,len(selected),256):
                indices=selected[start:start+256]
                raw=counts[start:start+256].toarray()
                z=(np.log1p(raw/totals[indices,None]*10000)-np.asarray(ref['mean']))/np.asarray(ref['scale'])
                scores=np.column_stack([z[:,[lookup[g] for g in ref['programs'][state] if g in lookup]].mean(1) for state in state_ids])
                for i,state in zip(indices,scores.argmax(1)):
                    metadata[compartment].append(dict(cell_id=gsm+'@'+barcodes[i],accession='GSE154778',specimen=gsm,
                        compartment=compartment,state=state_ids[state],library_size=int(totals[i])))
            matrices[compartment].append(counts)
        inputs.extend(dict(file=p.name,sha256=sha256(p)) for p in paths)
    if any(missing_genes.values()):
        report={c:sorted(v) for c,v in missing_genes.items()}
        (output/'lin-missing-genes.json').write_text(json.dumps(report,indent=2)+'\n')
        raise ValueError('External assay lacks selected genes; freeze a common measured panel before training')
    artifacts={}
    for compartment,ref in refs.items():
        matrix=sparse.vstack(matrices[compartment],format='csr')
        manifest=dict(schema='ecosystem-counts-v1',scale='UMI counts',library_size_rule='measured-all-genes',
            population='primary-human-PDAC-external-development-treatment-unresolved',organism='human',tissue='pancreas',assay='scRNA',
            ontology='Peng2019-published-compartments-v1',state_dictionary='ecosystem-development-programs-v1',
            external_label_mapping='TISCH Malignant/Fibroblasts mapped to frozen malignant-enriched/fibroblast slots; development-only ontology bridge',
            sampling_justification='Ten distinct primary patients per original Lin publication; metastatic biopsies excluded; no confirmation independence certificate',
            specimen_rule='one-preselected-specimen-per-donor',
            sources=[dict(accession='GSE154778',license='public-GEO-research-data; source citation retained; no redistribution',access_status='verified-local',role='development',sha256=digest(inputs))],
            crosswalk=crosswalk,annotation_sha256=sha256(audit/'lin-celltypes.tsv'),
            annotation_source='https://tisch.compbio.cn/static/data/PAAD_GSE154778/PAAD_GSE154778_CellMetainfo_table.tsv',
            state_reference_hash=digest(ref),acquisition_inputs=inputs,reserved_studies=['GSE202051','GSE199102','SCP1089','SCP1096'])
        dataset=CountData(matrix.data.astype(np.int64),matrix.indices.astype(np.int64),matrix.indptr.astype(np.int64),tuple(ref['genes']),metadata[compartment],manifest)
        destination=output/f'lin-{compartment}-development.npz';dataset.save(destination)
        artifacts[compartment]=dict(path=str(destination),sha256=sha256(destination),cells=len(dataset.cells),data_hash=dataset.identity())
    (output/'lin-preparation-report.json').write_text(json.dumps(artifacts,indent=2)+'\n')
    return artifacts


def acquire(root):
    """Audit public metadata, freeze development roles, then acquire count files.

    Only original Peng and ten original Lin primary samples are downloaded.
    Downloads resume safely and remain local; no private study endpoint is used.
    """
    import requests
    import re
    import time
    root=Path(root);audit=root/'source-audit';raw=root/'raw';audit.mkdir(parents=True,exist_ok=True);raw.mkdir(exist_ok=True)
    records=[]
    def download(url,path,expected_size=None):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            partial=Path(str(path)+'.part')
            for attempt in range(8):
                offset=partial.stat().st_size if partial.exists() else 0
                try:
                    headers={'Range':f'bytes={offset}-'} if offset else {}
                    with requests.get(url,stream=True,headers=headers,timeout=(30,60)) as response:
                        response.raise_for_status()
                        if offset and (response.status_code!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                            raise ValueError('Server did not honor safe resume')
                        with partial.open('ab' if offset else 'wb') as stream:
                            for chunk in response.iter_content(1024**2):
                                stream.write(chunk)
                                if stream.tell()>3*1024**3:raise ValueError('Source exceeds acquisition cap')
                    if expected_size and partial.stat().st_size!=expected_size:raise ValueError('Incomplete or changed source')
                    partial.replace(path);break
                except (requests.RequestException,OSError):
                    if attempt==7:raise
                    time.sleep(min(attempt+1,5))
        if expected_size and path.stat().st_size!=expected_size:raise ValueError('Existing source size mismatch')
        records.append(dict(url=url,path=str(path),bytes=path.stat().st_size,sha256=sha256(path)))
    download('https://download.cncb.ac.cn/gsa/CRA001160/all_celltype.txt',audit/'peng-celltypes.txt',2101436)
    download('https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE154778&targ=all&form=text&view=full',audit/'geo-lin.txt')
    download('https://tisch.compbio.cn/static/data/PAAD_GSE154778/PAAD_GSE154778_CellMetainfo_table.tsv',audit/'lin-celltypes.tsv')
    training=[f'T{i}' for i in range(1,17)];development=[f'T{i}' for i in range(17,25)]
    partition=dict(schema='ecosystem-peng-split-v1',training=training,development=development,
        excluded=[f'N{i}' for i in range(1,12)],rule='numeric tumor IDs T1-T16 training; T17-T24 donor-held-out development, frozen before count access',
        crosswalk=[dict(accession='CRA001160',specimen=d,donor='CRA001160:'+d,role='training' if d in training else 'development') for d in training+development],
        source_aliases=['CRA001160','PRJCA001063','zenodo.3969339','TISCH:PAAD_CRA001160'],
        reserved_studies=['GSE202051','GSE199102','SCP1089','SCP1096'],annotation_sha256=sha256(audit/'peng-celltypes.txt'),
        training_compartment_rule={'malignant':'published Ductal cell type 2 label within tumor samples; malignant-enriched proxy, not independently CNA-validated',
                                  'fibroblast':'published Fibroblast cell label within tumor samples; Stellate cell excluded to keep compartment fixed'})
    partition_path=audit/'peng-partition.json'
    if partition_path.exists() and json.loads(partition_path.read_text())!=partition:
        raise ValueError('Existing frozen Peng partition differs')
    if not partition_path.exists():partition_path.write_text(json.dumps(partition,indent=2)+'\n')
    samples=[]
    for chunk in (audit/'geo-lin.txt').read_text().split('^SAMPLE = ')[1:]:
        gsm=chunk.splitlines()[0].strip();title=re.search(r'!Sample_title = (.*)',chunk).group(1).strip()
        if title.startswith('P'):
            samples.append(dict(accession='GSE154778',sample=gsm,title=title,role='external-development',files=re.findall(r'!Sample_supplementary_file_\d+ = (.*)',chunk)))
    if len(samples)!=10:raise ValueError('Lin primary inventory changed')
    lin_partition=dict(samples=samples,exclude_metastases=True,training=False,
        population='primary-human-PDAC-development-treatment-unresolved',
        canonical_donor_rule='P01-P10 are ten distinct patients per original publication; specimen/sample aliases mapped before counts',
        reserved_sources_excluded=partition['reserved_studies'])
    lin_path=audit/'lin-partition.json'
    if lin_path.exists() and json.loads(lin_path.read_text())!=lin_partition:
        raise ValueError('Existing frozen Lin partition differs')
    if not lin_path.exists():lin_path.write_text(json.dumps(lin_partition,indent=2)+'\n')
    # Both partition files are durable before any numerical downloads begin.
    download('https://download.cncb.ac.cn/gsa/CRA001160/count-matrix.txt',raw/'peng-count-matrix.txt',2771872913)
    for sample in samples:
        for original in sample['files']:
            url=original.strip().replace('ftp://','https://')
            if not url.startswith('https://ftp.ncbi.nlm.nih.gov/geo/samples/'):
                raise ValueError('Unexpected GEO source host')
            download(url,raw/'lin'/url.rsplit('/',1)[1])
    (audit/'acquisition.json').write_text(json.dumps(dict(schema='ecosystem-acquisition-v1',role='exposed-training-development',sources=records,
        reserved_studies_unopened=partition['reserved_studies']),indent=2)+'\n')
    return records
