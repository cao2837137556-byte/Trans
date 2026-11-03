"""Synthetic crash/restart tests. No frozen model, data or distance work."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

from hnr import encoding
from hnr.common import VERSION, digest, read, rows, sha, write, write_rows


class Crash(RuntimeError):
    pass


class Tensor:
    """The repeat contract used by physical_batch, without a model runtime."""
    def __init__(self, value):
        self.value = np.asarray(value, dtype=np.int64)
        self.shape = self.value.shape

    def repeat(self, repeats):
        return Tensor(np.tile(self.value, repeats))


class Runtime:
    def __init__(self):
        self.charges = []; self.updates = []

    def encoded(self, count):
        self.charges.append(count)

    def guard(self):
        pass

    def update(self, stage, **values):
        self.updates.append((stage, values))


def collate(examples):
    return {'x': Tensor([e['tokens'] for e in examples])}


def verify(examples, batch):
    if batch['x'].value.tolist() != [e['tokens'] for e in examples]:
        raise ValueError('BAD_MOCK_PACKING')


def tensor_hash(batch, index):
    return hashlib.sha256(batch['x'].value[index].tobytes()).hexdigest()


class ResumeChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.meta = [dict(uid=('%064x' % i), protocol=6 if i < 17 else 17) for i in range(36)]
        self.q = np.arange(36*14, dtype=np.float32).reshape(36, 14)
        self.examples = {i: dict(tokens=[i, i+1], dataset_burst_sizes=[1]) for i in range(36)}
        self.groups = {(17, 2, 1): list(reversed(range(17, 36))), (6, 2, 1): list(reversed(range(17)))}
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def forward(self, actual):
        x = actual['x'].value
        self.calls.append(x.copy())
        # Depend on physical batch size as well as each input. Batch reshaping
        # would change this result even when all logical inputs stayed equal.
        return (x[:, :1].astype(np.float32) + np.arange(768, dtype=np.float32)[None, :]/1024
                + np.float32(len(x)/128)).astype(np.float32)

    def run_batches(self, name='run', runtime=None, **kwargs):
        options = dict(collator=collate, verify_batch=verify, tensor_hash=tensor_hash,
                       forward=self.forward, encoder_identity={'model': 'frozen'},
                       bindings={'snapshot_sha256': 'a'*64})
        options.update(kwargs)
        runtime = runtime or Runtime()
        return encoding.encode_batches(self.meta, self.q, self.examples, self.groups,
                                       self.root/name, runtime, **options)

    def stop_at(self, stage, bid=0):
        def stop(actual_stage, actual_bid):
            if (actual_stage, actual_bid) == (stage, bid):
                raise Crash(stage)
        return stop

    def first_batch(self):
        with self.assertRaises(Crash):
            self.run_batches(crash_hook=self.stop_at('after_complete'))
        self.calls.clear()

    def test_exact_batches_singleton_and_complete_zero_forward_resume(self):
        runtime = Runtime()
        first, receipts, stats = self.run_batches(runtime=runtime)
        self.assertEqual([len(x) for x in self.calls], [16, 16, 16, 3])
        self.assertTrue(all(x.tobytes() == self.calls[1][0].tobytes() for x in self.calls[1]))
        self.assertEqual(runtime.charges, [16, 1, 16, 3])
        self.assertEqual(stats['new_forward_rows'], 36)
        self.assertEqual(stats['physical_positions'], 51)
        self.assertEqual([r['slot'] for r in receipts], list(range(36)))
        with np.load(self.root/'run/batches/000001.npz') as single:
            self.assertEqual(single['e3_actual'].shape, (16, 768))
            self.assertTrue(all(v.tobytes() == single['e3_actual'][0].tobytes() for v in single['e3_actual']))
        before = (self.root/'run/BATCH_LEDGER.jsonl').read_bytes()
        self.calls.clear(); runtime = Runtime()
        second, rr, resumed = self.run_batches(runtime=runtime, resume=True)
        self.assertEqual(first.tobytes(), second.tobytes()); self.assertEqual(receipts, rr)
        self.assertEqual(runtime.charges, []); self.assertEqual(self.calls, [])
        self.assertEqual(resumed['reused_rows'], 36); self.assertEqual(resumed['new_forward_rows'], 0)
        self.assertEqual(before, (self.root/'run/BATCH_LEDGER.jsonl').read_bytes())

    def test_each_recoverable_crash_matches_uninterrupted(self):
        expected, expected_receipts, _ = self.run_batches(name='expected')
        for stage, bid, expected_charge in [('after_attempt', 0, 36), ('after_receipt', 0, 20),
                                            ('after_complete', 0, 20), ('before_merge', None, 0)]:
            with self.subTest(stage=stage):
                name = stage
                with self.assertRaises(Crash):
                    self.run_batches(name=name, crash_hook=self.stop_at(stage, bid))
                before = (self.root/name/'BATCH_LEDGER.jsonl').read_bytes()
                runtime = Runtime(); self.calls.clear()
                actual, receipts, stats = self.run_batches(name=name, resume=True, runtime=runtime)
                self.assertEqual(actual.tobytes(), expected.tobytes()); self.assertEqual(receipts, expected_receipts)
                self.assertEqual(sum(runtime.charges), expected_charge)
                self.assertEqual(stats['new_forward_rows'], expected_charge)
                self.assertTrue((self.root/name/'BATCH_LEDGER.jsonl').read_bytes().startswith(before))
                self.assertEqual(stats['recovered_commits'], int(stage == 'after_receipt'))

    def test_orphan_npz_is_not_recomputed_or_overwritten(self):
        with self.assertRaises(Crash):
            self.run_batches(crash_hook=self.stop_at('after_npz'))
        evidence = (self.root/'run/batches/000000.npz').read_bytes(); self.calls.clear()
        runtime = Runtime()
        with self.assertRaisesRegex(ValueError, 'ORPHAN'):
            self.run_batches(resume=True, runtime=runtime)
        self.assertEqual(runtime.charges, []); self.assertEqual(self.calls, [])
        self.assertEqual(evidence, (self.root/'run/batches/000000.npz').read_bytes())

    def test_partial_temporary_write_retries_and_charges_attempt(self):
        def torn(stream, **arrays):
            stream.write(b'partial array'); raise Crash('temp')
        first = Runtime()
        with patch.object(encoding.np, 'savez', side_effect=torn), self.assertRaises(Crash):
            self.run_batches(runtime=first)
        partials = list((self.root/'run/batches').glob('*.tmp-*'))
        self.assertEqual(len(partials), 1); self.assertEqual(first.charges, [16])
        runtime = Runtime(); self.calls.clear()
        self.run_batches(resume=True, runtime=runtime)
        self.assertEqual(sum(runtime.charges), 36)
        self.assertEqual(partials[0].read_bytes(), b'partial array')

    def test_scientific_permission_error_is_fatal(self):
        original = encoding._durable_json
        def denied(path, value):
            if Path(path).name == '000000.json':
                raise PermissionError('checkpoint unavailable')
            return original(path, value)
        with patch.object(encoding, '_durable_json', side_effect=denied):
            with self.assertRaises(PermissionError):
                self.run_batches()
        self.assertFalse((self.root/'run/batches/000000.json').exists())

    def test_identity_and_input_changes_fail_before_any_new_forward(self):
        self.first_batch()
        mutations = [dict(encoder_identity={'model': 'changed'}), dict(bindings={'snapshot_sha256': 'b'*64})]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'PLAN_IDENTITY'):
                self.run_batches(resume=True, **mutation)
        for obj, key in [(self.examples[20], 'tokens'), (self.meta[20], 'uid')]:
            original = obj[key]; obj[key] = [999, 1] if key == 'tokens' else 'b'*64
            with self.assertRaisesRegex(ValueError, 'PLAN_IDENTITY'):
                self.run_batches(resume=True)
            obj[key] = original
        self.q[20, 0] += 1
        with self.assertRaisesRegex(ValueError, 'PLAN_IDENTITY'):
            self.run_batches(resume=True)
        self.assertEqual(self.calls, [])

    def test_actual_collator_input_mismatch_prevents_new_forwards(self):
        self.first_batch()
        def changed(examples):
            result = collate(examples); result['x'].value[:, 0] += 5; return result
        with self.assertRaisesRegex(ValueError, 'ACTUAL_INPUT_PIN'):
            self.run_batches(resume=True, collator=changed, verify_batch=lambda *a: None)
        self.assertEqual(self.calls, [])

    def test_sha_corruption_detected_before_missing_batch_forward(self):
        self.first_batch()
        with (self.root/'run/batches/000000.npz').open('ab') as stream:
            stream.write(b'corrupt')
        runtime = Runtime()
        with self.assertRaisesRegex(ValueError, 'RECEIPT_PIN'):
            self.run_batches(resume=True, runtime=runtime)
        self.assertEqual(runtime.charges, []); self.assertEqual(self.calls, [])

    def rewrite_checkpoint(self, mutate, bid=0):
        data = self.root/('run/batches/%06d.npz' % bid)
        receipt_path = data.with_suffix('.json')
        with np.load(data, allow_pickle=False) as saved:
            arrays = {k: saved[k].copy() for k in saved.files}
        mutate(arrays)
        with data.open('wb') as stream:
            np.savez(stream, **arrays)
        receipt = read(receipt_path); receipt['npz_sha256'] = sha(data)
        write(receipt_path, receipt)
        ledger = self.root/'run/BATCH_LEDGER.jsonl'
        events = list(rows(ledger))
        for event in events:
            if event['batch'] == bid and event['status'] == 'COMPLETE':
                event['receipt_sha256'] = sha(receipt_path)
        write_rows(ledger, events)

    def test_semantic_array_corruption_rejected_even_with_updated_file_pins(self):
        for field, change, error in [
            ('e3_actual', lambda x: x.astype(np.float64), 'E3_SCHEMA'),
            ('e3_actual', lambda x: x[:, :-1], 'E3_SCHEMA'),
            ('e3_actual', lambda x: np.full_like(x, np.nan), 'E3_SCHEMA'),
            ('slots', lambda x: np.zeros_like(x), 'SLOT_UID_ORDER'),
            ('uid', lambda x: x[::-1], 'SLOT_UID_ORDER'),
            ('q14', lambda x: x.astype(np.float64), 'Q14_PIN'),
            ('tensor_sha256', lambda x: x.astype('<U63'), 'TENSOR_ARRAY_SCHEMA'),
        ]:
            with self.subTest(field=field, error=error):
                self.temp.cleanup(); self.setUp(); self.first_batch()
                self.rewrite_checkpoint(lambda arrays: arrays.update({field: change(arrays[field])}))
                runtime = Runtime()
                with self.assertRaisesRegex(ValueError, error):
                    self.run_batches(resume=True, runtime=runtime)
                self.assertEqual(runtime.charges, []); self.assertEqual(self.calls, [])

    def test_singleton_output_inequality_is_rejected(self):
        original = self.forward
        def unequal(actual):
            value = original(actual)
            if len(self.calls) == 2:
                value[-1, 0] += 1
            return value
        with self.assertRaisesRegex(ValueError, 'CLONE_OUTPUT_EXACT'):
            self.run_batches(forward=unequal)
        self.assertTrue((self.root/'run/batches/000000.json').exists())
        self.assertFalse((self.root/'run/batches/000001.npz').exists())

    def test_singleton_input_inequality_is_rejected(self):
        class Unequal(Tensor):
            def repeat(self, repeats):
                result = super().repeat(repeats); result.value[-1, 0] += 1; return result
        with self.assertRaisesRegex(ValueError, 'CLONED_INPUT'):
            encoding.physical_batch({'x': Unequal([[1, 2]])}, 1, tensor_hash)

    def test_slot_coverage_and_legacy_outputs_fail_closed(self):
        for indices in [list(range(16)), list(range(17))+[0]]:
            self.groups[(6, 2, 1)] = indices
            with self.assertRaisesRegex(ValueError, 'SLOT_COVERAGE'):
                self.run_batches()
        self.groups[(6, 2, 1)] = list(reversed(range(17)))
        folder = self.root/'legacy'; folder.mkdir()
        write_rows(folder/'BATCH_LEDGER.jsonl', [dict(batch=0, status='ATTEMPT'), dict(batch=0, status='COMPLETE')])
        with self.assertRaisesRegex(ValueError, 'LEGACY_LEDGER_NOT_RECOVERABLE'):
            self.run_batches(name='legacy', resume=True)
        self.assertEqual(self.calls, [])

    def test_existing_output_requires_explicit_resume(self):
        self.first_batch()
        with self.assertRaisesRegex(ValueError, 'NO_OVERWRITE'):
            self.run_batches()

    def test_torn_ledger_is_preserved_and_rejected(self):
        self.first_batch()
        ledger = self.root/'run/BATCH_LEDGER.jsonl'
        with ledger.open('ab') as stream:
            stream.write(b'{"partial":')
        evidence = ledger.read_bytes()
        with self.assertRaises(ValueError):
            self.run_batches(resume=True)
        self.assertEqual(evidence, ledger.read_bytes()); self.assertEqual(self.calls, [])

    def test_all_commits_are_audited_before_forwarding_an_earlier_gap(self):
        self.run_batches(); self.calls.clear()
        # Model a missing first attempt and a corrupt later commit. Audit must
        # reject the later commit without forwarding the first batch.
        for suffix in ('.json', '.npz'):
            (self.root/('run/batches/000000'+suffix)).unlink()
        ledger = self.root/'run/BATCH_LEDGER.jsonl'
        write_rows(ledger, [e for e in rows(ledger) if e['batch'] != 0])
        with (self.root/'run/batches/000003.npz').open('ab') as stream:
            stream.write(b'bad')
        runtime = Runtime()
        with self.assertRaisesRegex(ValueError, 'RECEIPT_PIN'):
            self.run_batches(resume=True, runtime=runtime)
        self.assertEqual(runtime.charges, []); self.assertEqual(self.calls, [])

    def test_member_final_merge_interruption_and_completed_load_use_zero_forwards(self):
        prepared = self.root/'prepared'; prepared.mkdir()
        for row in self.meta:
            row.update(source_sha256='a'*64, use='REFERENCE' if int(row['uid'], 16) < 20 else 'QUERY',
                       history_role='HIST_REF' if int(row['uid'], 16) < 20 else 'HIST_DEV')
        spec = dict(status='SELECTED', device_scope=['fake'])
        for field, role in [('ref_rows', 'HIST_REF'), ('dev_rows', 'HIST_DEV')]:
            selected = [r for r in self.meta if r['history_role'] == role]
            path = prepared/(role+'.jsonl.gz'); write_rows(path, selected)
            spec[field] = dict(path=str(path), sha256=sha(path), uid_sha256=digest([r['uid'] for r in selected]))
        entries = [dict(uid=r['uid'], row=r, body=dict(flow=self.examples[i], provenance={}), q14=self.q[i].tolist())
                   for i, r in enumerate(self.meta)]
        write_rows(prepared/'selected_snapshots.jsonl.gz', entries)
        (prepared/'candidates.sqlite').write_bytes(b'fake read-only census')
        write(prepared/'LOGICAL_INPUT.json', dict(source_sha256='a'*64,
              source_kind='BYTE_PRESERVING_CHRONOLOGICAL_PCAPNG'))
        write(prepared/'PREPARE_RESULT.json', dict(version=VERSION, input_readout='RECENT_CURRENT_INCLUSIVE',
              status='PREPARED', source_sha256='a'*64, selection=spec,
              snapshots_sha256=sha(prepared/'selected_snapshots.jsonl.gz'),
              census_sha256=sha(prepared/'candidates.sqlite'), logical_input_sha256=sha(prepared/'LOGICAL_INPUT.json')))
        (prepared/'selection_replay').mkdir(); sentinel = prepared/'selection_replay/old_evidence.txt'
        sentinel.write_text('preserve')
        def descriptor(body, row):
            return self.q[int(row['uid'], 16)], None
        modules = {
            'constrained_onboarding_reference_v2': types.SimpleNamespace(reference_descriptor=descriptor,
                                                                       query_descriptor=descriptor),
            'continuous_input_v3': types.SimpleNamespace(VERSION='mock-input', verify_tokenized=lambda *a: None),
            'continuous_features_v3': types.SimpleNamespace(tokenize=lambda tokenizer, flow: flow,
                                                           verify_batch=verify, tensor_hash=tensor_hash)}
        encoder = (types.SimpleNamespace(core=types.SimpleNamespace(
            e3_forward_batches=lambda model, batches, device: self.forward(batches[0]))), None, None, None, collate)
        original = encoding._durable_file
        def interrupt(path, writer, **kw):
            if Path(path).name == 'queries.npz':
                raise Crash('final merge')
            return original(path, writer, **kw)
        kwargs = dict(encoder=encoder, encoder_identity={'model': 'mock-frozen'}, synthetic=True)
        with patch.dict(sys.modules, modules), patch('hnr.selection.select_candidates', return_value=spec):
            with patch.object(encoding, '_durable_file', side_effect=interrupt), self.assertRaises(Crash):
                encoding.encode_member(prepared, self.root/'member', {'old_rows': []}, Runtime(), **kwargs)
            self.assertTrue((self.root/'member/references.npz').exists())
            self.assertFalse((self.root/'member/ENCODE_RESULT.json').exists())
            self.calls.clear(); runtime = Runtime()
            result = encoding.encode_member(prepared, self.root/'member', {'old_rows': []}, runtime, resume=True, **kwargs)
            self.assertEqual(self.calls, []); self.assertEqual(runtime.charges, [])
            self.assertEqual(result['HIST_REF']['q14'].tobytes(), self.q[:20].tobytes())
            saved = read(self.root/'member/ENCODE_RESULT.json')
            self.assertEqual(saved['batch_counters']['reused_rows'], 36)
            before = {p.name: sha(p) for p in (self.root/'member').iterdir() if p.is_file()}
            again = encoding.encode_member(prepared, self.root/'member', {'old_rows': []}, Runtime(), resume=True, **kwargs)
            self.assertEqual(again['HIST_DEV']['e3'].tobytes(), result['HIST_DEV']['e3'].tobytes())
            self.assertEqual(before, {p.name: sha(p) for p in (self.root/'member').iterdir() if p.is_file()})
        self.assertEqual(sentinel.read_text(), 'preserve'); self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
