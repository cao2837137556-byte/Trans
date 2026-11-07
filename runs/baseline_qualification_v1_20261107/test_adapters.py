"""Local numerical smoke is not a substitute for real Linux input gates."""
import ast,json,time
import numpy as np
import torch
from worker import HERE,model_factory,choose,write
def main():
 torch.set_num_threads(1);torch.manual_seed(27);results={}
 for name in ['TabM','ModernNCA','DisentAD']:
  start=time.monotonic();m,c=model_factory(name);x=torch.randn(8,790);y=torch.arange(8)%2;m.train();opt=getattr(torch.optim,c['optimizer'])(m.parameters(),lr=c['lr'],weight_decay=c['weight_decay'])
  before={k:v.detach().clone() for k,v in m.state_dict().items()}
  if name=='TabM':
   z=m(x).squeeze(-1);assert z.shape==(8,32);loss=torch.nn.functional.binary_cross_entropy_with_logits(z,y[:,None].float().expand_as(z))
  elif name=='ModernNCA':loss=torch.nn.functional.nll_loss(m(x[:4],y[:4],x[4:],y[4:],True),y[:4])
  else:r,d=m(x[:2].unsqueeze(-1));loss=r+d
  assert torch.isfinite(loss);loss.backward();assert all(p.grad is None or torch.isfinite(p.grad).all() for p in m.parameters());opt.step();assert any(not torch.equal(before[k],v) for k,v in m.state_dict().items())
  m.eval()
  with torch.no_grad():
   def score():return m(x[:2]) if name=='TabM' else m(x[:2],None,x[2:],y[2:],False) if name=='ModernNCA' else m(x[:2].unsqueeze(-1))
   a=score().clone();state={k:torch.from_numpy(v.detach().numpy().copy()) for k,v in m.state_dict().items()};m.load_state_dict(state);b=score();assert torch.equal(a,b) and torch.isfinite(a).all()
  results[name]=dict(status='PASS',seconds=time.monotonic()-start,parameters=sum(p.numel() for p in m.parameters()))
 rr=[dict(uid=str(i),label=i%2,device='d',protocol=6) for i in range(20)];assert np.array_equal(choose(rr,np.arange(20),8),choose(rr,np.arange(20)[::-1],8))
 for p in HERE.glob('*.py'):ast.parse(p.read_text())
 write('LOCAL_REGRESSION.json',dict(status='PASS',scope='SYNTHETIC_API_NUMERICAL_ONLY',real_linux_pending=True,models=results,selection_order_invariant=True));print(json.dumps(results))
if __name__=='__main__':main()
