"""Real cloud regression: preserve every decoded byte while dropping raw-worker privilege."""
import hashlib,json,subprocess,sys,time,unittest
from pathlib import Path
ROOT=Path('/srv/paper04/onboarding_new_lineage_20261022_v2')
OUT=Path('/srv/paper04/onboarding_decoder_validation_20261022_v2r3')
sys.path.insert(0,str(ROOT));import onboarding_service as service
cfg=service.load();_,lc,m,_,_,_,captures=service.bindings(cfg)
OUT.mkdir(exist_ok=False)
(OUT/'decoder_profile').mkdir()
worker_cfg=dict(cfg,run=str(OUT))
import test_constrained_onboarding_integration_v1 as integ
integ.PROTOCOL=ROOT/'frozen_onboarding/protocol.json'
import test_onboarding_engineering_v2 as eng
eng.PROTOCOL=integ.PROTOCOL
names=['test_new_onboarding','test_constrained_onboarding_core_v1','test_constrained_onboarding_reference_v1','test_onboarding_engineering_v2','test_onboarding_delivery_v1']
with (OUT/'tests.log').open('x') as stream:
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
assert result.wasSuccessful(),'REGRESSION_FAILED'
import legacy_reference_sample_prepare_v1 as prep
import legacy_unsw_archival_runtime_v1 as runtime
fields=runtime.fields(prep.old.legacy_runtime())
evidence=[]
for pool,spec in captures.items():
    command=[cfg['tshark'],'-n','-r',spec['capture']['path'],'-c','64','-T','fields','-E','header=y','-E','separator=/t','-E','quote=d','-E','occurrence=f']
    for name in fields:command+=['-e',name]
    root=subprocess.run(command,capture_output=True,check=True,timeout=30)
    normal=subprocess.run(command,capture_output=True,check=True,timeout=30,**service.worker_options(worker_cfg,'raw-'+pool))
    assert root.stderr==b'Running as user "root" and group "root". This could be dangerous.\n','UNEXPECTED_ROOT_STDERR'
    assert normal.stderr==b'','UNPRIVILEGED_STDERR'
    assert root.stdout==normal.stdout and len(normal.stdout.splitlines())==65,'DECODE_OUTPUT_CHANGED'
    evidence.append(dict(pool=pool,packets=64,fields=len(fields),stdout_sha256=hashlib.sha256(normal.stdout).hexdigest(),
        stdout_bitwise_identical=True,unprivileged_stderr_bytes=0,exit_code=0))
probe='import sys,os;sys.path.insert(0,'+repr(str(ROOT))+');import onboarding_service as s;s.bindings(s.load());print(os.geteuid(),os.getegid(),os.getgroups())'
normal=subprocess.run([sys.executable,'-B','-c',probe],capture_output=True,text=True,check=True,timeout=30,**service.worker_options(worker_cfg,'raw-CIC_DEV'))
assert normal.stdout.strip()=='65534 65534 []','RAW_PYTHON_IDENTITY'
root_prefs=subprocess.run([cfg['tshark'],'-G','currentprefs'],capture_output=True,check=True,timeout=30)
plain_prefs=subprocess.run([cfg['tshark'],'-G','currentprefs'],capture_output=True,check=True,timeout=30,**service.worker_options(worker_cfg,'raw-CIC_DEV'))
# The live Cisco SSH capture helper defaults to the process username. Offline
# PCAP decoding never invokes it. Require every other preference byte identical.
old_line=b'#extcap.ciscodump.remoteusername: root\n';new_line=b'#extcap.ciscodump.remoteusername: nobody\n'
assert root_prefs.stdout.count(old_line)==plain_prefs.stdout.count(new_line)==1,'EXPECTED_EXTCAP_USERNAME'
assert root_prefs.stdout.replace(old_line,new_line)==plain_prefs.stdout and plain_prefs.stderr==b'','DECODER_PREFERENCES_CHANGED'
service.write(OUT/'PASS.json',dict(status='PASS',tests=result.testsRun,real_decodes=evidence,
    offline_dissection_preferences_identical=True,ignored_live_capture_default='extcap.ciscodump.remoteusername: root -> nobody',
    preferences_sha256=hashlib.sha256(plain_prefs.stdout).hexdigest(),
    raw_python_identity=normal.stdout.strip(),code_manifest_sha256=lc.sha(ROOT/'code_manifest.json'),
    frozen_decoder_unchanged=True,stderr_remains_strict=True,updated_epoch=time.time()))
print(json.dumps(service.b.read(OUT/'PASS.json')))
