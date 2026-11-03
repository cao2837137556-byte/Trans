"""Fresh complete GRU/student, plain context-normalized BCE only."""
import copy
import os
import platform
import random
import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence,pack_padded_sequence,pad_packed_sequence
import issue27frontend_paired_train_support_v1 as s


def configure():
    s.require(platform.python_version()=='3.9.13' and np.__version__=='2.0.2' and torch.__version__=='2.8.0+cpu','RUNTIME_VERSION')
    s.require(all(os.environ.get(k)==v for k,v in {'PYTHONHASHSEED':'2705','OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4'}.items()),'RUNTIME_ENV')
    torch.set_num_threads(4)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(2705);np.random.seed(2705);torch.manual_seed(2705)


class Student(nn.Module):
    def __init__(self):
        super().__init__()
        self.event_projection=nn.Linear(131,64)
        self.event_activation=nn.GELU(approximate='none')
        self.encoder=nn.GRU(64,128,num_layers=1,bias=True,batch_first=True,dropout=0.,bidirectional=False)
        self.head_hidden=nn.Linear(128,64)
        self.head_activation=nn.GELU(approximate='none')
        self.head_output=nn.Linear(64,1)
        s.require(sum(p.numel() for p in self.parameters())==91265,'MODEL_PARAMETERS')

    def forward(self, sequences, keys):
        s.require(len(sequences)==len(keys)>0 and len(set(keys))==len(keys),'BATCH_KEYS')
        for x in sequences:
            s.require(x.dtype==torch.float32 and x.device.type=='cpu' and x.ndim==2 and x.shape[1]==131 and 1<=len(x)<=256,'INPUT_SCHEMA')
            s.require(bool(torch.isfinite(x).all()),'NONFINITE_INPUT')
        order=sorted(range(len(keys)),key=lambda i:(-len(sequences[i]),keys[i]))
        lengths=[len(sequences[i]) for i in order]
        x=pad_sequence([sequences[i] for i in order],batch_first=True)
        packed=pack_padded_sequence(self.event_activation(self.event_projection(x)),lengths,batch_first=True,enforce_sorted=True)
        encoded,_=self.encoder(packed)
        hidden,_=pad_packed_sequence(encoded,batch_first=True)
        out=[None]*len(keys)
        for j,i in enumerate(order):
            q=self.head_output(self.head_activation(self.head_hidden(hidden[j,:lengths[j]]))).squeeze(-1)
            s.require(bool(torch.isfinite(q).all()),'NONFINITE_LOGIT');out[i]=q
        return out


def state_hash(model):
    import hashlib
    h=hashlib.sha256()
    for name,t in sorted(model.state_dict().items()):
        a=t.detach().cpu().contiguous().numpy()
        h.update(name.encode()+b'\0'+str(a.dtype).encode()+str(a.shape).encode());h.update(a.tobytes())
    return h.hexdigest()


def optimizer(model):
    return torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001,betas=(.9,.999),eps=1e-8,
        amsgrad=False,foreach=False,fused=False,maximize=False,capturable=False,differentiable=False)


def context_sum(model,batch):
    qs=model([c['x'][:c['length']] for c in batch],[c['key'] for c in batch])
    terms=[]
    for c,q in zip(batch,qs):
        selected=q[[t['event'] for t in c['targets']]]
        labels=torch.tensor([t['label'] for t in c['targets']],dtype=torch.float32)
        terms.append(nn.functional.binary_cross_entropy_with_logits(selected,labels,reduction='mean'))
    return torch.stack(terms).sum()


def update(model,opt,a,b,steps,na,nb,charge=lambda batch:None):
    opt.zero_grad(set_to_none=True);loss=0.
    for batch,denom in ((a,na),(b,nb)):
        for j in range(0,len(batch),32):
            micro=batch[j:j+32];charge(micro)
            term=context_sum(model,micro)*(steps/denom)
            s.require(bool(torch.isfinite(term)),'NONFINITE_LOSS')
            term.backward();loss+=float(term.detach())
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.,norm_type=2.,error_if_nonfinite=True)
    opt.step()
    s.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()),'NONFINITE_PARAMETER')
    return loss


def infer(model,contexts,charge=lambda batch:None):
    model.eval();out={}
    with torch.no_grad():
        for j in range(0,len(contexts),32):
            batch=contexts[j:j+32];charge(batch)
            qs=model([c['x'][:c['length']] for c in batch],[c['key'] for c in batch])
            for c,q in zip(batch,qs):
                for t in c['targets']:
                    s.require(t['uid'] not in out,'DUPLICATE_PREDICTION')
                    out[t['uid']]=float(q[t['event']])
    return out
