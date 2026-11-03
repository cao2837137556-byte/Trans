"""Source-only B1/B16-clone numerical diagnostic; default is a no-forward dry-run."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import threading
import time

ROW_BYTES = 768*4
ORIGINAL_SHA = 'ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120'
ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
ORIGINAL = ROOT/'runs/dense_reference_matrix_v1_20261027'
NUMPY = ROOT/'runs/dense_reference_launch_repair_v1_20261027/runtime/job_179536/science/runtime/numpy201'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
CHECKPOINT = ROOT/'assets/model.safetensors'
OUTPUT_ROOT = ROOT/'runs/dense_reference_original104_batch_diagnostic_v1_20261027_runtime'
LIMITS = dict(slurm_cpus=4, slurm_memory_gib=16, wall_seconds=600, rss_gib=8, output_mib=256, min_free_gib=1)


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    temp = path.with_name(path.name+'.tmp')
    with temp.open('wb') as stream:
        stream.write(canonical(value)+b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def verify_seal(root, name='PACKAGE_SHA256SUMS', expected_sha=None, ignored=('.private','validation')):
    root = Path(root).resolve()
    raw = (root/name).read_bytes()
    if expected_sha is not None:
        require(digest(raw) == expected_sha, 'PACKAGE_MANIFEST_IDENTITY')
    entries = {}
    for line in raw.decode().splitlines():
        checksum, relative = line.split('  ', 1)
        path = PurePosixPath(relative)
        require(len(checksum) == 64 and set(checksum) <= set('0123456789abcdef') and
            not path.is_absolute() and '..' not in path.parts and '\\' not in relative and ':' not in relative and
            str(path) == relative and relative not in entries and relative != name, 'SEALED_PATH_OR_DIGEST')
        entries[relative] = checksum
    actual = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if relative.parts[0] in ignored or '__pycache__' in relative.parts:
            continue
        require(not path.is_symlink(), 'SEALED_SYMLINK')
        if path.is_file() and relative.as_posix() != name:
            actual.add(relative.as_posix())
    require(actual == set(entries), 'SEALED_MEMBER_SET')
    for relative, checksum in entries.items():
        require(sha(root/relative) == checksum, 'SEALED_MEMBER_SHA:'+relative)
    return digest(raw)


def load_inputs(package):
    package = Path(package).resolve()
    seal = verify_seal(package)
    manifest = read(package/'manifest.json')
    require(manifest.get('schema') == 'paper04-source8-batch-size-diagnostic-v1' and
            manifest.get('scope') == 'SOURCE_REFERENCE8_B1_B16_CLONE_ONLY' and
            manifest.get('previous_job_id') == '179536' and manifest.get('anchor_count') == 8 and
            manifest.get('clone_count') == 16 and manifest.get('maximum_forward_positions') == 136 and
            manifest.get('limits') == LIMITS and manifest.get('real_execution_authorized') is False,
            'FIXED_DIAGNOSTIC_CONTRACT')
    for key in ('no_training','no_production_bank','no_source_cal','no_target_evaluation','no_automatic_variant'):
        require(manifest.get(key) is True, 'DIAGNOSTIC_SCOPE_ONLY')
    for relative, checksum in manifest['data_files'].items():
        require(relative in ('data/ANCHOR8.jsonl','data/EXPECTED8.f32','data/RUNTIME_179536.json') and sha(package/relative) == checksum,
                'DATA_IDENTITY')
    anchors = manifest['anchors']
    require(len(anchors) == 8 and len({a['uid'] for a in anchors}) == 8, 'EIGHT_UNIQUE_SOURCE_UIDS')
    for anchor in anchors:
        identity = anchor['source_identity']
        require(anchor.get('role') == 'SOURCE_REFS' and identity.get('use') == 'REFERENCE' and
                identity.get('partition') == 'LEARN' and anchor.get('original_batch_size') == 16,
                'SOURCE_REFERENCE_ONLY')
        require('label' not in identity and 'score' not in identity, 'NO_LABELS_OR_SCORES')
    rows = [json.loads(line) for line in (package/'data/ANCHOR8.jsonl').read_text().splitlines()]
    require(len(rows) == 8 and [r['uid'] for r in rows] == [a['uid'] for a in anchors] and
            all(set(r) == {'uid','flow','provenance'} for r in rows), 'FIXED_SOURCE_SNAPSHOT_ORDER')
    raw = (package/'data/EXPECTED8.f32').read_bytes()
    require(len(raw) == 8*ROW_BYTES, 'EXPECTED_F32_SHAPE')
    expected = []
    for i, (anchor, row) in enumerate(zip(anchors, rows)):
        require(digest(canonical(row['flow'])) == anchor['flow_sha256'] and
                digest(canonical(row['provenance'])) == anchor['provenance_sha256'], 'FLOW_PROVENANCE_IDENTITY')
        values = raw[i*ROW_BYTES:(i+1)*ROW_BYTES]
        require(digest(values) == anchor['expected_old_feature_sha256'], 'EXPECTED_UID_FEATURE_BYTES')
        expected.append(values)
    return manifest, rows, expected, seal


def authorize(value, seal, manifest_sha):
    require(isinstance(value, dict) and value.get('user_authorized') is True and
        value.get('scope') == 'SOURCE_REFERENCE8_B1_B16_CLONE_DIAGNOSTIC_ONLY' and
        value.get('package_sha256') == seal and value.get('manifest_sha256') == manifest_sha and
        value.get('previous_numerical_stop_job') == '179536' and value.get('maximum_forward_positions') == 136 and
        value.get('limits') == LIMITS and value.get('production_encode') is False and
        value.get('source_cal') is False and value.get('target_evaluation') is False and
        value.get('automatic_retry') is False and value.get('retries') == 0 and bool(value.get('evidence')),
        'NEW_EXPLICIT_DIAGNOSTIC_AUTHORIZATION_REQUIRED')


def observe_fixed(manifest, snapshots, expected, output, engine, guard=lambda:None):
    """All eight B1 controls must pass before any B16 diagnostic forward."""
    output = Path(output)
    forward_positions = 0
    observations = []
    def one(anchor, snapshot, size, mode):
        nonlocal forward_positions
        guard()
        batch, hashes = engine.prepare(anchor, snapshot, size)
        require(len(hashes) == size and all(h == anchor['observed_hpc_b1_tensor_sha256'] for h in hashes),
                'FAILED_HPC_TENSOR_IDENTITY:'+anchor['uid']+':'+mode)
        values = engine.forward(batch)
        forward_positions += size
        require(len(values) == size and all(isinstance(v, bytes) and len(v) == ROW_BYTES for v in values),
                'DIAGNOSTIC_F32_SCHEMA')
        raw = b''.join(values)
        filename = anchor['uid']+'.'+mode+'.diagnostic.f32'
        with (output/filename).open('xb') as stream:
            stream.write(raw)
        record = dict(uid=anchor['uid'], mode=mode, forward_positions=size, tensor_sha256=hashes,
            feature_sha256=[digest(v) for v in values], observation_file=filename,
            observation_sha256=digest(raw), diagnostic_only=True, production_reuse_prohibited=True)
        observations.append(record)
        write(output/'OBSERVATIONS.json', dict(observations=observations, total_forward_positions=forward_positions))
        guard()
        return values, record
    for anchor, snapshot in zip(manifest['anchors'], snapshots):
        values, record = one(anchor, snapshot, 1, 'B1')
        require(digest(values[0]) == anchor['observed_hpc_b1_feature_sha256'],
                'FAILED_HPC_B1_FEATURE_NOT_REPRODUCED_STOP:'+anchor['uid'])
        record['failed_hpc_control_reproduced'] = True
    matches = []
    for anchor, snapshot, old in zip(manifest['anchors'], snapshots, expected):
        values, record = one(anchor, snapshot, 16, 'B16_CLONE')
        require(all(v == values[0] for v in values), 'B16_CLONES_NOT_BYTE_IDENTICAL:'+anchor['uid'])
        record['all_16_clones_byte_equal'] = True
        record['old_feature_bytes_equal'] = values[0] == old
        matches.append(dict(uid=anchor['uid'], old_feature_bytes_equal=values[0] == old))
    require(forward_positions == 136, 'EXACT_DIAGNOSTIC_FORWARD_BUDGET')
    write(output/'OBSERVATIONS.json', dict(observations=observations, total_forward_positions=forward_positions))
    return dict(status='COMPLETE', diagnostic_only=True, original_cohort_restored=False,
        b1_reproduction_controls='8/8 EXACT', b16_clone_old_matches=sum(m['old_feature_bytes_equal'] for m in matches),
        b16_clone_all_old_bytes_equal=all(m['old_feature_bytes_equal'] for m in matches), per_uid=matches,
        forward_positions=136, unique_source_uids=8, new_production_positions=0, source_cal=False,
        target_evaluation=False, retries=0, automatic_variant=False, production_reuse_prohibited=True)


class RealEngine:
    def __init__(self, manifest, output):
        require(sys.platform == 'linux' and sys.version.split()[0] == '3.11.11' and sys.byteorder == 'little',
                'FIXED_LINUX_RUNTIME_REQUIRED')
        require(Path(sys.executable).resolve() == Path(PYTHON).resolve(), 'FIXED_PYTHON_EXECUTABLE')
        spec = manifest['runtime']
        require(spec['original_root'] == str(ORIGINAL) and spec['numpy_overlay'] == str(NUMPY) and
                spec['checkpoint'] == str(CHECKPOINT) and spec['python'] == PYTHON,
                'FIXED_READONLY_RUNTIME_PATHS')
        require(sys.version == spec['python_full'] and
                sha(spec['reference_environment_remote_file']) == spec['reference_environment_sha256'],
                'FAILED_HPC_RUNTIME_RECEIPT_IDENTITY')
        verify_seal(ORIGINAL, expected_sha=ORIGINAL_SHA, ignored=('.private','runtime','local_progress'))
        require(sha(CHECKPOINT) == spec['checkpoint_sha256'], 'CHECKPOINT_IDENTITY')
        for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            require(os.environ.get(key) == '4', 'THREAD_ENVELOPE')
        require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1',
                'CPU_ONLY_AND_READONLY_IMPORTS')
        sys.dont_write_bytecode = True
        vendor = ORIGINAL/'vendor/encoding_v2'
        sys.path[:0] = [str(NUMPY), str(ROOT/'environment/vendor_py311_v1'), str(vendor/'repo/ood')]
        import numpy as np
        import torch
        require(Path(np.__file__).resolve().is_relative_to(NUMPY.resolve()), 'FIXED_NUMPY_OVERLAY_NOT_IMPORTED')
        locations = {}
        for name, version in spec['versions'].items():
            module = importlib.import_module(name)
            distribution_version = importlib.metadata.version(name.replace('_','-'))
            actual = getattr(module, '__version__', distribution_version)
            require(actual.split('+')[0] == version and distribution_version.split('+')[0] == version,
                    'RUNTIME_VERSION:'+name)
            path = Path(module.__file__).resolve()
            allowed = (NUMPY, ROOT/'environment/vendor_py311_v1', Path(PYTHON).parent.parent/'lib/python3.11/site-packages')
            require(any(path.is_relative_to(root.resolve()) for root in allowed), 'RUNTIME_IMPORT_LOCATION:'+name)
            require(str(path) == spec['import_identities'][name]['path'], 'FAILED_HPC_IMPORT_LOCATION:'+name)
            locations[name] = dict(version=actual, path=str(path), module_file_sha256=sha(path))
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        require(torch.__version__ == spec['torch_full_version'] and
                digest(torch.__config__.show().encode()) == spec['torch_config_sha256'] and
                torch.backends.cpu.get_cpu_capability() == spec['cpu_capability'], 'FAILED_HPC_BUILD_IDENTITY')
        runtime = Path(output)/'private_model_runtime'
        shutil.copytree(vendor/'runtime', runtime)
        (runtime/'vendor/netFound-base/model.safetensors').symlink_to(CHECKPOINT.resolve())
        module = importlib.import_module('legacy_unsw_archival_runtime_v1')
        source = importlib.import_module('continuous_features_v3')
        inp = importlib.import_module('continuous_input_v3')
        for loaded in (module, source, inp):
            require(Path(loaded.__file__).resolve().is_relative_to((vendor/'repo/ood').resolve()), 'FROZEN_E3_WRAPPER_IMPORT')
        for name, identity in spec['import_identities'].items():
            if name == 'netFound_classes':
                continue
            loaded = importlib.import_module(name)
            require(str(Path(loaded.__file__).resolve()) == identity['path'], 'FAILED_HPC_IMPORT_CLOSURE:'+name)
        self.embed, _, self.model, self.tokenizer, self.collator = module.e3_runtime(runtime)
        classes = [type(self.model.config), type(self.collator), type(self.model), type(self.tokenizer)]
        require([dict(name=cls.__name__, module=cls.__module__) for cls in classes] ==
                spec['import_identities']['netFound_classes'], 'FAILED_HPC_NETFOUND_CLASS_IDENTITY')
        netfound_files = []
        for loaded in list(sys.modules.values()):
            name = getattr(loaded, '__name__', '')
            if not (name.startswith('modules.netFound') and getattr(loaded, '__file__', None)):
                continue
            path = Path(loaded.__file__).resolve()
            source_roots = (runtime/'vendor/netFound', vendor/'runtime/vendor/netFound')
            matched = next((root.resolve() for root in source_roots if path.is_relative_to(root.resolve())), None)
            require(matched is not None, 'FROZEN_NETFOUND_IMPORT_LOCATION')
            original = vendor/'runtime/vendor/netFound'/path.relative_to(matched)
            require(sha(path) == sha(original), 'FROZEN_NETFOUND_IMPORT_BYTES')
            netfound_files.append(dict(module=name, path=str(path), sha256=sha(path)))
        self.source, self.inp, self.np = source, inp, np
        write(Path(output)/'ENVIRONMENT.json', dict(python=sys.version, modules=locations,
            torch_config=torch.__config__.show(), threads=torch.get_num_threads(),
            deterministic=torch.are_deterministic_algorithms_enabled(), runtime_readonly=True,
            netfound_files=netfound_files,
            numpy_overlay_reused=str(NUMPY), original_package_modified=False))

    def prepare(self, anchor, snapshot, count):
        example = self.source.tokenize(self.tokenizer, snapshot['flow'])
        self.inp.verify_tokenized(snapshot['flow'], snapshot['provenance'], example)
        shape = [int(snapshot['flow']['protocol']), max(example['dataset_burst_sizes'])+1, len(example['dataset_burst_sizes'])]
        require(shape == anchor['shape'], 'FIXED_ANCHOR_TENSOR_SHAPE')
        examples = [copy.deepcopy(example) for _ in range(count)]
        batch = self.collator(examples)
        self.source.verify_batch(examples, batch)
        return batch, [self.source.tensor_hash(batch, i) for i in range(count)]

    def forward(self, batch):
        values = self.embed.core.e3_forward_batches(self.model, [batch], 'cpu')
        require(values.dtype == self.np.float32 and values.shape == (len(batch['input_ids']),768) and
                self.np.isfinite(values).all(), 'DIAGNOSTIC_FINITE_FLOAT32_REQUIRED')
        return [values[i].tobytes() for i in range(len(values))]


class Guard:
    def __init__(self, output):
        import psutil
        self.psutil = psutil
        self.process, self.output, self.start = psutil.Process(), Path(output), time.monotonic()
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()

    def __call__(self):
        require(time.monotonic()-self.start < 600, 'DIAGNOSTIC_600_SECOND_WALL_LIMIT')
        rss = 0
        for process in [self.process]+self.process.children(recursive=True):
            try:
                rss += process.memory_info().rss
            except self.psutil.NoSuchProcess:
                pass
        require(rss < 8*1024**3, 'DIAGNOSTIC_8GIB_TREE_RSS_LIMIT')
        # Do not follow the checkpoint symlink when measuring diagnostic output.
        used = 0
        for path in self.output.rglob('*'):
            try:
                if path.is_file() and not path.is_symlink():
                    used += path.stat().st_size
            except FileNotFoundError:
                # Atomic receipt files may disappear between enumeration/stat.
                continue
        require(used < 256*1024**2, 'DIAGNOSTIC_256MIB_OUTPUT_LIMIT')
        require(shutil.disk_usage(self.output).free > 1024**3, 'DIAGNOSTIC_DISK_FREE_LIMIT')

    def watch(self):
        while not self.closed.wait(2):
            try:
                self()
            except BaseException as exc:
                write(self.output/'status.json', dict(status='EXCEPTION_STOP', reason=str(exc), retries=0))
                os._exit(70)

    def close(self):
        self.closed.set()
        self.thread.join(timeout=5)


def fresh_output(path):
    output = Path(path).resolve()
    require(output.parent.parent == OUTPUT_ROOT.resolve() and output.name == 'science' and
            re.fullmatch(r'job_[1-9][0-9]*', output.parent.name) is not None and not output.exists(),
            'FIXED_FRESH_DIAGNOSTIC_OUTPUT_REQUIRED')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', default=str(Path(__file__).resolve().parent))
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approval-file')
    parser.add_argument('--output')
    args = parser.parse_args()
    package = Path(args.package).resolve()
    manifest, rows, expected, seal = load_inputs(package)
    if not args.execute:
        print(json.dumps(dict(status='DRY_RUN_PASS', package_sha256=seal, source_uids=8,
            potential_forward_positions=136, actual_forwards=0, checkpoint_loads=0,
            target_query_inputs=0, production_encoding=False, source_cal=False, target_evaluation=False)))
        return 0
    require(args.approval_file and args.output, 'EXPLICIT_APPROVAL_AND_FRESH_OUTPUT_REQUIRED')
    authorize(read(args.approval_file), seal, sha(package/'manifest.json'))
    output = fresh_output(args.output)
    output.mkdir(parents=True, exist_ok=False)
    write(output/'status.json', dict(status='RUNNING', stage='RUNTIME_IDENTITY', retries=0))
    guard = None
    try:
        guard = Guard(output)
        engine = RealEngine(manifest, output)
        result = observe_fixed(manifest, rows, expected, output, engine, guard)
        write(output/'RESULT.json', result)
        write(output/'status.json', dict(result, stage='DIAGNOSTIC_COMPLETE'))
        return 0
    except BaseException as exc:
        write(output/'status.json', dict(status='EXCEPTION_STOP', reason=str(exc), retries=0,
            evidence_preserved=True, production_encode=False, source_cal=False, target_evaluation=False))
        raise
    finally:
        if guard:
            guard.close()


if __name__ == '__main__':
    sys.exit(main())
