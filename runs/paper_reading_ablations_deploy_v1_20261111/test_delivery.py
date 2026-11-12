import importlib.util,json,tempfile,types,hashlib,base64
from pathlib import Path
HERE=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/'project';h=root/'runs'/HERE.name;h.mkdir(parents=True);science=root/'runs/paper_reading_ablations_v2_20261111';result=science/'results';result.mkdir(parents=True)
    (h/'receiver.py').write_bytes((HERE/'receiver.py').read_bytes());(h/'.private.json').write_text(json.dumps(dict(token='synthetic')))
    sp=importlib.util.spec_from_file_location('isolated_receiver',h/'receiver.py');r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
    assert r.state()['stage']=='SUBMITTED'
    (h/'JOB.json').write_text(json.dumps(dict(job_id='123')));r.subprocess.run=lambda *a,**kw:types.SimpleNamespace(stdout='123|RUNNING|0:0|00:01:00||1|8G\n')
    assert r.state()['stage']=='RUNNING'
    for name in ['guard','exponent']:
        (result/name).mkdir();(result/name/'METRICS.json').write_text('{}');(result/name/'changed.jsonl.gz').write_bytes(b'large-data-stays-remote')
    assert not any('/METRICS.json' in n for n in r.receipts()['files'])
    (result/'guard/COMPLETE.json').write_text('{"status":"PASS"}')
    files=r.receipts()['files'];assert 'results/guard/METRICS.json' in files and 'results/exponent/METRICS.json' not in files
    assert not any(n.endswith('.gz') or '.private' in n for n in files)
    for n,v in files.items():assert hashlib.sha256(base64.b64decode(v['base64'])).hexdigest()==v['sha256']
    (result/'STOP.json').write_text('{"error":"synthetic"}');assert r.state()['stage']=='STOP'
(HERE/'LOCAL_DELIVERY_CHECK.json').write_text(json.dumps(dict(status='PASS',science_unchanged=True,per_item_complete_before_retrieval=True,large_changed_uid_files_excluded=True,receipt_sha_verified=True,scheduler_stop_distinguished=True,scope='synthetic receiver test only'),indent=2));print('LOCAL_DELIVERY_PASS')
