"""Bounded decoder and CPU workers, with visible durable progress and no retries."""
import contextlib
import csv
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import legacy_unsw_archival_common_v1 as c


def tree_rss():
    if os.name=='nt':
        from legacy_qref_common_v1 import rss_bytes
        return rss_bytes()
    processes={}
    for p in Path('/proc').glob('[0-9]*'):
        try:
            fields=(p/'stat').read_text().rsplit(')',1)[1].split()
            processes[int(p.name)]=(int(fields[1]),int((p/'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE'))
        except (OSError,ValueError,IndexError): continue
    ids={os.getpid()}
    while True:
        new={pid for pid,(parent,rss) in processes.items() if parent in ids}-ids
        if not new: break
        ids.update(new)
    return sum(processes.get(pid,(0,0))[1] for pid in ids)


class Progress:
    def __init__(self,out,limits):
        self.out=Path(out); self.out.mkdir(parents=True,exist_ok=False)
        self.limits=limits; self.started=time.monotonic(); self.last=0.; self.stage='PREFLIGHT'
        self.children=[]; self.error=None; self.closed=threading.Event(); self.latest={}; self.disk_at=0.
        self.rss=0; self.measure_key=None; self.measure_started=self.started; self.measure_done=0; self.emit('RUNNING')
        self.thread=threading.Thread(target=self.watch,daemon=True); self.thread.start()

    def watch(self):
        while not self.closed.wait(2):
            try:
                self.guard()
            except Exception as exc:
                self.error=str(exc)
                for p in list(self.children):
                    if p.poll() is None: p.kill()
                return

    def guard(self):
        c.require(self.error is None,self.error or 'WATCHDOG_FAILURE')
        c.require(not (self.out/'STOP_REQUESTED').exists(),'USER_STOP_REQUESTED')
        c.require(time.monotonic()-self.started<self.limits['wall_seconds'],'WALL_TIME_LIMIT')
        self.rss=tree_rss()
        c.require(self.rss<self.limits['memory_gib']*1024**3,'COMBINED_MEMORY_LIMIT')
        if time.monotonic()-self.disk_at>30:
            self.disk_at=time.monotonic()
            used=sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())
            c.require(used<self.limits['disk_gib']*1024**3,'OUTPUT_DISK_LIMIT')
            c.require(shutil.disk_usage(self.out).free>1024**3,'OUTPUT_DISK_FREE_LIMIT')

    def emit(self,status='RUNNING',**extra):
        c.write(self.out/'status.json',dict(status=status,stage=self.stage,
            elapsed_seconds=time.monotonic()-self.started,utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            rss_gib=self.rss/1024**3,retries=0,optimizer_updates=0,calibration_updates=0,
            historical_holdout_opened=False,**extra),replace=True)

    def tick(self,done=0,total=0,force=False):
        self.guard()
        now=time.monotonic()
        if self.measure_key!=(self.stage,total) or done<self.measure_done:
            self.measure_key=(self.stage,total); self.measure_started=now; self.measure_origin=done
        self.measure_done=done
        elapsed=now-self.measure_started
        rate=(done-self.measure_origin)/elapsed if elapsed>30 else None
        if force or time.monotonic()-self.last>5:
            self.last=time.monotonic(); self.latest=dict(completed=done,total=total,
                percent=100*done/total if total else None,
                remaining_seconds_estimate=(total-done)/rate if rate is not None and rate>0 else None,
                estimate_scope='current stage only; measured throughput, not a completion guarantee')
            self.emit(**self.latest)

    def stop(self,status,error=None,**extra):
        if status=='COMPLETE':
            self.guard()
        self.closed.set(); self.thread.join(timeout=5)
        for p in self.children:
            if p.poll() is None: p.kill()
        for p in self.children:
            try: p.wait(timeout=15)
            except subprocess.TimeoutExpired: pass
        self.emit(status,error=error,**extra)


def fields(runtime):
    value=list(dict.fromkeys([f for f in runtime[2] if f not in ('tcp.payload','rtsp.url','rtsp.cseq')]+['tcp.stream','udp.stream']))
    c.require(len(value)==56,'DECODER_FIELDS')
    return value


@contextlib.contextmanager
def decode(path,spec,runtime,progress,log,tshark):
    progress.guard()
    names=fields(runtime)
    command=[str(tshark),'-n','-r',str(path),'-T','fields','-E','header=y','-E','separator=/t','-E','quote=d','-E','occurrence=f']
    for name in names: command+=['-e',name]
    with Path(log).open('x',encoding='utf-8') as err:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',errors='strict')
        progress.children.append(process)
        try:
            reader=csv.DictReader(process.stdout,delimiter='\t',quotechar='"')
            c.require(reader.fieldnames==names,'DECODER_HEADER')
            def checked():
                for row in reader:
                    c.require(None not in row and None not in row.values(),'DECODER_COLUMNS')
                    yield row
            yield checked()
            progress.guard()
            c.require(process.wait(timeout=60)==0,'DECODER_EXIT')
        finally:
            if process.poll() is None: process.kill()
            process.wait(timeout=60); process.stdout.close()
    c.require(Path(log).stat().st_size==0,'DECODER_STDERR')


def e3_runtime(root,synthetic=False):
    import torch
    import issue27ckda_d1_e3_embed_v1 as embed
    import issue27ckda_d0_resource_pilot_v1 as translator
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    root=Path(root)
    if not synthetic:
        model,tokenizer,collator=embed.build_e3_runtime(translator,root/'vendor/netFound',root/'vendor/netFound-base','cpu')
        model.requires_grad_(False)
    else:
        from types import SimpleNamespace
        config_type,collator_type,_,tokenizer_type=translator.import_netfound(root/'vendor/netFound')
        config=config_type.from_pretrained(str(root/'vendor/netFound-base'),local_files_only=True)
        config.pretraining=False; config.compile=False
        tokenizer=tokenizer_type(config=config); tokenizer.pretraining=True; tokenizer.raw_labels=False
        collator=collator_type(pad_token_id=tokenizer.pad_token_id)
        class StandIn:
            def eval(self): return self
            def base_transformer(self,**batch):
                value=(batch['input_ids'].float()%101)/101
                return SimpleNamespace(last_hidden_state=value[:,:,None]*torch.linspace(.01,1.,768)[None,None,:])
        model=StandIn()
    return embed,translator,model,tokenizer,collator


def feature_worker(root,out,shard,explicit):
    c.require(explicit,'REAL_EXECUTION_NOT_AUTHORIZED')
    root,out=Path(root),Path(out)
    c.verify(root,exact=False); c.verify(out/'manifests'); c.verify(out/'flows')
    launch=c.read(out/'launch.json')
    c.require(launch['recipe_sha256']==c.RECIPE_SHA and launch['scope']=='MATERIALIZE_FROZEN_SCORE_EXPORT','WORKER_AUTHORITY')
    progress=Progress(out/('worker_%02d'%shard),c.read(root/'runtime_contract.json')['limits'])
    try:
        import numpy as np
        embed,translator,model,tokenizer,collator=e3_runtime(root)
        spec=c.read(out/'flows/index.json')['shards'][shard]
        target=progress.out/'features.npy'
        features=np.lib.format.open_memmap(target,mode='w+',dtype=np.float32,shape=(spec['count'],768))
        uids=[]; flows=[]; done=0
        progress.stage='E3_FEATURES'
        def flush():
            nonlocal done,flows
            if not flows: return
            progress.guard()
            result=embed.embed_flows(translator,model,tokenizer,collator,flows,'cpu',16)
            c.require(result.shape==(len(flows),768) and result.dtype==np.float32 and np.isfinite(result).all(),'E3_OUTPUT')
            features[done:done+len(flows)]=result; done+=len(flows); flows=[]
            progress.tick(done,spec['count'])
        with gzip.open(out/'flows'/spec['file'],'rt',encoding='utf-8') as f:
            for line in f:
                r=json.loads(line); uids.append(r['uid']); flows.append(r['flow'])
                if len(flows)==16: flush()
        flush(); features.flush(); del features
        c.require(done==spec['count'] and len(set(uids))==len(uids),'WORKER_COVERAGE')
        c.write(progress.out/'uids.json',uids)
        progress.stop('COMPLETE',completed=done,total=done)
        c.seal(progress.out)
    except BaseException as exc:
        progress.stop('STOPPED_NO_RETRY',repr(exc))
        raise


def launch_features(root,out,progress):
    root,out=Path(root),Path(out)
    workers=c.read(root/'runtime_contract.json')['workers']; logs=[]; processes=[]
    try:
        for shard in range(workers):
            stream=(out/('worker_%02d.log'%shard)).open('x',encoding='utf-8'); logs.append(stream)
            p=subprocess.Popen([sys.executable,str(root/'repo/ood/legacy_unsw_archival_runner_v1.py'),
                 'worker','--root',str(root),'--output',str(out),'--shard',str(shard),'--authorize-frozen-evaluation'],
                 stdout=stream,stderr=subprocess.STDOUT)
            processes.append(p); progress.children.append(p)
        while any(p.poll() is None for p in processes):
            progress.guard()
            c.require(all(p.poll() in (None,0) for p in processes),'FEATURE_WORKER_FAILED')
            done=0; total=0
            for shard in range(workers):
                p=out/('worker_%02d'%shard)/'status.json'
                if p.exists():
                    state=c.read(p); done+=state.get('completed',0); total+=state.get('total',0)
            progress.tick(done,148408)
            time.sleep(2)
        c.require(all(p.returncode==0 for p in processes),'FEATURE_WORKER_FAILED')
    finally:
        for p in processes:
            if p.poll() is None: p.kill()
        for p in processes: p.wait(timeout=30)
        for f in logs: f.close()
