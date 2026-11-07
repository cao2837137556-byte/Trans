import ast,json,sys
from pathlib import Path
import numpy as np
from attribution import exact
from geometry import legal_indices,rms
HERE=Path(__file__).resolve().parent;checks=0
def check(v):
 global checks
 assert v
 checks+=1
class Tensor:
 def __init__(self,a):self.a=a
 def detach(self):return self
 def numpy(self):return self.a
class Layer:
 def __init__(self,w,b):self.weight=Tensor(w);self.bias=Tensor(b)
rng=np.random.default_rng(20261106)
for dim in [8,790]:
 w=rng.normal(size=(128,dim));b=rng.normal(size=128);v=rng.normal(size=(1,128));bias=np.array([.4]);model=[Layer(w,b),None,Layer(v,bias)];x=rng.normal(size=(63,dim))
 score,base,ig,grad=exact(model,x);check(np.allclose(ig.sum(1),score-base,atol=1e-9));check(np.allclose(score,np.maximum(x@w.T+b,0)@v[0]+bias[0]))
 for j in range(8):
  xp=x.copy();xp[:,-8+j]+=1e-7;finite=(np.maximum(xp@w.T+b,0)@v[0]+bias[0]-score)/1e-7;check(np.max(np.abs(finite-grad[:,j]))<1e-4)
refs=[dict(reference_end=10,capture_id='a',frame=i+1,component_id=str(i),bank_end_frame=5) for i in range(3)]
check(legal_indices(dict(timestamp=10,capture_id='b',frame=1),refs)[1]=='BANK_NOT_YET_AVAILABLE')
check(legal_indices(dict(timestamp=11,capture_id='a',frame=5),refs)[1]=='BANK_FRAME_NOT_YET_AVAILABLE')
check(legal_indices(dict(timestamp=11,capture_id='a',frame=6),refs)[0]==[0,1,2])
check(legal_indices(dict(timestamp=11,capture_id='a',frame=6),[refs[0]])[1]=='FEWER_THAN_TWO_LEGAL_COMPONENTS')
check(legal_indices(dict(timestamp=11,capture_id='a',frame=6),[])[1]=='NO_REFERENCE_BANK')
check(np.array_equal(rms(np.zeros((1,8)),np.ones((2,8))),np.ones((1,2))))
# Intersection is applied to each reference before second distinct-component selection.
dz=np.array([[.1,.9,.2]]);dc=np.array([[.9,.1,.8]]);joint=np.maximum(dz,dc)
check(np.sort(joint,axis=1)[0,1]==.9);check(np.sort(joint,axis=1)[0,1]>max(np.sort(dz)[0,1],np.sort(dc)[0,1]))
s2=rng.uniform(size=100);s3=s2*rng.uniform(size=100);raw=rng.normal(size=100);cap=24
check(np.all(raw-cap*(1-(1-s3)**3)>=raw-cap*(1-(1-s2)**3)));check(np.all(raw-cap*(1-(1-s3)**3)<=raw))
for f in HERE.glob('*.py'):ast.parse(f.read_text())
out=dict(status='PASS',checks=checks,scope='Exact ReLU contributions, gradient, legal reference timing/frame, intersection monotonicity, syntax')
(HERE/'LOCAL_REGRESSION.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(out)
