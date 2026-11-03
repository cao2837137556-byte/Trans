"""Real decoder, generated PCAP, pinned Windows interpreters; no model access."""
import ctypes,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
import dpkt
import legacy_reference_executor_common_v1 as c
import legacy_reference_executor_control_v2 as fix
from issue27frontend_inheritance_outer_control_v1 import pid_alive
class LauncherFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fix.PATCH.mkdir(exist_ok=False);cls.root=fix.PATCH/'synthetic';cls.root.mkdir()
        packet=dpkt.ethernet.Ethernet(src=bytes.fromhex('020000000001'),dst=bytes.fromhex('020000000002'),type=dpkt.ethernet.ETH_TYPE_IP)
        udp=dpkt.udp.UDP(sport=1000,dport=2000,data=b'synthetic');udp.ulen=len(udp)
        ip=dpkt.ip.IP(src=bytes([10,0,0,1]),dst=bytes([10,0,0,2]),p=17,ttl=64,data=udp);ip.len=len(ip);packet.data=ip
        cls.pcap=cls.root/'generated_only.pcap'
        with cls.pcap.open('wb') as f:
            writer=dpkt.pcap.Writer(f);writer.writepkt(bytes(packet),ts=1.);writer.close()
        cls.script=cls.root/'decoder_probe.py'
        cls.script.write_text("""import sys,os,json,time,subprocess
from pathlib import Path
folder=Path(sys.argv[1]);mode=sys.argv[2];pcap=Path(sys.argv[3])
(folder/'ready.json').write_text(json.dumps(dict(pid=os.getpid(),ppid=os.getppid())),encoding='utf8')
while not (folder/'permit').exists():time.sleep(.02)
if mode=='tree':
 child=subprocess.Popen([sys.argv[4],'-c','import time;time.sleep(30)'],creationflags=subprocess.CREATE_NO_WINDOW)
 (folder/'result.json').write_text(json.dumps(dict(status='TREE_STARTED',pid=child.pid)),encoding='utf8')
 time.sleep(30)
else:
 sys.path.insert(0,sys.argv[5])
 import legacy_reference_sample_prepare_v1 as prep
 try:
  rows=list(prep.decoded_rows(dict(path=str(pcap),mode='UDP'),folder/'decoder.stderr.log'))
  result=dict(status='PASS',rows=len(rows),first_frame=rows[0]['frame.number'])
 except Exception as e:result=dict(status='FAIL',error=str(e),winerror=getattr(e,'winerror',None))
 (folder/'result.json').write_text(json.dumps(result),encoding='utf8')
""",encoding='utf8')
        cls.runtime=c.recipe()['runtime']
    def run_probe(self,name,encoder,original=False,tree=False):
        folder=self.root/name;folder.mkdir();python=self.runtime['encoder_python' if encoder else 'training_python']
        args=[python,'-B',str(self.script),str(folder),'tree' if tree else 'decode',str(self.pcap),self.runtime['training_python'],str(c.ROOT/'repo/ood')]
        with (folder/'probe.log').open('xb') as log:
            proc=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            job=(fix.OriginalJob if original else fix.Job)(proc,12*2**30)
            try:
                deadline=time.monotonic()+15
                while not (folder/'ready.json').exists():
                    self.assertLess(time.monotonic(),deadline);self.assertIsNone(proc.poll());time.sleep(.05)
                info=job.Extended();self.assertTrue(job.kernel.QueryInformationJobObject(job.handle,9,ctypes.byref(info),ctypes.sizeof(info),None))
                expected=2 if original or not encoder else 3
                self.assertEqual(info.BasicLimitInformation.ActiveProcessLimit,expected)
                self.assertEqual(info.JobMemoryLimit,12*2**30);self.assertEqual(info.ProcessMemoryLimit,12*2**30)
                self.assertEqual(info.BasicLimitInformation.LimitFlags,0x2308)
                (folder/'permit').touch()
                while not (folder/'result.json').exists():
                    self.assertLess(time.monotonic(),deadline);time.sleep(.05)
                result=c.load(folder/'result.json')
                if tree:
                    child=result['pid'];self.assertTrue(pid_alive(child));job.terminate();proc.wait(timeout=5)
                    self.assertFalse(pid_alive(child))
                else:proc.wait(timeout=15)
                c.atomic_json(folder/'receipt.json',dict(result,process_limit=expected,job_memory_bytes=int(info.JobMemoryLimit),flags=int(info.BasicLimitInformation.LimitFlags),real_model_forwards=0))
                return result
            finally:
                if proc.poll() is None:job.terminate();proc.wait(timeout=5)
                job.close()
    def test_base_python_stays_two_and_decodes(self):
        result=self.run_probe('base_two',False);self.assertEqual(result['status'],'PASS');self.assertEqual(result['rows'],1)
    def test_venv_gets_launcher_slot_and_decodes(self):
        result=self.run_probe('venv_three',True);self.assertEqual(result['status'],'PASS');self.assertEqual(result['rows'],1)
    def test_original_venv_two_reproduces_1816(self):
        result=self.run_probe('original_venv_two',True,original=True);self.assertEqual(result['status'],'FAIL');self.assertEqual(result['winerror'],1816)
    def test_fixed_venv_job_kills_descendants(self):
        result=self.run_probe('venv_tree_cleanup',True,tree=True);self.assertEqual(result['status'],'TREE_STARTED')
if __name__=='__main__':unittest.main(verbosity=2)

