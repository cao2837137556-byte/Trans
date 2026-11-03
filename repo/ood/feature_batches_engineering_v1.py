"""Bounded SQLite batch-id assignment with exactly the original shape/UID order."""


def assign_batches(db,*,batch_size=16,update_chunk=4096):
    if batch_size!=16 or type(update_chunk) is not int or update_chunk<1:
        raise ValueError('FIXED_MODEL_BATCH_REQUIRED')
    db.execute('CREATE INDEX shape_uid ON snapshots(protocol,width,bursts,uid)')
    cursor=db.execute('SELECT uid,protocol,width,bursts FROM snapshots ORDER BY protocol,width,bursts,uid')
    batch_id=0;previous=None;offset=0;updates=[];rows=0;peak=0
    try:
        for uid,proto,width,bursts in cursor:
            key=(proto,width,bursts)
            if key!=previous or offset==16:
                batch_id+=1;offset=0;previous=key
            updates.append((batch_id-1,uid));offset+=1;rows+=1
            peak=max(peak,len(updates))
            if len(updates)==update_chunk:
                db.executemany('UPDATE snapshots SET batch_id=? WHERE uid=?',updates);updates=[]
        if updates:db.executemany('UPDATE snapshots SET batch_id=? WHERE uid=?',updates)
    finally:cursor.close()
    db.execute('CREATE INDEX batch_uid ON snapshots(batch_id,uid)');db.commit()
    return dict(rows=rows,batches=batch_id,peak_update_rows=peak,model_batch_size=16)
