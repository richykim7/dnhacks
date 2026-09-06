#!/usr/bin/env python3
"""Bounded CPU learned-set pilot against compressed donor-summary PCA."""
import argparse,json
from pathlib import Path
import numpy as np
from dnhacksbio.ecosystem_design import CountData
from dnhacksbio.ecosystem_encoder import load_encoder,fit_set_aggregator,evaluate_set_aggregator
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root)
report={'schema':'ecosystem-real-set-pilot-v1','confirmation':'unavailable','models':{}}
for compartment in ('malignant','fibroblast'):
 train=CountData.load(root/f'prepared/peng-{compartment}-training.npz',roles=('training',))
 cell=load_encoder(root/f'models/{compartment}-cell-pca.npz')
 model,baseline=fit_set_aggregator(train,cell)
 model.save(root/f'models/{compartment}-set.npz')
 np.savez_compressed(root/f'models/{compartment}-set-baseline.npz',projection=baseline)
 result={'model_hash':model.identity,'manifest':model.manifest,'held_out':{}}
 for source in ('peng','lin'):
  dev=CountData.load(root/f'prepared/{source}-{compartment}-development.npz',roles=('development',))
  result['held_out'][source]=evaluate_set_aggregator(dev,cell,model,baseline)
 report['models'][compartment]=result
 print(compartment,result['held_out'],flush=True)
(root/'models/set-comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
