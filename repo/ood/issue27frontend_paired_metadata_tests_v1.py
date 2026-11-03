"""Generated semantic, split, decoder and supervisor checks. No project packets."""
from __future__ import annotations

import copy
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

import issue27frontend_paired_metadata_v1 as s
import issue27frontend_paired_metadata_runner_v1 as r
import issue27frontend_paired_metadata_control_v1 as c

TSHARK = Path('C:/Program Files/Wireshark/tshark.exe')


def raw_packet(**changes):
    raw = {'frame.number': '1', 'frame.time_epoch': '1.25', 'frame.encap_type': '1', 'frame.len': '60',
           'eth.src': '00:01:02:03:04:05', 'eth.dst': '00:01:02:03:04:06', 'eth.type': '0x0800',
           'ip.src': '10.0.0.1', 'ip.dst': '10.0.0.2', 'ip.proto': '6', 'tcp.srcport': '12000', 'tcp.dstport': '443'}
    raw.update(changes)
    return raw


def target(uid='b', owner='B', context='c', position=0, tier='H1', label=0, session=None, source='generated'):
    return {'uid': uid, 'owner': owner, 'context_key': context, 'position': position, 'tier': tier,
            'source_group': source, 'member': 'generated.pcap', 'timestamp_epoch': '1.25',
            'label': label, 'attack_family': 'attack' if label else 'benign', 'device_family': 'generated',
            'event_index': position, 'context_events': position + 1, 'history': 'GENERATED',
            'session_kind': 'GENUINE_CANONICAL_OLD_SESSION' if owner == 'A' else 'UNENCODABLE_PER_TARGET_PLACEHOLDER',
            'old_session_id': session or s.digest(uid.encode())}


def descriptor_stub(t, route=None, session='', compatibility=''):
    return {k: t[k] for k in ('uid', 'source_group', 'member', 'position', 'tier', 'timestamp_epoch')} | {
        'base_route_sha256': route or s.digest(t['uid'].encode()), 'canonical_old_session_sha256': session,
        'f0_h1_compatibility_session_sha256': compatibility}


def population(n=10):
    ts = [target(g + str(i), g, g + str(i), label=label) for g, label in (('A', 0), ('B', 0)) for i in range(n)]
    ts += [target('x' + str(i), 'A', 'x' + str(i), label=1) for i in range(n)]
    ds = [descriptor_stub(t) for t in ts if t['owner'] == 'B']
    return ts, ds


class ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsers = s.parsers()

    def desc(self, raw=None, t=None):
        return s.descriptor(raw or raw_packet(), t or target(), self.parsers)

    def test_no_model_stack_imported(self):
        self.assertFalse(any(k in sys.modules for k in ('torch', 'numpy', 'pandas', 'scipy')))

    def test_reverse_endpoints_same_group(self):
        reverse = raw_packet(**{'ip.src': '10.0.0.2', 'ip.dst': '10.0.0.1', 'tcp.srcport': '443', 'tcp.dstport': '12000'})
        self.assertEqual(self.desc()['base_route_sha256'], self.desc(reverse)['base_route_sha256'])
        self.assertEqual(self.desc()['canonical_old_session_sha256'], self.desc(reverse)['canonical_old_session_sha256'])

    def test_scope_prevents_cross_member_merge(self):
        t = target(); t['member'] = 'other.pcap'
        self.assertNotEqual(self.desc()['base_route_sha256'], self.desc(t=t)['base_route_sha256'])

    def test_epoch_does_not_change_route(self):
        t = target('other', context='epoch999')
        self.assertEqual(self.desc()['base_route_sha256'], self.desc(t=t)['base_route_sha256'])

    def test_real_port_change_changes_group(self):
        self.assertNotEqual(self.desc()['base_route_sha256'], self.desc(raw_packet(**{'tcp.dstport': '444'}))['base_route_sha256'])

    def test_old_hash_matches_historical_tuple_rule(self):
        key = (6, ('10.0.0.1', 12000), ('10.0.0.2', 443))
        expected = s.digest(repr(('generated', 'generated.pcap', key)).encode())
        self.assertEqual(self.desc()['canonical_old_session_sha256'], expected)

    def test_ipv6_old_missing_has_conservative_h1_bridge(self):
        raw = raw_packet(**{'ip.src': '', 'ip.dst': '', 'ip.proto': '', 'ipv6.src': '::1', 'ipv6.dst': '::2', 'ipv6.nxt': '6'})
        d = self.desc(raw)
        self.assertEqual(d['canonical_old_session_sha256'], '')
        self.assertEqual(d['f0_h1_compatibility_session_sha256'], s.digest(repr(('generated', 'generated.pcap', (6, ('::1', 12000), ('::2', 443)))).encode()))

    def test_zero_port_legacy_udp_fallback_preserved(self):
        raw = raw_packet(**{'tcp.srcport': '0', 'udp.srcport': '333', 'udp.dstport': '444'})
        d = self.desc(raw)
        self.assertNotEqual(d['canonical_old_session_sha256'], d['f0_h1_compatibility_session_sha256'])
        self.assertEqual(d['canonical_old_session_sha256'], s.digest(repr(('generated', 'generated.pcap', (6, ('10.0.0.1', 333), ('10.0.0.2', 443)))).encode()))

    def test_h2_nontransport_group(self):
        d = self.desc(raw_packet(**{'ip.proto': '1', 'tcp.srcport': '', 'tcp.dstport': '', 'icmp.type': '8'}), target(tier='H2'))
        self.assertEqual(d['tier'], 'H2'); self.assertEqual(d['canonical_old_session_sha256'], '')

    def test_h3_link_pair_group(self):
        raw = raw_packet(**{'ip.src': '', 'ip.dst': '', 'ip.proto': '', 'tcp.srcport': '', 'tcp.dstport': '', 'eth.type': '0x0806'})
        self.assertEqual(self.desc(raw, target(tier='H3'))['tier'], 'H3')

    def test_h4_protocol_class_not_uid(self):
        raw = raw_packet(**{'ip.src': '', 'ip.dst': '', 'ip.proto': '', 'eth.src': '', 'eth.dst': '', 'tcp.srcport': '', 'tcp.dstport': ''})
        d = self.desc(raw, target(tier='H4'))
        self.assertEqual(d['base_route_sha256'], self.desc(raw, target(uid='different', tier='H4'))['base_route_sha256'])
        altered = dict(raw, **{'icmp.type': '8'})
        self.assertNotEqual(d['base_route_sha256'], self.desc(altered, target(tier='H4'))['base_route_sha256'])

    def test_descriptor_never_reads_label_or_score(self):
        class Guard(dict):
            def __getitem__(self, k):
                if k in {'owner', 'label', 'teacher_kind', 'logit'}: raise AssertionError('forbidden field')
                return super().__getitem__(k)
        self.desc(t=Guard(target()))

    def test_no_raw_endpoints_persist(self):
        raw = s.canonical(self.desc()).decode()
        self.assertNotIn('10.0.0.', raw); self.assertNotIn('00:01:02', raw)

    def test_identity_failures(self):
        for changes in ({'frame.number': '2'}, {'frame.time_epoch': 'nan'}, {'frame.time_epoch': '2'}, {'ip.proto': '1'}):
            with self.subTest(changes=changes), self.assertRaises(s.Stop):
                self.desc(raw_packet(**changes))


class SplitTests(unittest.TestCase):
    def test_80_20_group_counts_and_conservation(self):
        ts, ds = population()
        out = s.build_membership(ts, ds)
        self.assertEqual(out['summary']['train_targets'], 24)
        self.assertEqual(out['summary']['check_targets'], 6)
        self.assertEqual(out['summary']['status'], 'MEMBERSHIP_QUALIFIED')
        self.assertEqual({r['uid'] for r in out['membership']}, {t['uid'] for t in ts})

    def test_input_order_and_old_errors_do_not_change_split(self):
        ts, ds = population(); expected = s.build_membership(ts, ds)['membership']
        for t in ts: t.update(logit=999, teacher_kind='CHANGED_UNUSED', known_five_error=True)
        self.assertEqual(s.build_membership(list(reversed(ts)), list(reversed(ds)))['membership'], expected)

    def test_same_old_session_spanning_epochs_is_whole(self):
        ts, ds = population()
        ts[1]['old_session_id'] = ts[0]['old_session_id']
        out = s.build_membership(ts, ds)
        rows = {r['uid']: r for r in out['membership']}
        self.assertEqual(rows['A0']['component_id'], rows['A1']['component_id'])
        self.assertEqual(rows['A0']['new_role'], rows['A1']['new_role'])

    def test_transitive_B_route_and_old_A_bridge(self):
        a = target('a', 'A', 'a', session='a' * 64)
        bs = [target('b1', context='b1'), target('b2', context='b2')]
        ds = [descriptor_stub(bs[0], route='b'*64, session='a'*64), descriptor_stub(bs[1], route='b'*64)]
        out = s.build_membership([a] + bs, ds)
        self.assertEqual(out['summary']['components'], 1)
        self.assertEqual(out['summary']['check_targets'], 0)

    def test_f0_compatibility_bridge_connects_A(self):
        a, b = target('a', 'A', session='a'*64), target('b', context='b')
        out = s.build_membership([a, b], [descriptor_stub(b, compatibility='a'*64)])
        self.assertEqual(out['summary']['components'], 1)

    def test_shared_context_not_split_by_labels(self):
        a, b = target('a', 'A', context='shared'), target('b', context='shared', position=1, label=1)
        a['context_events'] = 2
        out = s.build_membership([a, b], [descriptor_stub(b)])
        self.assertEqual(len({r['new_role'] for r in out['membership']}), 1)
        self.assertEqual(len(out['components'][0]['stratum']), 2)

    def test_singleton_is_train_only_not_vacuous_pass(self):
        b = target()
        out = s.build_membership([b], [descriptor_stub(b)])
        self.assertEqual(out['membership'][0]['new_role'], 'train')
        self.assertEqual(out['summary']['status'], 'METADATA_COMPLETE_COVERAGE_INSUFFICIENT')
        self.assertEqual(out['coverage'][0]['same_behavior_check'], 'NOT_ESTABLISHED')

    def test_ton_gap_cannot_hide_in_other_source(self):
        ts, ds = population(); b = target('ton-b', source='normal_1.pcap', context='ton-b')
        out = s.build_membership(ts + [b], ds + [descriptor_stub(b)])
        self.assertIn('MISSING_TON_TRAIN_CHECK:normal_1.pcap:B', out['summary']['coverage_gaps'])

    def test_missing_duplicate_unknown_descriptors_fail(self):
        ts, ds = population(2)
        for changed in (ds[:-1], ds + [ds[0]], ds + [descriptor_stub(target('alien'))]):
            with self.subTest(n=len(changed)), self.assertRaises(s.Stop): s.build_membership(ts, changed)

    def test_descriptor_attachment_drift_fails(self):
        ts, ds = population(2); ds[0]['position'] += 1
        with self.assertRaises(s.Stop): s.build_membership(ts, ds)

    def test_multiple_routes_in_one_context_fail(self):
        b1, b2 = target('b1'), target('b2', position=1)
        b1['context_events'] = 2
        with self.assertRaises(s.Stop): s.build_membership([b1, b2], [descriptor_stub(b1), descriptor_stub(b2)])

    def test_regression_placeholder_requires_real_bridge(self):
        b = target(); b['session_kind'] = 'UNENCODABLE_TIMESTAMP_REGRESSION_PER_TARGET_PLACEHOLDER'
        with self.assertRaises(s.Stop): s.build_membership([b], [descriptor_stub(b)])

    def test_json_roundtrip_preserves_recomputed_results(self):
        ts, ds = population(2); result = s.build_membership(ts, ds)
        self.assertEqual(json.loads(s.canonical(result)), result)

    def test_matched_exposure_schedule_with_large_B_and_tail_batches(self):
        rows = []
        for g, n in (('A', 33), ('B', 129)):
            for i in range(n): rows.append({'owner': g, 'context_key': g+str(i), 'event_index': i % 7, 'new_role': 'train'})
        out = s.schedule_receipt(rows)
        self.assertEqual((out['N_A'], out['N_B'], out['steps_per_epoch'], out['updates_per_arm']), (33, 129, 2, 80))
        expected = 40 * sum((2 if x['owner']=='A' else 1) * (x['event_index']+1) for x in rows)
        self.assertEqual(out['train_context_events_both_arms'], expected)


def generated_pcap():
    ethernet = bytes.fromhex('00112233445566778899aabb0800')
    ip = bytes.fromhex('4500001d00000000401100000a0000010a000002')
    frame = ethernet + ip + struct.pack('!HHHH', 12345, 443, 9, 0) + b'x'
    return struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1) + b''.join(
        struct.pack('<IIII', sec, 0, len(frame), len(frame)) + frame for sec in (1, 2, 1, 4))


class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not TSHARK.is_file() or s.sha_file(TSHARK) != '908a3b04da69ee45be9bd54627a722741d895262b4ce0b39f6d79a03daa24087':
            raise AssertionError('Pinned TShark required for generated files')
        cls.decode, cls.helper = r.decoder_api()

    def test_command_exact_cutoff_and_frame_reset(self):
        cmd = self.helper.tshark_command(TSHARK, 'generated', 3, ['frame.number'])
        self.assertEqual(cmd[cmd.index('-c')+1], '3')
        self.assertEqual(self.helper.normalize_reset_frame_number('1', 100000), '100001')
        with self.assertRaises(s.Stop): self.helper.normalize_reset_frame_number('2', 100000)

    def test_direct_generated_cutoff(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'fixture.pcap'; path.write_bytes(generated_pcap())
            rows = list(type(self).decode(TSHARK, {'dataset_kind': 'direct_pcap', 'container_path': str(path)}, 3, ['frame.number']))
            self.assertEqual([x['frame.number'] for x in rows], ['1', '2', '3'])

    def test_short_capture_fails(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'fixture.pcap'; path.write_bytes(generated_pcap())
            with self.assertRaises(s.Stop): list(type(self).decode(TSHARK, {'dataset_kind': 'direct_pcap', 'container_path': str(path)}, 5, ['frame.number']))

    def test_exact_zip_member_and_bad_crc(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'fixture.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('chosen.pcap', generated_pcap()); z.writestr('excluded.pcap', b'NOT_A_CAPTURE')
                info = z.getinfo('chosen.pcap')
            identity = {'dataset_kind': 'gotham_zip', 'container_path': str(path), 'raw_source_path': 'chosen.pcap',
                        'member_uncompressed_bytes_if_archive': info.file_size, 'member_crc32_if_archive': '%08x'%info.CRC}
            self.assertEqual(len(list(type(self).decode(TSHARK, identity, 2, ['frame.number']))), 2)
            identity['member_crc32_if_archive'] = '00000000'
            with self.assertRaises(s.Stop): list(type(self).decode(TSHARK, identity, 2, ['frame.number']))

    def test_generated_end_to_end_B_projection_and_membership(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); path = folder/'generated.pcap'; path.write_bytes(generated_pcap())
            b = target('b', position=2); b['timestamp_epoch']='1.0'
            b['session_kind']='UNENCODABLE_TIMESTAMP_REGRESSION_PER_TARGET_PLACEHOLDER'
            m = {'source_group': b['source_group'], 'member': b['member'], 'dataset_kind': 'direct_pcap',
                 'container_path': str(path), 'selected_B_targets': 1, 'single_pass_prefix_packets': 3}
            progress = r.Progress(folder, dict(s.CAPS, targets=1, packets=3, members=1), time.monotonic())
            ds = r.extract([b], [m], s.parsers(), type(self).decode, TSHARK, progress)
            self.assertEqual(len(ds), 1); self.assertEqual(ds[0]['position'], 2)
            self.assertTrue(ds[0]['canonical_old_session_sha256'])
            a = target('a', 'A', 'a', session=ds[0]['canonical_old_session_sha256'])
            result = s.build_membership([a, b], ds)
            self.assertEqual(result['summary']['components'], 1)
            r.write_result(folder, result, ds, {'generated': True})
            self.assertEqual(s.read_json(folder/'membership_result.json'), result['summary'])

    def test_unselected_headers_and_labels_are_not_projected(self):
        class Poison(dict):
            def get(self, *args): raise AssertionError('unselected packet accessed')
        b = target(position=1); raw = raw_packet(**{'frame.number':'2'})
        def fake(*args): yield Poison(); yield raw
        m={'source_group':'generated','member':'generated.pcap','selected_B_targets':1,'single_pass_prefix_packets':2}
        with tempfile.TemporaryDirectory() as d:
            progress=r.Progress(Path(d),dict(s.CAPS,targets=1,packets=2,members=1),time.monotonic())
            self.assertEqual(len(r.extract([b],[m],s.parsers(),fake,'unused',progress)),1)


class ControllerTests(unittest.TestCase):
    def test_no_real_namespace_started(self):
        self.assertFalse((s.ROOT/s.REAL).exists())

    def test_explicit_gate_rejects_before_readiness(self):
        proc = subprocess.run([sys.executable, '-B', str(Path(c.__file__)), 'run-real'], capture_output=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b'EXPLICIT_B_HEADER_READ_AUTHORIZATION_REQUIRED', proc.stderr)

    def test_absent_and_incomplete_status(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'absent'; self.assertEqual(c.status(folder)['status'],'NOT_STARTED')
            folder.mkdir(); s.atomic_json(folder/'attempt.json',{'controller_pid':os.getpid()})
            s.atomic_json(folder/'worker_terminal.json',{'status':'METADATA_WORK_COMPLETE'})
            self.assertEqual(c.status(folder)['status'],'SEALING'); self.assertFalse(c.status(folder)['final'])

    def test_tamper_and_extra_file_invalidate_seal(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d); s.atomic_json(folder/'supervisor_terminal.json',{'verdict':{'status':'METADATA_COMPLETE_COVERAGE_INSUFFICIENT'}})
            s.seal(folder); self.assertTrue(c.status(folder)['final'])
            (folder/'extra').write_bytes(b'x'); self.assertFalse(c.status(folder)['final'])

    def test_dead_controller_never_means_finished(self):
        with tempfile.TemporaryDirectory() as d:
            s.atomic_json(Path(d)/'attempt.json',{'controller_pid':99999999})
            self.assertEqual(c.status(Path(d))['status'],'INTERRUPTED_DO_NOT_RESTART')

    def test_existing_output_cannot_restart(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileExistsError): c.supervise([],Path(d),{})

    def config(self, wall=10):
        return {'caps':dict(s.CAPS,wall_seconds=wall,memory_bytes=512*1024**2,controller_reserve_bytes=192*1024**2,output_bytes=1024**2,reserve_bytes=65536)}

    def test_generated_stop_sealed_without_scientific_success(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'attempt'
            code='import pathlib,json,time; p=pathlib.Path('+repr(str(folder))+');\nwhile not (p/"worker_gate.json").exists(): time.sleep(.01)\n(p/"worker_terminal.json").write_text(json.dumps({"status":"INPUT_OR_EXECUTION_STOP","reason":"GENERATED"}))'
            out=c.supervise([sys.executable,'-B','-c',code],folder,self.config(),True)
            self.assertEqual(out['reason'],'GENERATED'); self.assertTrue(c.status(folder)['final'])

    def test_generated_success_runs_validator_then_seals(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'attempt'
            code='import pathlib,time; p=pathlib.Path('+repr(str(folder))+');\nwhile not (p/"worker_gate.json").exists(): time.sleep(.01)\n(p/"worker_terminal.json").write_text("{}")'
            def validate(*args):return {'status':'MEMBERSHIP_QUALIFIED','scientific_capability':'NOT_TESTED','training_authorized':False}
            out=c.supervise([sys.executable,'-B','-c',code],folder,self.config(),True,validate)
            self.assertEqual(out['status'],'MEMBERSHIP_QUALIFIED'); self.assertTrue(c.status(folder)['seal_verified'])

    def test_generated_hung_worker_is_killed(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'attempt'
            out=c.supervise([sys.executable,'-B','-c','import time; time.sleep(20)'],folder,self.config(3),True)
            self.assertEqual(out['reason'],'WALL_CAP'); self.assertTrue(c.status(folder)['final'])

    def test_generated_output_overrun_stops(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'attempt'
            code='import pathlib,time; p=pathlib.Path('+repr(str(folder))+');\nwhile not (p/"worker_gate.json").exists(): time.sleep(.01)\n(p/"too-big").write_bytes(bytes(1048577)); time.sleep(20)'
            out=c.supervise([sys.executable,'-B','-c',code],folder,self.config(),True)
            self.assertEqual(out['status'],'INPUT_OR_EXECUTION_STOP')

    def test_generated_decoder_child_is_killed_with_worker(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'attempt'
            code=('import pathlib,time,subprocess,sys; p=pathlib.Path('+repr(str(folder))+');\n'
                  'while not (p/"worker_gate.json").exists(): time.sleep(.01)\n'
                  'child=subprocess.Popen([sys.executable,"-B","-c","import time; time.sleep(20)"],creationflags=subprocess.CREATE_NO_WINDOW)\n'
                  '(p/"child_pid").write_text(str(child.pid)); time.sleep(20)')
            out=c.supervise([sys.executable,'-B','-c',code],folder,self.config(3),True)
            self.assertEqual(out['reason'],'WALL_CAP')
            pid=int((folder/'child_pid').read_text())
            until=time.monotonic()+2
            while c.pid_alive(pid) and time.monotonic()<until: time.sleep(.02)
            self.assertFalse(c.pid_alive(pid))


if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'tests_run':result.testsRun,'tests_passed':result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'real_packets_decoded':0,'model_calls':0,'fixtures':'generated headers/PCAP/ZIP and disposable child processes'}
    print('SYNTHETIC_RESULT '+json.dumps(report),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
