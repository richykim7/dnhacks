#!/usr/bin/env python3
"""Export real-data model comparison figures; no simulated biological results."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True);p.add_argument('--output',required=True)
a=p.parse_args();report=json.loads(Path(a.report).read_text());out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
fig,axes=plt.subplots(1,3,figsize=(15,4.3),layout='constrained')
colors={'malignant':'#137F8C','fibroblast':'#AC6732'}
for comp in colors:
 model=report['models'][comp+'-nb'];loss=model['manifest']['training_loss']
 axes[0].plot(range(1,len(loss)+1),loss,label=comp,color=colors[comp],linewidth=2)
axes[0].set(xlabel='Training epoch',ylabel='Masked NB reconstruction loss',title='Real count-model training')
axes[0].legend(frameon=False)
methods=['pseudobulk-pca','cell-pca','nb'];labels=['Pseudobulk PCA','Cell PCA','Masked NB']
for ax,comp in zip(axes[1:],colors):
 for i,source in enumerate(['peng','lin']):
  values=[report['models'][comp+'-'+m]['held_out'][source]['donor_mean_reconstruction_mse'] for m in methods]
  ax.bar(np.arange(3)+(i-.5)*.34,values,width=.34,label='Peng held-out' if source=='peng' else 'Lin external',color=colors[comp],alpha=1 if i==0 else .5)
 ax.set(xticks=np.arange(3),xticklabels=labels,ylabel='Donor-mean log-library MSE',title=('Malignant-enriched' if comp=='malignant' else 'Fibroblast')+' representation')
 ax.tick_params(axis='x',labelrotation=18);ax.legend(frameon=False)
fig.suptitle('Cellular ecosystems — observed development-model comparison',fontweight='bold')
fig.savefig(out/'ecosystem-training.png',bbox_inches='tight',pad_inches=.15);fig.savefig(out/'ecosystem-training.pdf',bbox_inches='tight',pad_inches=.15);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
for ax,comp in zip(axes,colors):
 model=report['models'][comp+'-cell-pca'];eligible=[model['training_donors'],model['held_out']['peng']['eligible_donors'],model['held_out']['lin']['eligible_donors']]
 totals=[16,8,10];x=np.arange(3)
 ax.bar(x,eligible,color=colors[comp],label='Eligible at 32 cells')
 ax.bar(x,np.array(totals)-eligible,bottom=eligible,color='#D9DDDD',label='Unavailable coverage')
 ax.set(xticks=x,xticklabels=['Peng train','Peng holdout','Lin external'],ylabel='Canonical donor labels (development)',title='Malignant-enriched' if comp=='malignant' else 'Fibroblast')
 ax.set_ylim(0,18)
 for i,n in enumerate(eligible):ax.text(i,n+.3,str(n),ha='center')
 ax.legend(frameon=False,fontsize=8)
fig.suptitle('Missing compartments remain unavailable; cells do not increase donor n',fontweight='bold')
fig.savefig(out/'ecosystem-coverage.png',bbox_inches='tight',pad_inches=.15);fig.savefig(out/'ecosystem-coverage.pdf',bbox_inches='tight',pad_inches=.15)
