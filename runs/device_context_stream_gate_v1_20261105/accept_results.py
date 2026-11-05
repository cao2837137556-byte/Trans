"""Verify only small receipts returned through the existing tunnel."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def sha(n):return hashlib.sha256((HERE/n).read_bytes()).hexdigest()
def accept():
 receipt=read('TRAINING_FREEZE_RECEIPT.json');spec=read('TRAINING_SPEC_FROZEN.json');assert receipt['status']=='PASS' and sha('TRAINING_SPEC_FROZEN.json')==receipt['spec_sha256']
 assert not receipt['training_started'] and receipt['automatic_training_jobs']==0 and spec['status']=='FROZEN_TRAINING_SPEC_NOT_STARTED'
 for n,h in receipt['evidence_pins'].items():assert sha(n)==h,'EVIDENCE_SHA:'+n
 for phase in ['PREFLIGHT','FULL']:
  r=read(phase+'_RESULT.json');assert r['status']=='PASS' and not r['failures']
  assert '|COMPLETED|0:0|' in read(phase+'_SCHEDULER.json')['stdout']
 out=dict(result='PASS',impact='Stream/resource gate accepted; training specification frozen, no training run',next='Source feature admission and training-runtime gate',status='PASS',freeze_receipt_sha256=sha('TRAINING_FREEZE_RECEIPT.json'),spec_sha256=receipt['spec_sha256'])
 (HERE/'ARTIFACT_ACCEPTANCE.json').write_text(json.dumps(out,indent=2));return out
if __name__=='__main__':print(json.dumps(accept()))
