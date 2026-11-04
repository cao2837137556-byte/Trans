"""Bounded review probes. No models, raw packets, external predictions or network.

Production source and old receipts remain read-only. All simulated authorization,
mutated dependencies and lifecycle fixtures live in automatically cleaned temp dirs.
The fixture authorizations are never passed to a worker or used for real work.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'runs/edge_formal_execution_v1_20261103'
sys.path.insert(0, str(SOURCE))
import engineering_gate as gate
from checkpoint import atomic_json, canonical, sha
from worker import Guard, input_binding
import psutil


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def child_memory(path):
    payload = bytearray(64 * 1024**2)
    for i in range(0, len(payload), 4096):
        payload[i] = 1
    child = psutil.Process()
    parent = child.parent()
    atomic_json(path, dict(child_rss=child.memory_info().rss,
                          parent_plus_child_rss=parent.memory_info().rss + child.memory_info().rss))
    time.sleep(2.5)


def child_scratch(output, scratch_root):
    scratch = scratch_root / ('edge-gate-owned-' + 'a' * 32)
    scratch.mkdir()
    owner = dict(scope=gate.SCOPE, pid=os.getpid(), output=str(output.resolve()))
    atomic_json(scratch / 'OWNERSHIP.json', owner)
    # Model the actual main phase: unlike crash/resume, it has no SCRATCH_main marker.
    (scratch / 'fixture.sqlite').write_bytes(b'x' * 65536)
    atomic_json(output / 'CHILD_READY.json', dict(scratch=str(scratch), **owner))
    try:
        time.sleep(30)
    finally:
        (scratch / 'FINALLY_RAN').write_text('yes')


def pins_and_closure():
    card = read(SOURCE / 'ENGINEERING_GATE_CARD_DRAFT.json')
    checked = {}
    for name, expected in card['artifact_pins'].items():
        actual = sha(ROOT / name)
        assert actual == expected, name
        checked[name] = actual
    dependencies = [
        'repo/ood/continuous_input_engineering_v1.py',
        'repo/ood/continuous_features_v3.py',
        'repo/ood/query_tail_core_v2.py',
        'repo/ood/legacy_reference_sample_prepare_v1.py',
        'repo/ood/legacy_unsw_archival_runtime_v1.py',
    ]
    facts = {name: dict(exists=(ROOT/name).is_file(),
                       artifact_pin=name in card['artifact_pins'],
                       scientific_input_pin=name in card['scientific_input_artifact_pins'],
                       actual_sha256=sha(ROOT/name)) for name in dependencies}
    assert all(not x['artifact_pin'] for x in facts.values())
    # Exercise the real gate against an isolated synthetic file tree with the
    # same pin key sets. Only content hashes and readiness/auth fixture differ.
    with tempfile.TemporaryDirectory(prefix='edge11-pin-review-') as tmp:
        root = Path(tmp)
        fixture = copy.deepcopy(card)
        for field in ('artifact_pins', 'scientific_input_artifact_pins'):
            for name in fixture[field]:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('synthetic pinned fixture\n', encoding='utf-8')
                fixture[field][name] = sha(target)
        fixture['status'] = gate.READY
        fixture['independent_review'] = {'status': 'PASS', 'fixture_only': True}
        cp, ap = root/'CARD.json', root/'AUTH.json'
        atomic_json(cp, fixture)
        atomic_json(ap, dict(scope=gate.SCOPE, user_authorized=True, card_sha256=sha(cp), fixture_only=True))
        target = root / dependencies[0]
        target.write_text('version A\n', encoding='utf-8')
        before = gate.require_engineering_authorization(cp, ap, root)
        source = dict(raw_inputs={r: dict(bytes=1, sha256=r) for r in ('NORMAL','HTTP','UDP')})
        binding_before = input_binding(before, {'fixture': 'same'}, source)
        target.write_text('version B with different context semantics\n', encoding='utf-8')
        after = gate.require_engineering_authorization(cp, ap, root)
        assert binding_before == input_binding(after, {'fixture': 'same'}, source)
    return dict(verified_card_artifacts=len(checked), missing_direct_dependencies=facts,
                synthetic_dependency_change_accepted=True, scientific_binding_unchanged=True,
                production_files_mutated=False)


def resource_blind_wait():
    with tempfile.TemporaryDirectory(prefix='edge11-rss-review-') as tmp:
        root = Path(tmp)
        scratch = root/'scratch'; scratch.mkdir()
        budget = dict(wall_seconds=600, rss_bytes=psutil.Process().memory_info().rss+80*1024**2,
                      disk_bytes=1024**3, scratch_bytes=1024**3)
        guard = Guard(root, scratch, budget, formal=False)
        guard()
        code = gate.bounded_process([sys.executable, '-B', __file__, '--child-memory', str(root/'child.json')],
                                    root/'child.log', time.monotonic()+20)
        guard.last = 0
        guard()
        observed = read(root/'child.json')
        assert code == 0 and observed['parent_plus_child_rss'] > budget['rss_bytes']
        assert observed['child_rss'] < budget['rss_bytes']
        assert guard.max_rss < observed['parent_plus_child_rss']
        return dict(child_exit=code, configured_rss_bytes=budget['rss_bytes'],
                    reported_max_tree_rss_bytes=guard.max_rss, **observed,
                    exceeded_combined_limit_without_guard_stop=True,
                    child_alone_below_limit=True,
                    note='64MiB child only; observes the production blocking wait with before/after Guard calls')


def supervisor_timeout_cleanup():
    with tempfile.TemporaryDirectory(prefix='edge11-timeout-review-') as tmp:
        root=Path(tmp); output=root/'output'; output.mkdir(); scratch=root/'scratch'; scratch.mkdir()
        original=gate.bounded_process
        seen=[]
        def shortened(command, log, deadline, on_exit=None):
            seen.append(on_exit is not None)
            return original([sys.executable, '-B', __file__, '--child-scratch', str(output), str(scratch)],
                            log, time.monotonic()+6, on_exit=on_exit)
        with patch.object(gate, 'require_engineering_authorization', return_value={}), \
             patch.object(gate.platform, 'system', return_value='Linux'), \
             patch.object(gate, 'bounded_process', side_effect=shortened):
            try:
                gate.run(root/'unused-card', root/'unused-auth', root/'unused-runtime', output)
            except RuntimeError as exc:
                assert str(exc)=='ENGINEERING_HARD_DEADLINE'
            else:
                raise AssertionError('Timeout not raised')
        ready=read(output/'CHILD_READY.json'); owned=Path(ready['scratch'])
        assert owned.parent.resolve()==scratch.resolve()
        assert owned.is_dir() and (owned/'fixture.sqlite').is_file()
        assert not (owned/'FINALLY_RAN').exists()
        assert seen==[False] and (output/'ENGINEERING_SUPERVISOR_STOP.json').exists()
        return dict(supervisor_stop_written=True, main_on_exit_cleanup_registered=False,
                    owned_scratch_remained_after_timeout=True,
                    simulated_database_bytes=(owned/'fixture.sqlite').stat().st_size,
                    fixture_removed_by_temp_directory_after_observation=True)


def stale_receipt():
    with tempfile.TemporaryDirectory(prefix='edge11-status-review-') as tmp:
        root=Path(tmp); output=root/'output'; output.mkdir(); sr=root/'scratch'; sr.mkdir()
        scratch=sr/'edge-gate-owned-fixture'; scratch.mkdir()
        old=dict(schema='EDGE_FORMAL_WORKER_ENGINEERING_GATE_RECEIPT_V1', status='PASS',
                 card_sha256='fixture_same_card', recovery={'attempt_id': 'a'*32})
        atomic_json(output/'ENGINEERING_GATE_RECEIPT.json', old)
        atomic_json(output/'PROGRESS.json', {'stage':'ENGINEERING_GATE_PASS'})
        runtime=root/'runtime.json'; atomic_json(runtime,{})
        with patch.object(gate,'require_engineering_authorization',return_value={}), \
             patch.object(gate,'runtime_setup',return_value=(output,sr,scratch,None,{})), \
             patch.object(gate,'prepare_inputs',side_effect=RuntimeError('INJECTED_REPLAY_FAILURE')):
            try:
                gate.execute(root/'unused-card',root/'unused-auth',runtime,output,time.monotonic()+60)
            except RuntimeError as exc:
                assert str(exc)=='INJECTED_REPLAY_FAILURE'
            else:
                raise AssertionError('Failure not raised')
        assert read(output/'ENGINEERING_GATE_RECEIPT.json')==old
        assert read(output/'PROGRESS.json')['stage']=='ENGINEERING_GATE_PASS'
        assert (output/'ENGINEERING_STOP.json').exists()
        return dict(old_PASS_receipt_retained=True, old_PASS_progress_retained=True,
                    new_STOP_written=True, no_attempt_binding_in_stop=True,
                    scope='Injected replay failure on supported output-directory reentry; no actual model or runtime setup')


def main():
    result=dict(schema='EDGE_EXPERIMENT11_INDEPENDENT_REVIEW_REPRO_V1',
                source_sha256={p.name:sha(p) for p in SOURCE.glob('*.py')},
                pins_and_closure=pins_and_closure(), resource_wait=resource_blind_wait(),
                timeout_cleanup=supervisor_timeout_cleanup(), stale_receipt=stale_receipt(),
                models_loaded=0, raw_packets_read=0, external_quality_evaluations=0,
                cloud_jobs_submitted=0, production_code_modified=False)
    atomic_json(HERE/'REPRO_RESULTS.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--child-memory':
        child_memory(Path(sys.argv[2]))
    elif len(sys.argv)==4 and sys.argv[1]=='--child-scratch':
        child_scratch(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        main()
