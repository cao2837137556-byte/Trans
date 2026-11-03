"""One trajectory per arm, shared lawful supervision, fixed epoch20 endpoints."""
import copy
import math
import numpy as np
import torch
import issue27frontend_aligned_support_v1 as s
import issue27frontend_aligned_model_v1 as m


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


def fit(contexts, initial, guard, cache, r, out, budget):
    groups = {g:{c['key']:c for c in contexts if c['targets'][0]['owner'] == g} for g in 'AB'}
    steps,epochs = r['schedule']['steps_per_epoch'],r['schedule']['epochs']
    initial_hash = m.state_hash(initial); receipts = {}; order_hashes = {}
    for arm in ('Q','R'):
        m.configure()
        model = copy.deepcopy(initial); model.train()
        projection = m.Projection() if arm == 'R' else None
        s.require(m.state_hash(model) == initial_hash, 'INITIALIZATION_DRIFT')
        opt = m.optimizer(model,projection,r)
        s.require(not opt.state, 'OPTIMIZER_NOT_RESET')
        def completed_step(optimizer,args,kwargs):
            budget.access['optimizer_steps'] += 1
        opt.register_step_post_hook(completed_step)
        counts = dict(targets=0,contexts=0,events=0,padded_slots=0,forwards=0,updates=0)
        def charge(batch):
            counts['targets'] += sum(len(c['targets']) for c in batch)
            counts['contexts'] += len(batch); counts['events'] += sum(c['length'] for c in batch)
            counts['padded_slots'] += len(batch)*max(c['length'] for c in batch); counts['forwards'] += 1
            budget.access['student_forwards'] += 1
        hashes = []; pairs = 0
        for epoch in range(1,epochs+1):
            epoch_sums = {}
            ak,bk = s.order(groups['A'],epoch,'A'),s.order(groups['B'],epoch,'B')
            hashes.append({g:__import__('hashlib').sha256(s.canonical(ks)).hexdigest() for g,ks in [('A',ak),('B',bk)]})
            for step,(a,b) in enumerate(zip(s.buckets(ak,steps),s.buckets(bk,steps)),1):
                budget.check(phase='TRAINING',arm=arm,epoch=epoch,epochs=epochs,step=step,steps_per_epoch=steps,
                             updates=counts['updates'],updates_total=epochs*steps)
                stats = m.update(model,projection,opt,[groups['A'][k] for k in a],[groups['B'][k] for k in b],
                                 arm,epoch,guard,cache,r,charge)
                counts['updates'] += 1; pairs += stats['pairs']
                for k,v in stats.items():epoch_sums[k]=epoch_sums.get(k,0)+v
                with (out/'training_log.jsonl').open('ab') as f:
                    f.write(s.canonical(dict(arm=arm,epoch=epoch,step=step,**stats))+b'\n')
            s.require(epoch_sums['teacher_targets']==r['teacher_cache']['expected_targets'],'TEACHER_EPOCH_COVERAGE')
            n=epoch_sums['teacher_targets']
            summary=dict(arm=arm,epoch=epoch,loss_means={k:epoch_sums[k]/steps for k in ('label','guard','task_score','residual')},
                raw_logit_MAE=epoch_sums['raw_error_abs_sum']/n,normalized_MAE=epoch_sums['normalized_error_abs_sum']/n,
                teacher_targets=int(n),mean_student_gradient_L2=epoch_sums['student_gradient_L2']/steps,
                mean_D_gradient_L2=epoch_sums['D_gradient_L2']/steps,mean_clip_factor=epoch_sums['clip_factor']/steps)
            with (out/'epoch_log.jsonl').open('ab') as f:f.write(s.canonical(summary)+b'\n')
            budget.check(True,updates=counts['updates'])
        s.require(counts['updates'] == r['schedule']['updates_per_arm'] and counts['targets'] == r['schedule']['target_presentations_per_arm'], 'TRAIN_ACTION_COUNTS')
        s.require(pairs == r['losses']['A_guard']['pair_occurrences'], 'GUARD_PRESENTATIONS')
        path = out/(arm+'.pt')
        with path.open('xb') as f:
            torch.save(model.state_dict(),f)
        projection_sha = None
        if projection is not None:
            with (out/'R_projection_training_only.pt').open('xb') as f:
                torch.save(projection.state_dict(),f)
            projection_sha = s.sha(out/'R_projection_training_only.pt',budget.check)
        receipts[arm] = dict(file_sha256=s.sha(path,budget.check),state_sha256=m.state_hash(model),
                             initial_state_sha256=initial_hash,epoch=epochs,counts=counts,guard_pair_occurrences=pairs,projection_file_sha256=projection_sha)
        order_hashes[arm] = hashes
        s.atomic_json(out/(arm+'.receipt.json'),receipts[arm])
        del opt,model,projection
    s.require(order_hashes['Q'] == order_hashes['R'], 'ARM_ORDERS')
    s.require(receipts['Q']['counts'] == receipts['R']['counts'], 'ARM_EXPOSURE')
    barrier = dict(status='BOTH_FINAL_CANDIDATES_SEALED',candidates=receipts,order_hashes=order_hashes,
                   recipe_sha256=s.RECIPE_SHA)
    s.atomic_json(out/'candidates_sealed.json',barrier)
    return barrier


def train(r, out, budget):
    prep = s.OUTPUTS['P']; s.manifest(prep,check=budget.check)
    s.require(s.read_json(prep/'supervisor_terminal.json')['status'] == 'COMPLETE', 'P_NOT_COMPLETE')
    plan = s.read_json(s.pin(r['inputs']['plan'],budget.check))
    contexts = s.train_metadata(plan,r)
    from issue27frontend_aligned_prepare_v1 import load_guard, load_prepared
    guard = load_guard(contexts,r,budget)
    cache = load_prepared(contexts,r,prep,budget)
    contexts = load_contexts(contexts,s.pin(r['inputs']['train_check_features'],budget.check),budget)
    initial = m.Student()
    checkpoint = s.pin(r['inputs']['initial_A'],budget.check)
    initial.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True),strict=True)
    budget.access['historical_student_loads'] += 1
    s.require(m.state_hash(initial) == r['inputs']['initial_A']['state_sha256'], 'INITIAL_STATE')
    result = fit(contexts,initial,guard,cache,r,out,budget)
    expected = [{'A':v['A_order_sha256'],'B':v['B_order_sha256']} for v in plan['accounting']['epoch_order_hashes'][:20]]
    s.require(all(v == expected for v in result['order_hashes'].values()), 'ORIGINAL_FROZEN_BATCH_ORDERS')
    s.require(budget.access['optimizer_steps'] == r['schedule']['updates_all_arms'], 'TOTAL_UPDATES')
    return result
