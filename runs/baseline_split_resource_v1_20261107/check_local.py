import ast,json,tempfile
from pathlib import Path
import numpy as np
import torch
import split_resource as r
from pipeline_parent import HERE,write

def main():
 torch.set_num_threads(1)
 for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);(root/'artifacts').mkdir();mask=np.arange(1024)%5==0;np.save(root/'artifacts/INNER_VALID.npy',mask)
  rng=np.random.RandomState(27);x=rng.randn(1024,790).astype('float32');y=np.arange(1024)%2
  r.HERE=root;r.arrays=lambda:(x,y,np.arange(1024));r.read=lambda p:dict(status='PASS',mask_sha256=r.sha(root/'artifacts/INNER_VALID.npy'));r.progress=lambda *a,**k:None
  results={}
  for n in ['DTE_EPOCH','TABM_EPOCH']:
   v=r.epoch(n);assert v['same_process_optimizer_rng_cursor_replay_exact'] is True;assert v['validation_rows']==int(mask.sum());results[n]=dict(status='PASS',resume_exact=True,steps=v['steps'])
 write('LOCAL_REGRESSION.json',dict(status='PASS',synthetic_only=True,checks=results));print(results)
if __name__=='__main__':main()
