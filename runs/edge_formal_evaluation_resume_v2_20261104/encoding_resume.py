"""Read-only source import of validated committed encoding batches."""
import hashlib
import os
from pathlib import Path
from checkpoint import BatchStore,canonical,require,sha,atomic_json
from worker import read
from streaming import ROOT
from runtime_control import current_status

def encoding_binding(card,identity):
    spec=card['encoding_resume_source'];parent=ROOT/spec['parent_card']
    require(sha(parent)==spec['card_sha256'],'ENCODING_PARENT_CARD_SHA')
    old=read(parent)
    for key in ('scientific_input_artifact_pins','dependency_envelope','selection_seal_sha256','runtime_identity'):
        require(canonical(old[key])==canonical(card[key]),'ENCODING_SCIENTIFIC_IDENTITY:'+key)
    require(identity==old['runtime_identity'],'ENCODING_RUNTIME_IDENTITY')
    return dict(execution_card_sha256=spec['card_sha256'],selection_seal_sha256=old['selection_seal_sha256'],
                runtime_identity=identity,artifact_pins=old['artifact_pins'])

def import_batches(card,identity,output,plan,guard):
    spec=card['encoding_resume_source'];source=Path(spec['output']);output=Path(output)
    require(source.is_absolute() and not source.is_symlink() and source.resolve().is_relative_to(ROOT.parents[1])
        and source.resolve()!=output.resolve(),'ENCODING_SOURCE_SCOPE')
    pointer=sha(source/'CURRENT_ENGINEERING_ATTEMPT.json')
    stopped=current_status(source,card_sha256=spec['card_sha256'])
    require(stopped['status']=='STOP' and stopped['scratch_cleanup']['complete'] is True and
        sha(source/'CURRENT_ENGINEERING_ATTEMPT.json')==spec['pointer_sha256'],'ENCODING_STOPPED_SOURCE')
    binding=encoding_binding(card,identity)
    target=BatchStore(output/'encoded',binding)
    require(read(source/'encoded/BINDING.json')==read(target.root/'BINDING.json'),'ENCODING_EXACT_BINDING')
    require(read(source/'BATCH_PLAN.json')==plan,'ENCODING_EXACT_PLAN')
    expected={e['batch_id']:e['uids'] for e in plan};records=[]
    source_batches=source/'encoded/batches'
    before=sorted(p.name for p in source_batches.iterdir())
    require(before and set(before)<=set(expected),'SOURCE_COMMITTED_BATCH_SET')
    for name in before:
        guard();origin=source_batches/name
        record=target._validate(origin,expected[name]) # read-only; no source ledger write
        destination=target.batches/name;destination.mkdir(exist_ok=False)
        names=set(record['files'])|{'MANIFEST.json'}
        for filename in sorted(names):
            p=origin/filename;require(p.is_file() and not p.is_symlink(),'COMMITTED_SOURCE_FILE')
            os.link(p,destination/filename)
        require(target._validate(destination,expected[name])==record,'IMPORTED_BATCH_EXACT')
        records.append(dict(batch_id=name,rows=len(expected[name]),manifest_sha256=sha(origin/'MANIFEST.json')))
        if len(records)%64==0:guard.progress('IMPORT_ENCODED_BATCHES',validated_batches=len(records),source_batches=len(before))
    require(sorted(p.name for p in source_batches.iterdir())==before and
        sha(source/'CURRENT_ENGINEERING_ATTEMPT.json')==pointer,'STOPPED_SOURCE_UNCHANGED')
    checked=BatchStore(target.root,binding)
    require(set(checked.records)==set(before),'IMPORTED_COMMITTED_SET')
    receipt=dict(status='PASS_VALIDATED_COMMITTED_ENCODING_IMPORT',source=spec,
        batches=len(records),rows=sum(r['rows'] for r in records),records=records,
        source_pointer_unchanged=True,pending_imported=False,binding_sha256=checked.binding_sha256)
    atomic_json(output/'ENCODING_IMPORT.json',receipt)
    return binding,receipt
