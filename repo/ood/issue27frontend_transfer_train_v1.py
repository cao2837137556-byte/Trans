"""One trajectory per arm, shared lawful supervision, fixed epoch20 endpoints."""
import copy
import math
import numpy as np
import torch
import issue27frontend_transfer_support_v1 as s
import issue27frontend_transfer_model_v1 as m


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


def load_teacher(contexts, r, folder, budget):
    receipt = s.read_json(folder/'preparation_receipt.json'); rows = s.read_json(folder/'teacher_index.json')
    ts = s.teacher_targets(contexts,r)
    s.require(receipt['recipe_sha256'] == s.RECIPE_SHA and receipt['targets'] == len(ts), 'PREPARATION_IDENTITY')
    s.require(receipt['status'] == 'TEACHER_PREPARED' and receipt['dtype'] == '<f4' and math.isfinite(receipt['s_T'])
              and receipt['s_T'] > 0 and receipt['denominators'] == {str(y):r['losses']['P2_feature']['expected_N_T'+str(y)] for y in (0,1)}, 'TEACHER_SCALE_DENOMINATORS')
    s.require(s.sha(folder/'teacher.f32le',budget.check) == receipt['teacher_sha256'], 'TEACHER_CACHE_HASH')
    s.require(s.sha(folder/'teacher_index.json',budget.check) == receipt['index_sha256'], 'TEACHER_INDEX_HASH')
    s.require(len(rows) == len(ts) and receipt['shape'] == [len(ts),128], 'TEACHER_CACHE_SHAPE')
    for i,(row,t) in enumerate(zip(rows,ts)):
        s.require(row['row'] == i and all(row[k] == t[k] for k in ('uid','context_key','label')), 'TEACHER_CACHE_JOIN')
        s.require(math.isfinite(row['canonical_logit']) and math.isfinite(row['canonical_probability'])
                  and (row['canonical_probability'] >= .065159872174263) == bool(t['old_hard']), 'TEACHER_CANONICAL_CACHE')
    values = np.fromfile(folder/'teacher.f32le',dtype='<f4')
    s.require(values.size == len(ts)*128 and np.isfinite(values).all(), 'TEACHER_CACHE_VALUES')
    values = torch.from_numpy(values.reshape(len(ts),128))
    return {t['uid']:values[i] for i,t in enumerate(ts)}


def fit(contexts, initial, guard, cache, r, out, budget):
    groups = {g:{c['key']:c for c in contexts if c['targets'][0]['owner'] == g} for g in 'AB'}
    steps,epochs = r['schedule']['steps_per_epoch'],r['schedule']['epochs']
    initial_hash = m.state_hash(initial); receipts = {}; order_hashes = {}
    for arm in ('C0','C1','C2'):
        m.configure()
        model = copy.deepcopy(initial); model.train()
        projection = m.Projection() if arm == 'C2' else None
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
            ak,bk = s.order(groups['A'],epoch,'A'),s.order(groups['B'],epoch,'B')
            hashes.append({g:__import__('hashlib').sha256(s.canonical(ks)).hexdigest() for g,ks in [('A',ak),('B',bk)]})
            for step,(a,b) in enumerate(zip(s.buckets(ak,steps),s.buckets(bk,steps)),1):
                budget.check(phase='TRAINING',arm=arm,epoch=epoch,epochs=epochs,step=step,steps_per_epoch=steps,
                             updates=counts['updates'],updates_total=epochs*steps)
                stats = m.update(model,projection,opt,[groups['A'][k] for k in a],[groups['B'][k] for k in b],
                                 arm,epoch,guard,cache,r,charge)
                counts['updates'] += 1; pairs += stats['pairs']
                with (out/'training_log.jsonl').open('ab') as f:
                    f.write(s.canonical(dict(arm=arm,epoch=epoch,step=step,**stats))+b'\n')
            budget.check(True,updates=counts['updates'])
        s.require(counts['updates'] == r['schedule']['updates_per_arm'] and counts['targets'] == r['schedule']['target_presentations_per_arm'], 'TRAIN_ACTION_COUNTS')
        if arm != 'C0':
            s.require(pairs == r['losses']['A_guard']['pair_occurrences'], 'GUARD_PRESENTATIONS')
        path = out/(arm+'.pt')
        with path.open('xb') as f:
            torch.save(model.state_dict(),f)
        if projection is not None:
            with (out/'C2_projection_training_only.pt').open('xb') as f:
                torch.save(projection.state_dict(),f)
        receipts[arm] = dict(file_sha256=s.sha(path,budget.check),state_sha256=m.state_hash(model),
                             initial_state_sha256=initial_hash,epoch=epochs,counts=counts,guard_pair_occurrences=pairs)
        order_hashes[arm] = hashes
        s.atomic_json(out/(arm+'.receipt.json'),receipts[arm])
        del opt,model,projection
    s.require(order_hashes['C0'] == order_hashes['C1'] == order_hashes['C2'], 'ARM_ORDERS')
    s.require(receipts['C0']['counts'] == receipts['C1']['counts'] == receipts['C2']['counts'], 'ARM_EXPOSURE')
    barrier = dict(status='ALL_THREE_FINAL_CANDIDATES_SEALED',candidates=receipts,order_hashes=order_hashes,
                   recipe_sha256=s.RECIPE_SHA)
    s.atomic_json(out/'candidates_sealed.json',barrier)
    return barrier


def train(r, out, budget):
    prep = s.OUTPUTS['P']; s.manifest(prep,check=budget.check)
    s.require(s.read_json(prep/'supervisor_terminal.json')['status'] == 'COMPLETE', 'P_NOT_COMPLETE')
    plan = s.read_json(s.pin(r['inputs']['plan'],budget.check))
    contexts = s.train_metadata(plan,r)
    saved = s.read_json(s.pin(r['inputs']['saved_train_scores'],budget.check))['A']
    guard = s.guard_metadata(contexts,saved,r)
    cache = load_teacher(contexts,r,prep,budget)
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
