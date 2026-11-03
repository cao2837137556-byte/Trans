"""Generated-only integration fixtures for diagnostic math, I/O and Windows Job."""
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / 'tmp/frontend_transfer_diagnostic_synthetic_v1'


def no_real_numeric(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    raw_path = os.fsdecode(args[0])
    if raw_path.casefold() == os.devnull.casefold():
        return
    path = Path(raw_path).resolve()
    if ROOT / 'runs' in path.parents and path.suffix.lower() in (
            '.pt', '.pth', '.npz', '.npy', '.f32le', '.gz'):
        raise RuntimeError('DIAGNOSTIC_FIXTURE_BLOCKED_REAL_NUMERIC:' + str(path))


sys.addaudithook(no_real_numeric)

import issue27frontend_transfer_diagnostic_v1 as runner

s = runner.s


def checked_directory(path):
    path = Path(path).resolve()
    s.require(TEST_ROOT.resolve() in path.parents, 'GENERATED_FIXTURE_DIRECTORY_ONLY')
    return path


def generated_diagnose(out):
    """Use the production diagnose loop; replace only historical asset I/O."""
    import copy
    from contextlib import ExitStack
    from unittest.mock import patch
    import torch
    import issue27frontend_transfer_model_v1 as model_api
    import issue27frontend_transfer_train_v1 as train

    out = checked_directory(out)
    out.mkdir()
    dataset = out.parent / 'generated-inputs'
    dataset.mkdir()
    pdir, tdir, edir = (dataset / name for name in ('P', 'T', 'E'))
    for path in (pdir, tdir, edir):
        path.mkdir()
    torch.manual_seed(2705)
    contexts, features = [], {}
    for key, owner, label in (('A0', 'A', 0), ('A1', 'A', 1),
                              ('A2', 'A', 0), ('A3', 'A', 1),
                              ('B0', 'B', 0), ('B1', 'B', 1)):
        ts = [dict(uid=key + ':' + str(event), context_key=key, event=event,
                   label=label, owner=owner, old_hard=label, component_id=key,
                   new_role='train', source_group=owner + '-source',
                   attack_family='family-' + str(label), device_family='generated-device')
              for event in (0, 2)]
        contexts.append(dict(key=key, component=key, role='train', length=3, targets=ts))
        features[key] = torch.randn(3, 131)
    check_context = dict(key='check-sentinel', component='check-sentinel', role='check', length=1,
                         targets=[dict(uid='check-only', context_key='check-sentinel', event=0,
                                       label=1, owner='A', old_hard=1, new_role='check')])
    model, projection = model_api.Student(), model_api.Projection()
    with torch.no_grad():
        projection.weight.copy_(torch.eye(128) * .2)
        projection.bias.fill_(.1)
    initial_state = copy.deepcopy(model.state_dict())
    projection_state = copy.deepcopy(projection.state_dict())
    model.eval()
    with torch.no_grad():
        baseline = model([features[c['key']] for c in contexts], [c['key'] for c in contexts])
    with gzip.open(edir / 'C2_train.csv.gz', 'wt', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['uid', 'logit', 'hard'])
        writer.writeheader()
        for context, logits in zip(contexts, baseline):
            for target in context['targets']:
                logit = float(logits[target['event']])
                writer.writerow(dict(uid=target['uid'], logit=logit, hard=int(logit >= 0)))
    teacher_targets = [t for c in contexts for t in c['targets'] if t['owner'] == 'A']
    cache = {t['uid']: torch.linspace(-1., 1., 128) * (1 if t['label'] else -1)
             for t in teacher_targets}
    index = [dict(uid=t['uid'], context_key=t['context_key'], label=t['label'],
                  canonical_logit=2. if t['label'] else -2.) for t in teacher_targets]
    orders = {g + '_order_sha256': hashlib.sha256(s.canonical(s.order(
        [c['key'] for c in contexts if c['targets'][0]['owner'] == g], 20, g))).hexdigest()
              for g in 'AB'}
    plan = dict(contexts=contexts + [check_context], accounting=dict(epoch_order_hashes=[orders] * 20))
    saved = [dict(t, logit=2. if t['label'] else -2., hard=t['label']) for t in teacher_targets]
    s.atomic_json(dataset / 'plan.json', plan)
    s.atomic_json(dataset / 'saved.json', {'A': saved})
    (dataset / 'features.generated').write_text('No numerical feature decoding: generated tensors only.', encoding='utf-8')
    s.atomic_json(pdir / 'teacher_index.json', index)
    s.atomic_json(pdir / 'preparation_receipt.json', {'s_T': .5})
    s.atomic_json(tdir / 'C2.receipt.json', {'state_sha256': model_api.state_hash(model)})
    r = dict(inputs={key: dict(path=str(dataset / name), sha256=s.sha(dataset / name))
                     for key, name in [('plan', 'plan.json'), ('saved_train_scores', 'saved.json'),
                                       ('train_check_features', 'features.generated')]},
             data=dict(train_contexts=6, train_targets=12,
                       A=dict(contexts=4, targets=8, attack=4),
                       B=dict(contexts=2, targets=4, attack=2)),
             losses=dict(A_guard=dict(s_A=2., eligible_contexts=4, eligible_targets=8),
                         P2_feature=dict(expected_N_T0=2, expected_N_T1=2, targets=8,
                                         benign_targets=4, attack_targets=4)))
    asset_calls = []

    def load_generated_state(path, **kwargs):
        path = Path(path)
        s.require(kwargs.get('map_location') == 'cpu' and kwargs.get('weights_only') is True,
                  'FIXTURE_CHECKPOINT_OPTIONS')
        s.require(path in (tdir / 'C2.pt', tdir / 'C2_projection_training_only.pt'),
                  'FIXTURE_CHECKPOINT_WHITELIST')
        asset_calls.append(path.name)
        return copy.deepcopy(initial_state if path.name == 'C2.pt' else projection_state)

    def load_generated_contexts(selected, path, budget):
        s.require(Path(path) == dataset / 'features.generated', 'FIXTURE_FEATURE_WHITELIST')
        s.require(all(c['role'] == 'train' and c['key'] in features for c in selected),
                  'FIXTURE_NONTRAIN_FEATURE_ACCESS')
        return [dict(c, x=features[c['key']].clone()) for c in selected]

    def load_generated_teacher(selected, recipe, folder, budget):
        s.require(Path(folder) == pdir and recipe is r, 'FIXTURE_TEACHER_WHITELIST')
        s.require({t['uid'] for t in s.teacher_targets(selected, recipe)} == set(cache),
                  'FIXTURE_TEACHER_TARGETS')
        return {uid: value.clone() for uid, value in cache.items()}

    budget = runner.parent.v1.Budget(out, time.monotonic(), dict(seconds=60))
    budget.access.update(contexts_processed=0, task_gradient_calls=0,
                         hidden_gradient_calls=0, projection_loads=0, teacher_cache_rows=0)
    with ExitStack() as stack:
        for name, value in dict(N_BUCKETS=2, N_TARGETS=12, N_TEACHER=8,
                                N_CONTEXTS=6, MAX_BATCH=32, T=tdir, E=edir).items():
            stack.enter_context(patch.object(runner, name, value))
        stack.enter_context(patch.dict(s.OUTPUTS, {'P': pdir}))
        stack.enter_context(patch.object(torch, 'load', side_effect=load_generated_state))
        stack.enter_context(patch.object(train, 'load_contexts', side_effect=load_generated_contexts))
        stack.enter_context(patch.object(train, 'load_teacher', side_effect=load_generated_teacher))
        result = runner.diagnose(r, out, budget)
        budget.check(True, phase='GENERATED_VERIFIED')
    s.require(asset_calls == ['C2.pt', 'C2_projection_training_only.pt'], 'FIXTURE_LOAD_COUNT')
    return dict(result=result, access=budget.access, generated_state_loads=len(asset_calls))


def main():
    mode, out = sys.argv[1], checked_directory(sys.argv[2])
    if mode == 'supervise':
        runner.parent.v1.present = runner.present
        command = [str(s.PYTHON), '-B', str(Path(__file__).resolve()), 'worker', str(out)]
        result = runner.parent.v1.supervise('D', out,
            dict(seconds=45, memory=2 * 1024**3, output=8 * 1024**2), command, synthetic=True)
        print(json.dumps(result, ensure_ascii=True))
        return
    s.require(mode == 'worker', 'FIXTURE_MODE')
    deadline = time.monotonic() + 30
    while not (out / 'worker_gate.json').exists():
        s.require(time.monotonic() < deadline, 'FIXTURE_GATE_TIMEOUT')
        time.sleep(.01)
    gate = s.read_json(out / 'worker_gate.json')
    s.require(gate['pid'] == os.getpid() and gate['parent_pid'] == os.getppid()
              and gate['workspace_verified'] is False, 'FIXTURE_GATE')
    for step in range(500):
        s.atomic_json(out / 'progress.json', dict(phase='GENERATED_DIAGNOSTIC_IO',
                      bucket=step, targets=step, teacher_targets=step, padding='x' * 4096))
        time.sleep(.003)
    s.atomic_json(out / 'generated_result.json', dict(status='GENERATED_ONLY', progress_records=500,
                  real_model_forwards=0, real_teacher_rows=0, real_optimizer_steps=0))
    s.atomic_json(out / 'worker_terminal.json', dict(status='WORK_COMPLETE_VERIFIED', stage='D',
                  recipe_sha256=s.RECIPE_SHA,
                  output_hashes={'generated_result.json': s.sha(out / 'generated_result.json')}))


if __name__ == '__main__':
    main()
