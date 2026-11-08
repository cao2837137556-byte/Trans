import argparse,time,traceback
from pipeline_parent import dependencies,pipeline,write
from readiness import environment_gate,fidelity
p=argparse.ArgumentParser();p.add_argument('--phase',required=True);a=p.parse_args();t=time.monotonic()
try:
    dependencies();r={'ENVIRONMENT':environment_gate,'FIDELITY':fidelity,'PIPELINE':pipeline}[a.phase]();r['seconds']=time.monotonic()-t;write(a.phase+'_RESULT.json',r)
except Exception as e:write(a.phase+'_STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()));raise
