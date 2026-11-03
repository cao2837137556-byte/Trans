"""Generated contract cases only; never inspect real numerical inputs."""
import copy
import gzip
import json
import tempfile
import unittest
import os
import sys
import struct
import zipfile
from pathlib import Path
from unittest.mock import patch

import issue27frontend_inheritance_outer_support_v1 as s
import issue27frontend_inheritance_outer_metadata_v1 as m


def context_json():
    return {'context_key': 'member\x1f' + 'a' * 64 + '\x1f0', 'source_group': 'normal_scanning1.pcap',
        'split': 'internal_val', 'signatures': ['DO_NOT_DECODE_FEATURE'], 'targets': [{
            'uid': 'u', 'event_index': 0, 'owner': 'A', 'label': 1, 'teacher_kind': 'attack_hard',
            'role': 'fit', 'source_group': 'normal_scanning1.pcap', 'device_family': 'ton-iot-external',
            'attack_family': 'ToN-reconnaissance_scan', 'timestamp_epoch': float('nan')}]}


def contexts():
    result = []
    specs = [('A', 1, 'attack_hard', 'A1C', 'attack'), ('A', 0, 'benign_normal', 'A0C', 'normal'),
             ('A', 0, 'benign_hard', 'A0W', 'normal'),
             ('B', 0, 'none', 'B0N', 'iotsim-combined-cycle'),
             ('B', 0, 'none', 'B0N', 'iotsim-domotic-monitor')]
    for i, (owner, label, teacher, cat, family) in enumerate(specs):
        t = {'uid': str(i), 'event': 0, 'position': i, 'owner': owner, 'label': label,
             'teacher_kind': teacher, 'category': cat, 'device_family': family, 'attack_family': 'a' if label else 'benign',
             'source_group': 'source' + str(i), 'tier': 'H1', 'protected': cat in ('A1C', 'A0C')}
        result.append({'key': str(i), 'source': t['source_group'], 'split': 'internal_val',
                       'member': 'member', 'length': 1, 'targets': [t]})
    return result


class MetadataTests(unittest.TestCase):
    def test_integral_csv_position_without_rounding(self):
        self.assertEqual(m.ordinal('42.0'), 42)
        for value in ('42.5', '-1', 'NaN', 'inf', '1e3'):
            with self.assertRaises(s.Stop): m.ordinal(value)

    def test_no_signature_or_timestamp_decode(self):
        raw = json.dumps(context_json())
        original = json.loads
        def guard(value, *args, **kwargs):
            if 'DO_NOT_DECODE_FEATURE' in value or value == 'NaN':
                raise AssertionError('forbidden value decoded')
            return original(value, *args, **kwargs)
        with patch.object(m.json, 'loads', side_effect=guard):
            c = m.project_context(raw, {})
        self.assertNotIn('signatures', c)
        self.assertNotIn('timestamp_epoch', c['targets'][0])

    def test_train_signatures_never_decoded_even_real_projection(self):
        c = context_json(); c['split'] = 'train'; c['source_group'] = 'train_source'
        self.assertNotIn('signatures', m.project_context(json.dumps(c), {}, True))

    def test_selected_signature_decode_explicit(self):
        self.assertEqual(m.project_context(json.dumps(context_json()), {}, True)['signatures'], ['DO_NOT_DECODE_FEATURE'])

    def test_duplicate_key_rejected(self):
        with self.assertRaises(s.Stop): m.spans('{"x":1,"x":2}')

    def test_trailing_json_rejected(self):
        with self.assertRaises(s.Stop): m.spans('{"x":1} []')

    def test_malformed_array_rejected(self):
        with self.assertRaises(s.Stop): m.spans('[1,]', False)

    def test_context_split_drift(self):
        c = context_json(); c['split'] = 'select'
        with self.assertRaises(s.Stop): m.project_context(json.dumps(c), {})

    def test_csv_unselected_payload_not_retained(self):
        audit = {}
        rows = m.selected_csv(b'uid,phase,score\na,fit,secret\nb,select,forbidden\n',
                              lambda r: r['uid'] == 'a', ('uid', 'phase'), audit)
        self.assertEqual(rows, [{'uid': 'a', 'phase': 'fit'}])
        self.assertEqual(audit['unselected_payload_retained'], 0)

    def test_duplicate_corpus_context(self):
        raw = (json.dumps(context_json()) + '\n') * 2
        with self.assertRaises(s.Stop): m.corpus(gzip.compress(raw.encode()), {})


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.c = contexts(); self.p = {str(i): (1.0 if i == 0 else -1.0) for i in range(5)}

    def test_complete_protection_and_two_group_utility(self):
        result, rows = s.measurements(self.c, self.p, False)
        self.assertEqual(result['A_retention'], 'COMPLETE_ON_THIS_POOL')
        self.assertEqual(result['B_utility'], 'POSITIVE_IN_BOTH_REPRESENTED_GROUPS')
        self.assertFalse(result['F5_eligible'])
        self.assertEqual(result['A_negative_flip_rate']['denominator'], 3)
        self.assertEqual(result['A_conditional_loss']['denominator'], 2)

    def test_attack_regression_not_offset_by_B(self):
        self.p['0'] = -1.0
        result, _ = s.measurements(self.c, self.p, False)
        self.assertEqual(result['A_retention'], 'REGRESSION_ON_THIS_POOL')
        self.assertEqual(result['B_totals']['normal_targets'], 2)

    def test_zero_tie_hard_benign_regression(self):
        self.p['1'] = 0.0
        result, _ = s.measurements(self.c, self.p, False)
        self.assertEqual(result['categories']['A0C']['errors'], ['1'])

    def test_zero_tie_attack_correct(self):
        self.p['0'] = 0.0
        result, _ = s.measurements(self.c, self.p, False)
        self.assertEqual(result['categories']['A1C']['errors'], [])

    def test_one_B_group_is_partial(self):
        self.p['3'] = 1.0
        self.assertEqual(s.measurements(self.c, self.p, False)[0]['B_utility'], 'PARTIAL')

    def test_zero_B_gain(self):
        self.p['3'] = self.p['4'] = 1.0
        self.assertEqual(s.measurements(self.c, self.p, False)[0]['B_utility'], 'ZERO')

    def test_partial_context_not_released(self):
        t = copy.deepcopy(self.c[3]['targets'][0]); t['uid'] = '5'; t['event'] = 1
        self.c[3]['targets'].append(t); self.c[3]['length'] = 2; self.p['5'] = 1.0
        group = s.measurements(self.c, self.p, False)[0]['B_groups']['iotsim-combined-cycle']
        self.assertEqual(group['normal_targets'], 1)
        self.assertEqual(group['all_B_benign_normal_contexts'], 0)

    def test_missing_prediction(self):
        del self.p['0']
        with self.assertRaises(s.Stop): s.measurements(self.c, self.p, False)

    def test_nonfinite_prediction(self):
        for bad in (float('inf'), float('nan'), -float('inf')):
            self.p['0'] = bad
            with self.assertRaises(s.Stop): s.measurements(self.c, self.p, False)

    def test_wrong_real_denominator(self):
        with self.assertRaises(s.Stop): s.measurements(self.c, self.p)


def signature(frame='100'):
    return '\x1f'.join(['H1', 'A_TO_B', 'encap:1', '2048', '4', '6', 'TCP', 'true',
        'frame.encap_type|ip.dst|ip.proto|ip.src|tcp.dstport|tcp.srcport',
        '64-127', '(1e-3,1e-2]', 'false', 'NONE', 'NONE', 'false',
        'FRAME_LEN=' + frame, 'DELTA_LOG2_US=12', 'TRANSPORT_LEN=60', 'TCP_FLAGS=24'])


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import issue27frontend_inheritance_outer_runner_v1 as runner
        cls.r = runner

    def setUp(self):
        self.c = contexts()[:1]
        self.l1 = signature(); self.l0 = '\x1f'.join(self.l1.split('\x1f')[:15])
        self.rows = [{'uid': '0', 'scope': 'outer_internal_val', 'source_group': self.c[0]['source'],
            'context_key': '0', 'event_index': 0, 'l0_signatures': [self.l0], 'l1_signatures': [self.l1]}]

    def test_generated_L1_to_float32_payload(self):
        loaded, data, receipts = self.r.merge_semantics(self.c, self.rows, {'0': [self.l0]})
        self.assertEqual(len(data), 524)
        self.assertEqual(tuple(loaded[0]['x'].shape), (1, 131))
        self.assertEqual(receipts[0]['uid'], '0')

    def test_L0_cannot_be_used_as_L1(self):
        self.rows[0]['l1_signatures'] = [self.l0]
        with self.assertRaises(self.r.f4.F4Failure): self.r.merge_semantics(self.c, self.rows, {'0': [self.l0]})

    def test_mismatched_old_prefix_rejected(self):
        with self.assertRaises(s.Stop): self.r.merge_semantics(self.c, self.rows, {'0': ['wrong']})

    def test_duplicate_semantic_UID_rejected(self):
        with self.assertRaises(s.Stop): self.r.merge_semantics(self.c, self.rows * 2, {'0': [self.l0]})

    def test_wrong_context_rejected(self):
        self.rows[0]['context_key'] = 'bad'
        with self.assertRaises(s.Stop): self.r.merge_semantics(self.c, self.rows, {'0': [self.l0]})

    def test_target_event_shift_rejected(self):
        self.rows[0]['event_index'] = 1
        with self.assertRaises(s.Stop): self.r.merge_semantics(self.c, self.rows, {'0': [self.l0]})

    def test_generated_full_context_forward_no_optimizer(self):
        import torch
        c = contexts()[:1]; c[0]['length'] = 2; c[0]['targets'][0]['event'] = 1
        c[0]['x'] = torch.zeros((2, 131), dtype=torch.float32)
        class Model:
            def eval(self): return self
            def __call__(self, xs, keys):
                assert xs[0].shape[0] == 2
                return [torch.tensor([-2.0, 0.0])], None, None
        limits = {'wall_seconds': 10, 'memory_bytes': 10**9, 'output_bytes': 10**6, 'reserve_bytes': 1000,
                  'passes': 1, 'batches': 1, 'contexts': 1, 'targets': 1, 'events': 2, 'padded_slots': 2}
        budget = s.base.Budget(caps=limits, memory=lambda: 0)
        with patch.object(torch.optim, 'Adam', side_effect=AssertionError('optimizer')):
            result = self.r.canonical_pass(Model(), c, budget)
        self.assertEqual(result, {'0': 0.0})
        self.assertEqual(budget.counts['events'], 2)

    def test_real_student_synthetic_state_immutable(self):
        import torch
        model = self.r.f5.Student()
        before = self.r.f5.tensor_hash(model.state_dict())
        model.eval()
        with torch.no_grad(): model([torch.zeros(2, 131)], ['generated-context'])
        self.assertEqual(before, self.r.f5.tensor_hash(model.state_dict()))

    def test_synthetic_head_assembly_preserves_non_head(self):
        import torch
        state = self.r.f5.Student().state_dict()
        head = bytes(260)
        pins = {'terminal_state_tensor_sha256': self.r.f5.tensor_hash(state),
                'non_head_state_tensor_sha256': self.r.n3.non_head_hash(state), 'head_float32_le_sha256': s.digest(head)}
        limits = {'wall_seconds': 10, 'memory_bytes': 10**9, 'output_bytes': 10**6, 'reserve_bytes': 1000,
                  'head_decodes': 1, 'assemblies': 1}
        budget = s.base.Budget(caps=limits, memory=lambda: 0)
        model, identity = self.r.n3.assemble(state, head, pins, budget)
        self.assertEqual(self.r.n3.non_head_hash(model.state_dict()), pins['non_head_state_tensor_sha256'])
        self.assertTrue(torch.equal(model.head_output.weight, torch.zeros(1, 64)))

    def test_wrong_head_bytes_rejected_before_installation(self):
        state = self.r.f5.Student().state_dict()
        pins = {'terminal_state_tensor_sha256': self.r.f5.tensor_hash(state),
                'non_head_state_tensor_sha256': self.r.n3.non_head_hash(state), 'head_float32_le_sha256': s.digest(bytes(260))}
        with self.assertRaises(s.Stop): self.r.n3.assemble(state, bytes(259) + b'x', pins, None)

    def test_checkpoint_projection_never_indexes_ledger(self):
        class Poison:
            def __getitem__(self, key): raise AssertionError('forbidden ledger access')
        container = {'model': 'synthetic', 'identities': {}, 'optimizer': Poison(), 'RNG': Poison(),
            'progress': {'epoch': 21, 'cursor': 0, 'order': [], 'steps': 3120, 'stop_reached': True,
                         'selection': {'best_epoch': None, 'last_epoch': 20}, 'epoch_ledger': Poison()}}
        audit = {}
        model, _ = self.r.n3.project_checkpoint(container, {}, audit)
        self.assertEqual(model, 'synthetic')
        self.assertEqual(audit['checkpoint_projection']['ledger_values_indexed'], 0)

    def test_train_forward_rejected_before_model_call(self):
        import torch
        c = contexts()[:1]; c[0]['split'] = 'train'; c[0]['x'] = torch.zeros(1, 131)
        with self.assertRaises(s.Stop): self.r.canonical_pass(None, c, None)

    def test_decoder_packet_limit_and_autoreset_command(self):
        command = self.r.f3.tshark_command(Path('synthetic.exe'), 'synthetic.pcap', 3, ['frame.number'])
        self.assertEqual(command[command.index('-c')+1], '3')
        self.assertEqual(command[command.index('-M')+1], '100000')
        self.assertEqual(self.r.f3.normalize_reset_frame_number('1', 100000), '100001')


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import issue27frontend_inheritance_outer_control_v1 as controller
        cls.ctrl = controller

    def test_not_started(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.ctrl.status(Path(d)/'absent')['status'], 'NOT_STARTED')

    def test_seal_tamper_detected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            s.atomic_json(path/'supervisor_terminal.json', {'verdict': {'status': 'INPUT_OR_EXECUTION_STOP'}})
            s.seal(path)
            self.assertTrue(self.ctrl.status(path)['final'])
            (path/'extra').write_text('tamper')
            self.assertFalse(self.ctrl.status(path)['final'])

    def test_incomplete_worker_not_final(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            s.atomic_json(path/'attempt.json', {'controller_pid': os.getpid()})
            s.atomic_json(path/'worker_terminal.json', {'verdict': {'status': 'OUTER_COMPARISON_COMPLETE'}})
            state = self.ctrl.status(path)
            self.assertFalse(state['final']); self.assertEqual(state['status'], 'SEALING')

    def test_dead_controller_detected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d); s.atomic_json(path/'attempt.json', {'controller_pid': 99999999})
            self.assertEqual(self.ctrl.status(path)['status'], 'INTERRUPTED_DO_NOT_RESTART')

    def test_action_overrun_before_output_validation(self):
        receipt = {'verdict': {'status': 'OUTER_COMPARISON_COMPLETE', 'complete': True,
                   'targets': 4400, 'contexts': 3582, **s.CLAIMS}, 'resource': {'counts': {'passes': 2}}}
        with self.assertRaises(s.Stop): self.ctrl.validate_worker(receipt, Path('not-read'), {'expected_actions': {'passes': 1}})

    def test_stop_is_never_scientific_success(self):
        verdict = self.ctrl.validate_worker({'verdict': {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': 'synthetic'}}, Path('not-read'), {})
        self.assertEqual(verdict['status'], 'INPUT_OR_EXECUTION_STOP')
        self.assertFalse(verdict['F5_eligible'])

    def test_existing_attempt_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileExistsError): self.ctrl.supervise([], Path(d), {})

    @unittest.skipUnless(os.name == 'nt', 'Windows supervisor contract')
    def test_generated_worker_stop_is_sealed(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)/'attempt'
            code = ('import pathlib,time,json,os; p=pathlib.Path(' + repr(str(folder)) + '); '
                    '\nwhile not (p/"worker_gate.json").exists(): time.sleep(.01)\n'
                    '(p/"worker_terminal.json").write_text(json.dumps({"verdict":{"status":"INPUT_OR_EXECUTION_STOP","reason":"GENERATED"}}))')
            caps = {'wall_seconds': 10, 'memory_bytes': 128*1024**2, 'output_bytes': 1024**2, 'reserve_bytes': 65536}
            verdict = self.ctrl.supervise([sys.executable, '-B', '-c', code], folder, {'caps': caps}, True)
            self.assertEqual(verdict['reason'], 'GENERATED')
            self.assertTrue(self.ctrl.status(folder)['final'])


    @unittest.skipUnless(os.name == 'nt', 'Windows supervisor contract')
    def test_generated_hung_worker_is_killed(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)/'attempt'
            caps = {'wall_seconds': 3, 'memory_bytes': 128*1024**2, 'output_bytes': 1024**2, 'reserve_bytes': 65536}
            verdict = self.ctrl.supervise([sys.executable, '-B', '-c', 'import time; time.sleep(20)'], folder, {'caps': caps}, True)
            self.assertEqual(verdict['reason'], 'WALL_CAP')
            self.assertTrue(self.ctrl.status(folder)['final'])


class GeneratedDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import issue27frontend_inheritance_outer_runner_v1 as runner
        cls.r = runner
        cls.tshark = 'C:/Program Files/Wireshark/tshark.exe'
        if not Path(cls.tshark).is_file():
            raise AssertionError('Pinned decoder is required for generated contract checks')
        if s.sha_file(Path(cls.tshark)) != '908a3b04da69ee45be9bd54627a722741d895262b4ce0b39f6d79a03daa24087':
            raise AssertionError('Decoder identity drift')

    def fixture(self):
        ethernet = bytes.fromhex('00112233445566778899aabb0800')
        ip = bytes.fromhex('4500001d00000000401100000a0000010a000002')
        udp = struct.pack('!HHHH', 12345, 443, 9, 0) + b'x'
        frame = ethernet + ip + udp
        return struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1) + b''.join(
            struct.pack('<IIII', i+1, 0, len(frame), len(frame)) + frame for i in range(4))

    def test_direct_generated_cutoff(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'generated.pcap'; p.write_bytes(self.fixture())
            identity = {'dataset_kind': 'direct_pcap', 'container_path': str(p)}
            rows = list(self.r.decoder_rows(self.tshark, identity, 2, ['frame.number', 'udp.length']))
            self.assertEqual([r['frame.number'] for r in rows], ['1', '2'])
            self.assertEqual([r['udp.length'] for r in rows], ['9', '9'])

    def test_short_generated_capture_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'generated.pcap'; p.write_bytes(self.fixture())
            with self.assertRaises(s.Stop):
                list(self.r.decoder_rows(self.tshark, {'dataset_kind': 'direct_pcap', 'container_path': str(p)}, 5, ['frame.number']))

    def test_generated_zip_exact_member(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'generated.zip'
            with zipfile.ZipFile(p, 'w') as archive:
                archive.writestr('chosen.pcap', self.fixture())
                archive.writestr('excluded.pcap', b'not a capture; must never be decoded')
                info = archive.getinfo('chosen.pcap')
                identity = {'dataset_kind': 'gotham_zip', 'container_path': str(p), 'raw_source_path': 'chosen.pcap',
                            'member_uncompressed_bytes_if_archive': str(info.file_size), 'member_crc32_if_archive': '%08x' % info.CRC}
            rows = list(self.r.decoder_rows(self.tshark, identity, 2, ['frame.number']))
            self.assertEqual(len(rows), 2)

    def test_generated_zip_identity_drift(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'generated.zip'
            with zipfile.ZipFile(p, 'w') as archive: archive.writestr('chosen.pcap', self.fixture())
            identity = {'dataset_kind': 'gotham_zip', 'container_path': str(p), 'raw_source_path': 'chosen.pcap',
                        'member_uncompressed_bytes_if_archive': '1', 'member_crc32_if_archive': '00000000'}
            with patch.object(self.r.subprocess, 'Popen', side_effect=AssertionError('must stop before decoder')):
                with self.assertRaises(s.Stop): list(self.r.decoder_rows(self.tshark, identity, 2, ['frame.number']))

if __name__ == '__main__':
    unittest.main()
