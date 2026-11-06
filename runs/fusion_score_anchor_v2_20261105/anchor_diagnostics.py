"""Read-only loss/gradient/Adam probes for the declared training graph and step."""
import math
from contextlib import contextmanager
import json
import os
from pathlib import Path
import numpy as np
import torch
import continuous_common_v3 as c

SCHEMA = 'source-score-anchor-diagnostics-v1-20261105'
BACKWARD_SANITY_RTOL = 1e-4
BACKWARD_SANITY_ATOL = 1e-30
BACKWARD_SANITY_CRITERION = 'l2_difference <= 1e-4*(bce_grad_norm+tail_grad_norm)+1e-30'


class DiagnosticLog:
    """Bounded append-only probes and a contiguous per-update binary loss array."""
    def __init__(self, folder, updates, nbatches, epochs, probes):
        self.folder = Path(folder)
        self.losses = np.lib.format.open_memmap(self.folder/'batch_losses.npy', mode='w+',
                                               dtype='<f8', shape=(updates, 3))
        self.probe_stream = (self.folder/'fixed_probes.jsonl').open('x', encoding='utf-8', newline='\n')
        self.rows = 0
        self.completed_optimizer_updates = 0
        self.probes_written = 0
        self.observed_dtypes = [set(), set(), set()]
        self.meta = dict(bce_field_semantics='BCE_PLUS_ANCHOR; uncombined components saved in objective_components.npy', schema=SCHEMA, status='RUNNING', columns=['bce_plus_anchor', 'tail', 'total'],
                         shape=[updates, 3], storage_dtype='float64', updates_per_epoch=nbatches,
                         expected_probe_rows=epochs*len(probes),
                         epochs=epochs, index='row=prospective_global_update-1; batch and epoch are 1-based',
                         loss_timing='pre_step',
                         failure_row_rule='written_rows counts observed loss rows; the final row may not have completed its update if FAILED.',
                         probe_batches=probes, gradient_timing='pre_step', adam_state_timing='post_step',
                         model_logits_dtype='float32', elementwise_bce_dtype='float32',
                         elementwise_tail_dtype='float32', class_weights_dtype='float64',
                         loss_dtype_note='Storage does not upgrade float32 forward operations; weighted reductions use float64.',
                         side_effects='No RNG draws, model forwards, optimizer updates, or parameter/state writes added.')
        self.checkpoint()

    def loss(self, components):
        if self.rows >= len(self.losses):
            raise RuntimeError('LOSS_LOG_OVERFLOW')
        self.losses[self.rows] = [float(v.detach()) for v in components]
        for seen, component in zip(self.observed_dtypes, components):
            seen.add(str(component.dtype).split('.')[-1])
        self.rows += 1

    def probe(self, value):
        json.dump(dict(schema=SCHEMA, **value), self.probe_stream,
                  sort_keys=True, separators=(',', ':'), allow_nan=False)
        self.probe_stream.write('\n')
        self.probe_stream.flush()
        self.probes_written += 1

    def step_completed(self):
        # Count the actual original optimizer.step, including a later post-step probe failure.
        self.completed_optimizer_updates += 1
        if self.completed_optimizer_updates > self.rows:
            raise RuntimeError('DIAGNOSTIC_STEP_WITHOUT_LOSS_ROW')

    def checkpoint(self, complete=False, failure=None):
        # Validate first: incomplete arrays/probes must never leave a COMPLETE marker.
        if complete:
            if self.rows != len(self.losses) or self.completed_optimizer_updates != self.rows:
                raise RuntimeError('LOSS_LOG_INCOMPLETE')
            if self.probes_written != self.meta['expected_probe_rows']:
                raise RuntimeError('PROBE_LOG_INCOMPLETE')
        self.losses.flush()
        self.probe_stream.flush()
        os.fsync(self.probe_stream.fileno())
        value = dict(self.meta, status='FAILED' if failure is not None else 'COMPLETE' if complete else 'RUNNING', written_rows=self.rows,
                     completed_optimizer_updates=self.completed_optimizer_updates,
                     probe_rows=self.probes_written,
                     observed_component_dtypes={key:sorted(seen) for key, seen in
                                               zip(('bce','tail','total'), self.observed_dtypes)})
        if failure is not None:
            value['first_failure'] = dict(type=type(failure).__name__, message=str(failure))
        c.write(self.folder/'diagnostics_schema.json', value, replace=True)

    def close(self):
        # Try each resource, including mmap closure when an earlier flush/close fails.
        errors = []
        for action in (self.probe_stream.close, self.losses.flush, self.losses._mmap.close):
            try:
                action()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise errors[0]


@contextmanager
def diagnostic_context(log):
    """Flush partial evidence and close on failure, without replacing the first exception."""
    original = None
    try:
        yield log
    except BaseException as error:
        original = error
        if log is not None:
            try:
                log.checkpoint(failure=error)
            except BaseException:
                pass  # Runner's original failure is authoritative even if storage failed too.
        raise
    finally:
        if log is not None:
            try:
                log.close()
            except BaseException:
                if original is None:
                    raise


def probe_batches(nbatches, synthetic=False):
    if synthetic:
        return sorted({1, math.ceil(nbatches/2), nbatches})
    return [1, 1207, 2414]


def _gradients(component, parameters):
    if not component.requires_grad:
        return [torch.zeros_like(p) for p in parameters]
    values = torch.autograd.grad(component, parameters, retain_graph=True,
                                 create_graph=False, allow_unused=True)
    return [torch.zeros_like(p) if g is None else g.detach() for p, g in zip(parameters, values)]


def _flat(values):
    return torch.cat([v.detach().reshape(-1).to(dtype=torch.float64) for v in values])


def gradient_probe(bce, tail, parameters, attack_count, tail_enabled):
    """Keep autograd.grad out of .grad; caller performs the original total backward."""
    parameters = tuple(parameters)
    if any(p.grad is not None for p in parameters):
        raise RuntimeError('PROBE_EXPECTS_ZERO_GRAD')
    b = _gradients(bce, parameters)
    t = _gradients(tail, parameters)
    if any(p.grad is not None for p in parameters):
        raise RuntimeError('PROBE_WROTE_GRAD')
    if any(not bool(torch.isfinite(g).all()) for g in (*b, *t)):
        raise RuntimeError('PROBE_NONFINITE_COMPONENT_GRAD')
    bb, tt = _flat(b), _flat(t)
    bn, tn = float(torch.linalg.vector_norm(bb)), float(torch.linalg.vector_norm(tt))
    if not math.isfinite(bn) or not math.isfinite(tn):
        raise RuntimeError('PROBE_NONFINITE_COMPONENT_NORM')
    if not tail_enabled:
        status = 'TAIL_DISABLED'
    elif attack_count == 0:
        status = 'NO_ATTACK'
    elif bn == 0 and tn == 0:
        status = 'BOTH_ZERO'
    elif bn == 0:
        status = 'ZERO_BCE_GRAD'
    else:
        status = 'VALID'
    ratio = tn/bn if status == 'VALID' else None
    cosine = float(torch.dot(bb, tt)/(bn*tn)) if status == 'VALID' and tn > 0 else None
    if cosine is not None:
        cosine = max(-1., min(1., cosine))
    values = dict(status=status, attack_count=int(attack_count), parameter_coordinates=len(bb),
                  bce_grad_norm=bn, tail_grad_norm=tn, gradient_ratio=ratio,
                  gradient_cosine=cosine, cosine_status='DEFINED' if cosine is not None else
                  ('ZERO_TAIL_GRAD' if status == 'VALID' and tn == 0 else status),
                  gradient_timing='pre_step', weight_decay_included=False,
                  norm_accumulation_dtype='float64', autograd_grad_writes_grad=False)
    return values, tuple(x+y for x, y in zip(b, t))


def backward_sanity(expected, parameters, gradient):
    """Gate a float64 residual using norms from the same pre-step component probe.

    Float32 component gradients can cancel coordinatewise, making elementwise
    allclose too strict for two backwards versus one total backward. Its result
    remains observational; the stop gate scales with both component L2 norms.
    No component gradient is recomputed, and the real backward is not replaced.
    """
    parameters = tuple(parameters)
    expected = tuple(expected)
    if not parameters or len(expected) != len(parameters):
        raise RuntimeError('SANITY_PARAMETER_COUNT_MISMATCH')
    actual = tuple(p.grad for p in parameters)
    if any(v is None for v in actual):
        raise RuntimeError('SANITY_MISSING_BACKWARD_GRAD')
    if any(not torch.is_tensor(e) or e.shape != p.shape or a.shape != p.shape
           for e, a, p in zip(expected, actual, parameters)):
        raise RuntimeError('SANITY_GRAD_SHAPE_MISMATCH')
    if any(not bool(torch.isfinite(v).all()) for v in (*expected, *actual)):
        raise RuntimeError('SANITY_NONFINITE_GRAD')
    try:
        bn = float(gradient['bce_grad_norm'])
        tn = float(gradient['tail_grad_norm'])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise RuntimeError('SANITY_INVALID_COMPONENT_NORMS') from error
    scale = bn+tn
    if not all(math.isfinite(v) and v >= 0 for v in (bn, tn, scale)):
        raise RuntimeError('SANITY_INVALID_COMPONENT_NORMS')
    e, a = _flat(expected), _flat(actual)
    delta = a-e
    absolute = float(torch.linalg.vector_norm(delta))
    norm = float(torch.linalg.vector_norm(a))
    if not math.isfinite(absolute) or not math.isfinite(norm):
        raise RuntimeError('SANITY_NONFINITE_GRAD_NORM')
    threshold = BACKWARD_SANITY_RTOL*scale+BACKWARD_SANITY_ATOL
    elementwise = all(torch.allclose(x, y, rtol=1e-5, atol=1e-7) for x, y in zip(expected, actual))
    if absolute > threshold:
        raise RuntimeError('COMPONENT_SUM_BACKWARD_MISMATCH: l2_difference=%r l2_threshold=%r component_norm_scale=%r'
                           % (absolute, threshold, scale))
    return dict(allclose=elementwise, rtol=1e-5, atol=1e-7, allclose_is_stop_gate=False,
                criterion=BACKWARD_SANITY_CRITERION, norm_relative_tolerance=BACKWARD_SANITY_RTOL,
                absolute_l2_floor=BACKWARD_SANITY_ATOL, component_norm_scale=scale,
                l2_threshold=threshold, l2_pass=True,
                max_abs_difference=float(delta.abs().max()), l2_difference=absolute,
                relative_l2_difference=absolute/norm if norm > 0 else None,
                component_relative_l2_difference=absolute/scale if scale > 0 else None,
                reference_grad_norm=norm, status='VALID' if norm > 0 else 'ZERO_TOTAL_GRAD')


def _moment_summary(entries):
    """One coordinate has its own parameter-group eps and actual per-parameter step."""
    coordinates = sum(v.numel() for v, _, _, _, _ in entries)
    if not coordinates:
        return dict(status='NOT_APPLICABLE', coordinates=0)
    vv = torch.cat([v.reshape(-1).double() for v, _, _, _, _ in entries])
    active = torch.cat([m.reshape(-1).ne(0) for _, m, _, _, _ in entries])
    low = torch.cat([v.reshape(-1).double().lt(eps) for v, _, eps, _, _ in entries])
    steps = [step for _, _, _, _, step in entries]
    eps_values = sorted({eps for _, _, eps, _, _ in entries})
    beta2_values = sorted({beta2 for _, _, _, beta2, _ in entries})
    active_count = int(active.sum())
    active_low = int((active & low).sum())
    return dict(status='VALID', coordinates=coordinates, step_min=min(steps), step_max=max(steps),
                eps_values=eps_values, beta2_values=beta2_values,
                sqrt_vhat_median=float(torch.quantile(vv, .5)),
                sqrt_vhat_p90=float(torch.quantile(vv, .9)), sqrt_vhat_max=float(vv.max()),
                below_eps_count=int(low.sum()), below_eps_fraction=float(low.double().mean()),
                zero_second_moment_count=int(vv.eq(0).sum()),
                active_first_moment_count=active_count,
                active_first_moment_below_eps_count=active_low,
                active_first_moment_below_eps_fraction=active_low/active_count if active_count else None)


def adam_probe(model, optimizer):
    """Read the just-completed step; no synthetic zeros before state initialization."""
    by_parameter = {id(p):(group['betas'][1], group['eps'])
                    for group in optimizer.param_groups for p in group['params']}
    groups = dict(all_parameters=[], first_layer=[], output_layer=[], query14_columns=[], context8_columns=[])
    for name, parameter in model.named_parameters():
        beta2, eps = by_parameter[id(parameter)]
        state = optimizer.state.get(parameter, {})
        if not all(key in state for key in ('step', 'exp_avg_sq', 'exp_avg')):
            raise RuntimeError('ADAM_STATE_MISSING_POST_STEP')
        raw_step = state['step']
        step = float(raw_step.item()) if torch.is_tensor(raw_step) else float(raw_step)
        if not step.is_integer() or step < 1:
            raise RuntimeError('ADAM_STEP_INVALID')
        step = int(step)
        v = state['exp_avg_sq'].detach().double()
        m = state['exp_avg'].detach()
        if not bool(torch.isfinite(v).all()) or not bool((v >= 0).all()):
            raise RuntimeError('ADAM_SECOND_MOMENT_INVALID')
        # Promote stored state to float64 for the summary only, not for optimizer arithmetic.
        sqrt_vhat = torch.sqrt(v/(1-beta2**step))
        entry = (sqrt_vhat, m, float(eps), float(beta2), step)
        groups['all_parameters'].append(entry)
        if name.startswith('0.'):
            groups['first_layer'].append(entry)
        elif name.startswith('2.'):
            groups['output_layer'].append(entry)
        if name == '0.weight' and parameter.shape[1] in (782, 790):
            groups['query14_columns'].append((sqrt_vhat[:, 768:782], m[:, 768:782],
                                              float(eps), float(beta2), step))
        if name == '0.weight' and parameter.shape[1] in (8, 790):
            start = 0 if parameter.shape[1] == 8 else 782
            groups['context8_columns'].append((sqrt_vhat[:, start:], m[:, start:], float(eps), float(beta2), step))
    return dict(adam_state_timing='post_step', correction='exp_avg_sq/(1-beta2**actual_parameter_step)',
                summary_dtype='float64', state_dtype=str(next(model.parameters()).dtype).split('.')[-1],
                groups={name:_moment_summary(entries) for name, entries in groups.items()})
