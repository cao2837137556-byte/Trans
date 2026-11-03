"""Replay every real warning header before submitting continuous RECENT work."""
import json
import numpy as np
from hnr.common import PACKAGE,read,require,sha
from decoder_guard import audit_packet

def qualify():
    probe=read(PACKAGE/'qualification/HEADER_ROWS.json')
    cfg=read(PACKAGE/'config/EXECUTION.json')
    spec=next(d for d in cfg['devices'] if d['key']=='NETATMO')
    rr=probe['rows'];require(len(rr)==246 and len({r['logical_frame'] for r in rr})==246,'REAL_HEADER_QUALIFICATION_COVERAGE')
    index=np.load(spec['packet_index']['path'],mmap_mode='r',allow_pickle=False)
    order=np.load(spec['chronological_order']['path'],mmap_mode='r',allow_pickle=False)
    audits=[]
    with open(spec['raw']['path'],'rb') as stream:
        for record in rr:
            frame=record['logical_frame'];row=record['row']
            require(int(row['frame.number'])==frame and len(row)==56,'REAL_HEADER_FIELD_FRAME_JOIN')
            audits.append(audit_packet(row,stream,index[int(order[frame-1])]))
    return dict(status='PASS_REAL_HEADER_QUALIFICATION',packets=len(audits),
                probe_sha256=sha(PACKAGE/'qualification/HEADER_ROWS.json'),
                audit_frames=[a['frame'] for a in audits],
                scope='Static original outer headers only; continuous full-census and warning-signature replay still required.')

if __name__=='__main__':print(json.dumps(qualify()))
