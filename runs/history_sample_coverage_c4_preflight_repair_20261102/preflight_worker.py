"""Durable, staged engineering preflight for the unchanged installed C4 card.

Full raw hashes and indexed-census integrity checks remain mandatory inside the
existing preparation worker. This preflight does not duplicate those large reads.
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
PACKAGE_NAME = 'history_sample_coverage_c4_header_repair_v1_20261101'
CARD_SHA = 'fdd491483c8408b8054cf195de5cfaee82c2f0772d56313ee1ae5ca34633350b'
ENV_SHA = '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf'
PREVIOUS_CONFIG_SHA = 'b2c80539fa91008191cecb1fa81899e0ce49e3a3f0c764a05d98677b7bed7c3d'
COUNTS = {'HIST_REF': 2612450, 'HIST_DEV': 980497}
TEST_MODULES = ('test_runner', 'test_topup', 'test_memory_worker',
                'test_recovery', 'test_decoder_guard', 'test_resume_prepare')


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
    """Check small receipts and existence; no raw/chronological/census hashing."""
    card = read(package / 'EXECUTION_CARD.json')
    require(card['recovery']['prior_wall_seconds_charged'] == 24534 and
            card['recovery']['remaining_seconds'] == 4266 and
            card['limits']['total_wall_seconds'] == 28800,
            'CUMULATIVE_WALL_BUDGET')
    require(card['pair_limit'] == 1000000000 and card['limits']['encoded'] == 36864,
            'REGISTERED_COMPUTE_CAPS')
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
    source = recovery.LATEST / 'outputs/encoding/history/NETATMO'
    checkpoint = read(source / 'CENSUS_CHECKPOINT.json')
    require(checkpoint['previous_job'] == '180552' and
            checkpoint['legal_endpoints'] == COUNTS and
            checkpoint['complete_first_pass_packets'] == 4967010,
            'COMPLETED_CENSUS_RECEIPT')
    for name in ('LOGICAL_INPUT.json', 'ROLE_BINDING.json', 'decoder_pass1.stderr.log'):
        require(sha(source/name) == checkpoint['files'][name]['sha256'],
                'SMALL_CHECKPOINT_RECEIPT_PIN:' + name)
    logical = read(source / 'LOGICAL_INPUT.json')
    require(logical['source_sha256'] == checkpoint['files']['chronological.pcapng']['sha256'],
            'CHRONOLOGICAL_RECEIPT_LINK')
    for name in ('chronological.pcapng', 'candidates.sqlite'):
        require((source/name).is_file() and (source/name).stat().st_size > 0,
                'COMPLETED_CHECKPOINT_FILE_MISSING:' + name)
    selection = read(source / 'selection/SELECTION.json')
    require(selection['status'] == 'SELECTED' and
            isinstance(selection['census_sha256'], str) and
            len(selection['census_sha256']) == 64, 'INDEXED_SELECTION_RECEIPT')
    for role, count in (('ref_rows', 8192), ('dev_rows', 4096)):
        item = selection[role]
        path = Path(item['path']).resolve()
        require(path.parent == (source/'selection').resolve() and path.is_file() and
                item['rows'] == count and sha(path) == item['sha256'],
                'SMALL_SELECTION_FILE_PIN:' + role)
    return dict(status='RECEIPT_METADATA_ACCEPTED', registered_input_files=len(existing),
                retained_REF=8192, retained_DEV=4096,
                full_checks_deferred_to_existing_preparation=[
                    'Raw/index/order full SHA256', 'Indexed-census full SHA256',
                    'SQLite quick_check, counts and full UID join',
                    'Continuous endpoint replay and exact warning multiset'],
                full_checks_removed=False)


def execute(root, directory=HERE):
    root = Path(root).resolve()
    package = root / 'runs' / PACKAGE_NAME
    runner = StagedPreflight(directory)
    try:
        with runner.step('PIN_ENVIRONMENT_AND_CARD') as step:
            require(sha(root/'frontend_compat_v1/environment.sh') == ENV_SHA, 'ENV_PIN')
            require(sha(root/'runs/history_normal_reference_keyrepair_v1_20261031/config/EXECUTION.json')
                    == PREVIOUS_CONFIG_SHA, 'PRIOR_HPC_CONFIG')
            require(sha(package/'EXECUTION_CARD.json') == CARD_SHA, 'INSTALLED_SCIENCE_CARD')
            step['card_sha256'] = CARD_SHA
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
            require(observed == dict(system='Linux', python='3.11.11', numpy='2.0.1',
                                     torch='2.5.1'), 'FROZEN_PREFLIGHT_ENVIRONMENT')
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
        with runner.step('RETAINED_CHECKPOINT_SMALL_RECEIPTS') as step:
            step['receipt'] = receipt_metadata(root, package, recovery)
        for key in recovery.KEYS:
            with runner.step('COMPLETED_ENCODING_' + key) as step:
                proof = recovery.check_member(key)
                step['receipt'] = {name: str(value) if isinstance(value, Path) else value
                                   for name, value in proof.items()}
        with runner.step('REGISTERED_59_ENGINEERING_TESTS') as step:
            import unittest
            suite = unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)
            result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
            require(result.wasSuccessful() and result.testsRun == 59,
                    'REGISTERED_ENGINEERING_TESTS')
            step['tests_run'] = result.testsRun
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
    args = parser.parse_args()
    raise SystemExit(execute(args.root, args.output))
