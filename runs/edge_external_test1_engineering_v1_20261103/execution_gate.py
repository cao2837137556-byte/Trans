"""Fail-closed checks for a future Edge evaluation; never submits a job."""
import hashlib
import json
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 2**20), b''):
            h.update(block)
    return h.hexdigest()


def readiness(card, root):
    failures = []
    if card.get('status') != 'FROZEN_ENGINEERING_READY_FOR_AUTHORIZATION':
        failures.append('CARD_NOT_ENGINEERING_READY')
    if not card.get('population', {}).get('sealed'):
        failures.append('POPULATION_NOT_SEALED')
    if not card.get('baselines', {}).get('source_calibrated'):
        failures.append('BASELINE_SOURCE_CALIBRATION_PENDING')
    if card.get('full_streaming_resume_worker') != 'PASS_VALIDATED':
        failures.append('FULL_STREAMING_RESUME_WORKER_PENDING')
    preflight = card.get('same_runtime_preflight', {})
    if preflight.get('status') != 'REAL_SLICE_E2E_PASS':
        failures.append('SAME_RUNTIME_E2E_PENDING')
    if not preflight.get('runtime_identity') or preflight.get('runtime_identity') != card.get('runtime_identity'):
        failures.append('RUNTIME_IDENTITY_NOT_EQUAL')
    budget = card.get('budget', {})
    for key in ('cpu', 'rss_bytes', 'disk_bytes', 'wall_seconds', 'encoding_rows', 'distance_pairs'):
        if type(budget.get(key)) is not int or budget[key] <= 0:
            failures.append('BUDGET_NOT_FIXED:' + key)
    if budget.get('automatic_resubmit') is not False or budget.get('automatic_extension') is not False:
        failures.append('AUTOMATIC_RETRY_OR_EXTENSION_UNSET')
    pins = card.get('artifact_pins', {})
    if not pins:
        failures.append('NO_ARTIFACT_PINS')
    for relative, expected in pins.items():
        path = Path(root) / relative
        if not path.is_file() or sha(path) != expected:
            failures.append('ARTIFACT_IDENTITY:' + relative)
    return dict(status='PASS' if not failures else 'BLOCKED', failures=failures)


def require_evaluation_authorization(card_path, authorization_path, root):
    card_path, authorization_path = Path(card_path), Path(authorization_path)
    card = json.loads(card_path.read_text(encoding='utf-8-sig'))
    result = readiness(card, root)
    if result['status'] != 'PASS':
        raise RuntimeError('ENGINEERING_GATE:' + ','.join(result['failures']))
    authorization = json.loads(authorization_path.read_text(encoding='utf-8-sig'))
    if (authorization.get('scope') != 'EDGE_EXTERNAL_TEST_1_FULL_EVALUATION'
            or authorization.get('user_authorized') is not True
            or authorization.get('card_sha256') != sha(card_path)):
        raise RuntimeError('ACTUAL_BOUND_USER_EVALUATION_AUTHORIZATION_REQUIRED')
    return result
