"""Synthetic fault tests; no SSH, remote connection, model or service starts."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import client
import pipeline


def archive_with(name, payload=b'x', link=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as out:
        member = tarfile.TarInfo(name)
        if link:
            member.type = tarfile.SYMTYPE
            member.linkname = '/outside'
            out.addfile(member)
        else:
            member.size = len(payload)
            out.addfile(member, io.BytesIO(payload))
    buffer.seek(0)
    return tarfile.open(fileobj=buffer, mode='r:')


class ExistingTunnelClient(unittest.TestCase):
    def test_short_socks_reply_fails_closed(self):
        class Closed:
            def recv(self, count): return b''
        with self.assertRaisesRegex(ConnectionError, 'EXISTING_TUNNEL_CLOSED'):
            client.exact(Closed(), 2)

    def test_upload_recovers_ack_loss_using_remote_offset_not_old_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            specs = {}
            data = {}
            for key in client.KEYS:
                data[key] = (key*3).encode()
                path = base/key
                path.write_bytes(data[key])
                specs[key] = dict(path=str(path), bytes=len(data[key]), sha256=client.sha(path))
            state = dict(files={k:dict(offset=0, complete=False, bytes=v['bytes'], sha256=v['sha256'])
                                    for k,v in specs.items()})
            uploads = []
            lost = False
            def action(route, body=b'', headers=None, **unused):
                nonlocal lost
                if route == 'state':
                    return json.loads(json.dumps(state))
                key = route.split('/')[1]
                uploads.append((key, int(headers['X-Offset'])))
                self.assertEqual(int(headers['X-Offset']), state['files'][key]['offset'])
                self.assertEqual(hashlib.sha256(body).hexdigest(), headers['X-Chunk-SHA256'])
                state['files'][key].update(offset=specs[key]['bytes'], complete=True)
                if not lost:
                    lost = True
                    raise ConnectionError('synthetic ACK lost after durable write')
                return dict(state['files'][key])
            result = client.upload_files(specs, action=action)
            self.assertTrue(all(v['complete'] for v in result['files'].values()))
            self.assertEqual([k for k,_ in uploads], list(client.KEYS))

    def test_changed_remote_identity_is_rejected_before_upload(self):
        with self.assertRaisesRegex(ValueError, 'REMOTE_FILE_IDENTITY'):
            client.remote_file({'files':{'archive':dict(offset=0,bytes=3,sha256='bad')}},
                               'archive', dict(bytes=3,sha256='a'*64))

    def test_result_path_escape_and_links_are_rejected(self):
        for name, link in (('../outside',False),('/absolute',False),('C:/escape',False),('ok',True)):
            with self.subTest(name=name, link=link), archive_with(name, link=link) as archive:
                with self.assertRaises(ValueError):
                    client.safe_members(archive)

    def test_linux_pass_requires_all_three_real_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base/'real_slice').mkdir()
            client.write(base/'DELIVERY_RESULT.json',dict(status='LINUX_PREFLIGHT_PASS'))
            client.write(base/'real_slice/RESULT.json',dict(status='SAME_RUNTIME_REAL_SLICE_E2E_PASS',
                                                          final_linux_runtime_gate_pass=True))
            # An outer PASS alone cannot hide a missing or failed strict probe.
            self.assertFalse(client.validate_result_directory(base)['linux_actual_preflight_pass'])
            client.write(base/'real_slice/STRICT_SHAPE_PROBE_SUMMARY.json',dict(status='PASS'))
            self.assertTrue(client.validate_result_directory(base)['linux_actual_preflight_pass'])
            client.write(base/'real_slice/RESULT.json',dict(status='SAME_RUNTIME_REAL_SLICE_E2E_PASS',
                                                          final_linux_runtime_gate_pass=False))
            self.assertFalse(client.validate_result_directory(base)['linux_actual_preflight_pass'])

    def test_member_manifest_rejects_same_size_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            payload=base/'detail.txt'
            payload.write_bytes(b'abc')
            client.write(base/'RESULT_MANIFEST.json',dict(files={'detail.txt':dict(bytes=3,sha256=client.sha(payload))}))
            client.write(base/'DELIVERY_RESULT.json',dict(status='STOPPED_NO_RETRY'))
            self.assertFalse(client.validate_result_directory(base)['linux_actual_preflight_pass'])
            payload.write_bytes(b'abd')
            with self.assertRaisesRegex(ValueError, 'RESULT_MEMBER_PIN'):
                client.validate_result_directory(base)

    def test_missing_final_receipt_preserves_verified_failure_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            log=base/'SLURM-123.log'
            log.write_bytes(b'job killed before final receipt\n')
            client.write(base/'RESULT_MANIFEST.json',dict(files={log.name:dict(bytes=log.stat().st_size,sha256=client.sha(log))}))
            result=client.validate_result_directory(base)
            self.assertFalse(result['linux_actual_preflight_pass'])
            self.assertEqual(result['delivery_status'],'MISSING_FINAL_RECEIPT')
            self.assertTrue(log.is_file())


class SubmitAndObservation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder=Path(self.tmp.name)
        self.patch=patch.object(pipeline,'HERE',self.folder)
        self.patch.start()
        pipeline.record.clear()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_lost_submit_reply_reconciles_one_remote_job_without_second_post(self):
        calls=[]
        known=False
        def action(route, **unused):
            nonlocal known
            calls.append(route)
            if route=='state':
                return dict(job=dict(job_id='123') if known else None)
            known=True
            raise ConnectionError('synthetic response lost')
        result=pipeline.submit_once(action=action)
        self.assertEqual(result['job_id'],'123')
        self.assertEqual(calls,['state','submit','state'])
        pipeline.submit_once(action=action)
        self.assertEqual(calls.count('submit'),1)

    def test_unknown_submission_persists_intent_and_forbids_later_post(self):
        calls=[]
        def action(route, **unused):
            calls.append(route)
            if route=='state':return dict(job=None)
            raise ConnectionError('synthetic no receipt')
        with self.assertRaisesRegex(RuntimeError,'UNKNOWN_NO_AUTOMATIC_RETRY'):
            pipeline.submit_once(action=action)
        with self.assertRaisesRegex(ValueError,'PRIOR_SUBMISSION_UNCERTAIN'):
            pipeline.submit_once(action=action)
        self.assertEqual(calls.count('submit'),1)
        self.assertTrue((self.folder/'SUBMIT_UNCERTAIN.json').is_file())

    def test_scheduler_completed_does_not_count_as_linux_pass(self):
        now=[0.]
        def action(route):return dict(status='SUBMITTED',job=dict(job_id='123',state='COMPLETED'))
        with patch.object(pipeline,'retrieve_results') as retrieve:
            result=pipeline.watch_and_retrieve(40,20,action=action,clock=lambda:now[0],
                                               pause=lambda amount:now.__setitem__(0,now[0]+amount))
            self.assertIsNone(result)
            retrieve.assert_not_called()
        self.assertEqual(client.read(self.folder/'PROGRESS.json')['stage'],'OBSERVATION_WINDOW_ENDED')

    def test_prepare_disconnect_waits_read_only_and_never_reposts(self):
        calls=[]
        now=[0.]
        prepared=False
        def action(route, **unused):
            nonlocal prepared
            calls.append(route)
            if route=='prepare':
                prepared=True
                raise ConnectionError('synthetic prepare response lost')
            return dict(status='PREPARED',prepare_receipt=dict(status='PREPARED')) if prepared else dict(status='UPLOADED')
        result=pipeline.prepare_once(action=action,clock=lambda:now[0],
                                      pause=lambda amount:now.__setitem__(0,now[0]+amount))
        self.assertEqual(result['status'],'PREPARED')
        self.assertEqual(calls,['state','prepare','state'])
        pipeline.prepare_once(action=action)
        self.assertEqual(calls.count('prepare'),1)

    def test_prepare_ambiguous_restart_queries_until_bounded_stop(self):
        client.write(self.folder/'PREPARE_ATTEMPT.json',dict(status='INTENT_PERSISTED_BEFORE_REQUEST'))
        now=[0.]
        calls=[]
        def action(route):calls.append(route);return dict(status='PREPARING')
        with self.assertRaisesRegex(TimeoutError,'UNRESOLVED_NO_AUTOMATIC_RETRY'):
            pipeline.prepare_once(action=action,maximum=10,interval=5,clock=lambda:now[0],
                                   pause=lambda amount:now.__setitem__(0,now[0]+amount))
        self.assertTrue(all(route=='state' for route in calls))

    def test_actual_receiver_prepared_status_and_top_level_scheduler(self):
        self.assertEqual(pipeline.prepared_receipt(dict(status='PREPARED_NOT_SUBMITTED',
                         prepare_receipt=dict(status='PREPARED_NOT_SUBMITTED')))['status'],
                         'PREPARED_NOT_SUBMITTED')
        now=[0.]
        pipeline.watch_and_retrieve(1,1,action=lambda route:dict(status='SUBMITTED',job=dict(job_id='123'),
                                    scheduler=dict(stdout='123|RUNNING|0:0|00:01|\n')),
                                     clock=lambda:now[0],pause=lambda amount:now.__setitem__(0,now[0]+amount))
        self.assertEqual(client.read(self.folder/'PROGRESS.json')['scheduler'],'123|RUNNING|0:0|00:01|\n')

    def test_final_receipt_stops_observation_after_single_result_fetch(self):
        seen=[]
        receipt=dict(linux_actual_preflight_pass=False,delivery_status='STOPPED_NO_RETRY')
        def retrieve(progress, **unused):seen.append('fetch');return receipt
        result=pipeline.watch_and_retrieve(30,20,action=lambda route:dict(result_ready=True,job=dict(job_id='123')),
                                           retrieve=retrieve,clock=lambda:0.,pause=lambda amount:None)
        self.assertEqual(result,receipt)
        self.assertEqual(seen,['fetch'])
        self.assertEqual(client.read(self.folder/'PROGRESS.json')['stage'],'PREFLIGHT_STOPPED')


if __name__=='__main__':
    unittest.main()
