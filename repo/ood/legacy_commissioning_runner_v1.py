"""Synthetic demo or separately authorized, pinned LEARN/DEV metadata planning.

There is deliberately no decode, encode, evaluate, train, calibration, download,
HPC or confirmation command. Metadata claims are never labelled real validation.
"""
import argparse
import hashlib
import sys
from pathlib import Path

import legacy_commissioning_common_v1 as c
import legacy_commissioning_policy_v1 as p

FORBIDDEN = ('pcap_decode', 'model_forward', 'training', 'calibration', 'new_confirmation', 'download', 'HPC')


def authorize_metadata(scope, root, out, explicit):
    c.require(explicit is True and isinstance(scope, dict) and scope.get('authorized') is True, 'REAL_METADATA_NOT_AUTHORIZED')
    c.fields(scope, ('schema', 'authorized', 'policy_sha256', 'root', 'output', 'stage', 'roles',
                     'retries', 'inputs', 'forbidden'))
    c.require(scope['schema'] == 'commissioning-metadata-scope-v1' and scope['policy_sha256'] == c.POLICY_SHA,
              'SCOPE_POLICY')
    c.require(scope['stage'] == 'LEARN_DEV_METADATA_PLAN' and scope['roles'] == ['LEARN', 'DEV'] and
              type(scope['retries']) is int and scope['retries'] == 0, 'SCOPE_BOUNDARY')
    c.fields(scope['forbidden'], FORBIDDEN)
    c.require(all(scope['forbidden'][k] is False for k in FORBIDDEN), 'REAL_ACTION_FORBIDDEN')
    root, out = Path(root).resolve(), Path(out).resolve()
    c.require(Path(scope['root']).resolve() == root and Path(scope['output']).resolve() == out, 'SCOPE_PATH')
    c.require(out.parent == root / 'runs', 'OUTPUT_MUST_BE_NEW_TOP_LEVEL_RUN')
    c.require(not out.exists(), 'OUTPUT_EXISTS_NO_RETRY')
    c.fields(scope['inputs'], ('episode', 'sources', 'events'))
    for spec in scope['inputs'].values():
        c.fields(spec, ('path', 'sha256'))
        c.confined(root, spec['path']); c.sha_text(spec['sha256'])
    c.require(len({c.confined(root, spec['path']) for spec in scope['inputs'].values()}) == 3, 'DUPLICATE_INPUT_PATH')
    return root, out


def _seal(out):
    with (out / 'SHA256SUMS').open('x', encoding='utf-8', newline='\n') as stream:
        for file in sorted(out.iterdir()):
            if file.is_file() and file.name != 'SHA256SUMS':
                stream.write(hashlib.sha256(file.read_bytes()).hexdigest() + '  ' + file.name + '\n')


def execute_metadata(root, scope_name, out, explicit=False):
    # Deny before reading even a scope or any protected input when flag is absent.
    c.require(explicit is True, 'REAL_METADATA_NOT_AUTHORIZED')
    root = Path(root).resolve()
    scope = c.parse_json(c.confined(root, scope_name).read_text(encoding='utf-8-sig'))
    root, out = authorize_metadata(scope, root, out, explicit)
    out.mkdir(exist_ok=False)
    c.write_new(out / 'scope_receipt.json', scope)
    try:
        c.load_contracts(root)
        inputs = {key: c.pinned_json(c.confined(root, spec['path']), spec['sha256'])
                  for key, spec in scope['inputs'].items()}
        c.require(inputs['episode'].get('synthetic') is False, 'REAL_INPUT_IS_SYNTHETIC')
        plan = p.plan_bank(inputs['episode'], inputs['sources'], inputs['events'])
        c.write_new(out / 'bank_plan.json', plan)
        c.write_new(out / 'status.json', {'status': 'METADATA_PLAN_COMPLETE_NOT_ENCODED',
            'stage': 'LEARN_DEV_METADATA_PLAN', 'retries': 0, 'bank_registered': False,
            'real_decodes': 0, 'real_forwards': 0, 'optimizer_updates': 0, 'calibration': 0,
            'new_confirmation_opened': False, 'plan_sha256': plan['plan_sha256']})
        _seal(out)
        return plan
    except Exception as exc:
        c.write_new(out / 'failure.json', {'status': 'STOPPED_NO_RETRY', 'error': str(exc),
                                         'retries': 0, 'no_encoder_or_optimizer_in_this_entrypoint': True})
        raise


def synthetic_demo(root, out):
    # No user-provided metadata file may enter this branch.
    from legacy_commissioning_fixture_v1 import fixture, query, ready
    root, out = Path(root).resolve(), Path(out).resolve()
    c.require(out.parent == root / 'runs' and not out.exists(), 'SYNTHETIC_OUTPUT_EXISTS_OR_OUTSIDE_RUNS')
    c.load_contracts(root)
    out.mkdir(exist_ok=False)
    try:
        cases = []
        for tcp, udp in ((40, 40), (1, 70), (0, 2), (1, 0), (0, 0)):
            e, sources, events = fixture(tcp, udp)
            plan = p.plan_bank(e, sources, events)
            cases.append({'tcp_candidates': tcp, 'udp_candidates': udp, 'plan': plan,
                          'routes_before_ready': {str(x): p.route_query(plan, query(plan, x)) for x in (6, 17)},
                          'routes_after_ready': {str(x): p.route_query(plan, query(plan, x), ready(plan)) for x in (6, 17)}})
        c.write_new(out / 'synthetic_cases.json', cases)
        c.write_new(out / 'status.json', {'status': 'SYNTHETIC_DEMO_COMPLETE_NOT_A_SCIENTIFIC_RESULT',
                     'cases': len(cases), 'real_inputs_read': 0, 'real_decodes': 0, 'model_forwards': 0,
                     'optimizer_updates': 0, 'new_confirmation_opened': False, 'retries': 0})
        _seal(out)
        return cases
    except Exception as exc:
        c.write_new(out / 'failure.json', {'status': 'STOPPED_NO_RETRY', 'error': str(exc)})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    demo = sub.add_parser('synthetic-demo')
    demo.add_argument('--output', type=Path, required=True)
    real = sub.add_parser('metadata-plan')
    real.add_argument('--scope', required=True)
    real.add_argument('--output', type=Path, required=True)
    real.add_argument('--authorize-metadata-scope', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'synthetic-demo':
            synthetic_demo(args.root, args.output)
        else:
            execute_metadata(args.root, args.scope, args.output, args.authorize_metadata_scope)
    except (c.Stop, OSError, ValueError, TypeError, KeyError) as exc:
        print('STOPPED_NO_RETRY: ' + str(exc), file=sys.stderr)
        return 1
    print('COMPLETE; NO_DECODE; NO_MODEL_FORWARD; NO_TRAINING; NO_CONFIRMATION')
    return 0


if __name__ == '__main__':
    sys.exit(main())
