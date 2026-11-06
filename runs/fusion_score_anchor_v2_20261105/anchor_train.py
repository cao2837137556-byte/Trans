"""Nine v2 small heads; sum loss, fixed probes, unchanged FIT-only sample stream."""
from collections import defaultdict
import hashlib
import math
import time
from pathlib import Path
import numpy as np
import torch
import context_core as k
import anchor_diagnostics as d
c = k.c


def tail_audit(rows, probabilities, stages):
    ix = np.flatnonzero(probabilities > 0); p = probabilities[ix]
    groups = {}
    for field in ('device', 'activity', 'capture_id', 'component_id'):
        groups[field+'_count'] = len({rows[int(i)][field] for i in ix})
    stage_mass = defaultdict(float)
    for i in ix: stage_mass[k.STAGES[int(stages[int(i)])]] += float(probabilities[i])
    ordered = sorted((int(i) for i in ix), key=lambda i: rows[i]['uid'])
    digest = hashlib.sha256()
    for i in ordered:
        digest.update((rows[i]['uid']+'\n').encode()); digest.update(np.float64(probabilities[i]).tobytes())
    return dict(rows=len(ix), ESS=1/float(np.dot(p, p)), max_weight=float(p.max()),
                uid_weight_sha256=digest.hexdigest(), stages=dict(stage_mass), **groups)


def train(design, rows, values, q, norm, indices, stages, arm, seed, out, progress, synthetic=False, logging_enabled=None, runtime_batches=None, teacher_scores=None, teacher_scale=1., anchor_lambda=1.):
    c.require(runtime_batches in (None, 128) and not (synthetic and runtime_batches), "RUNTIME_GATE_SCOPE")
    c.require(arm in k.ARMS and seed in c.SEEDS, 'TRAIN_SCOPE')
    hp = design['training']; n = len(indices)
    if synthetic:
        c.require(design.get('synthetic_only') is True and n <= 256 and hp['epochs'] <= 2, 'SYNTHETIC_BOUNDS')
    else:
        c.require(n == 617908 and hp['epochs'] == 40 and hp['batch_size'] == 256 and hp['tail_negatives_per_batch'] == 128, 'PRODUCTION_TRAINING')
    diagnostics = hp.get('diagnostics', {})
    enabled = diagnostics.get('enabled', True) if logging_enabled is None else logging_enabled
    c.require(type(enabled) is bool, 'DIAGNOSTICS_ENABLED_TYPE')
    if not synthetic:
        c.require(enabled and logging_enabled is None and diagnostics.get('enabled') is True,
                  'PRODUCTION_DIAGNOSTICS_REQUIRED')
        c.require(diagnostics.get('loss_log_format') == 'npy_float64' and
                  diagnostics.get('loss_columns') == ['bce','tail','total'] and
                  diagnostics.get('probe_batches') == [1,1207,2414] and
                  diagnostics.get('gradient_timing') == 'pre_step' and
                  diagnostics.get('adam_state_timing') == 'post_step', 'DIAGNOSTICS_CONTRACT')
    rr = [rows[int(i)] for i in indices]; w = k.weights(rr)
    c.require(arm == 'FUSION790' and anchor_lambda in (0.,1.) and teacher_scale > 0, 'ANCHOR_CONTRACT')
    c.require(teacher_scores is not None and teacher_scores.shape == (n,) and np.isfinite(teacher_scores).all(), 'TEACHER_TARGETS')
    c.require(len(set(indices)) == n and all(r['use'] != 'REFERENCE' for r in rr), 'TRAIN_UID_ROLE')
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    dimension = k.DIMENSIONS[arm]
    torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
    model = k.classifier(seed, dimension)
    torch.manual_seed(seed)
    c.save_arrays(out/'initial.npz', **{name:v.detach().numpy() for name,v in model.state_dict().items()})
    optimizer = torch.optim.AdamW(model.parameters(), amsgrad=False, foreach=False, **dict(hp['optimizer_parent_values'], betas=tuple(hp['optimizer_parent_values']['betas'])))
    generator = torch.Generator(device='cpu').manual_seed(seed)
    normal = np.asarray([i for i, r in enumerate(rr) if r['label'] == 0], dtype=np.int64)
    normal_rows = [rr[int(i)] for i in normal]
    stage_normal = stages[indices[normal]]
    labels = np.asarray([r['label'] for r in rr], dtype=np.float32)
    count = 0; orders = []; tail = True
    nbatches = math.ceil(n/hp['batch_size'])
    epochs_run = 1 if runtime_batches else hp["epochs"]
    executed_batches = runtime_batches or nbatches
    probe_batches = [1, 64, 128] if runtime_batches else d.probe_batches(nbatches, synthetic=synthetic)
    profile = []
    component_losses = np.empty((epochs_run*executed_batches,4),np.float64)
    probe_indices = np.asarray(sorted(range(n),key=lambda i:rr[i]['uid'])[:4096],dtype=np.int64)
    c.save_arrays(out/'source_probe_identity.npz',uid=np.asarray([rr[i]['uid'] for i in probe_indices],dtype='S64'),teacher=teacher_scores[probe_indices])
    diagnostic_log = d.DiagnosticLog(out, epochs_run*executed_batches, executed_batches, epochs_run, probe_batches) if enabled else None
    with d.diagnostic_context(diagnostic_log):
        for epoch in range(epochs_run):
            epoch_started = time.monotonic()
            sampler = None; audit = None; sampled_digest = hashlib.sha256(); sampled_count = 0
            if tail:
                progress.stage = 'T_TAIL_REFRESH_'+arm+'_'+str(seed)+'_epoch'+str(epoch+1)
                scores = k.scores(model, values, q, indices[normal], norm, dimension, progress)
                h = k.tail_distribution(scores, 2*w[normal], hp['negative_tail_mass'])
                sampler = k.TailSampler(normal_rows, h, seed, epoch)
                audit = tail_audit(normal_rows, h, stage_normal)
            tail_seconds = time.monotonic()-epoch_started
            order = torch.randperm(n, generator=generator).numpy()
            orders.append(hashlib.sha256(order.tobytes()).hexdigest())
            loss_total = 0.; bce_total = 0.; tail_total = 0.; visits = 0
            progress.stage = 'T_BATCH_'+arm+'_'+str(seed)+'_epoch'+str(epoch+1)
            batch_started = time.monotonic()
            for start in range(0, min(n, executed_batches*hp['batch_size']), hp['batch_size']):
                local = order[start:start+hp['batch_size']]
                optimizer.zero_grad(set_to_none=True)
                logits = model(k.normalized(values, q, indices[local], norm, dimension)).flatten()
                negatives = None
                if tail:
                    sampled = sampler.draw(hp['tail_negatives_per_batch'])
                    sampled_digest.update(sampled.astype('<i8').tobytes()); sampled_count += len(sampled)
                    negatives = model(k.normalized(values, q, indices[normal[sampled]], norm, dimension)).flatten()
                batch = start//hp['batch_size']+1
                batch_labels = torch.from_numpy(labels[local])
                bce, pair, loss = k.objective_components(logits, batch_labels, w[local], n, negatives)
                base_bce = bce
                targets = torch.from_numpy(teacher_scores[local].copy())
                anchor = (torch.from_numpy(w[local]) * ((logits-targets)/teacher_scale).square()).sum() * n / len(local)
                if anchor_lambda:
                    bce = bce + anchor_lambda * anchor
                    loss = bce + pair
                component_losses[count] = [float(base_bce.detach()),float(pair.detach()),float(anchor.detach()),float(loss.detach())]
                c.require(bool(torch.isfinite(loss)), 'NONFINITE_LOSS')
                probe = expected = None
                if enabled:
                    diagnostic_log.loss((bce, pair, loss))
                    if batch in probe_batches:
                        probe, expected = d.gradient_probe(bce, pair, model.parameters(),
                                                          int((batch_labels == 1).sum()), tail)
                loss.backward()
                c.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()), 'INVALID_GRADIENT')
                if probe is not None:
                    probe['backward_sanity'] = d.backward_sanity(expected, model.parameters(), probe)
                optimizer.step()
                if enabled: diagnostic_log.step_completed()
                c.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), 'INVALID_PARAMETER')
                if probe is not None:
                    diagnostic_log.probe(dict(epoch=epoch+1, batch=batch, global_update=count+1,
                                              batch_rows=len(local), arm=arm, seed=seed,
                                              gradient=probe, adam=d.adam_probe(model, optimizer)))
                count += 1; visits += len(local); loss_total += float(loss.detach())*len(local)/n
                bce_total += float(bce.detach())*len(local)/n
                tail_total += float(pair.detach())*len(local)/n
                progress.optimizer_updates = count
                progress.tick(count, epochs_run*executed_batches)
            c.save_arrays(out/('epoch_%02d_head.npz' % (epoch+1)), **{name:v.detach().numpy() for name,v in model.state_dict().items()})
            probe_scores = k.scores(model,values,q,indices[probe_indices],norm,dimension)
            c.save_arrays(out/('epoch_%02d_source_probe.npz' % (epoch+1)),scores=probe_scores)
            c.require(visits == min(n, executed_batches*hp['batch_size']), 'FULL_FIT_OR_GATE_PREFIX_VISITS')
            profile.append(dict(epoch=epoch+1, tail_seconds=tail_seconds, batch_seconds=time.monotonic()-batch_started, batches=executed_batches))
            if enabled: diagnostic_log.checkpoint()
            c.write(out/('epoch_%02d.json' % (epoch+1)), dict(epoch=epoch+1, updates=count, bce_visits=visits, loss=loss_total,
                    bce_loss=bce_total, tail_loss=tail_total, loss_aggregation='sum(batch_loss*batch_rows/FIT_rows)',
                    tail=audit, tail_sample_count=sampled_count, sample_index_sha256=sampled_digest.hexdigest(),
                    tail_selection='epoch_start_fixed_not_SOPA', order_sha256=orders[-1]))
        c.require(count == epochs_run*executed_batches, 'UPDATE_COUNT')
        if not synthetic and runtime_batches is None: c.require(count == hp['updates_per_head'], 'FROZEN_UPDATE_COUNT')
        if enabled:
            diagnostic_log.checkpoint(complete=True)
    np.save(out/'objective_components.npy',component_losses,allow_pickle=False)
    c.write(out/'anchor_contract.json',dict(lambda_value=anchor_lambda,teacher_scale=teacher_scale,teacher_source='matched frozen REFIT782 FIT logits',component_columns=['BCE','TAIL','ANCHOR_UNSCALED','TOTAL'],diagnostic_bce_field='BCE_PLUS_ANCHOR',source_probe_selection='first 4096 FIT UIDs in lexical order; report only',probe_uid_sha256=c.uid_sha(rr[i]['uid'] for i in probe_indices)))
    c.save_arrays(out/'head.npz', **{name:v.detach().numpy() for name,v in model.state_dict().items()})
    c.write(out/'endpoint.json', dict(status='COMPLETE', arm=arm, seed=seed, dimension=dimension,
            epochs=epochs_run, runtime_gate_only=runtime_batches is not None, profile=profile, updates=count, rows=n, uid_sha256=c.uid_sha(r['uid'] for r in rr),
            weight_sha256=hashlib.sha256(w.tobytes()).hexdigest(), order_hashes=orders,
            initial_sha256=c.sha(out/'initial.npz'), head_sha256=c.sha(out/'head.npz'),
            normalizer_digest=c.digest([v.tolist() for v in norm]), design_digest=c.digest(design),
            synthetic_only=synthetic, reference_used=False, DEV_used=False,
            diagnostics_enabled=enabled, diagnostics_schema=d.SCHEMA,
            objective='BCE+TAIL+SOURCE_SCORE_ANCHOR', sampler_salt='query-tail-v1'))
    c.seal(out); c.verify(out)
    return model.eval().requires_grad_(False)


def load(folder, arm, seed, design):
    folder = Path(folder); c.verify(folder)
    r = c.read(folder/'endpoint.json')
    c.require(r['status'] == 'COMPLETE' and r['arm'] == arm and r['seed'] == seed and r['design_digest'] == c.digest(design), 'ENDPOINT_IDENTITY')
    model = k.classifier(seed, k.DIMENSIONS[arm])
    with np.load(folder/'head.npz', allow_pickle=False) as saved:
        c.require(set(saved.files) == set(model.state_dict()), 'HEAD_KEYS')
        model.load_state_dict({key:torch.from_numpy(saved[key].copy()) for key in saved.files})
    return model.eval().requires_grad_(False)
