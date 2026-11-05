"""Compare adapted REFIT to parent, and exercise all dimensions and diagnostics."""
import json
from pathlib import Path
import tempfile
import types
import numpy as np
import torch
import context_core as k
import context_train as adapted
import context_diagnostics as diag
import query_tail_core_v2 as parent_core

HERE = Path(__file__).resolve().parent


class Progress:
    stage = ''
    optimizer_updates = 0

    def tick(self, *args):
        pass


def main(output='LOCAL_ADAPTER_REGRESSION.json'):
    torch.set_num_threads(1)
    rng = np.random.default_rng(91)
    n = 192
    values = rng.normal(size=(n, 794)).astype(np.float32)
    q = rng.uniform(size=(n, 14)).astype(np.float32)
    extra = rng.normal(size=(n, 8)).astype(np.float32)
    indices = np.arange(n)
    rows = [dict(uid=f'{i:064x}', partition='LEARN', fit_role='FIT', use='QUERY', label=i % 2,
                 device='d'+str(i % 3), activity='a', capture_id='c'+str(i % 5), session_id='s'+str(i//4), component_id='k'+str(i//4)) for i in indices]
    spec = json.loads((HERE / 'TRAINING_SPEC_FROZEN.json').read_text())
    design = dict(synthetic_only=True, training=dict(spec['training']['parent_recipe']))
    design['training'].update(epochs=2, batch_size=64)
    norm = np.zeros(768), np.ones(768)
    stages = np.zeros(n, np.uint8)
    # Parent recipe differs only in CPU thread count to honor this experiment's 1 CPU contract.
    module = types.ModuleType('parent_single_cpu')
    exec(compile((HERE / 'query_tail_train_v2.py').read_text().replace('torch.set_num_threads(4)', 'torch.set_num_threads(1)'), 'parent_single_cpu', 'exec'), module.__dict__)
    evidence = []
    with tempfile.TemporaryDirectory(dir=HERE / '.private') as temp:
        temp = Path(temp)
        for seed in (27, 127, 227):
            old = parent_core.classifier(seed, 782)
            new = k.classifier(seed, 790)
            assert torch.equal(old[0].weight, new[0].weight[:, :782])
            assert torch.count_nonzero(new[0].weight[:, 782:]) == 0
            assert torch.equal(old[0].bias, new[0].bias)
            assert all(torch.equal(old[2].state_dict()[key], new[2].state_dict()[key]) for key in old[2].state_dict())
        old = module.train(design, rows, values, q, norm, indices, stages, 'QUERY_TAIL', 27, temp/'parent', Progress(), synthetic=True)
        for arm in k.ARMS:
            folder = temp/arm
            new = adapted.train(design, rows, (values, extra), q, norm, indices, stages, arm, 27, folder, Progress(), synthetic=True)
            if arm == 'FUSION790':
                assert torch.count_nonzero(new[0].weight[:, 782:]) > 0
            without = adapted.train(design, rows, (values, extra), q, norm, indices, stages, arm, 27,
                                    temp/(arm+'_no_diagnostics'), Progress(), synthetic=True, logging_enabled=False)
            assert all(torch.equal(new.state_dict()[key], without.state_dict()[key]) for key in new.state_dict())
            if arm == 'REFIT782':
                assert all(torch.equal(old.state_dict()[key], new.state_dict()[key]) for key in old.state_dict())
                assert np.array_equal(np.load(temp/'parent/batch_losses.npy'), np.load(folder/'batch_losses.npy'))
                for epoch in (1, 2):
                    a = json.loads((temp/'parent'/f'epoch_{epoch:02d}.json').read_text())
                    b = json.loads((folder/f'epoch_{epoch:02d}.json').read_text())
                    assert a == b
            probes = [json.loads(s) for s in (folder/'fixed_probes.jsonl').read_text().splitlines()]
            for probe in probes:
                groups = probe['adam']['groups']
                assert groups['query14_columns']['coordinates'] == (0 if arm == 'STATS8' else 128*14)
                assert groups['context8_columns']['coordinates'] == (0 if arm == 'REFIT782' else 128*8)
            evidence.append(dict(arm=arm, finite=True, diagnostics_probes=len(probes)))
    out = dict(status='PASS', refit_parent_parameters_losses_orders_and_samples_exact=True,
               diagnostics_do_not_change_parameters=True, fusion_context_columns_receive_updates=True,
               fusion_initial_copy_and_zero_columns_seeds=[27, 127, 227], dimensions=evidence,
               scope='Generated local invariance; real Linux runtime gate still mandatory', torch=torch.__version__)
    (HERE/output).write_bytes((json.dumps(out, indent=2)+'\n').encode())
    print(json.dumps(out))


if __name__ == '__main__':
    main()
