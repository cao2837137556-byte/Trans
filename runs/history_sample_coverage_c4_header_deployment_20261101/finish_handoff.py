"""Bounded local receipt finalizer; no science or periodic AI monitoring."""
import json,subprocess,sys,time,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    deadline=time.monotonic()+15*60
    while time.monotonic()<deadline:
        if (HERE/'PIPELINE_ERROR.json').exists():
            (HERE/'HANDOFF_STOPPED.json').write_text(json.dumps(dict(reason='PIPELINE_ERROR',details=read(HERE/'PIPELINE_ERROR.json'))))
            return
        sub=HERE/'SUBMIT_RECEIPT.json';state=HERE/'STATE_RECEIPT.json'
        if sub.exists() and state.exists():
            submitted=read(sub);observed=read(state)
            if submitted.get('submitted') and observed.get('job_id')==submitted['job_id']:
                with urllib.request.urlopen('http://127.0.0.1:18789/',timeout=5) as r:status=r.status
                evidence=dict(progress_page_status=status,state=observed,ordinary_pipeline_only=True,continuous_AI_monitoring=False)
                (HERE/'STARTUP_VERIFICATION.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
                subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'write_handoff.py')],cwd=HERE,check=True)
                return
        time.sleep(5)
    (HERE/'HANDOFF_STOPPED.json').write_text(json.dumps(dict(reason='LOCAL_RECEIPT_FINALIZER_TIMEOUT',no_resubmission=True)))

if __name__=='__main__':main()
