"""AB native identity and the C0_AB reference order; no teacher preparation."""
import issue27frontend_readout_support_v1 as s


def preflight(r, plan, out, budget):
    budget.check(True, phase='ENTRY_PREFLIGHT')
    s.pin(r['inputs']['membership'], budget.check)
    spec = r['inputs']; manifest = s.pin(spec['historical_train_manifest'], budget.check)
    entries = s.manifest(manifest.parent, spec['historical_train_manifest']['sha256'], budget.check)
    for key in ('initial_AB','initial_AB_receipt','initial_AB_terminal'):
        path = s.pin(spec[key], budget.check)
        s.require(path.parent == manifest.parent and entries[path.name] == spec[key]['sha256'], 'AB_MANIFEST_JOIN')
    rec = s.read_json(s.ROOT/spec['initial_AB_receipt']['path'])
    terminal = s.read_json(s.ROOT/spec['initial_AB_terminal']['path'])
    s.require(terminal['verdict']['status'] == 'PAIRED_COMPARISON_COMPLETE', 'AB_NATIVE_TERMINAL')
    s.require(all(rec[k] == spec['initial_AB_receipt'][k] for k in ('epoch','updates','initial_state_sha256'))
              and rec['state_sha256'] == spec['initial_AB']['state_sha256']
              and rec['file_sha256'] == spec['initial_AB']['sha256'], 'AB_RECEIPT')
    s.require((s.ROOT/spec['initial_AB']['path']).stat().st_size == spec['initial_AB']['bytes'], 'AB_SIZE')
    comparison = r['comparison_training_receipt']
    path = s.pin(comparison['manifest'], budget.check)
    entries = s.manifest(path.parent, comparison['manifest']['sha256'], budget.check)
    worker = s.pin(comparison['terminal'], budget.check)
    s.require(worker.parent == path.parent and entries[worker.name] == comparison['terminal']['sha256'], 'C0_RECEIPT_JOIN')
    s.require(s.read_json(path.parent/'supervisor_terminal.json')['status'] == 'COMPLETE', 'C0_T_INCOMPLETE')
    old = s.read_json(worker)
    s.require(old['status'] == 'WORK_COMPLETE_VERIFIED' and old['stage'] == 'T'
              and old['recipe_sha256'] == r['base_contract']['sha256'], 'C0_PRODUCER_RECEIPT')
    reference = old['result']['candidates']['C0_AB']
    s.require(reference['initial_state_sha256'] == spec['initial_AB']['state_sha256']
              and reference['counts'] == r['schedule']['expected_counts_per_arm']
              and reference['epoch'] == r['schedule']['epochs'], 'C0_MATCHED_HISTORY')
    expected = [{'A':v['A_order_sha256'], 'B':v['B_order_sha256']}
                for v in plan['accounting']['epoch_order_hashes'][:r['schedule']['epochs']]]
    s.require(len(expected) == r['schedule']['epochs'] and old['result']['order_hashes']['C0_AB'] == expected, 'C0_FROZEN_ORDERS')
    receipt = dict(status='INPUT_AND_ORDER_IDENTITY_VERIFIED', recipe_sha256=s.RECIPE_SHA,
                   initial_AB_file_sha256=spec['initial_AB']['sha256'], initial_AB_state_sha256=spec['initial_AB']['state_sha256'],
                   reference_recipe_sha256=r['base_contract']['sha256'], reference_order_hashes=expected,
                   teacher_rows_read=0, guard_pairs_read=0, student_forwards=0, optimizer_steps=0, new_P_stage=False)
    s.atomic_json(out/'entry_receipt.json', receipt)
    return expected
