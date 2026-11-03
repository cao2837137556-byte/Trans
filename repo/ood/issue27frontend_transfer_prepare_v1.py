"""Selective train-only P2 task-contribution materialization (authorized P only)."""
import math
import zipfile
from collections import defaultdict
import numpy as np
import torch
from torch.nn import functional as F
import issue27frontend_transfer_support_v1 as s


def select_rows(path, indices, shape, audit, check=lambda: None):
    s.require(indices == sorted(set(indices)) and all(0 <= i < shape[0] for i in indices), 'SELECTIVE_INDICES')
    wanted = set(indices); values = []
    with zipfile.ZipFile(path) as z:
        s.require(z.namelist().count('representation.npy') == 1, 'REPRESENTATION_MEMBER')
        with z.open('representation.npy') as f:
            version = np.lib.format.read_magic(f)
            s.require(version in ((1,0),(2,0)), 'NPY_VERSION')
            header = np.lib.format.read_array_header_1_0 if version == (1,0) else np.lib.format.read_array_header_2_0
            dims, fortran, dtype = header(f)
            s.require(tuple(dims) == tuple(shape) and not fortran and dtype == np.dtype('<f4'), 'REPRESENTATION_HEADER')
            for i in range(shape[0]):
                check()
                raw = f.read(shape[1]*4)
                s.require(len(raw) == shape[1]*4, 'SHORT_REPRESENTATION')
                audit['opaque_bytes_streamed'] += len(raw)
                if i in wanted:
                    row = np.frombuffer(raw,dtype='<f4').copy()
                    s.require(np.isfinite(row).all(), 'NONFINITE_SELECTED_REPRESENTATION')
                    values.append(row); audit['numeric_rows_opened'] += 1
            s.require(f.read(1) == b'', 'REPRESENTATION_TRAILING_BYTES')
    return np.stack(values)


def contributions(values, state, expected_hard):
    shapes = {'normalizer_mean':(768,), 'normalizer_scale':(768,), 'p2__0.weight':(128,769),
              'p2__0.bias':(128,), 'p2__3.weight':(1,128), 'p2__3.bias':(1,)}
    s.require(set(state) == set(shapes), 'STATE_ALLOWLIST')
    s.require(values.dtype == np.float32 and values.ndim == 2 and values.shape[1] == 768
              and np.isfinite(values).all(), 'TEACHER_INPUT')
    for k,shape in shapes.items():
        s.require(state[k].shape == shape and np.isfinite(state[k]).all(), 'TEACHER_STATE:'+k)
    s.require((state['normalizer_scale'] > 0).all(), 'NORMALIZER_SCALE')
    z = (values.astype(np.float64)-state['normalizer_mean'].astype(np.float64))/state['normalizer_scale'].astype(np.float64)
    x = torch.from_numpy(np.concatenate([z,np.zeros((len(z),1))],axis=1).astype(np.float32))
    with torch.no_grad():
        a = F.relu(F.linear(x,torch.as_tensor(state['p2__0.weight'],dtype=torch.float32),torch.as_tensor(state['p2__0.bias'],dtype=torch.float32)))
        w = torch.as_tensor(state['p2__3.weight'],dtype=torch.float32)
        b = torch.as_tensor(state['p2__3.bias'],dtype=torch.float32)
        raw = F.linear(a,w,b).flatten()
        probability = raw.sigmoid().numpy().astype(np.float64)
        c = (a*w).numpy()
        ref = a.numpy().astype(np.float64)*w.numpy().astype(np.float64)
        reconstructed = ref.sum(axis=1)+float(b[0])
    s.require(np.isfinite(c).all() and bool(torch.isfinite(raw).all()), 'TEACHER_NONFINITE')
    s.require(np.array_equal(probability >= .065159872174263,np.asarray(expected_hard,dtype=bool)), 'OLD_HARD_DRIFT')
    gamma = 258*2.**-23/(1-258*2.**-23)
    error = np.abs(reconstructed-raw.numpy().astype(np.float64))
    tolerance = gamma*(np.abs(ref).sum(axis=1)+abs(float(b[0])))+1e-6
    s.require(np.all(error <= tolerance), 'CONTRIBUTION_RECONSTRUCTION')
    return c,raw.numpy(),probability,dict(max_reconstruction_error=float(error.max()), max_tolerance=float(tolerance.max()))


def normalize(c, ts):
    groups = defaultdict(list)
    for i,t in enumerate(ts):
        groups[(t['label'],t['context_key'])].append(i)
    means = {y:[] for y in (0,1)}
    for (y,_),indices in sorted(groups.items()):
        means[y].append(float(np.square(c[indices].astype(np.float64)).mean()))
    s.require(all(means.values()), 'EMPTY_TEACHER_CLASS')
    rms = math.sqrt(.5*sum(float(np.mean(means[y])) for y in (0,1)))
    s.require(math.isfinite(rms) and rms > 0, 'ZERO_OR_NONFINITE_TEACHER_RMS')
    scale = max(1e-6,rms)
    cache = (c.astype(np.float64)/scale).astype('<f4')
    s.require(np.isfinite(cache).all(), 'NORMALIZED_TEACHER_NONFINITE')
    return cache,scale,{str(y):len(means[y]) for y in (0,1)}


def materialize(r, contexts, out, budget):
    ts = s.teacher_targets(contexts,r); wanted = [t['uid'] for t in ts]
    spec = r['old_teacher_inputs']
    paths = {k:s.pin(spec[k],budget.check) for k in ('representations','state','threshold_marker')}
    audit = budget.access
    audit.update(identity_records=0, numeric_rows_opened=0, opaque_bytes_streamed=0, state_arrays=0, teacher_passes=0)
    budget.check(True,phase='TEACHER_IDENTITIES')
    with zipfile.ZipFile(paths['representations']) as z:
        s.require(all(z.namelist().count(k+'.npy') == 1 for k in ('uid','missing')), 'IDENTITY_MEMBERS')
    with np.load(paths['representations'],allow_pickle=False) as z:
        uids, missing = z['uid'],z['missing']
    n = spec['representation_shape'][0]
    s.require(uids.shape == missing.shape == (n,) and missing.dtype == np.bool_, 'TEACHER_IDENTITIES')
    mapping = {str(u):i for i,u in enumerate(uids)}
    s.require(len(mapping) == n and all(u in mapping and not missing[mapping[u]] for u in wanted), 'TEACHER_UID_MISSING')
    audit['identity_records'] = n
    indices = sorted(mapping[u] for u in wanted)
    values = select_rows(paths['representations'],indices,spec['representation_shape'],audit,budget.check)
    inverse = {j:i for i,j in enumerate(indices)}
    values = values[[inverse[mapping[u]] for u in wanted]]
    with zipfile.ZipFile(paths['state']) as z:
        s.require(all(z.namelist().count(k+'.npy') == 1 for k in spec['state_array_allowlist']), 'STATE_MEMBERS')
    with np.load(paths['state'],allow_pickle=False) as z:
        state = {k:z[k] for k in spec['state_array_allowlist']}
    audit['state_arrays'] = 6
    budget.check(True,phase='MATERIALIZING_TEACHER',targets_total=len(ts))
    c,raw,probability,checks = contributions(values,state,[t['old_hard'] for t in ts]); audit['teacher_passes'] += 1
    cache,scale,denoms = normalize(c,ts)
    cfg = r['losses']['P2_feature']
    s.require(denoms == {str(y):cfg['expected_N_T'+str(y)] for y in (0,1)}, 'TEACHER_DENOMINATORS')
    with (out/'teacher.f32le').open('xb') as f:
        f.write(cache.tobytes())
    rows = [dict(uid=t['uid'],context_key=t['context_key'],label=t['label'],row=i,source_row=mapping[t['uid']],
                 canonical_logit=float(raw[i]),canonical_probability=float(probability[i])) for i,t in enumerate(ts)]
    s.atomic_json(out/'teacher_index.json',rows)
    receipt = dict(status='TEACHER_PREPARED',targets=len(ts),shape=[len(ts),128],dtype='<f4',s_T=scale,
                   denominators=denoms,checks=checks,teacher_sha256=s.sha(out/'teacher.f32le',budget.check),
                   index_sha256=s.sha(out/'teacher_index.json',budget.check),recipe_sha256=s.RECIPE_SHA)
    s.atomic_json(out/'preparation_receipt.json',receipt)
    return receipt


def prepare(r, out, budget):
    inputs = r['inputs']
    plan = s.read_json(s.pin(inputs['plan'],budget.check))
    s.pin(inputs['membership'],budget.check)
    contexts = s.train_metadata(plan,r)
    saved = s.read_json(s.pin(inputs['saved_train_scores'],budget.check))['A']
    groups,scale = s.guard_metadata(contexts,saved,r)
    keys = ('uid','context_key','label','component_id','event','logit')
    s.atomic_json(out/'guard.json',dict(scale=scale,groups={k:[{f:t[f] for f in keys} for t in vs] for k,vs in groups.items()}))
    # Opaque identity hashes only: P never decodes student features or loads A.
    s.pin(inputs['train_check_features'],budget.check)
    s.pin(inputs['initial_A'],budget.check)
    return materialize(r,contexts,out,budget)
