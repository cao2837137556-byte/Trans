"""Standard-library Linux supervisor tests, no dataset/model imports."""
import json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import legacy_reference_executor_common_v1 as c
import legacy_reference_hpc_control_v1 as h
HELPER="""import argparse,json,time,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--run');p.add_argument('--request');a=p.parse_args()
q=json.loads(Path(a.request).read_text());out=Path(q['out']);out.mkdir()
if q.get('child'):
 child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
 (out/'child.json').write_text(json.dumps({'pid':child.pid}))
(out/'status.json').write_text(json.dumps({'done':0,'total':1,'status':'RUNNING'}))
time.sleep(q.get('sleep',0.1))
sys.exit(q.get('exit',0))
"""
@unittest.skipUnless(sys.platform=='linux','Linux process-group behavior')
class LinuxTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='reference_hpc_synthetic_'));(self.root/'requests').mkdir()
        self.helper=self.root/'helper.py';self.helper.write_text(HELPER)
    def task(self,name,**kw):return dict(name=name,out=str(self.root/name),**kw)
    def test_success_all_tasks_once(self):
        with patch.object(h,'__file__',str(self.helper)),patch.object(h,'WORKERS',2):
            got=h.jobs([self.task(str(i)) for i in range(4)],self.root,time.monotonic()+20)
        self.assertEqual(set(got),set(map(str,range(4))))
        self.assertEqual(len(list((self.root/'requests').glob('*.exit.json'))),4)
    def test_failure_kills_sibling_descendant(self):
        with patch.object(h,'__file__',str(self.helper)),patch.object(h,'WORKERS',2),self.assertRaisesRegex(c.Stop,'WORKER_FAILED'):
            h.jobs([self.task('slow',child=True,sleep=60),self.task('fail',sleep=1,exit=2)],self.root,time.monotonic()+20)
        pid=json.loads((self.root/'slow/child.json').read_text())['pid']
        stat=Path('/proc')/str(pid)/'stat'
        self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z')
        self.assertFalse((self.root/'requests/slow.exit.json').exists())
    def test_stop_before_launch(self):
        (self.root/'STOP_REQUESTED').touch()
        with self.assertRaisesRegex(c.Stop,'USER_STOP_REQUESTED'):h.jobs([self.task('never')],self.root,time.monotonic()+20)
        self.assertFalse((self.root/'never').exists())
    def test_deadline_before_launch(self):
        with self.assertRaisesRegex(c.Stop,'CHAIN_WALL_TIME_LIMIT'):h.jobs([self.task('never')],self.root,time.monotonic()-1)
        self.assertFalse((self.root/'never').exists())
    def test_monitor_tolerates_atomic_temp_disappearance(self):
        from types import SimpleNamespace
        def gone():raise FileNotFoundError('atomic temp renamed')
        vanished=SimpleNamespace(is_file=lambda:True,stat=gone)
        present=SimpleNamespace(is_file=lambda:True,stat=lambda:SimpleNamespace(st_size=123))
        folder=SimpleNamespace(rglob=lambda pattern:iter([vanished,present]))
        self.assertEqual(h.directory_bytes(folder),123)
    def test_status_replace_with_open_reader(self):
        p=self.root/'status.json';c.atomic_json(p,{'n':1})
        with p.open() as reader:
            c.atomic_json(p,{'n':2});self.assertEqual(json.load(reader),{'n':1})
        self.assertEqual(c.load(p),{'n':2})
if __name__=='__main__':unittest.main(verbosity=2)
