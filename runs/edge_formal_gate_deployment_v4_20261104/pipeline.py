"""Ordinary bounded transfer/progress program; no SSH authentication or retry jobs."""
import concurrent.futures
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('_edge_existing_transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py')
transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport);transport.HERE=HERE
read,write,sha,need=transport.read,transport.write,transport.sha,transport.need
record={}


def progress(stage,**extra):
    if stage!=record.get('stage'):
        for key in ('done_bytes','total_bytes','error','worker','engineering_current','attempt_receipt','attempt_id','scheduler_state'):record.pop(key,None)
    record.update(stage=stage,updated_utc=datetime.now(timezone.utc).isoformat(),**extra)
    record.update(cpu=1,memory_gib=8,wall_seconds=7200,formal_external_evaluation=False,automatic_resubmit=False)
    write(HERE/'PROGRESS.json',record)


def request(route,*args,**kwargs):
    value=transport.request(route,*args,**kwargs)
    if route=='state':
        delivery=read(HERE/'DELIVERY.json')
        need(value.get('receiver_source_sha256')==delivery['receiver_source_sha256'] and
             value.get('namespace')==HERE.name,'REMOTE_RECEIVER_IDENTITY')
    return value


def prepare_once():
    state=request('state')
    if state.get('prepare_receipt'):return state['prepare_receipt']
    intent=HERE/'PREPARE_ATTEMPT.json';future=None
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        if not intent.exists():
            write(intent,dict(status='PREPARATION_REQUEST_INTENT'))
            future=pool.submit(request,'prepare',timeout=900)
        end=time.monotonic()+920
        while time.monotonic()<end:
            state=request('state',timeout=30)
            progress('PREPARING',message='核验原863件基包、v4依赖、原包和冻结运行时。',remote_prepare=state.get('prepare_status'))
            if state.get('prepare_receipt'):
                write(HERE/'PREPARE_RECEIPT.json',state['prepare_receipt']);return state['prepare_receipt']
            need(not state.get('last_error'),'REMOTE_PREPARATION_FAILED:'+str(state.get('last_error')))
            if future is not None and future.done():
                result=future.result();write(HERE/'PREPARE_RECEIPT.json',result);return result
            time.sleep(5)
    raise RuntimeError('PREPARATION_OUTCOME_UNCONFIRMED_NO_DUPLICATE_REQUEST')


def submit_once(action=request, phase='preflight'):
    need(phase in ('preflight','gate'),'SUBMIT_PHASE')
    key='preflight_job' if phase=='preflight' else 'gate_job'
    prefix='PREFLIGHT_' if phase=='preflight' else ''
    state=action('state')
    if state.get(key):
        write(HERE/(prefix+'SUBMIT_RECEIPT.json'),state[key]);return state[key]
    need(not (HERE/(prefix+'SUBMIT_ATTEMPT.json')).exists(),'SUBMISSION_UNCERTAIN_NO_AUTOMATIC_RETRY')
    write(HERE/(prefix+'SUBMIT_ATTEMPT.json'),dict(status='INTENT_BEFORE_POST',allowed_jobs=1,phase=phase))
    try:job=action('submit',timeout=300)
    except Exception:
        job=action('state').get(key)
        if not job:raise RuntimeError('SUBMISSION_OUTCOME_UNKNOWN_DO_NOT_RESUBMIT') from None
    need(str(job.get('job_id','')).isdigit() and job.get('phase')==phase,'SUBMISSION_JOB_PHASE_REQUIRED')
    write(HERE/(prefix+'SUBMIT_RECEIPT.json'),job);return job


def retrieve(state):
    progress('RETRIEVING',job_id=state['job']['job_id'],message='只取回小型回执和日志，完整spool与编码批次保留超算。')
    connection,response=request('results',timeout=120)
    try:
        size=int(response.getheader('Content-Length'));digest=response.getheader('X-Content-SHA256')
        need(0<size<=32*1024**2,'RESULT_TRANSFER_LIMIT')
        target=HERE/'.private/results.tar';target.parent.mkdir(exist_ok=True)
        with target.open('wb') as out:
            remaining=size
            while remaining:
                data=response.read(min(1024**2,remaining));need(data,'RESULT_EARLY_EOF');out.write(data);remaining-=len(data)
        need(sha(target)==digest,'RESULT_TRANSFER_SHA')
    finally:connection.close()
    output=HERE/'retrieved';output.mkdir(exist_ok=True)
    with tarfile.open(target) as tar:
        for m in transport.safe_members(tar):
            need(m.isfile(),'RESULT_FILES_ONLY');dest=output/m.name;dest.parent.mkdir(parents=True,exist_ok=True)
            data=tar.extractfile(m).read()
            if dest.exists():need(dest.read_bytes()==data,'NO_OVERWRITE_DIFFERENT_RESULT')
            else:dest.write_bytes(data)
    manifest=read(output/'RESULT_MANIFEST.json')
    for name,pin in manifest['files'].items():
        p=output/name;need(p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'RESULT_MEMBER_SHA:'+name)
    job=state['job']['job_id'];phase=state['job']['phase'];job_output=output/'outputs'/(phase+'_'+job)
    sys.path.insert(0,str(ROOT/'runs/edge_formal_execution_v4_20261104'))
    from runtime_control import current_status
    current=None;validation_error=None
    try:
        current=current_status(job_output,card_sha256=read(HERE/'AUTHORIZATION.json')['card_sha256'])
        need(current['status']=='PASS','CURRENT_ATTEMPT_NOT_PASS')
        if phase=='preflight':raise ValueError('PREFLIGHT_FAILED_FULL_GATE_NOT_SUBMITTED')
        from preflight_acceptance import inspect
        pre=read(output/'PREFLIGHT_ACCEPTANCE.json')
        for name,digest in pre['files'].items():need(sha(output/name)==digest,'RETRIEVED_PREFLIGHT_PIN')
        local_pre_job=dict(pre['job'],output_directory=str(output/'outputs'/('preflight_'+pre['job']['job_id'])))
        inspect(output,HERE/'ENGINEERING_CARD.json',local_pre_job,pre['scheduler'])
        candidate=read(job_output/'engineering_attempts'/current['attempt_id']/'CANDIDATE.json')
        need(candidate['shape_count']==73 and candidate['logical_spool_rows']==64124 and
             candidate['recovery']['committed_files_byte_identical'] is True and
             candidate['runtime_identity']==read(HERE/'ENGINEERING_CARD.json')['runtime_identity'] and
             current['resources']['max_tree_rss_bytes']<=8*1024**3 and current['cleanup_complete'] is True,
             'ENGINEERING_ACCEPTANCE_FIELDS')
        rows=[line.split('|') for line in manifest['scheduler']['stdout'].splitlines()]
        primary=[row for row in rows if len(row)>=8 and row[0]==job]
        need(len(primary)==1 and primary[0][1]=='COMPLETED' and primary[0][2]=='0:0' and primary[0][5]=='1',
             'SCHEDULER_SUCCESS_ONE_CPU_REQUIRED')
    except Exception as exc:validation_error=type(exc).__name__+':'+str(exc)
    result=dict(status='PASS' if validation_error is None else 'STOP',job_id=job,
        phase=phase,card_sha256=read(HERE/'AUTHORIZATION.json')['card_sha256'],attempt=current,
        result_archive=dict(bytes=size,sha256=digest),result_members=len(manifest['files']),
        scheduler=manifest['scheduler'],acceptance_error=validation_error,
        formal_external_evaluation=False,automatic_resubmit=False)
    child=job_output/'engineering_attempts'/(current or {}).get('attempt_id','absent')/'CHILD_STOP_main.json'
    if child.exists():result['root_cause']=read(child).get('reason')
    write(HERE/'FINAL_ACCEPTANCE.json',result)
    progress(result['status'],job_id=job,error=result.get('root_cause') or validation_error or '',worker={},engineering_current=current,
        scheduler_state=state['status'],attempt_receipt=current,phase=phase,
        message='工程验证已验收通过；正式外部评价未启动。' if result['status']=='PASS' else '工程验证未通过，已保留失败回执，不自动重投。')
    return result


def main():
    try:
        if (HERE/'FINAL_ACCEPTANCE.json').exists():
            final=read(HERE/'FINAL_ACCEPTANCE.json');progress(final['status'],job_id=final['job_id']);return
        delivery=read(HERE/'DELIVERY.json');p=Path(delivery['archive_local_path']);pin=delivery['files']['archive']
        progress('LOCAL_CHECK');need(p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'LOCAL_DELIVERY_PIN')
        state=request('state',timeout=15);current=state['files']['archive']
        need(current['sha256']==pin['sha256'] and current['bytes']==pin['bytes'],'UPLOAD_BINDING')
        with p.open('rb') as source:
            failures=0
            while not current['complete']:
                offset=current['offset'];source.seek(offset);data=source.read(min(4*1024**2,pin['bytes']-offset))
                try:
                    current=request('upload/archive',data,{'X-Offset':str(offset),'X-Chunk-SHA256':hashlib.sha256(data).hexdigest()},timeout=90)
                    failures=0
                except OSError:
                    failures+=1;need(failures<=3,'TRANSFER_RETRY_LIMIT');current=request('state')['files']['archive']
                progress('UPLOADING',done_bytes=current['offset'],total_bytes=pin['bytes'])
        progress('PREPARING');prepare_once()
        progress('SUBMITTING');job=submit_once();progress('SUBMITTED',job_id=job['job_id'],phase=job['phase'])
        end=time.monotonic()+4*3600
        while time.monotonic()<end:
            try:
                state=request('state',timeout=30)
                if state['result_ready']:
                    if state['job']['phase']=='preflight' and state['status']=='COMPLETED' and (state.get('current') or {}).get('status')=='PASS':
                        progress('PREFLIGHT_VALIDATING',job_id=job['job_id'],worker={},message='真实小切片及帧级中断恢复已结束，正在核验快照一致性、资源和调度终态。')
                        try:
                            job=submit_once(phase='gate')
                        except Exception:
                            retrieve(state)
                            raise
                        progress('SUBMITTED',job_id=job['job_id'],phase='gate',preflight_job_id=state['job']['job_id'],preflight_status='PASS',
                            message='真实小切片验收通过，已提交独立的1CPU、8GiB、2小时完整工程验证。')
                        continue
                    retrieve(state);return
                current=state.get('current') or {}
                stage='RUNNING' if state['status']=='RUNNING' else 'SUBMITTED'
                worker=state.get('progress') or {}
                receipt=state.get('attempt_receipt') or {}
                job=state['job']
                progress(stage,job_id=job['job_id'],phase=job['phase'],scheduler_state=state['status'],worker=worker,replay_checkpoint=state.get('replay_checkpoint'),
                    preflight_job_id=(state.get('preflight_job') or {}).get('job_id'),
                    preflight_status='PASS' if state.get('preflight_acceptance') else 'PENDING',
                    attempt_id=current.get('attempt_id'),error='',
                    message=('本轮工程检查已停止，等待调度终态并取回诊断。' if current.get('status')=='STOP' else
                             ('正在执行真实78端点小切片，预检未通过不会启动完整工程验证。' if job['phase']=='preflight' else '正在执行v4工程续跑：先核验复用NORMAL/HTTP，UDP重建并定期保存持久上下文；最终回执通过才判定成功。')),
                    engineering_current=current,attempt_receipt=receipt)
            except (OSError,ConnectionError) as exc:
                progress('CONNECTION_INTERRUPTED',job_id=job['job_id'],error=type(exc).__name__,
                         message='作业状态未知；程序只尝试读取现有通道，不登录、不重投。')
            time.sleep(15)
        progress('OBSERVATION_ENDED',job_id=job['job_id'],message='4小时自动观察窗口结束，作业未重投；后续可继续只读取回。')
    except Exception as exc:
        write(HERE/'PIPELINE_FAILURE.json',dict(error=type(exc).__name__+':'+str(exc),automatic_resubmit=False))
        progress('STOP',error=type(exc).__name__+':'+str(exc),message='交付或验收出现故障，未自动重投。')
        raise


if __name__=='__main__':main()
