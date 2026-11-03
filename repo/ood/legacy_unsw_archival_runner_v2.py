"""Explicit new attempt from Job176411 sealed inputs; never reuses uncertified features."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile

import legacy_unsw_archival_common_v1 as c
import legacy_unsw_archival_runtime_v2 as rt
import legacy_unsw_archival_runner_v1 as old


def preflight(root, out, target=True):
    old.preflight(root, out, target)
    # Store new checks outside the immutable v1 preflight seal.
    result = subprocess.run([sys.executable,'-m','unittest','-v','test_legacy_unsw_archival_v2'],
        cwd=Path(root)/'repo/ood', capture_output=True, text=True, timeout=300)
    (Path(out).parent/'recovery_tests.log').write_bytes((result.stdout+result.stderr).encode('utf-8'))
    c.require(result.returncode == 0, 'RECOVERY_SYNTHETIC_TESTS_FAILED')
    # Probe commit/fsync on the actual output filesystem, not only node /tmp.
    import numpy as np
    folder = Path(out).parent/'synthetic_output_filesystem_probe'
    identity = dict(synthetic_only=True, real_model_forwards=0)
    values = np.arange(2*768,dtype=np.float32).reshape(2,768)
    block = rt.commit_block(folder,0,0,['synthetic-a','synthetic-b'],values,identity)
    c.require(np.array_equal(rt.read_block(block,['synthetic-a','synthetic-b'],0,identity),values), 'OUTPUT_FILESYSTEM_COMMIT_PARITY')
    c.write(folder/'probe.json',dict(status='PASS',synthetic_only=True,output_filesystem_tested=True))
    c.seal(folder)


def recover_inputs(root, out, progress):
    root, out = Path(root), Path(out)
    contract = c.read(root/'recovery_contract.json')
    source = Path(contract['source_root']).resolve()
    c.require(source != root.resolve() and source not in root.resolve().parents and
              root.resolve() not in source.parents, 'RECOVERY_ROOTS_OVERLAP')
    c.pin(source/'SHA256SUMS', contract['source_package_seal_sha256'])
    c.verify(source, exact=False)
    c.pin(source/'export_manifest.json', contract['export_manifest_sha256'])
    c.pin(source/'job.id', contract['source_identity_pins']['job.id'])
    c.require((source/'job.id').read_text().strip() == '176411', 'SOURCE_JOB')
    for rel, h in contract['source_identity_pins'].items(): c.pin(c.confined(source,rel),h)
    status = c.read(source/'runs/real_evaluation/status.json')
    c.require(status['status'] == 'STOPPED_NO_RETRY' and status['stage'] == 'E3_FEATURES', 'SOURCE_STATUS')
    recipe, _, _, _ = c.contracts(root)
    for sub in ('manifests','flows'):
        origin = source/'runs/real_evaluation'/sub
        c.verify(origin)
        expected = {name:spec for name,spec in contract['input_pins'].items()
                    if name.startswith('runs/real_evaluation/'+sub+'/')}
        c.require({p.relative_to(source).as_posix() for p in origin.rglob('*') if p.is_file()}
                  == set(expected), 'RECOVERY_INPUT_FILE_SET')
        for rel, spec in expected.items():
            progress.guard()
            path = c.confined(source,rel)
            c.require(path.stat().st_size == spec['bytes'], 'RECOVERY_INPUT_SIZE')
            c.pin(path, spec['sha256'])
        shutil.copytree(origin, out/sub)
        c.verify(out/sub)
    manifest = c.read(out/'manifests/manifest.json')
    c.require(manifest['recipe_sha256'] == c.RECIPE_SHA and
              manifest['status'] == 'IDENTITIES_SEALED_BEFORE_ANY_FORWARD' and
              manifest['queries'] == 148316 and manifest['references'] == 92, 'RECOVERY_DENOMINATORS')
    index = c.read(out/'flows/index.json')
    c.require(index['manifest_seal_sha256'] == c.sha(out/'manifests/SHA256SUMS') and
              index['total'] == recipe['counts']['total_feature_targets'] == 148408 and
              index['immutable_causal_snapshots'] is True, 'RECOVERY_FLOW_LINEAGE')
    query = c.rows(out/'manifests/queries.jsonl.gz')
    refs = c.rows(out/'manifests/references.jsonl.gz')
    expected_uids = {r['uid'] for r in query+refs}
    c.require(len(query) == 148316 and len(refs) == 92 and len(expected_uids) == 148408, 'RECOVERY_UID_COUNTS')
    c.require(sum(r['label'] == 1 for r in query) == 72553 and
              sum(r['label'] == 0 for r in query) == 75763, 'RECOVERY_LABEL_COUNTS')
    import gzip
    seen = set()
    c.require(len(index['shards']) == 4, 'RECOVERY_SHARD_COUNT')
    for spec in index['shards']:
        path = c.confined(out/'flows',spec['file'])
        count = 0
        with gzip.open(path,'rt',encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                c.require(row['uid'] in expected_uids and row['uid'] not in seen, 'RECOVERY_FLOW_UID')
                seen.add(row['uid']); count += 1
                if count % 1024 == 0: progress.tick(len(seen),len(expected_uids))
        c.require(count == spec['count'], 'RECOVERY_SHARD_ROWS')
    c.require(seen == expected_uids, 'RECOVERY_FLOW_COVERAGE')
    c.write(out/'recovery_receipt.json', dict(source_job=176411, source_root=str(source),
        manifests_verified=True, flows_verified=True, uid_coverage=len(seen),
        old_partial_features_reused=False, raw_decodes=0, recipe_sha256=c.RECIPE_SHA))
    return query, refs


def execute(root, explicit):
    c.require(explicit is True, 'REAL_EXECUTION_NOT_AUTHORIZED')
    root = Path(root).resolve()
    out = root/'runs/real_evaluation'
    c.require(not out.exists(), 'OUTPUT_EXISTS_NO_RETRY')
    c.verify(root, exact=False)
    recipe, roster, labels, controls = c.contracts(root)
    contract = c.read(root/'runtime_contract.json')
    progress = rt.Progress(out, contract['limits'])
    def interrupt(signum,frame): raise RuntimeError('SIGNAL_STOP:'+str(signum))
    previous = signal.signal(signal.SIGTERM,interrupt)
    try:
        c.write(out/'launch.json', dict(scope='SEALED_INPUTS_FROZEN_RECOVERY_V2',
            authority='Explicit --authorize-recovery invocation', recipe_sha256=c.RECIPE_SHA,
            source_job=176411, new_attempt=True, retries=0, optimizer=False, calibration=False))
        preflight(root,out/'preflight')
        progress.stage = 'VERIFY_AND_COPY_SEALED_INPUTS'
        progress.tick(force=True)
        c.pin(root/'vendor/netFound-base/model.safetensors',contract['checkpoint_sha256'])
        query, refs = recover_inputs(root,out,progress)
        progress.stage = 'E3_FEATURES'
        progress.tick(0,148408,force=True)
        rt.launch_features(root,out,progress)
        progress.stage = 'MERGE_FEATURES'; progress.tick(force=True)
        features = old.merge_features(out,query,refs,contract['workers'])
        progress.stage = 'FROZEN_SCORING'; progress.tick(force=True)
        from legacy_unsw_archival_score_v1 import evaluate
        decision = evaluate(root,out/'evaluation',recipe,roster,controls,query,refs,features,progress)
        progress.stop('COMPLETE',scientific_gate=decision)
        c.seal(out)
    except BaseException as exc:
        progress.record_failure(exc,'main')
        progress.stop('STOPPED_NO_RETRY',repr(exc))
        raise
    finally:
        signal.signal(signal.SIGTERM,previous)


def export(root):
    root = Path(root); target = root/'evaluation_pullback.tar.gz'
    c.require(not target.exists(),'EXPORT_EXISTS')
    paths = [p for folder in ('runs/real_evaluation','logs') for p in (root/folder).rglob('*') if p.is_file()]
    paths += [p for p in (root/'job.id',root/'exit_code.txt',root/'runtime_contract.json',root/'recovery_contract.json') if p.is_file()]
    included, omitted = {}, {}
    for path in sorted(paths):
        rel = path.relative_to(root).as_posix()
        # Keep flow index/seals, error logs and committed-block receipts; omit large arrays/database.
        skip = rel.endswith('population.sqlite') or rel.endswith('/features.npy') or ('/flows/' in rel and rel.endswith('.jsonl.gz'))
        dest = omitted if skip else included
        dest[rel] = dict(sha256=c.sha(path),bytes=path.stat().st_size)
    manifest = root/'export_manifest.json'
    c.write(manifest,dict(included=included,omitted=omitted,recipe_sha256=c.RECIPE_SHA,
        source_job=176411,original_seals_are_provenance_not_complete_export_seals=True,
        raw_captures_included=False,source_checkpoint_included=False))
    with tarfile.open(target.with_suffix('.partial'),'x:gz',compresslevel=1) as tar:
        for rel in included: tar.add(root/rel,arcname=rel,recursive=False)
        tar.add(manifest,arcname='export_manifest.json',recursive=False)
    target.with_suffix('.partial').replace(target)
    Path(str(target)+'.sha256').write_bytes((c.sha(target)+'  '+target.name+'\n').encode('ascii'))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=['run','worker','preflight','export'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--shard',type=int)
    parser.add_argument('--authorize-recovery',action='store_true')
    parser.add_argument('--local-synthetic',action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'run': execute(args.root,args.authorize_recovery)
    elif args.command == 'worker':
        c.require(args.output is not None and args.output.resolve() == args.root.resolve()/'runs/real_evaluation','OUTPUT_SCOPE')
        c.require(args.shard in range(4),'SHARD_SCOPE')
        rt.feature_worker(args.root,args.output,args.shard,args.authorize_recovery)
    elif args.command == 'preflight': preflight(args.root,args.output,not args.local_synthetic)
    else: export(args.root)


if __name__ == '__main__': main()
