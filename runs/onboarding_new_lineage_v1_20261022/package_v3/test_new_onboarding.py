"""Binding failure cases for the new bridge; original algorithm tests remain unchanged."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import onboarding_service as service
import new_onboarding_adapter as adapter
import backup_chunks as b

class BoundaryTests(unittest.TestCase):
    def test_raw_worker_drops_user_group_and_supplementary_groups(self):
        config=dict(raw_worker_uid=65534,raw_worker_gid=65534,run='/tmp/test-run')
        before=dict(os.environ);options=service.worker_options(config,'raw-CIC_DEV')
        env=options.pop('env')
        self.assertEqual(options,dict(user=65534,group=65534,extra_groups=[],umask=0o022))
        self.assertEqual(env['WIRESHARK_CONFIG_DIR'],str(Path(config['run'])/'decoder_profile'))
        self.assertEqual(dict(os.environ),before)
        self.assertEqual(service.worker_options(config,'evaluate'),{})
        for bad in (dict(raw_worker_uid=0,raw_worker_gid=65534),dict(raw_worker_uid=65534,raw_worker_gid=0)):
            with self.assertRaisesRegex(RuntimeError,'NON_ROOT_RAW_ID_REQUIRED'):
                service.worker_options(bad,'raw-UNSW_DEV')

    def test_absent_regression_never_becomes_complete_system_pass(self):
        result=dict(status='COMPLETE',optimizer_updates=0,automatic_model_selection=False,
            scientific_decisions={p:dict(status='INSUFFICIENT_EVIDENCE') for p in ('OLD_BANK','B0','B1','B2')})
        service.validate_result(result)
        for mutation in ('PASS','training','selection','missing'):
            bad=copy.deepcopy(result)
            if mutation=='PASS':bad['scientific_decisions']['B2']['status']='PASS'
            if mutation=='training':bad['optimizer_updates']=1
            if mutation=='selection':bad['automatic_model_selection']=True
            if mutation=='missing':del bad['scientific_decisions']['B0']
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):service.validate_result(bad)

    def test_endpoint_cache_and_data_isolation_and_weight_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td);folder=run/'endpoints/QUERY_TAIL_27';folder.mkdir(parents=True)
            audit=run/'endpoint_audits/QUERY_TAIL_27';audit.mkdir(parents=True)
            (folder/'head.npz').write_bytes(b'weights');(folder/'SHA256SUMS').write_bytes(b'seal');(run/'cache_binding.json').write_text('{}')
            evidence=dict(lineage='NEW_RECONSTRUCTION_LINEAGE',arm='QUERY_TAIL',seed=27,
                cache_binding_sha256=b.sha(run/'cache_binding.json'),feature_manifest_sha256='new-f',normalizer_manifest_sha256='new-n',
                historical_weights_or_scores_used=False,CAL_used=False,DEV_used=False,reference_used=False,synthetic_only=False,
                head_sha256=b.sha(folder/'head.npz'),endpoint_seal_sha256=b.sha(folder/'SHA256SUMS'))
            receipt=dict(arm='QUERY_TAIL',seed=27);binding=dict(marker=dict(feature_manifest_sha256='new-f',normalizer_manifest_sha256='new-n'))
            def pin(p,d):b.require(b.sha(p)==d,'PIN')
            lc=SimpleNamespace(read=b.read,sha=b.sha,require=b.require,pin=pin,LINEAGE='NEW_RECONSTRUCTION_LINEAGE')
            def check(v):
                (audit/'lineage.json').write_text(json.dumps(v))
                return adapter.validate_endpoint_binding(folder,binding,dict(endpoints=[receipt]),receipt,lc)
            check(evidence)
            for field in ('feature_manifest_sha256','normalizer_manifest_sha256','cache_binding_sha256','historical_weights_or_scores_used','CAL_used','DEV_used','reference_used'):
                bad=copy.deepcopy(evidence);bad[field]='old' if isinstance(bad[field],str) else True
                with self.subTest(field=field),self.assertRaises(RuntimeError):check(bad)
            (folder/'head.npz').write_bytes(b'tampered')
            with self.assertRaises(RuntimeError):check(evidence)

if __name__=='__main__':unittest.main()
