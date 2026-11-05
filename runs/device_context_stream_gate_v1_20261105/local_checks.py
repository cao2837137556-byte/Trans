"""Existing local raw prefixes only; independent reference, no downloaded data."""
import ast,json,struct
from pathlib import Path
from stream_core import Engine
from packet_reader import packets
from test_core import run
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
 for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 unit=run();card=json.loads((ROOT/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json').read_text());counts={}
 for role in ['NORMAL','HTTP','UDP']:
  engine=Engine();history=[];clock=None;checks=0
  for frame,t,p,reason in packets(Path(card['raw_inputs'][role]['path'])):
   clock=t if clock is None else max(clock,t);event=None
   if p and p[-2]=='dca632fb69b5':
    proto,size,src,dst,sp,dp,md,ms=p;conn=(proto,src,dst,sp,dp);event=(md,proto,size,src,conn);history.append((clock,event))
   engine.advance(frame,t,0,event)
   if frame%137==0:
    for proto in [6,17]:
     expected=[]
     for w in [10**9,10**10]:
      rows=[e for c,e in history if clock-w<c<=clock and e[1]==proto]
      expected.extend([len(rows),sum(e[2] for e in rows),len({e[3] for e in rows}),len({e[4] for e in rows})])
     assert tuple(expected)==engine.integers('dca632fb69b5',proto);checks+=1
   if frame==5000:break
  counts[role]=dict(frames=frame,integer_checks=checks)
 receipt=dict(status='PASS',synthetic=unit,existing_local_raw_prefixes=counts,linux_gate='PENDING',real_training=0)
 (HERE/'LOCAL_CHECKS.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
