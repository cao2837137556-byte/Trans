"""Freeze one concrete implementation, existing assets and source-only scope."""
from common import *


def main():
    need(not (HERE / 'PREPARE_ATTEMPT.json').exists(), 'CONTRACT_FROZEN_AFTER_FIRST_REAL_STAGE')
    proposal = ROOT / 'runs/mainline_docs/collab/20261031_history_normal_reference_c3_contract_review_and_d3_codex.md'
    need(sha(proposal) == '81dc2150811bb6a40ae7821b456492820c15bf01a6e2f40dc6f0f0f75c686581', 'DESIGN_PIN')
    import legacy_reference_sample_prepare_v1 as prep
    roster, catalog = prep.source_catalog()
    captures = [dict(s) for s in catalog if s.get('file_id') in (189, 190, 191)]
    need(len(captures) == 3 and all(s['provenance'] == 'normal' and s['use'] == 'REFERENCE' for s in captures), 'REGISTERED_NORMAL_REFERENCE')
    normality = ('CIC original member paths 3-Interactions/Cameras/HeimVision Camera/LAN_WATCH; '
                 'publisher normal interaction category, verified device MAC and pre-existing REFERENCE time role. '
                 'No independent per-packet maliciousness oracle; interaction-attack is only a project capture prefix.')
    for spec in captures:
        path = Path(spec['path']); spec['path'] = path.relative_to(ROOT).as_posix()
        need(sha(path) == spec['sha256'] and path.stat().st_size == spec['bytes'], 'RAW_SOURCE_PIN')
        spec['normality_evidence'] = normality
    pins = {}
    def pin(path, expected=None):
        path = Path(path).resolve(); need(path.is_relative_to(ROOT), 'PIN_OUTSIDE_PROJECT')
        value = sha(path)
        if expected: need(value == expected, 'PRIOR_PIN_CHANGED:' + str(path))
        pins[path.relative_to(ROOT).as_posix()] = value
    pin(proposal)
    previous = ROOT / 'runs/history_normal_reference_d2_review_v1_20261031/REVIEW_EVIDENCE.json'
    pin(previous, '5b100c61584cc343939178f7dd62c9631eac7d83d5a2ed02fce40bee82665ca4')
    prior = read(previous)
    for path, identity in prior['inputs'].items(): pin(ROOT / path, identity['sha256'])
    for pool, item in prior['heim']['overlap'].items(): need(all(v == 0 for v in item['matches'].values()), 'PRIOR_OVERLAP_AUDIT')
    assets = read(C1 / 'config/ASSETS.json'); pin(C1 / 'config/ASSETS.json')
    def collect(item):
        if isinstance(item, dict):
            if 'path' in item and 'sha256' in item: pin(ROOT / item['path'], item['sha256'])
            else:
                for v in item.values(): collect(v)
        elif isinstance(item, list):
            for v in item: collect(v)
    collect(assets)
    pin(C2 / 'output/RESULT.json', '092ff373b6231b52969d59aa54f84b976ab8ef3facb1c0a3bd67c891cfc722e8')
    for rel, value in read(C2 / 'output/ARTIFACTS.json').items():
        if rel.startswith(('ab/', 'dev/')): pin(C2 / 'output' / rel, value['sha256'])
    pin(C2 / 'FINAL_ACCEPTANCE.json', '8528bba55bdc0ef2c7571e9c409742a67566ed10fa2b3550f158e8a0248f503d')
    dpins = read(D2 / 'EVIDENCE_SHA256.json'); census = {}
    for name in ('TP_LINK', 'SAMSUNG', 'WEMO_POWER'):
        rel = f'retrieved/history/{name}/selection/SELECTION.json'
        pin(D2 / rel, dpins[rel])
        census[name] = [g for g in read(D2 / rel)['groups'] if g['role'] == 'HIST_REF']
        for group in census[name]:
            need(group['cap'] == CAP and (group['candidate_rows'] > CAP or group['selected_rows'] == group['candidate_rows']), 'B_NOT_UNCHANGED_BY_RULE')
    rel = 'retrieved/dev/QUERIES.jsonl.gz'; pin(D2 / rel, dpins[rel])
    # Pin scientific Python dependencies without importing training or drivers.
    for path in (ROOT / 'repo/ood').glob('*.py'): pin(path)
    for folder in (C1 / 'hnr', ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src'):
        for path in folder.glob('*.py'): pin(path)
    for source in ('reused_and_new_file_metadata.json', 'review_summary.json', 'selected_new_members.json', 'prospective_time_membership.json'):
        pin(ROOT / 'runs/legacy_reference_material_audit_v1_20260916' / source)
    runtime = read(C1 / 'config/EXECUTION.json')['encoder']
    pin(Path(runtime['runtime_files_manifest']['path']), runtime['runtime_files_manifest']['sha256'])
    encoder_paths = {k: v for k, v in pins.items() if k.startswith('repo/ood/') or k.startswith(C1.relative_to(ROOT).as_posix() + '/hnr/')}
    manifest = dict(schema='c3-input-manifest-v1', captures=captures, known_macs=sorted(d['mac'] for d in roster),
        normality_basis=normality, old_a_rows=assets['a_history']['rows']['path'], B_census=census,
        input_sha256=pins, encoder_source_sha256=encoder_paths,
        tshark=dict(path='C:/Program Files/Wireshark/tshark.exe', sha256=sha('C:/Program Files/Wireshark/tshark.exe')),
        overlap_evidence=dict(path=previous.relative_to(ROOT).as_posix(), sha256=sha(previous), findings=prior['heim']['overlap']))
    write(HERE / 'INPUT_MANIFEST.json', manifest)
    code = {p.name: sha(p) for p in [*HERE.glob('*.py'), *HERE.glob('*.slurm')]}
    card = dict(candidate=CANDIDATE, authorization='User transmitted Antigravity acceptance and instruction to implement and run once, 2026-11-01 Asia/Shanghai.',
        design_sha256=sha(proposal), limits=LIMITS, code_sha256=code, input_manifest_sha256=sha(HERE / 'INPUT_MANIFEST.json'),
        selection='Complete admitted device/protocol domains <=4096, otherwise retain frozen C1 selection; no query feedback.',
        lambda_value=.25, guard='ALL_DEVICE_TCP_SYN1_ACK0_KEEP_RAW', max_new_tcp=212, max_new_udp=66,
        evaluate_once=True, automatic_retry=False, no_new_training=True,
        adoption='All full/primary four-head protection gates pass; no pool/device normal FPR or FP-count increase; Heim primary ensemble FPR strictly decreases.',
        failure='Freeze C2, never pick another frame set after seeing AB results.',
        evidence='CONSUMED_DEVELOPMENT_ONLY', stages=['prepare_local', 'encode_HPC_Python311', 'saved_input_AB_local_once', 'verify_and_freeze'])
    write(HERE / 'EXECUTION_CARD.json', card)
    for path in (HERE / 'INPUT_MANIFEST.json', HERE / 'EXECUTION_CARD.json'):
        path.with_name(path.name + '.sha256').write_text(sha(path) + '  ' + path.name + '\n', encoding='utf-8')
    progress('IMPLEMENTED_PENDING_TESTS', 'C3 实现及执行卡已封存，准备工程检查', input_pins=len(pins), encoder_source_pins=len(encoder_paths))


if __name__ == '__main__': main()
