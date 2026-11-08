import argparse,time,traceback
import torch
from pipeline_parent import dependencies,write,pipeline
from readiness import fidelity,source_prepare,dte_pilot,catboost_pilot,profile,seal,environment_gate

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);phase=p.parse_args().phase;start=time.monotonic()
    try:
        dependencies();torch.set_num_threads(1)
        if phase=='ENVIRONMENT':r=environment_gate()
        elif phase=='PIPELINE':r=pipeline()
        elif phase=='FIDELITY':r=fidelity()
        elif phase=='SOURCE':r=source_prepare()
        elif phase=='DTE_PILOT':r=dte_pilot()
        elif phase=='CAT_PILOT':r=catboost_pilot()
        elif phase=='SEAL':r=seal()
        else:r=profile(phase)
        dependencies();r['seconds']=time.monotonic()-start;write(phase+'_RESULT.json',r)
    except Exception as e:write(phase+'_STOP.json',dict(status='FAIL',error=str(e),traceback=traceback.format_exc(),seconds=time.monotonic()-start));raise
if __name__=='__main__':main()
