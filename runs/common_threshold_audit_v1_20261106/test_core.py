import json
from pathlib import Path
import numpy as np
from core import curve,analyze
def main():
 rng=np.random.default_rng(4);checks=0
 for n in [2,31,100]:
  x=rng.integers(-3,4,n).astype(float);w=rng.random(n);cuts=np.r_[-4,np.unique(x),4]
  got=curve(x,w,w.sum(),cuts)
  for i,c in enumerate(cuts):assert abs(got[i]-w[x>c].sum()/w.sum())<1e-12;checks+=1
 g={f'EDGE/sample/{r}':dict(scores=np.array(x,float),weights=np.ones(len(x)),denominator=len(x)) for r,x in [('NORMAL',[0]*98+[1]*2),('HTTP',[2]*1000),('UDP',[2]*1000)]}
 a=analyze(g,.5);p=a['results']['EDGE/sample'];assert p['status']=='FEASIBLE' and p['lower_cut']==1 and p['upper_cut_exclusive']==2;checks+=1
 g['EDGE/sample/UDP']['scores'][:]=0;a=analyze(g,.5);assert a['results']['EDGE/sample']['status']=='INFEASIBLE';checks+=1
 # 99.9% inclusive, score ties never split.
 g['EDGE/sample/UDP']['scores'][:]=2;g['EDGE/sample/UDP']['scores'][0]=0
 assert analyze(g,.5)['results']['EDGE/sample']['status']=='FEASIBLE';checks+=1
 out=dict(status='PASS',checks=checks,tests=['bruteforce weighted ties','strict FPR equality rejected','inclusive recall','common-class infeasibility'])
 (Path(__file__).parent/'LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2));print(out)
if __name__=='__main__':main()
