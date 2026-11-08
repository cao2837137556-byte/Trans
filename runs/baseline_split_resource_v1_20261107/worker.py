import argparse,time,traceback,torch
from pipeline_parent import dependencies,write,pipeline
from readiness import environment_gate,fidelity
from split_resource import split,epoch,review
def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);phase=p.parse_args().phase;t=time.monotonic()
    try:
        torch.set_num_threads(1);dependencies()
        fn={'ENVIRONMENT':environment_gate,'FIDELITY':fidelity,'PIPELINE':pipeline,'SPLIT':split,'RESOURCE_REVIEW':review}.get(phase)
        result=fn() if fn else epoch(phase);dependencies();result['seconds']=time.monotonic()-t;write(phase+'_RESULT.json',result)
    except Exception as e:write(phase+'_STOP.json',dict(status='FAIL',error=str(e),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
