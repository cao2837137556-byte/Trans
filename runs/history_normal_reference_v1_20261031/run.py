"""Default is read-only acceptance. Real stages require an explicit execute flag."""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '4'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import argparse
from pathlib import Path
import platform

from hnr.common import PACKAGE, ROOT, VERSION, HEIM, digest, read, require, sha, write


def validate_config_bindings(config):
    """Deployment can relocate existing assets, never replace scientific pins."""
    frozen = read(PACKAGE/'config/EXECUTION.json')
    def semantic(value):
        if isinstance(value, dict):
            return {k: semantic(v) for k,v in value.items()
                    if not (k in ('root','path','tshark','runtime_root','normalizer','assets_manifest')
                            and isinstance(v, str))}
        if isinstance(value, list):
            return [semantic(v) for v in value]
        return value
    require(config.get('candidate') == 'C1' and config.get('path') == 'P-DEVONLY', 'FIXED_CANDIDATE_PATH')
    require(semantic(config) == semantic(frozen), 'EXECUTION_SCIENTIFIC_BINDING_CHANGED')
    require(semantic(read(config['assets_manifest'])) == semantic(read(PACKAGE/'config/ASSETS.json')),
            'ASSET_SCIENTIFIC_BINDING_CHANGED')


def environment_check():
    import numpy as np
    import torch
    observed = dict(system=platform.system(), python=platform.python_version(),
                    numpy=np.__version__, torch=str(torch.__version__).split('+')[0])
    require(observed == dict(system='Linux', python='3.11.11', numpy='2.0.1', torch='2.5.1'),
            'FROZEN_HPC_ENVIRONMENT_MISMATCH:' + str(observed))
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    return observed


def _joined(data):
    ids = [r['uid'] for r in data['rows']]
    return dict(data, feature_uids=ids, q_uids=ids)


def cleanup_intermediates(member, runtime):
    """Only this run's known reproducible intermediate files may be removed."""
    member = Path(member).resolve()
    require(member.is_relative_to(runtime.output.resolve()), 'INTERMEDIATE_OUTSIDE_THIS_RUN')
    removed = []
    for name in ('chronological.pcapng', 'candidates.sqlite', 'contexts_1.sqlite', 'contexts_2.sqlite'):
        path = member/name
        if path.is_file():
            require(not path.is_symlink() and path.resolve().parent == member, 'UNSAFE_INTERMEDIATE_PATH')
            removed.append(dict(name=name, bytes=path.stat().st_size, sha256=sha(path)))
            path.unlink()
    write(member/'INTERMEDIATE_CLEANUP.json', dict(removed=removed, selected_snapshots_and_results_preserved=True))
    runtime.update('MEMBER_INTERMEDIATES_RELEASED', files=len(removed))


def execute(config, output, *, run_runtime=None):
    """One whole-experiment transaction. No checkpoint resume or auto-retry."""
    from hnr.checks import preflight
    from hnr.runtime import Runtime
    validate_config_bindings(config)
    accepted = preflight(config)
    require(accepted['status'] == 'READY', 'EXECUTION_INPUTS_NOT_READY:' + str(accepted['blockers']))
    environment = environment_check()
    factory = Runtime if run_runtime is None else run_runtime
    with factory(output) as runtime:
        write(runtime.output/'ACCEPTANCE.json', accepted)
        write(runtime.output/'ENVIRONMENT.json', environment)
        write(runtime.output/'EXECUTION_CONFIG.json', config)
        # A scientific single-attempt latch is independent of the output name.
        # Packaging/run ownership does not grant permission to clear this file.
        latch = PACKAGE/'EXECUTION_ATTEMPT.json'
        with latch.open('x', encoding='utf-8') as stream:
            import json
            json.dump(dict(status='ATTEMPT_STARTED', output=str(runtime.output),
                           config_sha256=digest(config), version=VERSION), stream)
        from hnr.assets import load_assets, score_dev
        from hnr.encoding import new_encoder, encode_member, concatenate
        from hnr.history import prepare_member
        from hnr.evaluation import evaluate_dev, evaluate_ab
        assets = load_assets(Path(config.get('root', ROOT)), config.get('assets_manifest'))
        dense_b = assets.dense('UNSW_DEV')
        a = assets.a_history()
        dense_a = assets.dense('CIC_DEV')
        old_a = {(r['protocol'], r['component_id']) for r in dense_a['rows'] if r['device'] == HEIM['device']}
        new_a = {(r['protocol'], r['component_id']) for r in a['rows']} - old_a
        if not new_a:
            result = dict(status='STOP_NO_NEW_COMPONENT', device=HEIM['device'], AB_evaluated=False)
            runtime.finish(result); return result
        frozen = assets.calibration()
        old_rows = dense_b['rows']
        del dense_b, dense_a
        refs, queries = [], []
        physical_positions = 0
        encoder = encoder_identity = None
        for device in config['devices']:
            member = runtime.output/'history'/device['key']
            prepared = prepare_member(device, member, old_rows, runtime, config['tshark'])
            if prepared['status'] != 'PREPARED':
                result = dict(prepared, AB_evaluated=False)
                runtime.finish(result); return result
            if encoder is None:
                runtime.update('LOAD_FROZEN_ENCODER')
                encoder, encoder_identity = new_encoder(config['encoder'])
            encoded = encode_member(member, member/'encoded', dict(config['encoder'], old_rows=old_rows),
                                    runtime, encoder=encoder, encoder_identity=encoder_identity)
            physical_positions += read(member/'encoded/ENCODE_RESULT.json')['physical_positions']
            refs.append(encoded['HIST_REF']); queries.append(encoded['HIST_DEV'])
            cleanup_intermediates(member, runtime)
        # Release the single frozen encoder before DEV heads and AB geometry.
        del encoder
        references = _joined(concatenate(refs)); dev = _joined(concatenate(queries))
        dev = score_dev(dev, assets, frozen, runtime)
        assets.immutable()
        dev_result = evaluate_dev(dev, references, frozen, runtime, output=runtime.output/'dev')
        dev_result['encoding_physical_positions'] = physical_positions
        write(runtime.output/'DEV_RESULT.json', dev_result)
        if dev_result['status'] != 'PASS_DEV':
            result = dict(dev_result, AB_evaluated=False, terminal=True)
            runtime.finish(result); return result
        history = _joined(concatenate([a, references]))
        result = evaluate_ab(Path(config.get('root', ROOT)), runtime.output/'ab', history,
                             dev_result, runtime, config.get('assets_manifest'))
        result.update(AB_evaluated=True, old_source_reference_rows_preserved=4728,
                      dense_original_total_rows_preserved=26549,
                      encoding_physical_positions=physical_positions)
        runtime.finish(result)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('check', 'execute'), nargs='?', default='check')
    parser.add_argument('--runtime-config', type=Path, default=PACKAGE/'config/EXECUTION.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--execute-real-data', action='store_true')
    parser.add_argument('--verify-raw-hash', action='store_true')
    args = parser.parse_args(argv)
    require(args.stage == 'execute' or not args.execute_real_data, 'EXECUTE_FLAG_REQUIRES_EXECUTE_STAGE')
    config = read(args.runtime_config)
    validate_config_bindings(config)
    if args.stage == 'check':
        from hnr.checks import preflight
        result = preflight(config, verify_raw_hash=args.verify_raw_hash)
        if args.output:
            out = args.output.resolve()
            require(out.is_relative_to(PACKAGE/'validation') and not out.exists(), 'NEW_VALIDATION_FILE_REQUIRED')
            write(out, result)
        import json
        print(json.dumps(dict(status=result['status'], blockers=result['blockers'],
                              packet_decodes=0, model_forwards=0, new_scores=0), ensure_ascii=False))
        return 0 if result['status'] == 'READY' else 2
    require(args.execute_real_data, 'REAL_DATA_EXECUTION_FLAG_REQUIRED')
    require(args.output is not None, 'NEW_OUTPUT_REQUIRED')
    execute(config, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
