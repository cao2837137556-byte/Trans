"""Durable environment, budget, retained-array and PREPARED receipt preflight.

The reuse worker checks the full pinned snapshots, census joins and descriptors.
This preflight does not replay captures or duplicate those large source reads.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback


HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
PACKAGE_NAME = 'history_sample_coverage_c4_batch_resume_v1_20261102'


def require(value, message):
    if not value:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(chunk)
    return value.hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.' + str(os.getpid()) + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                    indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


class StagedPreflight:
    """Persist a stage before entering it, including any later exception."""
    def __init__(self, directory, *, stream=None, clock=time.monotonic):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        require(not (self.directory / 'PREFLIGHT_RESULT.json').exists(),
                'PREFLIGHT_RESULT_ALREADY_EXISTS')
        require(not (self.directory / 'PREFLIGHT_STATUS.json').exists(),
                'PREFLIGHT_STATUS_ALREADY_EXISTS')
        self.stream = sys.stdout if stream is None else stream
        self.clock = clock
        self.started = clock()
        self.state = dict(status='RUNNING', pid=os.getpid(), started_utc=utc(),
                          current_stage='STARTING', elapsed_seconds=0., stages=[],
                          science_started=False, submission_started=False)
        self._persist()

    def _persist(self):
        self.state.update(updated_utc=utc(), elapsed_seconds=self.clock()-self.started)
        write(self.directory / 'PREFLIGHT_STATUS.json', self.state)

    def _log(self, event, **values):
        print(json.dumps(dict(event=event, utc=utc(), pid=os.getpid(), **values),
                         ensure_ascii=False, allow_nan=False), file=self.stream, flush=True)

    @contextmanager
    def step(self, name):
        require(self.state['status'] == 'RUNNING', 'PREFLIGHT_ALREADY_TERMINAL')
        require(not self.state['stages'] or self.state['stages'][-1]['status'] == 'DONE',
                'PREFLIGHT_PREVIOUS_STAGE_INCOMPLETE')
        started = self.clock()
        stage = dict(name=name, status='START', started_utc=utc())
        self.state['stages'].append(stage)
        self.state['current_stage'] = name
        self._persist()
        self._log('START', stage=name)
        try:
            yield stage
        except BaseException as error:
            stage.update(status='FAIL', ended_utc=utc(),
                         elapsed_seconds=self.clock()-started, error=str(error),
                         error_type=type(error).__name__, traceback=traceback.format_exc())
            self._persist()
            self._log('FAIL', stage=name, error=str(error),
                      elapsed_seconds=stage['elapsed_seconds'])
            raise
        else:
            stage.update(status='DONE', ended_utc=utc(),
                         elapsed_seconds=self.clock()-started)
            self._persist()
            self._log('DONE', stage=name, elapsed_seconds=stage['elapsed_seconds'])

    def finish(self, error=None):
        require(self.state['status'] == 'RUNNING', 'PREFLIGHT_ALREADY_TERMINAL')
        if error is None:
            require(self.state['stages'] and
                    all(s['status'] == 'DONE' for s in self.state['stages']),
                    'PREFLIGHT_UNFINISHED_STAGE')
        self.state.update(status='PASS' if error is None else 'FAIL', ended_utc=utc())
        if error is not None:
            self.state.update(error=str(error), error_type=type(error).__name__,
                              traceback=traceback.format_exc())
        self._persist()
        write(self.directory / 'PREFLIGHT_RESULT.json', self.state)
        self._log('RESULT', status=self.state['status'],
                  elapsed_seconds=self.state['elapsed_seconds'])
        return self.state


def receipt_metadata(root, package, recovery):
    """Check the complete PREPARED receipt; full reuse checks run in the worker."""
    card = read(package / 'EXECUTION_CARD.json')
    import run
    plan=run.budget_plan(card)
    require(card['pair_limit'] == 1000000000, 'REGISTERED_DISTANCE_CAP')
    cfg = read(package / 'config/EXECUTION.json')
    expected = {'TP_LINK', 'WEMO_POWER', 'SAMSUNG', 'NETATMO'}
    require({d['key'] for d in cfg['devices']} == expected and len(cfg['devices']) == 4,
            'EXACT_REGISTERED_DEVICES')
    existing = []
    for device in cfg['devices']:
        for field in ('raw', 'packet_index', 'chronological_order'):
            spec = device[field]
            path = Path(spec['path']).resolve()
            require(path.is_relative_to(root) and path.is_file(),
                    'REGISTERED_SOURCE_MISSING:' + device['key'] + ':' + field)
            require(path.stat().st_size > 0, 'REGISTERED_SOURCE_EMPTY')
            if 'bytes' in spec:
                require(path.stat().st_size == spec['bytes'], 'REGISTERED_SOURCE_SIZE')
            existing.append(str(path))
    from prepared_reuse import source_package
    source = source_package(card) / 'outputs/encoding/history/NETATMO'
    receipt = read(source/'PREPARE_RESULT.json')
    require(sha(source/'PREPARE_RESULT.json') == card['recovery']['prepared_source_receipt_sha256'] and
            receipt['status']=='PREPARED' and receipt['real_E3_forwards']==0 and
            receipt['all_legal_endpoint_rows_exactly_replayed'] is True,'COMPLETE_PREPARED_RECEIPT')
    for name,field in (('LOGICAL_INPUT.json','logical_input_sha256'),('DECODER_DIAGNOSTIC_AUDIT.json','diagnostic_audit_sha256')):
        require(sha(source/name)==receipt[field],'SMALL_PREPARED_FILE_PIN:'+name)
    require(read(source/'ROLE_BINDING.json')==receipt['role_binding'],'PREPARED_ROLE_BINDING')
    logical = read(source / 'LOGICAL_INPUT.json')
    require(logical['source_sha256'] == receipt['source_sha256'], 'PREPARED_SOURCE_LINK')
    for name in ('selected_snapshots.jsonl.gz', 'candidates.sqlite'):
        require((source/name).is_file() and (source/name).stat().st_size > 0,
                'COMPLETED_CHECKPOINT_FILE_MISSING:' + name)
    selection = read(source / 'selection/SELECTION.json')
    require(selection==receipt['selection'] and selection['status'] == 'SELECTED' and
            isinstance(selection['census_sha256'], str) and
            len(selection['census_sha256']) == 64, 'INDEXED_SELECTION_RECEIPT')
    for role, count in (('ref_rows', 8192), ('dev_rows', 4096)):
        item = selection[role]
        path = Path(item['path']).resolve()
        require(path.parent == (source/'selection').resolve() and path.is_file() and
                item['rows'] == count and sha(path) == item['sha256'],
                'SMALL_SELECTION_FILE_PIN:' + role)
    return dict(status='RECEIPT_METADATA_ACCEPTED', registered_input_files=len(existing),budget=plan,
                retained_REF=8192, retained_DEV=4096,
                full_checks_deferred_to_existing_preparation=[
                    'Complete PREPARED source and selected snapshot hashes',
                    'Selected census UID/physical-origin join and descriptor replay',
                    'Complete three-member encoded-array and batch-ledger verification',
                    'Independent deterministic selection replay before encoding'],
                full_checks_removed=False)


def execute(root, directory=HERE, config=None):
    root = Path(root).resolve()
    package = root / 'runs' / PACKAGE_NAME
    runner = StagedPreflight(directory)
    try:
        require(isinstance(config,dict),'PREFLIGHT_MACHINE_CONFIG')
        with runner.step('PIN_ENVIRONMENT_AND_CARD') as step:
            require(sha(root/'frontend_compat_v1/environment.sh') == config['environment_sha256'], 'ENV_PIN')
            require(sha(root/'runs/history_normal_reference_keyrepair_v1_20261031/config/EXECUTION.json')
                    == config['previous_hpc_config_sha256'], 'PRIOR_HPC_CONFIG')
            require(sha(package/'EXECUTION_CARD.json') == config['execution_card_sha256'], 'INSTALLED_SCIENCE_CARD')
            step['card_sha256'] = config['execution_card_sha256']
        with runner.step('ENVIRONMENT_IMPORTS') as step:
            for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                         'NUMEXPR_NUM_THREADS'):
                os.environ[name] = '4'
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
            sys.dont_write_bytecode = True
            if hasattr(os, 'sched_getaffinity'):
                allowed = sorted(os.sched_getaffinity(0))
                require(bool(allowed), 'EMPTY_CPU_AFFINITY')
                os.sched_setaffinity(0, allowed[:4])
            import numpy as np
            import torch
            observed = dict(system=platform.system(), python=platform.python_version(),
                            numpy=np.__version__, torch=str(torch.__version__).split('+')[0])
            expected=config.get('expected_environment',dict(system='Linux',python='3.11.11',numpy='2.0.1',torch='2.5.1'))
            require(expected==dict(system='Linux',python='3.11.11',numpy='2.0.1',torch='2.5.1') and observed==expected,'FROZEN_PREFLIGHT_ENVIRONMENT')
            torch.set_num_threads(4)
            step['observed'] = observed
        with runner.step('SCIENTIFIC_CODE_PINS') as step:
            sys.path.insert(0, str(package))
            import run
            require(run.PACKAGE.resolve() == package, 'SCIENTIFIC_MODULE_COLLISION')
            card = run.verify('encode')
            step['candidate'] = card['candidate']
        with runner.step('REAL_246_HEADER_QUALIFICATION') as step:
            import header_qualification
            step['receipt'] = header_qualification.qualify()
            require(step['receipt']['status'] == 'PASS_REAL_HEADER_QUALIFICATION',
                    'REAL_HEADER_QUALIFICATION')
        with runner.step('PREVIOUS_FAILURE_AND_BUDGET_RECEIPTS'):
            import recovery
            recovery.previous_status()
        with runner.step('COMPLETE_PREPARED_SMALL_RECEIPTS') as step:
            step['receipt'] = receipt_metadata(root, package, recovery)
        for key in recovery.KEYS:
            with runner.step('COMPLETED_ENCODING_' + key) as step:
                proof = recovery.check_member(key)
                step['receipt'] = {name: str(value) if isinstance(value, Path) else value
                                   for name, value in proof.items()}
        with runner.step('ALL_REGISTERED_ENGINEERING_TESTS') as step:
            import unittest
            modules=sorted(p.stem for p in package.glob('test_*.py'))
            require(bool(modules),'ENGINEERING_TEST_MODULES_PRESENT')
            for p in Path(directory).glob('test_*.py'):
                if p.stem not in modules:modules.append(p.stem)
            registered=config.get('test_modules',modules)
            require(set(registered)==set(modules) and len(registered)==len(set(registered)),'ALL_ENGINEERING_MODULES_REGISTERED')
            suite = unittest.defaultTestLoader.loadTestsFromNames(registered)
            result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
            require(result.wasSuccessful() and result.testsRun>0 and
                (config.get('expected_test_count') is None or result.testsRun==config['expected_test_count']),'REGISTERED_ENGINEERING_TESTS')
            step['tests_run'] = result.testsRun
            step['modules']=registered
        with runner.step('FINAL_CODE_PIN_RECHECK'):
            run.verify('encode')
        runner.finish()
        return 0
    except BaseException as error:
        runner.finish(error)
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--config', type=Path, default=HERE/'PREFLIGHT_CONFIG.json')
    args = parser.parse_args()
    raise SystemExit(execute(args.root, args.output, read(args.config)))
