"""Generated supervisor fixtures in an isolated, lightweight controller process."""
import os
from pathlib import Path
import subprocess
import sys
import time
import issue27frontend_transfer_support_v1 as s


def run():
    mode,out,behavior,seconds = sys.argv[1],Path(sys.argv[2]),sys.argv[3],float(sys.argv[4])
    base = (s.ROOT/'tmp/task_knowledge_transfer_synthetic_v1').resolve()
    s.require(base in out.resolve().parents, 'GENERATED_FIXTURE_DIRECTORY_ONLY')
    if mode == 'supervise':
        import issue27frontend_transfer_control_v1 as control
        command = [str(s.PYTHON),'-B',str(Path(__file__).resolve()),'worker',str(out),behavior,str(seconds)]
        result = control.supervise('P',out,dict(seconds=seconds,memory=2*1024**3,output=8*1024**2),command,synthetic=True)
        print(s.canonical(result).decode('utf-8'));return
    deadline = time.monotonic()+30
    while not (out/'worker_gate.json').exists():
        s.require(time.monotonic() < deadline, 'FIXTURE_GATE_TIMEOUT');time.sleep(.05)
    gate = s.read_json(out/'worker_gate.json')
    s.require(gate['pid'] == os.getpid() and gate['parent_pid'] == os.getppid(), 'FIXTURE_GATE')
    if behavior == 'hang':
        time.sleep(30);return
    if behavior == 'missing':
        return
    if behavior == 'child':
        try:
            subprocess.run([sys.executable,'-c','pass'],check=True)
        except OSError:
            pass
        else:
            raise RuntimeError('single-worker Job allowed another process')
    if behavior == 'numeric':
        import issue27frontend_transfer_model_v1 as m
        m.configure()
        import torch
        model=m.Student()
        model([torch.zeros(2,131)],['generated'])
    (out/'generated.txt').write_text('synthetic only',encoding='utf-8')
    h=s.sha(out/'generated.txt')
    s.atomic_json(out/'worker_terminal.json',dict(status='WORK_COMPLETE_VERIFIED',stage='P',recipe_sha256=s.RECIPE_SHA,output_hashes={'generated.txt':h}))
    if behavior == 'corrupt':
        (out/'generated.txt').write_text('tampered',encoding='utf-8')


if __name__ == '__main__':
    run()
