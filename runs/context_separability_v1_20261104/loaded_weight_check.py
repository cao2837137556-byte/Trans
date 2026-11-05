"""Require live tensor equality, resolving only actual shared storage aliases."""
def verify_weights(live,saved):
    import torch
    keys=set(saved.keys());aliases={};checked=0
    def identity(t):return (t.untyped_storage().data_ptr(),t.storage_offset(),tuple(t.shape),tuple(t.stride()),t.dtype)
    for key,value in live.items():
        if not key.startswith('base_transformer.'):continue
        assert not value.is_meta,'META_WEIGHT:'+key
        canonical=key
        if key not in keys:
            assert key.startswith('base_transformer.encoder.layer.') and key.endswith('.position_embeddings.weight'),'UNEXPECTED_MISSING_WEIGHT:'+key
            candidates=[k for k in keys if k in live and identity(live[k])==identity(value)]
            assert len(candidates)==1,('UNRESOLVED_SHARED_WEIGHT',key,candidates)
            canonical=candidates[0];aliases[key]=canonical
        expected=saved.get_tensor(canonical).to(dtype=value.dtype)
        assert torch.equal(value.cpu(),expected),'LOADED_WEIGHT_DIFFERENT:'+key
        checked+=1
    assert checked>0
    return dict(checked_names=checked,shared_aliases=aliases,all_exact=True)

if __name__=='__main__':
    import torch,json
    from pathlib import Path
    class Saved(dict):
        def get_tensor(self,key):return self[key]
    a='base_transformer.encoder.layer.0.position_embeddings.weight';b='base_transformer.encoder.layer.9.position_embeddings.weight'
    value=torch.arange(12,dtype=torch.float32).reshape(3,4);saved=Saved({b:value.clone()})
    assert verify_weights({a:value,b:value},saved)['shared_aliases']=={a:b}
    for case in [{a:value.clone(),b:value},{a:value+1,b:value}]:
        try:verify_weights(case,saved)
        except AssertionError:pass
        else:raise AssertionError('UNSHARED_MISSING_NAME_ACCEPTED')
    try:verify_weights({b:value+1},saved)
    except AssertionError:pass
    else:raise AssertionError('WRONG_WEIGHT_ACCEPTED')
    Path(__file__).with_name('WEIGHT_AUDIT_REGRESSION.json').write_text(json.dumps(dict(status='PASS',checks=['actual_storage_alias_exact','same_values_different_storage_rejected','different_unshared_values_rejected','wrong_saved_weight_rejected']),indent=2))
    print('PASS: loaded weight identity regression')
