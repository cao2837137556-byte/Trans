"""Exercise sealed Bash entry points using fake Python/sbatch only.

No production Python, decoder, model, source fitting or network command runs.
The released plan and seal are copied unchanged to a private temporary fixture.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BUNDLE = Path(os.environ.get('ONBOARDING_TEST_BUNDLE', str(HERE/'bundle')))
BASH = shutil.which('bash')
AUTHORITY = '2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@unittest.skipUnless(os.name == 'posix' and BASH and shutil.which('sha256sum'), 'POSIX Bash required')
class SubmitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'bundle'
        shutil.copytree(BUNDLE, self.root)
        self.plan_bytes = (self.root/'resource_plan.json').read_bytes()
        self.seal_bytes = (self.root/'SHA256SUMS').read_bytes()
        self.plan = json.loads(self.plan_bytes)
        self.memory, self.cpus = self.plan['memory_gib'], self.plan['cpus']
        self.bin = Path(self.temp.name)/'bin'
        self.bin.mkdir()
        fake_python = self.bin/'fake_python'
        fake_python.write_text('#!'+sys.executable+'\n'+r'''
import hashlib,json,os,pathlib,sys
root=pathlib.Path(os.environ['MOCK_ROOT'])
args=sys.argv[1:]
with open(os.environ['MOCK_PYTHON_CALLS'],'a') as stream: stream.write(json.dumps(args)+'\n')
def require(ok):
    if not ok: raise SystemExit(99)
mode=os.environ['MOCK_MODE']
resource=['repo/ood/onboarding_resources_v1.py','--plan','resource_plan.json']
if args[:3]==resource:
    require(args==resource or args==resource+['--slurm-fields'])
    plan=json.loads((root/'resource_plan.json').read_text())
    if mode=='resource_fail': raise SystemExit(31)
    if args==resource+['--slurm-fields']:
        checksum=hashlib.sha256((root/'resource_plan.json').read_bytes()).hexdigest()
        print(plan['memory_gib'],plan['cpus'],checksum)
    raise SystemExit(0)
if args==['repo/ood/onboarding_delivery_v1.py','preflight','--root',str(root)]:
    if mode=='input_preflight_fail': raise SystemExit(32)
    raise SystemExit(0)
if args==['repo/ood/onboarding_synthetic_checks_v1.py','--root',str(root),'--output',str(root/'logs/synthetic')]:
    if mode=='synthetic_fail': raise SystemExit(33)
    raise SystemExit(0)
if args==['repo/ood/onboarding_delivery_v1.py','run','--root',str(root),'--authorize-chain']:
    if mode=='run_fail': raise SystemExit(34)
    raise SystemExit(0)
if args==['repo/ood/onboarding_delivery_io_v1.py','export','--root',str(root)]:
    require((root/'experiment_exit_code.txt').is_file())
    require(not (root/'exit_code.txt').exists())
    require(not (root/'export_exit_code.txt').exists())
    override=int(os.environ.get('MOCK_EXPORT_RC','0'))
    if override: raise SystemExit(override)
    if mode=='export_fail': raise SystemExit(35)
    raise SystemExit(0)
raise SystemExit(99)
''')
        fake_python.chmod(0o755)
        fake_sbatch = self.bin/'fake_sbatch'
        fake_sbatch.write_text(r'''#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$MOCK_SBATCH_CALLS"
[[ "$#" == 4 && "$2" == "--mem=${MOCK_MEMORY}G" && "$3" == "--cpus-per-task=${MOCK_CPUS}" && "$4" == scripts/run.slurm ]] || exit 98
if [[ "$1" == --test-only ]]; then
  [[ "$MOCK_MODE" != scheduler_preflight_fail ]] || exit 9
  if [[ "$MOCK_MODE" == mutate_plan ]]; then printf ' ' >> resource_plan.json; fi
  if [[ "$MOCK_MODE" == mutate_payload ]]; then printf ' ' >> scripts/run.slurm; fi
  exit 0
fi
[[ "$1" == --parsable ]] || exit 98
[[ "${ONBOARDING_AUTHORIZED:-}" == "$MOCK_AUTHORITY" ]] || exit 97
[[ "${ONBOARDING_RESOURCE_SHA:-}" == "$MOCK_PLAN_SHA" ]] || exit 96
[[ "$MOCK_MODE" != submit_fail ]] || exit 7
if [[ "$MOCK_MODE" == ambiguous ]]; then echo unknown; exit 0; fi
echo '12345;synthetic-cluster'
''')
        fake_sbatch.chmod(0o755)
        self.python_calls = Path(self.temp.name)/'python_calls'
        self.sbatch_calls = Path(self.temp.name)/'sbatch_calls'
        self.envfile = Path(self.temp.name)/'bash_env'
        self.envfile.write_text(r'''function sbatch() { "$MOCK_SBATCH" "$@"; }
function sacct() { printf '%s\n' 'FAKE_SACCT_NO_REMOTE'; }
function source() {
  if [[ "$#" == 1 && "$1" == scripts/env.sh ]]; then
    export ONBOARDING_PYTHON="$MOCK_PYTHON"
    export PYTHONDONTWRITEBYTECODE=1
    return 0
  fi
  builtin source "$@"
}
''')
        self.env = dict(os.environ, BASH_ENV=str(self.envfile), MOCK_ROOT=str(self.root),
            MOCK_PYTHON=str(fake_python), MOCK_SBATCH=str(fake_sbatch),
            MOCK_PYTHON_CALLS=str(self.python_calls), MOCK_SBATCH_CALLS=str(self.sbatch_calls),
            MOCK_MODE='success', MOCK_MEMORY=str(self.memory), MOCK_CPUS=str(self.cpus),
            MOCK_PLAN_SHA=sha(self.root/'resource_plan.json'), MOCK_AUTHORITY=AUTHORITY)
        # Tests must not inherit a real task's submission authorization.
        self.env.pop('ONBOARDING_AUTHORIZED', None)
        self.env.pop('ONBOARDING_RESOURCE_SHA', None)

    def submit(self, *args):
        return subprocess.run([BASH,str(self.root/'scripts/submit_logged.sh'),*args],
            env=self.env,text=True,capture_output=True,timeout=30)

    def run_job(self, authorized=True):
        self.env.update(SLURM_SUBMIT_DIR=str(self.root),SLURM_JOB_ID='12345',
                        ONBOARDING_RESOURCE_SHA=sha(self.root/'resource_plan.json'))
        if authorized: self.env['ONBOARDING_AUTHORIZED']=AUTHORITY
        return subprocess.run([BASH,str(self.root/'scripts/run.slurm')],
            env=self.env,text=True,capture_output=True,timeout=30)

    def scheduler_lines(self):
        return self.sbatch_calls.read_text().splitlines() if self.sbatch_calls.exists() else []

    def python_lines(self):
        return [json.loads(line) for line in self.python_calls.read_text().splitlines()] if self.python_calls.exists() else []

    def assert_failed_without_claim(self, result):
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse((self.root/'submit_claim').exists())
        self.assertFalse((self.root/'job.id').exists())

    def test_no_wrong_or_extra_authority(self):
        for arguments in [(),('--not-authorized',),('--authorize-chain','extra')]:
            with self.subTest(arguments=arguments):
                self.assert_failed_without_claim(self.submit(*arguments))
                self.assertEqual(self.scheduler_lines(),[])
                self.assertEqual(self.python_lines(),[])

    def test_sealed_production_plan_drives_both_scheduler_calls(self):
        declared={line.split('  ',1)[1]:line.split('  ',1)[0]
                  for line in self.seal_bytes.decode().splitlines()}
        self.assertEqual(declared['resource_plan.json'],sha(self.root/'resource_plan.json'))
        result=self.submit('--authorize-chain')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((self.root/'job.id').read_text().strip(),'12345')
        allocation='--mem=%sG --cpus-per-task=%s scripts/run.slurm'%(self.memory,self.cpus)
        self.assertEqual(self.scheduler_lines(),['--test-only '+allocation,'--parsable '+allocation])
        self.assertEqual((self.root/'resource_plan.json').read_bytes(),self.plan_bytes)
        self.assertEqual((self.root/'SHA256SUMS').read_bytes(),self.seal_bytes)
        self.assertEqual(self.python_lines(),[
            ['repo/ood/onboarding_resources_v1.py','--plan','resource_plan.json','--slurm-fields'],
            ['repo/ood/onboarding_delivery_v1.py','preflight','--root',str(self.root)]])

    def test_duplicate_submission_does_not_reach_scheduler(self):
        self.assertEqual(self.submit('--authorize-chain').returncode,0)
        self.assertNotEqual(self.submit('--authorize-chain').returncode,0)
        self.assertEqual(len(self.scheduler_lines()),2)

    def test_submit_failure_retains_claim(self):
        self.env['MOCK_MODE']='submit_fail'
        self.assertNotEqual(self.submit('--authorize-chain').returncode,0)
        self.assertTrue((self.root/'submit_claim').is_dir())
        self.assertFalse((self.root/'job.id').exists())
        self.assertNotEqual(self.submit('--authorize-chain').returncode,0)
        self.assertEqual(len(self.scheduler_lines()),2)

    def test_ambiguous_submit_retains_claim(self):
        self.env['MOCK_MODE']='ambiguous'
        self.assertNotEqual(self.submit('--authorize-chain').returncode,0)
        self.assertTrue((self.root/'submit_claim').is_dir())
        self.assertFalse((self.root/'job.id').exists())
        self.assertNotEqual(self.submit('--authorize-chain').returncode,0)
        self.assertEqual(len(self.scheduler_lines()),2)

    def test_resource_rejection_does_not_reach_preflight_or_scheduler(self):
        self.env['MOCK_MODE']='resource_fail'
        self.assert_failed_without_claim(self.submit('--authorize-chain'))
        self.assertEqual(self.scheduler_lines(),[])
        self.assertEqual(len(self.python_lines()),1)

    def test_input_preflight_failure_does_not_reach_scheduler(self):
        self.env['MOCK_MODE']='input_preflight_fail'
        self.assert_failed_without_claim(self.submit('--authorize-chain'))
        self.assertEqual(self.scheduler_lines(),[])
        self.assertEqual(len(self.python_lines()),2)

    def test_scheduler_preflight_failure_does_not_claim(self):
        self.env['MOCK_MODE']='scheduler_preflight_fail'
        self.assert_failed_without_claim(self.submit('--authorize-chain'))
        self.assertEqual(len(self.scheduler_lines()),1)

    def test_resource_drift_after_scheduler_preflight_does_not_submit(self):
        self.env['MOCK_MODE']='mutate_plan'
        self.assert_failed_without_claim(self.submit('--authorize-chain'))
        self.assertEqual(len(self.scheduler_lines()),1)

    def test_payload_drift_after_scheduler_preflight_does_not_submit(self):
        self.env['MOCK_MODE']='mutate_payload'
        self.assert_failed_without_claim(self.submit('--authorize-chain'))
        self.assertEqual(len(self.scheduler_lines()),1)

    def test_tampered_payload_does_not_call_python_or_scheduler(self):
        with (self.root/'scripts/run.slurm').open('a') as stream: stream.write(' ')
        self.assert_failed_without_claim(self.submit('--authorize-chain'))
        self.assertEqual(self.python_lines(),[])
        self.assertEqual(self.scheduler_lines(),[])

    def test_existing_run_or_claim_does_not_call_python_or_scheduler(self):
        for relative in ('runs/onboarding','submit_claim'):
            path=self.root/relative; path.mkdir(parents=True)
            self.assertNotEqual(self.submit('--authorize-chain').returncode,0)
            self.assertEqual(self.python_lines(),[])
            self.assertEqual(self.scheduler_lines(),[])
            path.rmdir()

    def test_run_orders_synthetic_before_real_entry_and_exports(self):
        result=self.run_job()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.python_lines(),[
            ['repo/ood/onboarding_resources_v1.py','--plan','resource_plan.json'],
            ['repo/ood/onboarding_synthetic_checks_v1.py','--root',str(self.root),'--output',str(self.root/'logs/synthetic')],
            ['repo/ood/onboarding_delivery_v1.py','run','--root',str(self.root),'--authorize-chain'],
            ['repo/ood/onboarding_delivery_io_v1.py','export','--root',str(self.root)]])
        self.assertEqual((self.root/'exit_code.txt').read_text().strip(),'0')
        self.assertEqual(self.scheduler_lines(),[])

    def test_run_without_authority_never_checks_or_executes_models(self):
        result=self.run_job(authorized=False)
        self.assertEqual(result.returncode,2)
        self.assertEqual(self.python_lines(),[
            ['repo/ood/onboarding_delivery_io_v1.py','export','--root',str(self.root)]])

    def test_run_synthetic_failure_blocks_real_entry_and_exports_failure(self):
        self.env['MOCK_MODE']='synthetic_fail'
        result=self.run_job()
        self.assertEqual(result.returncode,33,result.stdout+result.stderr)
        self.assertEqual((self.root/'exit_code.txt').read_text().strip(),'33')
        calls=self.python_lines()
        self.assertEqual(len(calls),3)
        self.assertFalse(any(c[:2]==['repo/ood/onboarding_delivery_v1.py','run'] for c in calls))
        self.assertEqual(calls[-1][:2],['repo/ood/onboarding_delivery_io_v1.py','export'])

    def test_run_failure_is_preserved_through_export(self):
        self.env['MOCK_MODE']='run_fail'
        result=self.run_job()
        self.assertEqual(result.returncode,34,result.stdout+result.stderr)
        self.assertEqual((self.root/'exit_code.txt').read_text().strip(),'34')
        self.assertEqual(self.python_lines()[-1][:2],['repo/ood/onboarding_delivery_io_v1.py','export'])

    def assert_exit_receipts(self, result, experiment, export, final):
        self.assertEqual(result.returncode,final,result.stdout+result.stderr)
        for name,value in [('experiment_exit_code.txt',experiment),
                           ('export_exit_code.txt',export),('exit_code.txt',final)]:
            self.assertEqual((self.root/name).read_text().strip(),str(value),name)

    def test_success_records_both_statuses_and_final_zero(self):
        self.assert_exit_receipts(self.run_job(),0,0,0)

    def test_export_failure_after_success_fails_job(self):
        self.env['MOCK_MODE']='export_fail'
        result=self.run_job()
        self.assert_exit_receipts(result,0,35,35)
        self.assertIn('EXPORT_FAILED',result.stderr)
        self.assertEqual(sum(c[:2]==['repo/ood/onboarding_delivery_v1.py','run'] for c in self.python_lines()),1)

    def test_experiment_failure_with_successful_export_preserves_failure(self):
        self.env['MOCK_MODE']='run_fail'
        self.assert_exit_receipts(self.run_job(),34,0,34)

    def test_simultaneous_failures_preserve_experiment_and_record_export(self):
        self.env.update(MOCK_MODE='run_fail',MOCK_EXPORT_RC='35')
        self.assert_exit_receipts(self.run_job(),34,35,34)

    def test_status_write_failure_cannot_report_success(self):
        (self.root/'exit_code.txt').mkdir()
        # The fake exporter checks receipt ordering; bypass only that fixture
        # check because this directory deliberately simulates an output I/O error.
        fake_python=Path(self.env['MOCK_PYTHON'])
        source=fake_python.read_text().replace("require(not (root/'exit_code.txt').exists())",'pass')
        fake_python.write_text(source)
        result=self.run_job()
        self.assertEqual(result.returncode,74,result.stdout+result.stderr)
        self.assertEqual((self.root/'experiment_exit_code.txt').read_text().strip(),'0')
        self.assertEqual((self.root/'export_exit_code.txt').read_text().strip(),'0')
        self.assertIn('STATUS_WRITE_FAILED',result.stderr)

    def test_bash_syntax_and_plan_controls_allocations(self):
        for path in sorted((self.root/'scripts').iterdir()):
            if path.is_file():
                result=subprocess.run([BASH,'-n',str(path)],env=self.env,text=True,capture_output=True,timeout=20)
                self.assertEqual(result.returncode,0,str(path)+'\n'+result.stderr)
                self.assertNotIn(b'\r',path.read_bytes())
        slurm=(self.root/'scripts/run.slurm').read_text()
        self.assertNotIn('#SBATCH --mem=',slurm)
        self.assertNotIn('#SBATCH --cpus-per-task=',slurm)
        self.assertIn('#SBATCH --time=1-00:00:00',slurm)
        self.assertIn('#SBATCH --no-requeue',slurm)
        self.assertEqual(self.scheduler_lines(),[])


if __name__=='__main__': unittest.main()
