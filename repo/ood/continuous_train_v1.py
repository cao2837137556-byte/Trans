"""Fixed endpoints; only FIT rows enter normalization or optimizers."""
from pathlib import Path
import hashlib
import math
import numpy as np
import torch
import torch.nn.functional as F
import continuous_common_v1 as c
import continuous_model_v1 as m


def train(design, metadata, values, norm, indices, bank, arm, seed, out, progress, synthetic=False):
    c.require(arm in (*c.ARMS, 'LEARNED') and seed in c.SEEDS, 'TRAIN_ARM')
    hp = design['training']
    if synthetic:
        c.require(len(metadata) <= 256 and hp['epochs'] <= 2 and design.get('synthetic_only') is True, 'SYNTHETIC_BOUND')
    else:
        c.require(hp['epochs'] == 40 and hp['batch_size'] == 256, 'FROZEN_TRAINING')
    rr = [metadata[int(i)] for i in indices]
    w = m.weights(rr)
    if arm == 'LEARNED':
        c.require(bank is not None and all(r['partition'] == 'LEARN' for r in bank.rows), 'SOURCE_REFERENCE_ONLY')
    out = Path(out); out.mkdir(exist_ok=False)
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    model = m.Metric(seed) if arm == 'LEARNED' else m.classifier(seed, values.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=hp['lr'], weight_decay=hp['weight_decay'],
        betas=tuple(hp['betas']), eps=hp['eps'], amsgrad=False, foreach=False)
    generator = torch.Generator(device='cpu').manual_seed(seed)
    n = len(indices); count = 0; orders = []; subsets = []
    for epoch in range(hp['epochs']):
        order = torch.randperm(n, generator=generator).numpy()
        orders.append(hashlib.sha256(order.tobytes()).hexdigest())
        if bank is not None:
            subsets.append(c.digest({str(k): [bank.rows[i]['uid'] for i in bank.subset(k, design, seed, epoch)] for k in bank.keys}))
        loss_total = 0.
        for start in range(0, n, hp['batch_size']):
            local = order[start:start+hp['batch_size']]
            selected = np.asarray(indices)[local]
            rows = [metadata[int(i)] for i in selected]
            z = m.normalized(values, selected, norm)
            yy = torch.tensor([r['label'] for r in rows], dtype=torch.float32)
            optimizer.zero_grad(set_to_none=True)
            if arm == 'LEARNED':
                own, valid = bank.own(z, rows, model, design, minimum=1, seed=seed, epoch=epoch)
                c.require(bool(valid.all()), 'FIT_REFERENCE_MISSING')
                matrix, mask = bank.matrix(z, rows, model, design, minimum=1, seed=seed, epoch=epoch)
                c.require(bool(mask.any(1).all()), 'FIT_DONOR_MISSING')
                li = torch.where(yy == 0, F.softplus(-10*own), F.softplus(10*matrix.max(1).values))
            else:
                li = F.binary_cross_entropy_with_logits(model(z).flatten(), yy, reduction='none')
            loss = (li * torch.from_numpy(w[local])).sum() * (n/len(local))
            c.require(bool(torch.isfinite(loss)), 'NONFINITE_LOSS')
            loss.backward()
            c.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()), 'GRADIENT_INVALID')
            optimizer.step()
            c.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), 'PARAMETER_INVALID')
            count += 1; loss_total += float(loss.detach()) * len(local)/n
            progress.optimizer_updates = count
            progress.tick(count, hp['epochs'] * math.ceil(n/hp['batch_size']))
        c.write(out/('epoch_%02d.json' % (epoch+1)), dict(epoch=epoch+1, updates=count, loss=loss_total))
    c.require(count == hp['epochs'] * math.ceil(n/hp['batch_size']), 'UPDATE_COUNT')
    c.save_arrays(out/'head.npz', **{k: v.detach().numpy() for k, v in model.state_dict().items()})
    c.write(out/'endpoint.json', dict(status='COMPLETE', arm=arm, seed=seed, epochs=hp['epochs'],
        rows=n, updates=count, uid_sha256=c.uid_sha(r['uid'] for r in rr), order_hashes=orders,
        reference_subset_hashes=subsets, weight_sha256=hashlib.sha256(w.tobytes()).hexdigest(),
        normalizer_sha256=c.digest([norm[0].tolist(), norm[1].tolist()]),
        design_digest=c.digest(design), head_sha256=c.sha(out/'head.npz'), synthetic_only=synthetic,
        zero_vector_invocations=getattr(model,'zero_counts',None)))
    c.seal(out); c.verify(out)
    return model.eval()


def load_model(folder, arm, seed, design):
    folder = Path(folder); c.verify(folder)
    receipt = c.read(folder/'endpoint.json')
    c.require(receipt['status'] == 'COMPLETE' and receipt['arm'] == arm and receipt['seed'] == seed and
              receipt['design_digest'] == c.digest(design), 'ENDPOINT_IDENTITY')
    model = m.Metric(seed) if arm == 'LEARNED' else m.classifier(seed, 794 if arm == 'RECENT_STATE' else 768)
    with np.load(folder/'head.npz', allow_pickle=False) as saved:
        c.require(set(saved.files) == set(model.state_dict()), 'ENDPOINT_KEYS')
        model.load_state_dict({k: torch.from_numpy(saved[k].copy()) for k in saved.files})
    return model.eval().requires_grad_(False)
