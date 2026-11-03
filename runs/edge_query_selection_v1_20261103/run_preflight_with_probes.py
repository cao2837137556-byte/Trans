"""Same old bounded worker plus required-shape singleton byte probes.

Run only under the package's 540s process-group supervisor / 600s Slurm wall.
No frozen source files are changed; temporary adapter attributes are restored.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

for _name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT/'runs/edge_external_test1_engineering_v1_20261103/preflight'
sys.path.insert(0, str(HERE))
from strict_shape_probes import (AttributeProxy, StrictShapeProbes, replaced_attribute,
                                 require, write_json)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sidecar(path):
    path = Path(path)
    path.with_name(path.name+'.sha256').write_text(sha(path)+'  '+path.name+'\n', encoding='utf-8')


def run_worker(args):
    out = Path(args.output)
    gate = None
    previous_sys_path = list(sys.path)
    result_path = out/'RESULT.json'
    code = 1
    try:
        card = json.loads(Path(args.slice).read_text(encoding='utf-8-sig'))
        required = {tuple(int(v) for v in r['shape'])
                    for r in card['shape_expansion']['required']['representatives']}
        base_rows = sum(len(s['frames']) for s in card['slices'])
        require(required and base_rows+len(required) <= 100, 'SLICE_PLUS_REQUIRED_PROBES_CAP')
        sys.path.insert(0, str(OLD))
        spec = importlib.util.spec_from_file_location('_edge_original_preflight_runner', OLD/'run_preflight.py')
        old_runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old_runner)
        import engine
        old_encode = engine.encode_snapshots

        def encode_with_probes(entries, runtime, progress):
            nonlocal gate
            require(gate is None and len(entries) == base_rows, 'SINGLE_ENCODING_STAGE_AND_ROW_PARITY')
            sys.path.insert(0, str(ROOT/'runs/history_normal_reference_keyrepair_v1_20261031'))
            from hnr import encoding
            from continuous_features_v3 import tokenize, tensor_hash
            original_factory = encoding.new_encoder

            def factory(config):
                nonlocal gate
                encoder, identity = original_factory(config)
                embed, _, model, tokenizer, _ = encoder
                groups = Counter()
                for entry in entries:
                    example = tokenize(tokenizer, entry['body']['flow'])
                    groups[(entry['row']['protocol'], max(example['dataset_burst_sizes'])+1,
                            len(example['dataset_burst_sizes']))] += 1
                plan = [(shape, min(16, n-start)) for shape, n in sorted(groups.items())
                        for start in range(0, n, 16)]
                gate = StrictShapeProbes(required, plan, len(entries), out,
                    embed.core.e3_forward_batches, encoding.physical_batch, tensor_hash, progress.guard)
                proxied = AttributeProxy(embed, core=AttributeProxy(embed.core, e3_forward_batches=gate.forward))
                gate.save()
                return (proxied,)+tuple(encoder[1:]), identity

            with replaced_attribute(encoding, 'new_encoder', factory):
                result = old_encode(entries, runtime, progress)
            require(gate is not None, 'ENCODER_FACTORY_WAS_NOT_USED')
            gate.require_complete()
            e3, q14, receipt = result
            receipt = dict(receipt, strict_required_shape_singleton_probes=gate.summary(),
                total_logical_with_extra_probes=len(entries)+gate.extra_logical,
                total_physical_with_extra_probes=runtime['physical_reserved']+gate.extra_physical)
            return e3, q14, receipt

        with replaced_attribute(engine, 'encode_snapshots', encode_with_probes):
            code = old_runner.worker(args)
    except BaseException as error:
        write_json(result_path, dict(status='STOPPED_NO_RETRY', error=repr(error),
            traceback=traceback.format_exc(), final_linux_runtime_gate_pass=False,
            scope='ENGINEERING_ONLY_NOT_EXTERNAL_EVALUATION', external_quality_metrics=False,
            training=False, automatic_retry=False))
        code = 1
    finally:
        sys.path[:] = previous_sys_path
        summary = gate.summary() if gate is not None else dict(status='NOT_STARTED',
            strict_byte_identity_unchanged=True, extra_logical_rows=0, extra_physical_rows=0,
            external_quality_used=False)
        write_json(out/'STRICT_SHAPE_PROBE_SUMMARY.json', summary)
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding='utf-8-sig'))
            result['strict_shape_probes'] = summary
            result['strict_shape_probe_adapter_code_pins'] = {
                p.name:sha(p) for p in (Path(__file__), HERE/'strict_shape_probes.py')}
            if code == 0 and summary['status'] != 'PASS':
                result.update(status='STOPPED_NO_RETRY', error='REQUIRED_PROBES_NOT_PASSED',
                              final_linux_runtime_gate_pass=False)
                code = 1
            write_json(result_path, result)
            write_json(out/'STATUS.json', result)
        for name in ('RESULT.json', 'STATUS.json', 'STRICT_SHAPE_PROBE_SUMMARY.json',
                     'STRICT_SHAPE_PROBE_LEDGER.jsonl', 'STRICT_SHAPE_PROBE_FAILURE.json'):
            if (out/name).exists():
                sidecar(out/name)
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slice', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--strict-runtime', action='store_true')
    parser.add_argument('--tshark')
    parser.add_argument('--raw-directory')
    parser.add_argument('--worker', action='store_true', help='Output directory already created by supervisor')
    args = parser.parse_args()
    out = Path(args.output)
    if args.worker:
        require(out.is_dir(), 'WORKER_OUTPUT_DIRECTORY_REQUIRED')
    else:
        out.mkdir(parents=True, exist_ok=False)
    return run_worker(args)


if __name__ == '__main__':
    raise SystemExit(main())

