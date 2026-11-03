"""Use the sealed three-stage chain with one explicit encoder adapter."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import signal
import sys

from repair_gate import authorize, read, require, sha, verify_inputs, write, ORIGINAL_SHA, STAGES

ENCODING_PACKAGE_SHA = '50969f127dbb258b851f36ea03669456863a7d532b1c6f1b70a9c6a84088a910'


def runtime_identity(actual, expected, overlay):
    require(actual.get('status')=='PASS' and actual.get('neural_forwards')==0 and
            actual.get('checkpoint_loads')==0 and actual.get('python')==expected['python'] and
            actual.get('torch_cpu_capability')==expected['torch_cpu_capability'] and
            actual.get('torch_config')==expected['torch_config'], 'DIAGNOSTIC_RUNTIME_BUILD_IDENTITY')
    for name, identity in expected['dependencies'].items():
        observed = actual.get('dependencies', {}).get(name)
        if name=='numpy':
            require(observed is not None and observed.get('version')==identity['version'] and
                    Path(observed['path']).resolve().is_relative_to(Path(overlay).resolve()), 'FRESH_NUMPY_RUNTIME_IDENTITY')
        else:
            require(observed==identity, 'DIAGNOSTIC_RUNTIME_DEPENDENCY_IDENTITY:'+name)


def encoding_identity(output, budget, budget_file):
    output = Path(output)
    result = read(output/'RESULT.json')
    receipt_path = output/'BATCH_REPAIR_RECEIPT.json'
    receipt = read(receipt_path)
    parity = read(output/'ORIGINAL104_PARITY.json')
    canonical = __import__('json').dumps(budget, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=True, allow_nan=False).encode()
    require(result.get('status')=='COMPLETE' and result.get('mode')=='encode' and
            result.get('batch_repair_verified') is True and
            result.get('batch_repair_receipt_sha256')==sha(receipt_path), 'ENCODER_REPAIR_COMPLETE_RECEIPT')
    require(receipt.get('status')=='COMPLETE' and receipt.get('policy')==budget['policy'] and
            receipt.get('budget_sha256')==sha(budget_file) and
            receipt.get('budget_content_sha256')==hashlib.sha256(canonical).hexdigest() and
            receipt.get('totals')==budget['totals'] and receipt.get('clone_rows_in_bank')==0 and
            receipt.get('logical_uids_unchanged') is True and receipt.get('target_query_inputs')==0,
            'ENCODER_REPAIR_BUDGET_AND_UNIQUE_UIDS')
    require(receipt.get('batch_ledger_sha256')==sha(output/'BATCH_REPAIR_BATCHES.jsonl'), 'ENCODER_REPAIR_LEDGER_IDENTITY')
    require(len(receipt.get('datasets', []))==len(budget['datasets']) and
            [(item['name'],item['measured_rows']) for item in result.get('datasets', [])]==
            [(item['name'],item['logical_rows']) for item in budget['datasets']], 'ENCODER_REPAIR_DATASET_ORDER')
    for expected, measured in zip(budget['datasets'], receipt['datasets']):
        require(all(measured.get(key)==value for key,value in expected.items()) and
                all(measured.get('actual', {}).get(key)==expected[key] for key in
                    ('logical_rows','physical_positions','clone_positions','singleton_batches','batches')),
                'ENCODER_REPAIR_DATASET_ACTUAL_BUDGET')
    require(parity.get('original104_exact_bytes') is True and parity.get('mismatch_count')==0 and
            parity.get('max_abs_error')==0, 'REPAIRED_ORIGINAL104_ZERO_TOLERANCE')
    require(result.get('package_sha256')==ENCODING_PACKAGE_SHA and result.get('no_training') is True and
            result.get('target_evaluation') is False,
            'ENCODER_SCIENTIFIC_SCOPE')


def make_runner(chain, original, overlay, output, budget):
    original, overlay, output = map(lambda p: Path(p).resolve(), (original,overlay,output))
    original_runner = chain.run_stage
    def repaired_runner(argv, **kwargs):
        stage = Path(kwargs['output']).name
        command = list(argv)
        if stage=='encode':
            require(command[:4]==[sys.executable,'-B','-u',str(original/'vendor/encoding_v2/repo/ood/onboarding_supplement_encoder_r2.py')],
                    'EXACT_ORIGINAL_ENCODER_COMMAND_REQUIRED')
            command = [sys.executable,'-B','-u',str(overlay/'encoder_adapter.py'),
                '--frozen-root',str(original),'--budget-file',str(overlay/'ENCODER_PHYSICAL_BUDGET.json')]+command[4:]
        elif stage=='source_cal':
            encoding_identity(output/'encode', budget, overlay/'ENCODER_PHYSICAL_BUDGET.json')
        require(stage in STAGES, 'PREFIX_ONLY_NO_TARGET_MATRIX')
        result = original_runner(command, **kwargs)
        if stage=='runtime':
            runtime_identity(read(output/'runtime/environment.json'), read(overlay/'RUNTIME_BINDING_179536.json'),
                             output/'runtime/numpy201')
        elif stage=='encode':
            encoding_identity(output/'encode', budget, overlay/'ENCODER_PHYSICAL_BUDGET.json')
        return result
    return repaired_runner


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', required=True)
    parser.add_argument('--overlay', default=str(Path(__file__).resolve().parent))
    parser.add_argument('--assets-root')
    parser.add_argument('--checkpoint')
    parser.add_argument('--output')
    parser.add_argument('--approval-file')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    original, overlay = Path(args.original).resolve(), Path(args.overlay).resolve()
    proof = verify_inputs(original, overlay)
    # The exact budget is recomputed from sealed normal-reference snapshots,
    # without importing Torch, a tokenizer, a model or a checkpoint.
    sys.path.insert(0, str(overlay))
    from encoder_adapter import build_budget
    budget = read(overlay/'ENCODER_PHYSICAL_BUDGET.json')
    require(build_budget(original, verified=True)==budget, 'SEALED_PHYSICAL_PLAN_RECOMPUTATION')
    if not args.execute:
        import json
        print(json.dumps(dict(proof, physical_positions=budget['totals']['physical_positions'],
                              logical_rows=budget['totals']['logical_rows']), sort_keys=True))
        return 0
    require(args.approval_file and args.output and args.assets_root and args.checkpoint, 'EXECUTION_ARGUMENTS_REQUIRED')
    require(sys.platform=='linux' and sys.version.split()[0]=='3.11.11' and
            Path(sys.executable).resolve()==Path('/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python').resolve(),
            'FIXED_LINUX_CP311_EXECUTION_RUNTIME')
    approval = read(args.approval_file)
    authorize(approval, overlay, proof)
    output = Path(args.output).resolve()
    require(not output.exists() and output.name=='science' and not output.is_relative_to(original) and
            not output.is_relative_to(overlay) and output.parent.is_dir(), 'FRESH_EXTERNAL_SCIENCE_OUTPUT')
    delegated = dict(user_authorized=True, package_sha256=ORIGINAL_SHA, scope='DENSE_REFERENCE_V1',
        stages=STAGES, retries=0, total_wall_seconds=43200, evidence=approval['evidence'],
        outer_repair_manifest_sha256=proof['overlay']['manifest_sha256'], outer_repair_approval_sha256=sha(args.approval_file),
        logical_positions=budget['totals']['logical_rows'], physical_positions=budget['totals']['physical_positions'],
        target_evaluation=False, optimizer_updates=0)
    delegated_path = output.parent/'BATCH_REPAIR_CHAIN_APPROVAL.json'
    write(delegated_path, delegated, exclusive=True)
    write(output.parent/'REPAIR_PREFLIGHT.json', proof, exclusive=True)
    sys.path.insert(0, str(original/'src'))
    spec = importlib.util.spec_from_file_location('sealed_dense_chain_with_batch_adapter', original/'src/chain.py')
    chain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chain)
    chain.run_stage = make_runner(chain, original, overlay, output, budget)
    return chain.main(['--package',str(original),'--assets-root',str(Path(args.assets_root).resolve()),
        '--checkpoint',str(Path(args.checkpoint).resolve()),'--approval-file',str(delegated_path),
        '--output',str(output),'--stages']+STAGES)


if __name__=='__main__':
    def stopped(signum, frame):
        # Unwind the original supervisor so detached stage children are cleaned.
        raise RuntimeError('TERMINATION_SIGNAL:'+str(signum))
    signal.signal(signal.SIGTERM, stopped)
    raise SystemExit(main())
