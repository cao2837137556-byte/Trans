"""Explicit, audited v3r1-to-v4 adoption of COMPLETE roles only."""
from pathlib import Path
from checkpoint import PackedRoleSpool, atomic_json, canonical, require, sha
from streaming import ROOT
from runtime_control import current_status

PARENT_CARD = 'runs/edge_formal_gate_deployment_v3_20261104/ENGINEERING_CARD.json'
PARENT_SHA = 'bd28847882260862f20d161d59b39e71770d95711e55cd54ad992eda40bda6b8'
SOURCE_OUTPUT = '/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_gate_deployment_v3_20261104/outputs/gate_181699'


def adopt(card, output, source_card, identity, refs, selected, binding, guard):
    from worker import read, input_binding
    source = card.get('complete_role_adoption')
    if source is None: return
    require(source == dict(parent_card=PARENT_CARD, parent_sha256=PARENT_SHA,
        output=SOURCE_OUTPUT, roles=['NORMAL', 'HTTP']), 'ADOPTION_EXPLICIT_CONTRACT')
    require(sha(ROOT/PARENT_CARD) == PARENT_SHA, 'ADOPTION_PARENT_CARD_SHA')
    parent = read(ROOT/PARENT_CARD)
    require(parent['selection_seal_sha256'] == card['selection_seal_sha256']
            and parent['runtime_identity'] == identity == card['runtime_identity']
            and parent['C5_method_freeze_sha256'] == card['C5_method_freeze_sha256'], 'ADOPTION_SCIENTIFIC_CONTRACT')
    for name, digest in parent['artifact_pins'].items():
        require(card['artifact_pins'].get(name) == digest and sha(ROOT/name) == digest, 'ADOPTION_PARENT_PIN:'+name)
    prior = Path(source['output'])
    require(prior.is_dir() and not prior.is_symlink(), 'ADOPTION_SOURCE_DIRECTORY')
    require(current_status(prior, card_sha256=PARENT_SHA)['status'] == 'STOP', 'ADOPTION_SOURCE_TERMINAL')
    old_binding = input_binding(parent, identity, source_card)
    audit = dict(status='COMPLETE_ROLE_ADOPTION_VERIFIED', parent_card_sha256=PARENT_SHA,
        new_binding_sha256=__import__('hashlib').sha256(canonical(binding)).hexdigest(), roles={},
        partial_udp_adopted=False, mathematical_core_changed=False)
    for role in source['roles']:
        expected = sorted((refs if role == 'NORMAL' else [])+selected[role], key=lambda row: row['uid'])
        target = PackedRoleSpool(Path(output)/'spools'/role, binding, role, [r['uid'] for r in expected])
        already_complete = target.is_complete()
        if already_complete and (target.root/'REPLAY_COVERAGE.json').is_file(): continue
        guard.progress('AUDITING_PRIOR_COMPLETE_ROLE', role=role)
        origin = PackedRoleSpool(prior/'spools'/role, old_binding, role, [r['uid'] for r in expected])
        require(origin.is_complete(), 'ADOPTION_COMPLETE_REQUIRED')
        coverage = read(origin.root/'REPLAY_COVERAGE.json'); raw = source_card['raw_inputs'][role]
        require(coverage.get('last_frame') == coverage.get('expected_records') == raw['records']
                and coverage.get('raw_sha256') == raw['sha256'] and coverage.get('generator_exhausted') is True
                and coverage.get('final_raw_identity_pass') is True and coverage.get('replay_to_eof') is True,
                'ADOPTION_COMPLETE_RAW_EOF')
        count = 0
        from worker import merge_selected
        for row in expected:
            guard()
            snapshot = origin.load(row['uid'])
            require(canonical(merge_selected(snapshot, row)) == canonical(snapshot), 'ADOPTION_METADATA')
            if not already_complete: target.append(snapshot)
            count += 1
        if not already_complete: target.complete(generator_exhausted=True, raw_final_identity_pass=True)
        # Independently read every new payload before granting the new binding.
        for row in expected:
            guard()
            require(canonical(target.load(row['uid'])) == canonical(origin.load(row['uid'])), 'ADOPTION_VALUE_PARITY')
        atomic_json(target.root/'REPLAY_COVERAGE.json', coverage)
        audit['roles'][role] = dict(rows=count, all_chunk_and_snapshot_sha_verified=True,
            source_complete_sha256=sha(origin.root/'COMPLETE.json'), source_binding_sha256=sha(origin.root/'BINDING.json'),
            target_complete_sha256=sha(target.root/'COMPLETE.json'), snapshots_exact=True, raw_eof_verified=True)
        atomic_json(Path(output)/'COMPLETE_ROLE_ADOPTION.json', audit)
        guard.progress('PRIOR_COMPLETE_ROLE_ADOPTED', role=role, rows=count)
