"""Scope isolation regressions, including two pinned real header-only fixtures.

No full capture, checkpoint, model scoring or optimizer access in this module.
"""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import continuous_audit_v3 as audit_api
import continuous_input_v3 as inp
import legacy_reference_sample_prepare_v1 as prep
from test_continuous_amendment_v3 import target
from test_continuous_repair_v3 import packet

FIXTURE = Path(__file__).parent/'fixtures/continuous_scope_v3'
FIXTURE_SHA = '1bcb7e6b72c5a33e3c3283fbe430732e6cb17c25ec6c300fb35a9109e8ecfada'
OTHER = '70:5a:0f:e4:9b:c0'
NS = inp.NS


def fragments():
    return copy.deepcopy(json.loads((FIXTURE/'decoded_headers.json').read_text())['rows'])


def context(max_states=1_000_000):
    return inp.Contexts('generated', {'aa', OTHER}, prep.old.legacy_runtime()[0],
                        max_states=max_states, required_owners={'aa'})


def sequence():
    first, last = fragments()
    first['frame.number'], last['frame.number'] = '2', '3'
    before = packet(1, inp.nanos(first['frame.time_epoch'])-NS)
    after = packet(4, inp.nanos(last['frame.time_epoch'])+NS)
    return [before, first, last, after]


class ScopeIsolation(unittest.TestCase):
    def test_real_fixture_identity_and_current_decoder(self):
        p = FIXTURE/'udp_first_and_last.pcapng'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), FIXTURE_SHA)
        executable = shutil.which('tshark')
        if not executable and Path('C:/Program Files/Wireshark/tshark.exe').is_file():
            executable = 'C:/Program Files/Wireshark/tshark.exe'
        self.assertIsNotNone(executable, 'tshark is required for the pinned fixture')
        fields = ['frame.time_epoch','frame.cap_len','frame.len','eth.src','eth.dst',
                  'ip.src','ip.dst','ip.proto','udp.srcport','udp.dstport','udp.length']
        command = [executable,'-n','-r',str(p),'-T','fields','-E','header=y']
        for field in fields:
            command += ['-e',field]
        result = subprocess.run(command,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stderr,'')
        actual = list(csv.DictReader(io.StringIO(result.stdout),delimiter='\t'))
        self.assertEqual(actual,[{k:r[k] for k in fields} for r in fragments()])

    def test_real_unrelated_fragments_leave_target_snapshot_byte_identical(self):
        ct = context(); control = inp.Contexts('generated',{'aa'},prep.old.legacy_runtime()[0])
        for row in sequence():
            ct.append(row); control.append(row)
            if ct.states:
                self.assertEqual(json.dumps([s.snapshot() for s in ct.states.values()],sort_keys=True),
                                 json.dumps([s.snapshot() for s in control.states.values()],sort_keys=True))
        self.assertEqual(ct.reasons['OUTSIDE_REQUIRED_OWNER'],2)
        self.assertEqual(set(ct.last_seen),set(control.last_seen))
        self.assertEqual(ct.tainted,control.tainted)
        self.assertEqual(ct.poisoned,control.poisoned)

    def test_real_first_fragment_becomes_required_owner_and_stops(self):
        p = fragments()[0]; p['frame.number'] = '1'; p['eth.src'] = 'aa'
        ct = context()
        with self.assertRaisesRegex(RuntimeError,'MISSING_NAMESPACE_HEADERS'):
            ct.append(p)
        self.assertFalse(ct.states)
        self.assertFalse(ct.last_seen)

    def test_full_registry_multi_owner_remains_excluded(self):
        ct = context(); p = packet(1,0); p['eth.dst'] = OTHER; p['tcp.srcport'] = ''
        self.assertEqual(ct.append(p)[:2],(None,None))
        self.assertFalse(ct.frame_required_owner)
        self.assertEqual(ct.reasons['OUTSIDE_REQUIRED_OWNER'],0)
        self.assertFalse(ct.states)

    def test_outside_frame_contiguity_is_not_skipped(self):
        p = fragments()[0]; p['frame.number'] = '2'
        with self.assertRaisesRegex(RuntimeError,'NONCONTIGUOUS_CAPTURE_FRAME'):
            context().append(p)

    def test_outside_capture_regression_recorded_without_namespace_poison(self):
        ct = context(); ct.append(packet(1,10*NS))
        p = packet(2,9*NS); p['eth.src'] = OTHER; ct.append(p)
        self.assertEqual(ct.previous_ns,9*NS)
        self.assertEqual(ct.reasons['CAPTURE_REGRESSION_OUTSIDE_SCOPE'],1)
        ct.append(packet(3,11*NS)); ct.require_target()
        self.assertFalse(ct.poisoned)

    def test_outside_time_or_frame_volume_cannot_evict_or_reset_target(self):
        ct = context(max_states=1); _,ns,_ = ct.append(packet(1,0))
        original = ct.states[ns].snapshot()
        for i in range(2,202):
            p = packet(i,(10000+i)*NS); p['eth.src'] = OTHER; p['tcp.srcport'] = str(i)
            ct.append(p)
        self.assertEqual(ct.states[ns].snapshot(),original)
        self.assertFalse(ct.retired)
        self.assertEqual(len(ct.last_seen),1)
        ct.append(packet(202,10*NS)); ct.require_target()
        self.assertEqual(ct.states[ns].episode_first_frame,1)
        ct.append(packet(203,70*NS)); ct.require_target()
        self.assertEqual(ct.states[ns].episode_first_frame,1)
        ct.append(packet(204,130*NS+1)); ct.require_target()
        self.assertEqual(ct.states[ns].episode_first_frame,204)

    def test_unknown_required_owner_cannot_silently_disappear(self):
        with self.assertRaisesRegex(RuntimeError,'REQUIRED_OWNER_NOT_REGISTERED'):
            inp.Contexts('generated',{'aa'},prep.old.legacy_runtime()[0],required_owners={'missing'})

    def test_query_reference_union_is_independent_of_labels_and_times(self):
        with tempfile.TemporaryDirectory() as td:
            targets = {1:('FIT',0,dict(owner='aa',label=1,timestamp=100)),
                       2:('UNSW_REFS',0,dict(owner=OTHER,label=0,timestamp=0))}
            a = audit_api.CaptureAudit(dict(capture_id='union'),{'aa',OTHER},prep.old.legacy_runtime(),targets,td)
            try:
                self.assertEqual(a.contexts.required,{'aa',OTHER})
            finally:
                a.close()
            targets[1][2].update(label=0,timestamp=-100)
            targets[2][2].update(label=1,timestamp=999)
            b = audit_api.CaptureAudit(dict(capture_id='union2'),{'aa',OTHER},prep.old.legacy_runtime(),targets,td)
            try:
                self.assertEqual(a.contexts.required,b.contexts.required)
            finally:
                b.close()

    def test_full_legacy_incomplete_receipt_and_scoped_identity_both_pass(self):
        rows = sequence()
        targets = {i:('FIT',j,target(rows[i-1])) for j,i in enumerate((1,4))}
        expected = dict(packets=4,anomalies=dict(NEW_TIMESTAMP_REGRESSION=0,POISONED_PREFIX=0,INCOMPLETE_TARGET=1))
        with tempfile.TemporaryDirectory() as td:
            a = audit_api.CaptureAudit(dict(capture_id='generated',sha256='fixture',expected_packets=4),
                                      {'aa',OTHER},prep.old.legacy_runtime(),targets,td,expected)
            try:
                for row in rows: a.append(row)
                result = a.finish()
            finally: a.close()
            self.assertEqual(result['targets'],2)
            self.assertEqual(result['required_identity_frames'],2)
            self.assertEqual(result['legacy_incomplete_outside_required_owner'],1)
            self.assertEqual(result['legacy_anomalies']['INCOMPLETE_TARGET'],1)

    def test_receipt_incomplete_on_required_owner_cannot_be_misclassified_outside(self):
        rows = [packet(1,0),packet(2,NS)]; rows[1]['frame.cap_len'] = '54'
        targets = {1:('FIT',0,target(rows[0]))}
        expected = dict(packets=2,anomalies=dict(NEW_TIMESTAMP_REGRESSION=0,POISONED_PREFIX=0,INCOMPLETE_TARGET=1))
        with tempfile.TemporaryDirectory() as td:
            a = audit_api.CaptureAudit(dict(capture_id='generated',sha256='fixture',expected_packets=2),
                                      {'aa',OTHER},prep.old.legacy_runtime(),targets,td,expected)
            try:
                for row in rows: a.append(row)
                with self.assertRaisesRegex(RuntimeError,'STATIC_INCOMPLETE_NOT_ALL_OUTSIDE_REQUIRED_OWNER'):
                    a.finish()
            finally: a.close()

    def test_fixed_uid_with_wrong_owner_is_still_rejected(self):
        first = fragments()[0]; first['frame.number'] = '1'
        with tempfile.TemporaryDirectory() as td:
            a = audit_api.CaptureAudit(dict(capture_id='generated',sha256='fixture',expected_packets=1),
                                      {'aa',OTHER},prep.old.legacy_runtime(),{1:('FIT',0,target(packet(1,0)))},td)
            try:
                with self.assertRaisesRegex(RuntimeError,'FIXED_TARGET_INVALID:OUTSIDE_REQUIRED_OWNER'):
                    a.append(first)
            finally: a.close()

    def test_required_namespace_identity_check_not_disabled(self):
        p = packet(1,0)
        with tempfile.TemporaryDirectory() as td:
            a = audit_api.CaptureAudit(dict(capture_id='generated',sha256='fixture',expected_packets=1),
                                      {'aa'},prep.old.legacy_runtime(),{1:('FIT',0,target(p))},td)
            try:
                with patch.object(a.legacy,'append',return_value=(None,None,True)):
                    with self.assertRaisesRegex(RuntimeError,'LEGACY_NAMESPACE_IDENTITY'): a.append(p)
            finally: a.close()


if __name__ == '__main__':
    unittest.main()
