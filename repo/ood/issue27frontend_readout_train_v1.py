"""One trajectory per arm, shared lawful supervision, fixed epoch20 endpoints."""
import copy
import math
import numpy as np
import torch
import issue27frontend_readout_support_v1 as s
import issue27frontend_readout_model_v1 as m


def load_contexts(contexts, path, budget):
    out = []
    with path.open('rb') as f:
        for c in contexts:
            budget.check(phase='LOADING_'+c['role'].upper())
            f.seek(c['offset']); raw = f.read(c['length']*524)
            s.require(len(raw) == c['length']*524, 'FEATURE_TRUNCATED')
            for t in c['targets']:
                s.require(s.prefix(raw,t['event']) == t['feature_prefix_sha256'], 'PREFIX_IDENTITY')
            x = np.frombuffer(raw,dtype='<f4').copy().reshape(c['length'],131)
            s.require(np.isfinite(x).all(), 'FEATURE_NONFINITE')
            out.append({**c,'x':torch.from_numpy(x)})
            budget.access['feature_bytes_decoded'] += len(raw)
    return out


def fit(contexts, initial, r, out, budget, expected_orders):
    groups = {g:{c['key']:c for c in contexts if c['targets'][0]['owner'] == g} for g in 'AB'}
    steps, epochs = r['schedule']['steps_per_epoch'], r['schedule']['epochs']
    m.configure()
    model = copy.deepcopy(initial); model.train()
    initial_hash = m.state_hash(initial)
    frozen = m.freeze(model)
    s.require(m.state_hash(model) == initial_hash, 'INITIALIZATION_DRIFT')
    opt = m.optimizer(model, r); s.require(not opt.state, 'OPTIMIZER_NOT_RESET')
    opt.register_step_post_hook(lambda optimizer,args,kwargs: budget.access.__setitem__('optimizer_steps',budget.access['optimizer_steps']+1))
    counts = dict(targets=0,contexts=0,events=0,padded_slots=0,forwards=0,updates=0)
    def charge(batch):
        counts['targets'] += sum(len(c['targets']) for c in batch)
        counts['contexts'] += len(batch); counts['events'] += sum(c['length'] for c in batch)
        counts['padded_slots'] += len(batch)*max(c['length'] for c in batch); counts['forwards'] += 1
        budget.access['student_forwards'] += 1
    orders = []
    for epoch in range(1,epochs+1):
        sums = dict(label=0.,head_gradient_L2=0.,clip_factor=0.)
        ak,bk = s.order(groups['A'],epoch,'A'),s.order(groups['B'],epoch,'B')
        hashes = {g:__import__('hashlib').sha256(s.canonical(ks)).hexdigest() for g,ks in [('A',ak),('B',bk)]}
        s.require(hashes == expected_orders[epoch-1], 'ORIGINAL_FROZEN_BATCH_ORDERS')
        orders.append(hashes)
        for step,(a,b) in enumerate(zip(s.buckets(ak,steps),s.buckets(bk,steps)),1):
            budget.check(phase='TRAINING',arm='H_AB',epoch=epoch,epochs=epochs,step=step,
                         steps_per_epoch=steps,updates=counts['updates'],updates_total=epochs*steps)
            stats = m.update(model,opt,[groups['A'][k] for k in a],[groups['B'][k] for k in b],epoch,r,charge)
            counts['updates'] += 1
            for key,value in stats.items(): sums[key] += value
            with (out/'training_log.jsonl').open('ab') as f:
                f.write(s.canonical(dict(arm='H_AB',epoch=epoch,step=step,**stats))+b'\n')
        m.verify_frozen(model,frozen,opt)
        summary = dict(arm='H_AB',epoch=epoch,label_loss=sums['label']/steps,
                       mean_head_gradient_L2=sums['head_gradient_L2']/steps,mean_clip_factor=sums['clip_factor']/steps,
                       frozen_tensor_hashes=m.tensor_hashes(model),frozen_grad_none=True,frozen_optimizer_state_absent=True)
        with (out/'epoch_log.jsonl').open('ab') as f:f.write(s.canonical(summary)+b'\n')
        budget.check(True,updates=counts['updates'])
    s.require(counts == r['schedule']['expected_counts_per_arm'], 'EXACT_TRAIN_COUNTS')
    m.verify_frozen(model,frozen,opt)
    path = out/'H_AB.pt'
    with path.open('xb') as f:torch.save(model.state_dict(),f)
    receipt = dict(file_sha256=s.sha(path,budget.check),state_sha256=m.state_hash(model),initial_state_sha256=initial_hash,
                   epoch=epochs,counts=counts,trainable_parameters=8321,frozen_parameters=82944,
                   initial_frozen_tensor_hashes=frozen,final_frozen_tensor_hashes=m.tensor_hashes(model),
                   frozen_grad_none=True,frozen_optimizer_state_absent=True,teacher_rows_read=0,guard_pairs_read=0)
    s.atomic_json(out/'H_AB.receipt.json',receipt)
    barrier = dict(status='FINAL_CANDIDATE_SEALED',candidates={'H_AB':receipt},order_hashes={'H_AB':orders},recipe_sha256=s.RECIPE_SHA)
    s.atomic_json(out/'candidates_sealed.json',barrier)
    return barrier


def train(r,out,budget):
    plan = s.read_json(s.pin(r['inputs']['plan'],budget.check))
    contexts = s.train_metadata(plan,r)
    from issue27frontend_readout_entry_v1 import preflight
    expected = preflight(r,plan,out,budget)
    contexts = load_contexts(contexts,s.pin(r['inputs']['train_check_features'],budget.check),budget)
    initial = m.Student()
    checkpoint = s.pin(r['inputs']['initial_AB'],budget.check)
    initial.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True),strict=True)
    budget.access['historical_student_loads'] += 1
    s.require(m.state_hash(initial) == r['inputs']['initial_AB']['state_sha256'], 'INITIAL_STATE')
    result = fit(contexts,initial,r,out,budget,expected)
    s.require(budget.access['optimizer_steps'] == r['schedule']['updates_all_arms'], 'TOTAL_UPDATES')
    return result

