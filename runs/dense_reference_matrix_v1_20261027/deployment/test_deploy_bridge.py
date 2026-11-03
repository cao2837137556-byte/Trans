"""Offline deployment transport tests; sbatch/Popen are always mocked."""
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('dense_deploy_bridge', Path(__file__).with_name('deploy_bridge.py'))
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def archive_bytes(extra=None, corrupt=False):
    files = {'hpc/run_dense.slurm': b'#!/bin/bash\n# inert fixture\n',
             'hpc/status_bridge.py': b'# inert fixture only\n', 'src/common.py': b'# fixture\n'}
    manifest = ''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n' for k,v in files.items()).encode()
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as tar:
        for name in (bridge.NAME, bridge.NAME+'/hpc', bridge.NAME+'/src'):
            item = tarfile.TarInfo(name)
            item.type = tarfile.DIRTYPE
            tar.addfile(item)
        for name, value in dict(files, PACKAGE_SHA256SUMS=manifest).items():
            if corrupt and name == 'src/common.py':
                value = b'different content with same frozen manifest'
            item = tarfile.TarInfo(bridge.NAME+'/'+name)
            item.size = len(value)
            tar.addfile(item, io.BytesIO(value))
        if extra:
            tar.addfile(*extra)
    raw = data.getvalue()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        members = tar.getmembers()
    return raw, manifest, len(members), sum(m.size for m in members)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.here = self.root/'bridge'
        self.here.mkdir()
        (self.root/'runs').mkdir()
        self.package = self.root/'runs'/bridge.NAME
        self.raw, self.manifest, count, size = archive_bytes()
        self.patcher = patch.multiple(bridge, ROOT=self.root, HERE=self.here, PACKAGE=self.package,
            ARCHIVE_SHA=hashlib.sha256(self.raw).hexdigest(), ARCHIVE_SIZE=len(self.raw),
            MANIFEST_SHA=hashlib.sha256(self.manifest).hexdigest(), MANIFEST_FILES=3,
            TAR_MEMBERS=count, TAR_BYTES=size)
        self.patcher.start()
        self.config = dict(schema='paper04-dense-deploy-bootstrap-v1', token='t'*64, status_token='s'*64,
            approval=dict(user_authorized=True, scope='DENSE_REFERENCE_V1', package_sha256=bridge.MANIFEST_SHA,
                          stages=['runtime','encode','source_cal'], total_wall_seconds=43200,retries=0,
                          evidence='Synthetic transport fixture only; never submit a real job'))

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def upload(self):
        return bridge.upload_chunk(self.raw, f'bytes 0-{len(self.raw)-1}/{len(self.raw)}',
                                   hashlib.sha256(self.raw).hexdigest())

    def deployed(self):
        self.upload()
        return bridge.deploy(self.config)

    def test_chunk_offset_sha_replay_and_whole_archive(self):
        split = len(self.raw)//2
        first, second = self.raw[:split], self.raw[split:]
        a = bridge.upload_chunk(first, f'bytes 0-{split-1}/{len(self.raw)}', hashlib.sha256(first).hexdigest())
        self.assertEqual(a['received_bytes'],split)
        replay = bridge.upload_chunk(first, f'bytes 0-{split-1}/{len(self.raw)}', hashlib.sha256(first).hexdigest())
        self.assertTrue(replay['replayed_chunk'])
        bridge.upload_chunk(second, f'bytes {split}-{len(self.raw)-1}/{len(self.raw)}',hashlib.sha256(second).hexdigest())
        self.assertEqual(bridge.upload_state()['status'],'UPLOADED_VERIFIED')
        self.assertEqual((self.here/'sealed_package.tar.gz').read_bytes(),self.raw)

    def test_bad_chunk_does_not_write_and_sparse_offset_not_allowed(self):
        with self.assertRaisesRegex(ValueError,'CHUNK_SHA'):
            bridge.upload_chunk(b'bad',f'bytes 0-2/{len(self.raw)}','0'*64)
        with self.assertRaisesRegex(ValueError,'CHUNK_OFFSET'):
            bridge.upload_chunk(b'a',f'bytes 1-1/{len(self.raw)}',hashlib.sha256(b'a').hexdigest())
        self.assertEqual(bridge.upload_state()['received_bytes'],0)

    def test_whole_archive_mismatch_preserves_partial_without_deploy(self):
        corrupt = bytearray(self.raw)
        corrupt[-1] ^= 1
        value = bytes(corrupt)
        with self.assertRaisesRegex(ValueError,'FULL_ARCHIVE_SHA256_MISMATCH'):
            bridge.upload_chunk(value,f'bytes 0-{len(value)-1}/{len(value)}',hashlib.sha256(value).hexdigest())
        self.assertTrue((self.here/'sealed_package.tar.gz.part').exists())
        self.assertFalse(self.package.exists())

    def test_safe_deploy_exact_hashes_approval_and_runtime(self):
        result = self.deployed()
        self.assertEqual(result['status'],'DEPLOYED_VERIFIED')
        self.assertEqual(result['files_verified'],3)
        self.assertEqual(bridge.read(self.package/'.private/APPROVED.json'),self.config['approval'])
        self.assertTrue((self.package/'runtime').is_dir())
        self.assertEqual(bridge.deploy(self.config),result)
        if os.name != 'nt':
            self.assertEqual((self.package/'.private/APPROVED.json').stat().st_mode & 0o077,0)

    def test_existing_package_never_overwritten(self):
        self.package.mkdir()
        (self.package/'keep').write_text('preserved')
        self.upload()
        with self.assertRaisesRegex(ValueError,'ALREADY_EXISTS'):
            bridge.deploy(self.config)
        self.assertEqual((self.package/'keep').read_text(),'preserved')

    def test_traversal_and_symlink_archive_rejected(self):
        malicious = tarfile.TarInfo(bridge.NAME+'/../outside')
        malicious.size=1
        link = tarfile.TarInfo(bridge.NAME+'/symlink')
        link.type=tarfile.SYMTYPE
        link.linkname='/tmp/elsewhere'
        for extra in ((malicious,io.BytesIO(b'x')),(link,None)):
            raw, manifest, count, size=archive_bytes(extra)
            path=self.here/'bad.tar.gz'
            path.write_bytes(raw)
            with patch.multiple(bridge,ARCHIVE_SHA=hashlib.sha256(raw).hexdigest(),ARCHIVE_SIZE=len(raw),
                                TAR_MEMBERS=count,TAR_BYTES=size):
                with self.assertRaisesRegex(ValueError,'UNSAFE'):
                    bridge.inspect_archive(path)
        self.assertFalse((self.root/'outside').exists())

    def test_changed_file_with_matching_archive_digest_still_fails_manifest(self):
        raw, manifest, count, size=archive_bytes(corrupt=True)
        path=self.here/'bad.tar.gz'
        path.write_bytes(raw)
        with patch.multiple(bridge,ARCHIVE_SHA=hashlib.sha256(raw).hexdigest(),ARCHIVE_SIZE=len(raw),
                            TAR_MEMBERS=count,TAR_BYTES=size):
            with self.assertRaisesRegex(ValueError,'ARCHIVE_FILE_SHA'):
                bridge.inspect_archive(path)

    def test_submit_exact_command_journal_before_call_and_no_duplicate(self):
        self.deployed()
        def scheduler(argv,**kwargs):
            self.assertEqual(argv,[bridge.SBATCH,'--export=NONE','hpc/run_dense.slurm'])
            self.assertEqual(kwargs['cwd'],self.package)
            self.assertTrue((self.package/'runtime').is_dir())
            self.assertEqual(bridge.read(self.here/'SUBMISSION_ATTEMPT.json')['status'],'ATTEMPTING')
            return SimpleNamespace(returncode=0,stdout='Submitted batch job 123456\n',stderr='')
        with patch.object(bridge.subprocess,'run',side_effect=scheduler) as run:
            one=bridge.submit(self.config)
            two=bridge.submit(self.config)
        self.assertEqual(run.call_count,1)
        self.assertEqual(one,two)
        self.assertEqual(one['job_id'],'123456')

    def test_timeout_is_uncertain_no_resubmit_no_monitor(self):
        self.deployed()
        with patch.object(bridge.subprocess,'run',side_effect=subprocess.TimeoutExpired('sbatch',20)) as run:
            result=bridge.submit(self.config)
            repeated=bridge.submit(self.config)
        self.assertEqual(run.call_count,1)
        self.assertEqual(result,repeated)
        self.assertEqual(result['status'],'SUBMISSION_TIMEOUT_UNKNOWN_NO_RETRY')
        with self.assertRaisesRegex(ValueError,'ONLY_VERIFIED_SUBMITTED'):
            bridge.monitor(self.config)

    def test_crash_after_exclusive_attempt_never_resubmits(self):
        self.deployed()
        (self.here/'SUBMISSION_ATTEMPT.json').write_bytes(b'{partial crash')
        with patch.object(bridge.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'ALREADY_ATTEMPTED'):
                bridge.submit(self.config)
            run.assert_not_called()

    def test_monitor_fixed_job_args_private_token_and_status_redaction(self):
        self.deployed()
        bridge.write(self.here/'submission.json',dict(status='SUBMITTED',job_id='123456'))
        with patch.object(bridge.subprocess,'Popen',return_value=SimpleNamespace(pid=999)) as popen:
            result=bridge.monitor(self.config)
            again=bridge.monitor(self.config)
        self.assertEqual(result,again)
        self.assertEqual(popen.call_count,1)
        args=popen.call_args.args[0]
        self.assertEqual(args[args.index('--root')+1],str(self.package/'runtime'))
        self.assertEqual(args[args.index('--job-id')+1],'123456')
        self.assertEqual(args[args.index('--port')+1],'18780')
        rendered=json.dumps(bridge.status())
        self.assertNotIn(self.config['token'],rendered)
        self.assertNotIn(self.config['status_token'],rendered)

    def test_bootstrap_and_approval_cannot_expand_scope(self):
        bridge.bootstrap_valid(self.config)
        for stages in (['runtime'],['runtime','encode','source_cal','matrix']):
            approval=dict(self.config['approval'],stages=stages)
            with self.assertRaisesRegex(ValueError,'PREFIX_APPROVAL'):
                bridge.approval_valid(approval)

    def test_http_auth_fixed_endpoints_and_no_parameters(self):
        from http.server import HTTPServer
        server=HTTPServer(('127.0.0.1',0),bridge.handler_class(self.config,time.monotonic()+30))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        def request(method,path,body=None,token=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            conn.request(method,path,body=body,headers={'Authorization':'Bearer '+(token or self.config['token'])})
            response=conn.getresponse()
            code=response.status
            response.read()
            conn.close()
            return code
        try:
            self.assertEqual(request('GET','/health'),200)
            self.assertEqual(request('GET','/health',token='wrong'),403)
            self.assertEqual(request('POST','/shell'),409)
            self.assertEqual(request('POST','/submit',body=b'{}'),409)
            self.assertEqual(request('GET','/status?path=/etc/passwd'),409)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__=='__main__':
    unittest.main()
