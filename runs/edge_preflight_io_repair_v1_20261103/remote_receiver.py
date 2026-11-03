"""One new bounded preflight, reusing verified inputs without altering 181403."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'edge_linux_preflight_deployment_v1_20261103'
BASE_SHA = 'e33aae00c97ab52d8ed51a9c4650c00cea845890755f26b0ba71bf8412892a80'
SOURCE_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
SOURCE = OLD / 'remote_receiver.py'
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != BASE_SHA:
    raise ValueError('OLD_RECEIVER_SOURCE_PIN')
spec = importlib.util.spec_from_file_location('_edge_io_base_receiver', SOURCE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.DEPLOYMENT = HERE.name
base.PORT = 18819


class Receiver(base.Receiver):
    def __init__(self, config, root=base.ROOT, runner=base.subprocess.run):
        super().__init__(config, root=root, runner=runner)
        self.old = self.root / 'runs' / OLD.name
        self.incoming = self.old / 'incoming'
        self.raw = self.old / 'raw'
        self.unpack = self.old / 'unpacked'
        self.checkout = self.unpack / 'edge_preflight_checkout'
        self.receiver_source_sha256 = SOURCE_SHA

    def repair_pins(self):
        contract = base.read(self.here / 'REPAIR_CONTRACT.json')
        base.need(contract['cpu'] == 1 and contract['memory_gib'] == 6
                  and contract['wall_seconds'] == 600
                  and contract['prior_job_id'] == '181403'
                  and contract['formal_external_evaluation'] is False
                  and contract['training'] is False, 'REPAIR_SCOPE')
        base.need(set(contract['files']) == {'launch_preflight.py', 'worker.py', 'replay_io.py',
                  'remote_receiver.py', 'ACTIVE_SLICE_CARD.json'}, 'REPAIR_REQUIRED_FILES')
        for name, pin in contract['files'].items():
            base.need(base.safe_name(name).name == name, 'FLAT_REPAIR_FILE')
            path = self.here / name
            base.need(path.is_file() and path.stat().st_size == pin['bytes']
                      and base.sha(path) == pin['sha256'], 'REPAIR_FILE_PIN:' + name)
        slice_copy = self.here / 'ACTIVE_SLICE_CARD.json'
        original = self.checkout / base.PACKAGE / 'ACTIVE_SLICE_CARD.json'
        base.need(slice_copy.read_bytes() == original.read_bytes(), 'SLICE_COPY_EXACT_BYTES')
        return contract

    def ensure_prior_terminal(self):
        job = base.read(self.old / 'SUBMIT_RECEIPT.json')
        base.need(str(job['job_id']) == '181403', 'PRIOR_JOB_ID_PIN')
        result = self.runner(['sacct', '-j', '181403', '--noheader', '--parsable2',
            '--format=JobIDRaw,State,ExitCode'], capture_output=True, text=True, timeout=10)
        rows = [line.split('|') for line in result.stdout.splitlines()]
        prior = [row for row in rows if len(row) >= 3 and row[0] == '181403']
        base.need(result.returncode == 0 and len(prior) == 1
                  and prior[0][1] in ('FAILED', 'TIMEOUT', 'CANCELLED', 'COMPLETED',
                                      'OUT_OF_MEMORY', 'NODE_FAIL'), 'PRIOR_JOB_NOT_TERMINAL')
        base.write(self.here / 'PRIOR_JOB_TERMINAL.json', dict(
            prior_job_id='181403', scheduler_row=prior[0], prior_intents_preserved=True))

    def shell_environment(self):
        return (super().shell_environment()
                + 'export EDGE_FROZEN_CHECKOUT=' + shlex.quote(self.checkout.as_posix()) + '\n'
                + 'export EDGE_IO_REPAIR_DIRECTORY=' + shlex.quote(self.here.as_posix()) + '\n'
                + 'export EDGE_REPLAY_CACHE=' + shlex.quote((self.here / 'replay_cache').as_posix()) + '\n')

    def create_path_adapter(self):
        self.repair_pins()
        original = self.checkout / base.PACKAGE / 'preflight.slurm'
        base.need(base.sha(original) == '631bded8b84233eac50bdf9beb67ee0c57a86c8bb871c05a912562dcd5e8f7a1',
                  'ORIGINAL_SLURM_IDENTITY')
        adapted, replacements = base.adapt_slurm_paths(original.read_bytes(),
            self.checkout.resolve().as_posix(), self.here.resolve().as_posix())
        target = self.here / 'PREFLIGHT_PATH_ADAPTER.slurm'
        target.write_bytes(adapted)
        syntax = self.runner(['bash', '-n', str(target)], capture_output=True, text=True, timeout=10)
        base.need(syntax.returncode == 0, 'REPAIR_SLURM_SYNTAX')
        return dict(schema='EDGE_PREFLIGHT_IO_REPAIR_PATH_ADAPTER_V1',
            original_slurm_path=original.resolve().as_posix(), original_slurm_sha256=base.sha(original),
            adapter_path=target.resolve().as_posix(), adapter_sha256=base.sha(target),
            checkout_root=self.checkout.resolve().as_posix(), package_directory=self.here.resolve().as_posix(),
            replacements=replacements, resource_directives_unchanged=True)

    def validate_path_adapter(self, prepared):
        self.repair_pins()
        adapter = prepared.get('slurm_path_adapter') or {}
        original = self.checkout / base.PACKAGE / 'preflight.slurm'
        target = self.here / 'PREFLIGHT_PATH_ADAPTER.slurm'
        base.need(adapter.get('adapter_path') == target.resolve().as_posix()
                  and adapter.get('original_slurm_path') == original.resolve().as_posix()
                  and adapter.get('checkout_root') == self.checkout.resolve().as_posix()
                  and adapter.get('package_directory') == self.here.resolve().as_posix(), 'REPAIR_ADAPTER_BINDING')
        expected, replacements = base.adapt_slurm_paths(original.read_bytes(),
            self.checkout.resolve().as_posix(), self.here.resolve().as_posix())
        base.need(base.sha(original) == adapter['original_slurm_sha256']
                  and base.sha(target) == adapter['adapter_sha256']
                  and target.read_bytes() == expected
                  and replacements == adapter['replacements'], 'REPAIR_ADAPTER_CHANGED')

    def prepare(self):
        self.repair_pins()
        self.ensure_prior_terminal()
        return super().prepare()

    def submit(self):
        self.repair_pins()
        self.ensure_prior_terminal()
        return super().submit()

    def state(self):
        value = super().state()
        value.update(base_receiver_source_sha256=BASE_SHA, prior_job_id='181403',
                     repair_namespace=self.here.name, input_bytes_reused=True)
        job = value.get('job')
        if job:
            output = Path(job['output_directory'])
            for field, relative in (('replay_progress', 'real_slice/REPLAY_HEARTBEAT.json'),
                                    ('repair_worker_progress', 'real_slice/STATUS.json')):
                path = output / relative
                if path.is_file():
                    try:
                        value[field] = base.read(path)
                    except (OSError, ValueError):
                        pass
            if value.get('replay_progress'):
                value['delivery_status'] = dict(value.get('delivery_status') or {},
                                                replay=value['replay_progress'])
        return value

    def results(self):
        # The reused checkout is outside this namespace. Copy only this job's
        # scheduler logs; never make ../ archive members or export state caches.
        with self.lock:
            state = self.state()
            base.need(state['job'] and state['result_ready'], 'RESULTS_NOT_READY')
            job = state['job']
            output = Path(job['output_directory'])
            for ending in ('.out', '.err'):
                source = self.checkout / ('edge-preflight-' + job['job_id'] + ending)
                if source.is_file():
                    base.need(source.stat().st_size <= 16 * 1024**2, 'SCHEDULER_LOG_SIZE')
                    shutil.copyfile(source, self.here / source.name)
            files = [p for p in output.rglob('*') if p.is_file() and not p.is_symlink()
                     and p.suffix in ('.json', '.jsonl', '.log', '.out', '.err', '.sha256')]
            files += [p for p in self.here.iterdir() if p.is_file() and not p.is_symlink()
                      and not p.name.startswith('.') and p.suffix in ('.json', '.out', '.err')]
            members = {p.relative_to(self.here).as_posix(): p for p in set(files)}
            synthesized = []
            if not (output / 'DELIVERY_RESULT.json').is_file():
                stop = self.here / 'EXPORT_TERMINAL_WITHOUT_RESULT.json'
                base.write(stop, dict(status='STOPPED_NO_RETRY', generated_export_receipt=True,
                    reason='SCHEDULER_TERMINAL_WITHOUT_FINAL_DELIVERY_RESULT',
                    actual_delivery_result_emitted=False, scheduler=state['scheduler'],
                    job_id=job['job_id'], final_runtime_gate_pass=False,
                    formal_external_evaluation=False, automatic_retry=False))
                name = output.relative_to(self.here).as_posix() + '/DELIVERY_RESULT.json'
                members[name] = stop
                synthesized.append(name)
            base.need(all(p.resolve().is_relative_to(self.here.resolve()) and
                          p.stat().st_size <= 16 * 1024**2 for p in members.values()), 'RESULT_SCOPE_SIZE')
            base.need(sum(p.stat().st_size for p in members.values()) < base.MAX_RESULT - 1024**2,
                      'RESULT_TOTAL_SIZE')
            manifest = dict(schema='EDGE_PREFLIGHT_RESULT_EXPORT_MANIFEST_V1',
                files={name: dict(bytes=p.stat().st_size, sha256=base.sha(p))
                       for name, p in sorted(members.items())},
                synthesized_failure_receipts=synthesized, formal_external_evaluation=False)
            payload = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
            archive = self.here / 'preflight_results.tar'
            temporary = archive.with_suffix('.tmp')
            with tarfile.open(temporary, 'w') as stream:
                for name, path in sorted(members.items()):
                    stream.add(path, arcname=name, recursive=False)
                entry = tarfile.TarInfo('RESULT_MANIFEST.json')
                entry.size = len(payload)
                stream.addfile(entry, io.BytesIO(payload))
            temporary.replace(archive)
            base.need(archive.stat().st_size <= base.MAX_RESULT, 'RESULT_FINAL_SIZE')
            return archive


if __name__ == '__main__':
    base.Receiver = Receiver
    base.main(base.read(HERE / '.receiver_private.json'))
