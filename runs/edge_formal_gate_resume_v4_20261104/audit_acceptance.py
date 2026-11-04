"""Revalidate actual downloaded results and regression-test archive SHA reporting."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
from unittest.mock import patch
import pipeline
sys.path.insert(1,str(Path(__file__).resolve().parent.parent/'edge_formal_execution_v4_20261104'))
from runtime_control import current_status
from preflight_acceptance import inspect
HERE=Path(__file__).resolve().parent
read=pipeline.read
sha=pipeline.sha

def main():
    archive=HERE/'.private/results.tar';payload=archive.read_bytes();digest=hashlib.sha256(payload).hexdigest()
    manifest=read(HERE/'retrieved/RESULT_MANIFEST.json')
    with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
        members=pipeline.transport.safe_members(tar)
        assert {m.name for m in members}==set(manifest['files'])|{'RESULT_MANIFEST.json'}
        for m in members:
            assert m.isfile()
            body=tar.extractfile(m).read();local=HERE/'retrieved'/m.name
            assert body==local.read_bytes()
            if m.name in manifest['files']:
                pin=manifest['files'][m.name];assert len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256']
    card=read(HERE/'ENGINEERING_CARD.json');job=manifest['job'];assert job['job_id']=='181905'
    out=HERE/'retrieved/outputs/gate_181905';current=current_status(out,card_sha256=sha(HERE/'ENGINEERING_CARD.json'))
    assert current['status']=='PASS' and current['cleanup_complete'] is True
    c=read(out/'engineering_attempts'/current['attempt_id']/'CANDIDATE.json')
    assert c['runtime_identity']==card['runtime_identity'] and c['logical_spool_rows']==64124
    assert c['shape_count']==len(c['throughput'])==73 and len({tuple(x['shape']) for x in c['throughput']})==73
    assert c['complete_roles']==['NORMAL','HTTP','UDP']
    for role,total in [('NORMAL',1629749),('HTTP',229142),('UDP',3215732)]:
        v=c['replay_coverage'][role];assert v['last_frame']==v['expected_records']==total
        assert all(v[k] is True for k in ('generator_exhausted','final_raw_identity_pass','replay_to_eof'))
        assert v['raw_sha256']==read(HERE/'DELIVERY.json')['raw_inputs'][role]['sha256']
    r=c['recovery'];assert r['actual_process_exit']==75 and r['committed_files_byte_identical'] and r['reused_rows']==r['new_rows']==16 and r['committed_files']==15
    parity=c['source_cached_head_parity'];assert parity['source_saved_max_absolute_error']==parity['cache_vs_old_max_absolute_error']==0
    assert parity['source_saved_four_head_decision_exact'] and parity['cache_vs_old_four_head_decision_exact']
    assert c['synthetic_distance']['data']=='SYNTHETIC_ONLY_NO_EXTERNAL_FEATURES'
    assert c['external_quality_computed'] is False and c['evaluation_authorized'] is False
    resumed=read(out/'replay_checkpoints/UDP/LAST_ATTEMPT.json')
    assert resumed==dict(numerical_frames_appended=338124,resume_from_frame=2877608,selected_saved=20000)
    pre=read(HERE/'retrieved/PREFLIGHT_ACCEPTANCE.json');prejob=dict(pre['job'],output_directory=str(HERE/'retrieved/outputs/preflight_181902'))
    inspect(HERE/'retrieved',HERE/'ENGINEERING_CARD.json',prejob,pre['scheduler'])
    actual=read(HERE/'retrieved/outputs/preflight_181902/prior_checkpoint_probe/RESULT.json')
    assert actual['status']=='PASS_REAL_PRIOR_CHECKPOINT_RESTORE' and actual['resume_from_frame']==2877608 and actual['numerical_frames_appended']==2972 and actual['source_unchanged']
    row=[r.split('|') for r in manifest['scheduler']['stdout'].splitlines() if r.startswith('181905|')][0]
    assert row[1:4]==['COMPLETED','0:0','00:44:17'] and row[5:8]==['1','8G','06:00:00']
    assert current['resources']['max_tree_rss_bytes']<=8*1024**3
    original=HERE/'validation_history/FINAL_ACCEPTANCE_ORIGINAL.json';original.parent.mkdir(exist_ok=True)
    if not original.exists():original.write_bytes((HERE/'FINAL_ACCEPTANCE.json').read_bytes())
    # Actual artifact replay exercises the entire retrieval path including the
    # preflight file loop which previously shadowed the archive digest.
    class Response(io.BytesIO):
        def getheader(self,name):return {'Content-Length':str(len(payload)),'X-Content-SHA256':digest}[name]
    class Connection:
        def close(self):pass
    state=dict(job=job,status='COMPLETED',scheduler=manifest['scheduler'])
    with patch.object(pipeline,'request',return_value=(Connection(),Response(payload))):
        final=pipeline.retrieve(state)
    assert final['status']=='PASS' and final['result_archive']['sha256']==digest
    assert digest!=list(pre['files'].values())[-1]
    v=dict(status='PASS_VERIFIED_ENGINEERING_ACCEPTANCE',job_id='181905',preflight_job_id='181902',gate_elapsed='00:44:17',preflight_elapsed='00:13:31',cpu=1,memory_limit_gib=8,observed_peak_rss_bytes=current['resources']['max_tree_rss_bytes'],logical_spool_rows=64124,encoder_shape_probes=73,actual_resume=resumed,encoded_recovery_byte_exact=True,source_saved_CAL_max_error=0,cleanup_complete=True,artifact_members_verified=len(manifest['files']),archive=dict(bytes=len(payload),sha256=digest),local_receipt_metadata_repair=dict(reason='archive digest shadowed by preflight file digest loop; original download check succeeded',original_receipt_sha256=sha(original),corrected_receipt_sha256=sha(HERE/'FINAL_ACCEPTANCE.json'),regression='PASS_actual_downloaded_archive_retrieval_replay'),formal_external_evaluation=False,full_64124_row_encoding_completed=False)
    pipeline.write(HERE/'VERIFIED_ACCEPTANCE.json',v);print(json.dumps(v,ensure_ascii=False))
if __name__=='__main__':main()
