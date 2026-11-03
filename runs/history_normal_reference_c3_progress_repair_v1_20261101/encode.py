"""Encode only the frozen new A references, in the accepted HPC environment."""
from collections import defaultdict
import platform
import time
from common import *


def batches(entries, encoder, progress_callback):
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from hnr.encoding import physical_batch
    import continuous_input_v3 as inp
    from constrained_onboarding_reference_v2 import reference_descriptor
    embed, _, model, tokenizer, collator = encoder
    groups, examples, descriptors = defaultdict(list), {}, []
    for i, entry in enumerate(entries):
        q, _ = reference_descriptor(entry['body'], entry['row'])
        need(np.array_equal(q, np.asarray(entry['q14'], dtype=np.float32)), 'SNAPSHOT_Q14_REPLAY')
        example = tokenize(tokenizer, entry['body']['flow'])
        inp.verify_tokenized(entry['body']['flow'], entry['body']['provenance'], example)
        shape = (entry['row']['protocol'], max(example['dataset_burst_sizes']) + 1, len(example['dataset_burst_sizes']))
        groups[shape].append(i); examples[i] = example; descriptors.append(q)
    e3 = np.empty((len(entries), 768), dtype=np.float32)
    receipts, ledger = [], []
    for shape, indices in sorted(groups.items()):
        ordered = sorted(indices, key=lambda i: entries[i]['uid'])
        for start in range(0, len(ordered), 16):
            ix = ordered[start:start + 16]; ee = [examples[i] for i in ix]
            batch = collator(ee); verify_batch(ee, batch)
            actual, physical = physical_batch(batch, len(ix), tensor_hash)
            progress_callback('ATTEMPT', len(receipts), len(entries), shape, len(ix), physical)
            values = embed.core.e3_forward_batches(model, [actual], 'cpu')
            need(values.shape == (physical, 768) and values.dtype == np.float32 and np.isfinite(values).all(), 'E3_OUTPUT')
            if len(ix) == 1:
                need(all(values[j].tobytes() == values[0].tobytes() for j in range(16)), 'SINGLETON_CLONES_NOT_IDENTICAL')
            for j, index in enumerate(ix):
                e3[index] = values[j]
                receipts.append(dict(uid=entries[index]['uid'], slot=index, shape=shape,
                    tensor_sha256=tensor_hash(actual, j), feature_sha256=hashlib.sha256(values[j].tobytes()).hexdigest()))
            ledger.append(dict(shape=shape, logical=len(ix), physical=physical))
            progress_callback('COMPLETE', len(receipts), len(entries), shape, len(ix), physical)
    return e3, np.asarray(descriptors, dtype=np.float32), receipts, ledger


def main():
    import torch
    card, manifest = verify_contract(remote=True)
    observed = dict(system=platform.system(), python=platform.python_version(), numpy=np.__version__,
                    torch=str(torch.__version__).split('+')[0])
    need(observed == dict(system='Linux', python='3.11.11', numpy='2.0.1', torch='2.5.1'), 'FROZEN_ENVIRONMENT:' + str(observed))
    prepare_pin = read(HERE / 'ENCODE_REQUEST.json')
    for name, expected in prepare_pin['prepared_sha256'].items():
        need(sha(HERE / 'prepared' / name) == expected, 'PREPARED_PIN:' + name)
    prep = read(HERE / 'prepared/PREPARE_RESULT.json')
    need(prep['status'] == 'PREPARED' and prep['old_q14_replay_rows'] == 11, 'PREPARE_ACCEPTANCE')
    entries = list(rows(HERE / 'prepared/SNAPSHOTS.jsonl.gz'))
    need(0 < len(entries) <= LIMITS['encoded_new_rows'], 'ENCODING_ROW_LIMIT')
    need([r['row'] for r in entries] == list(rows(HERE / 'prepared/REFERENCES.jsonl.gz')), 'PREPARED_METADATA_JOIN')
    write(HERE / 'ENCODE_ATTEMPT.json', dict(candidate=CANDIDATE, request_sha256=sha(HERE / 'ENCODE_REQUEST.json'), retries=0), exclusive=True)
    out = HERE / 'encoded'; out.mkdir(exist_ok=False)
    write(out / 'ENVIRONMENT.json', observed)
    started = time.monotonic()
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    from hnr.encoding import new_encoder
    config = read(C1 / 'config/EXECUTION.json')['encoder']
    progress('ENCODING_LOAD', '超算正在加载冻结的编码器', new_rows=len(entries))
    encoder, identity = new_encoder(config)
    ledger_path = out / 'BATCH_LEDGER.jsonl'
    def callback(status, done, total, shape, logical, physical):
        with ledger_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(status=status, done=done, total=total, shape=shape, logical=logical, physical=physical)) + '\n')
        progress('ENCODING', '超算正在编码新增参考点', status=status, completed=done, total=total)
    e3, q14, receipts, ledger = batches(entries, encoder, callback)
    write_rows(out / 'references.jsonl.gz', [e['row'] for e in entries])
    with (out / 'references.npz').open('xb') as stream:
        np.savez(stream, uid=np.asarray([e['uid'] for e in entries], dtype='<U64'), e3=e3, q14=q14)
    write_rows(out / 'tensor_receipts.jsonl.gz', receipts)
    verify_contract(remote=True)
    write(out / 'ENCODE_RESULT.json', dict(status='COMPLETE', candidate=CANDIDATE, new_rows=len(entries),
        physical_positions=sum(b['physical'] for b in ledger), batches=ledger, runtime_identity=identity,
        elapsed_seconds=time.monotonic() - started, model_training=False, query_encoding=0,
        encoder_source_pins_unchanged=True, execution_card_sha256=sha(HERE / 'EXECUTION_CARD.json'),
        request_sha256=sha(HERE / 'ENCODE_REQUEST.json'), files={p.name: sha(p) for p in out.iterdir() if p.is_file()}))
    progress('ENCODED', '新增参考编码完成，等待取回核验与一次评价', new_rows=len(entries))


if __name__ == '__main__': main()
