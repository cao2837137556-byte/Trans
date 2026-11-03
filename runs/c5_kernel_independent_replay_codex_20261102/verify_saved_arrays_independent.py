"""Second audit of persisted arrays only; no model, distance, or runner imports."""
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
C4 = ROOT / 'runs/history_sample_coverage_c4_batch_resume_v1_20261102'
AB = HERE / 'ab'
OUT = HERE / 'AB_SAVED_ARRAY_VERIFICATION.json'
HEADS = ('27', '127', '227', 'ensemble')
NAMES = ('1', '2', '3', '4', 'saturation')
PINS = {}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def pin(path):
    path = Path(path)
    PINS[str(path.relative_to(ROOT)).replace('\\', '/')] = sha(path)
    return path


def read(path):
    return json.loads(pin(path).read_text(encoding='utf-8-sig'))


FIELDS = ('uid', 'label', 'device', 'activity', 'annotation_id', 'capture_id',
          'session_id', 'component_id', 'label_metric_weight_denominator',
          'timestamp', 'frame')


def rows(path):
    with gzip.open(pin(path), 'rt', encoding='utf-8') as stream:
        return [{k: r[k] for k in FIELDS if k in r} for r in map(json.loads, stream)]


def load(path):
    with np.load(pin(path), allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


def independent_weights(rr, pool):
    w = np.zeros(len(rr), dtype=np.float64)
    for label in (0, 1):
        fields = (('device', 'component_id') if label == 0 else
                  ('device', 'annotation_id', 'component_id')) if pool == 'UNSW_DEV' else (
                  'device', 'activity', 'capture_id', 'session_id')
        indices = [i for i, r in enumerate(rr) if r['label'] == label]
        keys = {i: tuple(str(rr[i][k]) for k in fields) for i in indices}
        branches, leaves = defaultdict(set), Counter(keys.values())
        for key in keys.values():
            for depth, value in enumerate(key):
                branches[key[:depth]].add(value)
        for i, key in keys.items():
            divisor = leaves[key]
            for depth in range(len(fields)):
                divisor *= len(branches[key[:depth]])
            w[i] = 1 / divisor
    return w


def measure(ix, pred, w):
    count = len(ix)
    positives = int(pred[ix].sum())
    mass = math.fsum(w[ix])
    return dict(rows=count, positive=positives, negative=count-positives,
                rate=positives/count if count else None, weight_mass=mass,
                weighted_rate=math.fsum(w[ix][pred[ix]])/mass if mass else None)


def own_logits(raw, mapped, guard, scales, cuts):
    x = raw.copy()
    active = mapped > 0
    for j, scale in enumerate(scales):
        if scale > 0:
            x[active, j] = raw[active, j] - (.25 * scale) * mapped[active]
    x[guard] = raw[guard]
    ensemble = np.stack([x[:, j] for j in range(3)]).mean(0, dtype=np.float64)
    return x, np.column_stack((x > cuts['cuts'], ensemble > cuts['ensemble_cut']))


def mapped_support(s, name):
    if name == '1':
        return s.copy()
    out = np.zeros_like(s)
    active = s > 0
    out[active] = 1 if name == 'saturation' else 1 - (1-s[active]) ** int(name)
    return out


def audit_groups(rr, raw, pred, w, saved):
    failures, checked, details = [], 0, {}
    for kind, field, budget in (('device', 'device', 1.),
                                ('attack_type', 'activity', 5.),
                                ('annotation', 'annotation_id', 5.)):
        by = defaultdict(list)
        for i, row in enumerate(rr):
            by[str(row.get(field, 'NOT_AVAILABLE'))].append(i)
        saved_by = {str(g['group'][field]): g for g in saved['groups'][kind]}
        assert set(by) == set(saved_by)
        maximum, low_raw = 0., 0
        for name, ii in sorted(by.items()):
            aa = np.asarray([i for i in ii if rr[i]['label'] == 1], dtype=np.int64)
            base = measure(aa, raw, w)
            new = measure(aa, pred, w)
            sg = saved_by[name]
            assert base == sg['base']['attack'] and new == sg['corrected']['attack']
            if not len(aa):
                assert sg['attack_recall_loss_pp'] is None
                continue
            checked += 1
            withdrawn = aa[raw[aa] & ~pred[aa]]
            mass = math.fsum(w[aa])
            assert mass > 0
            loss = 100. * (math.fsum(w[withdrawn]) / mass)
            assert loss == sg['attack_recall_loss_pp']
            maximum = max(maximum, loss)
            if loss > budget + 1e-12:
                failures.append(kind + '_WITHDRAWAL_BUDGET:' + name)
            if base['weighted_rate'] < .99:
                low_raw += 1
                if len(withdrawn):
                    failures.append(kind + '_RAW_BELOW_99_REQUIRES_ZERO_WITHDRAWAL:' + name)
        details[kind] = dict(all_groups=len(by), attack_groups=sum(
            bool(saved_by[n]['base']['attack']['rows']) for n in by),
            max_cumulative_loss_pp=maximum, raw_below_99_groups=low_raw)
    expected = saved['protection']
    assert failures == expected['failures'] and expected['missing'] == []
    status = 'FAIL' if failures else 'PASS'
    assert status == expected['status']
    return dict(status=status, attack_group_checks=checked, groups=details)


def main():
    assert not OUT.exists(), 'AUDIT_EXISTS'
    result = read(AB / 'RESULT.json')
    spec = read(C4 / 'config/ASSETS.json')
    cuts = read(ROOT / spec['calibration']['cuts']['path'])
    scales = read(ROOT / spec['calibration']['scales']['path'])['scales']
    audit = dict(schema='C5_SAVED_ARRAY_SECOND_VERIFICATION_V1',
                 status='PASS', models_run=0, distance_pairs_computed=0,
                 AB_runner_executed=False, p_selected=False, pools={},
                 gate_checks={n: [] for n in NAMES})
    for pool in ('CIC_DEV', 'UNSW_DEV'):
        rr = rows(ROOT / spec['pools'][pool]['query']['rows']['path'])
        replay = load(AB / (pool + '_REPLAY.npz'))
        old = load(C4 / ('outputs/evaluation/ab/' + pool + '/DECISIONS.npz'))
        assert replay['candidate_names'].tolist() == list(NAMES)
        assert replay['uid'].tolist() == old['uid'].tolist() == [r['uid'] for r in rr]
        assert replay['decisions'][0].tobytes() == old['corrected'].tobytes()
        assert replay['kernel_support'][0].tobytes() == old['support'].tobytes()
        assert replay['guard'].tobytes() == old['guard'].tobytes()
        x, pred = own_logits(old['raw_logits'], old['support'], old['guard'], scales, cuts)
        assert x.tobytes() == old['corrected_logits'].tobytes()
        assert pred.tobytes() == old['corrected'].tobytes()
        full_weights = np.array([1/r['label_metric_weight_denominator'] for r in rr])
        assert full_weights.tobytes() == replay['full_weights'].tobytes()
        assert independent_weights(rr, pool).tobytes() == full_weights.tobytes()
        windows = {}
        for window in spec['pools'][pool]['windows']:
            end, frames = windows.setdefault(window['device'], (window['reference_end'], {}))
            assert end == window['reference_end']
            if 'frame_end' in window:
                frames[window['capture_id']] = window['frame_end']
        keep = []
        for i, row in enumerate(rr):
            end, frames = windows.get(row['device'], windows.get('*', (None, {})))
            assert end is not None
            if row['timestamp'] > end and row['frame'] > frames.get(row['capture_id'], -1):
                keep.append(i)
        assert np.asarray(keep, dtype=np.int64).tobytes() == replay['primary_indices'].tobytes()
        primary_rows = [rr[i] for i in keep]
        primary_weights = independent_weights(primary_rows, pool)
        assert primary_weights.tobytes() == replay['primary_weights'].tobytes()
        views = {'full': (np.arange(len(rr)), rr, full_weights),
                 'post_window_primary': (np.asarray(keep), primary_rows, primary_weights)}
        pa = dict(p1_decisions_support_guard_and_logits_byte_exact=True,
                  full_and_primary_population_weights_independently_exact=True,
                  counts={}, p3_devices={})
        for ci, name in enumerate(NAMES):
            saved = result['pools'][pool]['candidates'][name]
            assert mapped_support(old['support'], name).tobytes() == replay['kernel_support'][ci].tobytes()
            assert not np.any(~old['corrected'] & replay['decisions'][ci])
            pa['counts'][name] = {}
            for view, (ix, subset, w) in views.items():
                labels = np.asarray([r['label'] for r in subset])
                normal_ix, attack_ix = np.flatnonzero(labels == 0), np.flatnonzero(labels == 1)
                heads = {}
                for j, head in enumerate(HEADS):
                    pred = replay['decisions'][ci, ix, j]
                    raw = old['base'][ix, j]
                    sr = saved['views'][view]['reports'][head]
                    normal, attack = measure(normal_ix, pred, w), measure(attack_ix, pred, w)
                    assert normal == sr['corrected']['normal'] and attack == sr['corrected']['attack']
                    assert measure(normal_ix, raw, w) == sr['base']['normal']
                    assert measure(attack_ix, raw, w) == sr['base']['attack']
                    extra = int(np.sum(old['corrected'][ix, j][attack_ix] & ~pred[attack_ix]))
                    assert extra == sr['new_attack_misses_vs_C4']
                    gate = audit_groups(subset, raw, pred, w, sr)
                    audit['gate_checks'][name].append(dict(pool=pool, view=view, head=head, **gate))
                    heads[head] = dict(normal_rows=normal['rows'], fp=normal['positive'],
                        sample_fpr=normal['rate'], weighted_fpr=normal['weighted_rate'],
                        attack_rows=attack['rows'], fn=attack['negative'],
                        sample_recall=attack['rate'], weighted_recall=attack['weighted_rate'],
                        extra_fn_vs_C4=extra)
                    if name == '3' and view == 'post_window_primary' and head == 'ensemble':
                        for device in sorted({r['device'] for r in subset}):
                            di = np.array([i for i, r in enumerate(subset)
                                           if r['device'] == device and r['label'] == 0], dtype=np.int64)
                            pa['p3_devices'][device] = measure(di, pred, w)
                pa['counts'][name][view] = heads
        audit['pools'][pool] = pa
        print('VERIFIED', pool, flush=True)
    dev = load(C4 / 'outputs/evaluation/dev/DECISIONS.npz')
    dev_rows = rows(C4 / 'outputs/evaluation/dev/QUERIES.jsonl.gz')
    assert dev['uid'].tolist() == [r['uid'] for r in dev_rows]
    dev_counts = {}
    for name in NAMES:
        mapped = mapped_support(dev['support'], name)
        x, pred = own_logits(dev['raw_logits'], mapped, dev['guard'], scales, cuts)
        if name == '1':
            assert x.tobytes() == dev['corrected_logits'].tobytes()
            assert pred.tobytes() == dev['corrected'].tobytes()
        count = dict(zip(HEADS, pred.sum(0).astype(int).tolist()))
        assert count == result['dev']['candidates'][name]['fp_by_head']
        for device in sorted({r['device'] for r in dev_rows}):
            ix = np.array([r['device'] == device for r in dev_rows])
            assert dict(zip(HEADS, pred[ix].sum(0).astype(int).tolist())) == (
                result['dev']['candidates'][name]['devices'][device]['fp_by_head'])
        dev_counts[name] = count
    audit['HIST_DEV_counts_by_head'] = dev_counts
    for name, gates in audit['gate_checks'].items():
        assert len(gates) == 16 and all(g['status'] == 'PASS' for g in gates)
        assert result['summary'][name]['gate_count'] == 16
        assert result['summary'][name]['gate_passes'] == 16
    audit['all_80_AB_protection_reports_independently_verified'] = True
    audit['limitations'] = ['AB saved-array gates are distinct from source CAL zero-withdrawal gates',
        'This audit does not select p or resolve the incomplete 5% stopping rule']
    for rel, digest in PINS.items():
        assert sha(ROOT / rel) == digest, 'INPUT_CHANGED:' + rel
    audit['input_sha256'] = PINS
    with OUT.open('x', encoding='utf-8') as f:
        json.dump(audit, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n')
    digest = sha(OUT)
    with OUT.with_suffix('.json.sha256').open('x', encoding='ascii') as f:
        f.write(digest + '  ' + OUT.name + '\n')
    print('AB_SAVED_ARRAY_VERIFICATION_PASS', digest, flush=True)


if __name__ == '__main__':
    main()
