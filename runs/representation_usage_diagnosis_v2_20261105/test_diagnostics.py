"""Independent masked-forward, attribution and donor-contract regression."""
import ast,json,hashlib
from pathlib import Path
import numpy as np
import torch
import analysis_core as ac
HERE=Path(__file__).resolve().parent

def main():
 torch.set_num_threads(1);torch.manual_seed(7);rng=np.random.default_rng(7);count=0
 for p in HERE.glob('*.py'):ast.parse(p.read_text())
 for dimension in [8,782,790]:
  net=torch.nn.Sequential(torch.nn.Linear(dimension,128),torch.nn.ReLU(),torch.nn.Linear(128,1)).double();x=rng.normal(size=(11,dimension));values,grad,means=ac.decompose(net,x,dimension)
  for mask in range(8):
   altered=x.copy()
   for j,sl in enumerate(ac.SLICES):
    if mask&(1<<j):continue
    local=slice(0,8) if dimension==8 and j==2 else slice(0,0) if dimension==8 else sl
    altered[:,local]=0
   expected=net(torch.from_numpy(altered)).detach().numpy()[:,0];assert np.max(np.abs(values[:,mask]-expected))<1e-12;count+=1
  phi=ac.shapley(values[:,:,None]);assert np.max(np.abs(phi.sum(1)[:,0]-(values[:,7]-values[:,0])))<1e-12
  if dimension==8:assert np.array_equal(phi[:,:2],np.zeros_like(phi[:,:2]))
  t=torch.tensor(x,requires_grad=True);net(t).sum().backward();assert np.max(np.abs(means-np.mean(np.abs(t.grad.numpy()),axis=0)))<1e-12
 rows=[dict(uid=str(i),protocol=6 if i<5 else 17,label=i%2) for i in range(10)];mapping,single=ac.permutation(rows,5)
 assert single==0 and np.all(mapping!=np.arange(10));changed=[dict(r,label=1-r['label']) for r in rows];assert np.array_equal(mapping,ac.permutation(changed,5)[0])
 v=ac.changed(np.asarray([1.,-1]),np.asarray([-1.,2.]),0,np.arange(2));assert v['removed_alarms']==v['added_alarms']==1
 receipt=dict(status='PASS',independent_masked_forward_cases=count,exact_shapley_efficiency=True,dummy_blocks=True,analytic_gradient_matches_autograd=True,permutation_no_labels=True,linux_real_gate='PENDING')
 (HERE/'LOCAL_REGRESSION.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode());print('DIAGNOSTIC_LOCAL_REGRESSION_PASS',count)
if __name__=='__main__':main()
