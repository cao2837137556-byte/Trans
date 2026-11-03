"""Validate incremental head budgets and their frozen evidence."""
import math
from pathlib import Path
import continuous_common_v3 as c

PHASES = {'PREPARATION','MLP_TRAIN','TABM_TRAIN','LIGHTGBM_TRAIN','HEAD_EVALUATION','ONBOARDING'}


def load(path):
    path=Path(path).resolve(); p=c.read(path)
    c.require(p['schema']=='modern-head-resource-plan-v1' and p['status']=='REVIEWABLE','MODERN_RESOURCE_SCHEMA')
    c.require(p['processes']==1 and p['threads']==4 and p['cpus']==8,'MODERN_RESOURCE_CONCURRENCY')
    c.require(set(p['phases'])==PHASES,'MODERN_RESOURCE_PHASES')
    peaks=[]
    for phase in p['phases'].values():
        c.require(phase['basis'] in ('ESTIMATED','MEASURED') and phase['evidence'] and
                  phase['explanation'] and phase['includes_mappings_and_temporary_buffers'] is True,'MODERN_RESOURCE_EVIDENCE')
        total=0.; names=set()
        for v in phase['components']:
            c.require(v['name'] not in names and v['explanation'] and type(v['instances']) is int and v['instances']>0 and
                      type(v['gib_per_instance']) in (int,float) and math.isfinite(v['gib_per_instance']) and v['gib_per_instance']>0,'MODERN_RESOURCE_COMPONENT')
            names.add(v['name']); total+=v['instances']*v['gib_per_instance']
        c.require(phase['simultaneous_peak_gib']==math.ceil(total*2)/2,'MODERN_RESOURCE_SUM')
        peaks.append(phase['simultaneous_peak_gib'])
        for ref in phase['evidence']:
            source=(path.parent/ref['path']).resolve()
            c.require(source.is_relative_to(path.parent),'MODERN_EVIDENCE_ESCAPE'); c.pin(source,ref['sha256'])
    c.require(.1<=p['margin_fraction']<=.5 and p['memory_gib']==math.ceil(max(peaks)*(1+p['margin_fraction'])/2)*2,'MODERN_RESOURCE_ALLOCATION')
    c.require(max(peaks)<p['guard_gib']<p['memory_gib'],'MODERN_RESOURCE_GUARD')
    for key in ('disk_gib','minimum_free_gib','export_included_limit_gib','wall_seconds'):
        c.require(type(p[key]) in (int,float) and math.isfinite(p[key]) and p[key]>0,'MODERN_RESOURCE_LIMIT:'+key)
    c.require(p['minimum_free_gib']>=p['disk_gib']+p['export_included_limit_gib']+1,'MODERN_DISK_RESERVE')
    c.require(p['wall_seconds']==70*3600 and p['slurm_time']=='3-00:00:00' and p['disk_basis'] and p['time_basis'],'MODERN_TIME_BASIS')
    return p
