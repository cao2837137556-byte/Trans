"""Assemble the static portable input closure, never score or encode a query."""
from pathlib import Path
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'src'))
from common import read, require, sha, write


def main():
    frozen = HERE / 'preparation/frozen_final'
    entries = {}
    source_required = set(read(frozen / 'SOURCE_ASSETS.json')['assets'])
    for name in ('INPUT_OUTPUT_PINS.json', 'SOURCE_ASSETS.json'):
        for path, entry in read(frozen / name)['assets'].items():
            if path in entries:
                require(entries[path]['sha256'] == entry['sha256'], 'CONTRADICTORY_STATIC_PIN')
            entries[path] = dict(path=path, bytes=entry['bytes'], sha256=entry['sha256'])
    source_extras = [
        'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/cache_binding.json',
        'runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/evaluation/SHA256SUMS',
        'runs/onboarding_new_lineage_v1_20261022/package_v3/constrained_onboarding_core_v3.py',
        'runs/diagnostics_c2b_c4_step2_v1_20261025/source_cal/INPUT_SEAL.json',
        'runs/diagnostics_c2b_c4_step2_v1_20261025/source_cal/RESULT.json',
        'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/SHA256SUMS',
    ]
    for path in source_extras:
        original = ROOT / path
        entries[path] = dict(path=path, bytes=original.stat().st_size, sha256=sha(original))
        source_required.add(path)
    for entry in read(frozen / 'bindings.json')['calibration'].values():
        source_required.add(entry['path'])
    # Source CAL imports a pinned closure via the canonical logical root.
    for source in (HERE / 'vendor/encoding_v2/repo/ood').glob('*.py'):
        path = 'repo/ood/' + source.name
        entries[path] = dict(path=path, bytes=source.stat().st_size, sha256=sha(source))
        source_required.add(path)
    # Explicit aliases for already verified flat HPC source data. No search or
    # filename-only matching is used by the runtime preflight.
    flat_alias = 'runs/hpc_readiness_v1_20261026/assets/'
    existing_source = {
        'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy': 'LEARN.npy',
        'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/LEARN.jsonl.gz': 'LEARN.jsonl.gz',
        'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/LEARN_q.npy': 'LEARN_q.npy',
        'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/CAL.npz': 'CAL.npz',
        'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/FIT.npz': 'FIT.npz',
    }
    bundled, external = [], []
    for relative, entry in sorted(entries.items()):
        entry['required_for_source_cal'] = relative in source_required
        original = ROOT / relative
        if relative.startswith('repo/ood/'):
            original = HERE / 'vendor/encoding_v2' / relative
        require(original.is_file() and original.stat().st_size == entry['bytes'], 'STATIC_INPUT_CHANGED:' + relative)
        destination = HERE / 'assets' / relative
        if entry['bytes'] <= 16*1024**2:
            require(sha(original) == entry['sha256'], 'SMALL_STATIC_INPUT_SHA:' + relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
            require(sha(destination) == entry['sha256'], 'BUNDLED_COPY_SHA')
            entry['bundled'] = True
            bundled.append(entry)
        else:
            entry['bundled'] = False
            external.append(entry)
        if relative in existing_source:
            entry['aliases'] = [flat_alias + existing_source[relative]]
    manifest = dict(schema='dense-reference-static-assets-v1', files=list(entries.values()),
        bundled_files=len(bundled), external_files=len(external),
        bundled_bytes=sum(e['bytes'] for e in bundled),
        external_bytes=sum(e['bytes'] for e in external),
        original_inputs_modified=False, new_evaluation=False)
    write(HERE / 'config/ASSET_MANIFEST.json', manifest)
    source_files = [e for e in entries.values() if e['required_for_source_cal']]
    write(HERE / 'config/SOURCE_ASSET_MANIFEST.json', dict(manifest,
        files=source_files,
        bundled_files=sum(e['bundled'] for e in source_files),
        external_files=sum(not e['bundled'] for e in source_files),
        bundled_bytes=sum(e['bytes'] for e in source_files if e['bundled']),
        external_bytes=sum(e['bytes'] for e in source_files if not e['bundled']),
        scope='ENCODE_AND_SOURCE_CAL_PREFIX_ONLY'))
    template = read(frozen / 'bindings.json')
    template['root'] = 'READONLY_VIEW'
    template['synthetic_only'] = False
    write(HERE / 'config/MATRIX_TEMPLATE.json', template)
    wheel = next((HERE / 'wheels').glob('numpy-2.0.1-*.whl'))
    write(HERE / 'config/runtime.json', dict(numpy_wheel=wheel.relative_to(HERE).as_posix(),
        numpy_wheel_sha256=sha(wheel), python='CPython3.11 Linux x86_64',
        install_scope='fresh private runtime/numpy201 only', shared_environment_modified=False))
    write(HERE / 'config/chain.json', dict(schema='dense-reference-chain-v1',
        checkpoint_sha256='e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105',
        matrix_template='config/MATRIX_TEMPLATE.json',
        matrix_execution_blockers=[b for b in template['blockers']
                                   if b not in ('SUPPLEMENT_E3_AND_ORIGINAL104_BYTE_GATE_PENDING',
                                                'TRUE_DENSE_SOURCE_CAL_PENDING')],
        stages=['runtime', 'encode', 'source_cal', 'matrix'],
        prefix_execution_allowed=True, maximum_total_wall_seconds=43200,
        tree_rss_GiB=8, slurm_memory_GiB=16, automatic_retry=False))
    write(HERE / 'preparation/ASSET_CLOSURE_RECEIPT.json', dict(status='PASS',
        files=len(entries), bundled_bytes=manifest['bundled_bytes'],
        external_bytes=manifest['external_bytes'], new_forwards=0, new_evaluations=0,
        third_pool_status='BLOCKED_MISSING_FROZEN_BASE_B2'))
    print(json.dumps({k: manifest[k] for k in ('bundled_files', 'external_files', 'bundled_bytes', 'external_bytes')}))


if __name__ == '__main__':
    main()
