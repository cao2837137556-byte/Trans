"""Fixed causal AB encoder and two freshly initialized shared classification heads."""
import hashlib
import random
import platform
import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence, pad_packed_sequence
import issue27dualview_support_v1 as s


def configure():
    s.require(platform.python_version()=='3.9.13' and np.__version__=='2.0.2' and torch.__version__=='2.8.0+cpu','RUNTIME_VERSION')
    torch.set_num_threads(4)
    if torch.get_num_interop_threads()!=1: torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(2705); np.random.seed(2705); torch.manual_seed(2705)


def state_hash(state):
    if isinstance(state, nn.Module): state=state.state_dict()
    h=hashlib.sha256()
    for name,t in sorted(state.items()):
        a=t.detach().cpu().contiguous().numpy()
        h.update(name.encode()+b'\0'+str(a.dtype).encode()+str(a.shape).encode()); h.update(a.tobytes())
    return h.hexdigest()


class Encoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.event_projection=nn.Linear(131,64)
        self.encoder=nn.GRU(64,128,num_layers=1,bias=True,batch_first=True,dropout=0.,bidirectional=False)
        self.requires_grad_(False); self.eval()
        s.require(sum(p.numel() for p in self.parameters())==82944,'ENCODER_PARAMETERS')

    def forward(self, sequences, keys):
        s.require(not self.training and not torch.is_grad_enabled(),'ENCODER_MODE')
        s.require(len(sequences)==len(keys)>0 and len(set(keys))==len(keys),'ENCODER_KEYS')
        for x in sequences:
            s.require(x.dtype==torch.float32 and x.device.type=='cpu' and x.ndim==2 and x.shape[1]==131 and 1<=len(x)<=256 and bool(torch.isfinite(x).all()),'ENCODER_INPUT')
        order=sorted(range(len(keys)),key=lambda i:(-len(sequences[i]),keys[i]))
        lengths=[len(sequences[i]) for i in order]
        x=pad_sequence([sequences[i] for i in order],batch_first=True)
        packed=pack_padded_sequence(nn.functional.gelu(self.event_projection(x),approximate='none'),lengths,batch_first=True,enforce_sorted=True)
        encoded,_=self.encoder(packed); hidden,_=pad_packed_sequence(encoded,batch_first=True)
        out=[None]*len(keys)
        for j,i in enumerate(order): out[i]=hidden[j,:lengths[j]]
        return out


def load_encoder(r,budget):
    path=s.pin(r['inputs']['initial_AB'],budget.check)
    state=torch.load(path,map_location='cpu',weights_only=True)
    budget.access['historical_student_loads']+=1
    s.require(state_hash(state)==r['inputs']['initial_AB']['state_sha256'],'AB_STATE')
    model=Encoder()
    model.load_state_dict({k:v for k,v in state.items() if k.startswith(('event_projection.','encoder.'))},strict=True)
    del state
    return model,state_hash(model)


def verify_encoder(model,identity):
    s.require(not model.training and all(not p.requires_grad and p.grad is None for p in model.parameters()),'ENCODER_FREEZE')
    s.require(state_hash(model)==identity,'ENCODER_MUTATED')


def head():
    torch.manual_seed(2705)
    model=nn.Sequential(nn.Linear(897,128),nn.ReLU(),nn.Dropout(.1),nn.Linear(128,1))
    s.require(sum(p.numel() for p in model.parameters())==115073,'HEAD_PARAMETERS')
    return model


def optimizer(model,r):
    c=r['optimizer']; keys=('lr','weight_decay','eps','amsgrad','foreach','fused','maximize','capturable','differentiable')
    return torch.optim.AdamW(model.parameters(),betas=tuple(c['betas']),**{k:c[k] for k in keys})


def arm_input(x,arm):
    s.require(arm in ('U0','U1') and x.ndim==2 and x.shape[1]==897,'ARM_INPUT')
    if arm=='U0':
        x=x.clone(); x[:,128:896]=0
    return x


def update(model,opt,x,y,weights):
    opt.zero_grad(set_to_none=True)
    q=model(x).reshape(-1)
    loss=nn.functional.binary_cross_entropy_with_logits(q,y,weight=weights,reduction='mean')
    s.require(bool(torch.isfinite(loss)),'LOSS_NONFINITE'); loss.backward()
    norm=nn.utils.clip_grad_norm_(model.parameters(),1.,norm_type=2.,error_if_nonfinite=True,foreach=False)
    opt.step()
    s.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()),'PARAMETER_NONFINITE')
    return float(loss.detach()),float(norm)


def normalizers(ab,e3,mask):
    s.require(ab.shape==(len(mask),128) and e3.shape==(len(mask),768) and mask.dtype==np.bool_ and mask.any(),'NORMALIZER_SHAPE')
    values=[ab.astype(np.float64),e3[mask].astype(np.float64)]
    means=[];scales=[]
    for x in values:
        s.require(np.isfinite(x).all(),'NORMALIZER_NONFINITE')
        means.append(x.mean(axis=0)); sd=x.std(axis=0,ddof=0);scales.append(np.where(sd>0,sd,1.))
    return np.concatenate(means),np.concatenate(scales)


def normalize(ab,e3,mask,mean,scale):
    s.require(mean.shape==scale.shape==(896,) and np.isfinite(mean).all() and np.isfinite(scale).all() and (scale>0).all(),'NORMALIZER_SCHEMA')
    out=np.zeros((len(mask),897),dtype='<f4')
    for start in range(0,len(mask),4096):
        end=min(start+4096,len(mask)); valid=mask[start:end]
        out[start:end,:128]=((ab[start:end].astype(np.float64)-mean[:128])/scale[:128]).astype('<f4')
        block=out[start:end,128:896]
        block[valid]=((e3[start:end][valid].astype(np.float64)-mean[128:])/scale[128:]).astype('<f4')
        out[start:end,896]=valid.astype('<f4')
    s.require(np.isfinite(out).all(),'NORMALIZED_NONFINITE')
    return out
