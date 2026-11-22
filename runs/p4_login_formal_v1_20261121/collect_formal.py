"""Keep one isolated service alive across real enrollment, bank sealing and evaluation."""
from contextlib import ExitStack
from pathlib import Path
import fcntl
import http.client
import json
import os
import secrets
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import traceback
from urllib.parse import urlencode

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"p4_login_pilot_v1_20261121"))
from collect import (Budget, CAPTURE_FILES, CLIENTS, DISK_RESERVE, LoginHandler, LoginServer,
                     NS, PORT, SERVER, SERVER_MAC, isolate, jsonl, open_capture, save_json)
from schedule import ORDINARY, BURST, RECOVER, plan_enrollment, plan_evaluation

IP=socket.inet_aton(SERVER)
MAC=bytes.fromhex(SERVER_MAC.replace(":",""))


class FreeBudget(Budget):
    def check(self,size=0):
        if self.reason():
            return False
        if self.free()-size<=DISK_RESERVE:
            self.gate.write_text("D_DRIVE_FREE_SPACE")
            return False
        return True


class StageBudget:
    """The unchanged server writes to the active capture's log."""
    def __init__(self,out,control):
        self.out,self.control=out,control

    def append(self,name,record):
        stage=(self.control/"phase").read_text()
        assert stage in ("enrollment","evaluation")
        return FreeBudget(self.out/stage,self.control).append(name,record)


def serve(out,ctl):
    with LoginServer((SERVER,PORT),LoginHandler) as server:
        server.password=(ctl/"credential").read_text()
        server.budget=StageBudget(out,ctl)
        (ctl/"ready").write_text(str(os.getpid()))
        server.serve_forever()


def wait_at(when,stop):
    while not stop():
        remaining=(when-time.monotonic_ns())/NS
        if remaining<=0:
            return True
        time.sleep(min(remaining,.25))
    return False


class Session:
    def __init__(self,writer,client,control,action):
        self.log=writer
        self.ip=CLIENTS[client]
        self.meta=dict(scenario=action["scenario"],scenario_id=action["scenario_id"],client=client+1,
                       normal=True,boundary_probe=action.get("boundary_probe",False),
                       scheduled_rate=action.get("scheduled_rate"))
        self.correct=(control/"credential").read_text()
        self.wrong="test-"+self.correct
        self.peer=None
        self.conn=None
        self.opened=None

    def attempt(self,index,correct):
        started=time.time_ns()
        status=issue=None
        try:
            if index==1:
                assert self.conn is None
                self.opened,self.peer=started,None
                self.conn=http.client.HTTPConnection(SERVER,PORT,timeout=3,source_address=(self.ip,0))
                self.conn.connect()
                self.conn.auto_open=False
                self.peer=self.conn.sock.getsockname()
            encoded=urlencode(dict(username="pilot-user",password=self.correct if correct else self.wrong)).encode("ascii")
            self.conn.request("POST","/login",encoded,{"Content-Type":"application/x-www-form-urlencoded",
                              "User-Agent":"Paper04 Login Pilot","Accept":"text/html"})
            response=self.conn.getresponse()
            response.read()
            status=response.status
        except (OSError,http.client.HTTPException) as exc:
            issue=type(exc).__name__
        expected=200 if correct else 401
        self.log(dict(**self.meta,event="request",peer=self.peer,local=[SERVER,PORT],request_index=index,
                      connect_start_ns=self.opened,start_ns=started,done_ns=time.time_ns(),
                      observed_status=status,expected_status=expected,error=issue))
        return status==expected

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn=None

    def reset(self):
        started=time.time_ns()
        self.conn.sock.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack("ii",1,0))
        self.close()
        self.log(dict(**self.meta,event="disconnect",peer=self.peer,local=[SERVER,PORT],time_ns=started))


def apply_action(action,write,client,ctl,anchor,stop):
    label=action["scenario"]
    sess=Session(write,client,ctl,action)
    try:
        if label==BURST:
            t=anchor+round(float(action["offset_s"])*NS)
            sess.meta.update(scenario=ORDINARY[0],scenario_id=action["scenario_id"]+"-setup",setup_minute=action["scenario_id"])
            if not sess.attempt(1,True) or not wait_at(t,stop):
                return
            minute=time.time_ns()
            sess.meta.update(scenario=BURST,scenario_id=action["scenario_id"],setup_minute=None)
            write(dict(**sess.meta,event="minute_start",time_ns=minute))
            for step,offset in enumerate(action["within_minute_s"],1):
                if not wait_at(t+round(offset*NS),stop):
                    return
                sess.meta["reconnect_step"]=step
                sess.reset()
                if not sess.attempt(1,True):
                    return
            return
        if label==ORDINARY[0]:
            sess.attempt(1,True)
        elif label==ORDINARY[1]:
            if sess.attempt(1,False):
                time.sleep(.18)
                sess.attempt(2,True)
        elif label==ORDINARY[2]:
            if sess.attempt(1,False):
                sess.close()
                time.sleep(.29)
                sess.attempt(1,True)
        else:
            assert label==RECOVER
            if sess.attempt(1,True):
                sess.reset()
                time.sleep(.28)
                sess.attempt(1,True)
    finally:
        sess.close()


def client(folder,ctl,idx,anchor):
    budget=FreeBudget(folder,ctl)
    plan=json.loads((folder/"SCHEDULE.json").read_bytes())
    done=lambda: budget.reason() or (ctl/(folder.name+"_closed")).is_file()
    def writer(event):
        budget.append(f"client_{idx+1}.jsonl",jsonl(event))
    for action in plan["actions"]:
        if action["client"]!=idx:
            continue
        ready=action["offset_s"]-(3 if action["scenario"]==BURST else 0)
        if not wait_at(anchor+round(ready*NS),done):
            break
        if action.get("boundary_probe") and (ctl/"crossed").is_file():
            break
        apply_action(action,writer,idx,ctl,anchor,done)


def spawn(stack,namespace,*args):
    p=subprocess.Popen(["ip","netns","exec",namespace,sys.executable,"-B",str(HERE/"collect_formal.py"),*map(str,args)])
    def stop():
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=2)
    stack.callback(stop)
    return p


def eligible(frame):
    if len(frame)<54 or frame[:6]!=MAC or frame[12:14]!=b"\x08\x00" or frame[23]!=6 or frame[30:34]!=IP:
        return False
    pos=14+4*(frame[14]&15)
    return len(frame)>=pos+20 and int.from_bytes(frame[pos+2:pos+4],"big")==PORT


def publish_progress(out,**values):
    try:
        save_json(out/"COLLECTION_PROGRESS.json",dict(keeper_heartbeat_ns=time.time_ns(),**values))
    except PermissionError:
        # Windows readers may briefly prevent rename on /mnt/d. Telemetry is
        # optional, so a sharing violation must never unwind the network.
        return False
    return True


def process_start(pid):
    data=Path(f"/proc/{pid}/stat").read_text().rsplit(") ",1)[1].split()
    if data[0] in ("Z","X"):
        return None
    return int(data[19])


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def keeper_is_live(out):
    try:
        ids=json.loads((out/"COLLECTOR_IDENTITY.json").read_bytes())
        capture=json.loads((out/"enrollment/CAPTURE.json").read_bytes())
        server=capture["endpoints"][0]
        pid=ids["service_pid"]
        cname=f"p4lf-{capture['service_instance'][:8]}-srv"
        return (ids["boot"]==boot_id() and ids["instance"]==capture["service_instance"] and
                pid==capture["service_pid"] and cname==server["netns"] and
                os.path.samefile(f"/proc/{pid}/ns/net",Path("/run/netns")/cname) and
                ids["collector_start"]==process_start(ids["collector_pid"]) and
                ids["service_start"]==process_start(pid))
    except (OSError,ValueError,KeyError,IndexError):
        return False


def record_trace(root,folder,ctl,raw,begin,plan,budget):
    time.sleep(max(0,(begin-time.monotonic_ns())/NS))
    epoch=time.time_ns()
    first=previous=crossing=None
    count=0
    packet_directions=[0,0]
    last_ns=0
    min_free=budget.free()
    before=time.monotonic()
    enroll=folder.name=="enrollment"
    deadline=time.monotonic()+ (plan["window_seconds"]+192 if enroll else plan["duration_seconds"]+2)
    assert budget.append("login.pcap",struct.pack("<IHHIIII",0xa1b23c4d,2,4,0,0,65535,1))
    next_status=0.
    while time.monotonic()<deadline:
        now=time.monotonic()
        if now>=next_status:
            min_free=min(min_free,budget.free())
            if min_free<=DISK_RESERVE:
                budget.check()
            publish_progress(root,stage="RECORDING_"+folder.name.upper(),packets=count,
                             elapsed_seconds=(max(0,(last_ns-first[1])/NS) if first else 0),
                             duration_seconds=plan.get("window_seconds",plan.get("duration_seconds")),free_bytes=min_free)
            next_status=now+2.
        if budget.reason():
            break
        if not select.select([raw],[],[],.12)[0]:
            continue
        data, ancillary, flags, addr=raw.recvmsg(65535,socket.CMSG_SPACE(16))
        assert not flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC)
        t,=[struct.unpack("@ll",a) for level,kind,a in ancillary if level==socket.SOL_SOCKET and kind==35]
        ns=t[0]*NS+t[1]
        if ns<epoch:
            continue
        if not budget.append("login.pcap",struct.pack("<IIII",*t,len(data),len(data))+data):
            break
        count+=1
        packet_directions[int(addr[2]==socket.PACKET_OUTGOING)]+=1
        last_ns=max(last_ns,ns)
        if eligible(data):
            if first is None:
                first=(count,ns)
            if enroll and crossing is None and ns>first[1]+plan["window_seconds"]*NS:
                crossing=(count,ns)
                (ctl/"crossed").touch()
                deadline=time.monotonic()+2.2
        if crossing is None:
            previous=(count,ns)
    _, drops=struct.unpack("II",raw.getsockopt(263,6,8))
    (ctl/(folder.name+"_closed")).touch()
    cap=dict(start_ns=epoch,end_ns=time.time_ns(),last_frame_ns=last_ns,
             duration_seconds=time.monotonic()-before,captured_ingress=packet_directions[0],
             captured_egress=packet_directions[1],capture_kernel_drops=drops,
             min_free_bytes=min_free,stop_reason=budget.reason() or "PLANNED")
    if first:
        cap.update(first_qualifying_frame=first[0],first_qualifying_ns=first[1])
    if crossing:
        cap.update(reference_end_ns=first[1]+plan["window_seconds"]*NS,
                   last_frame_before_crossing=previous[0],crossing_frame=crossing[0],crossing_ns=crossing[1])
    return cap


def phase(root,stage,ctl,server,clients,plan,meta):
    out=root/stage
    out.mkdir(exist_ok=False)
    for name in CAPTURE_FILES:
        (out/name).touch(exist_ok=False)
    save_json(out/"SCHEDULE.json",plan)
    (ctl/"phase").write_text(stage)
    budget=FreeBudget(out,ctl)
    assert budget.check()
    with ExitStack() as stack:
        raw=stack.enter_context(open_capture(server))
        begin=time.monotonic_ns()+int(1.7*NS)
        workers=[spawn(stack,ns,"client",out,ctl,i,begin) for i,ns in enumerate(clients)]
        result=record_trace(root,out,ctl,raw,begin,plan,budget)
        for child in workers:
            assert child.wait(timeout=8)==0
    record=dict(**meta,capture=result,capture_files=budget.sizes(),remaining_bytes=budget.free(),
                stage="SEALED_CAPTURE",scope=stage,random_seed=plan["seed"])
    save_json(out/"CAPTURE.json",record)
    assert result["stop_reason"]=="PLANNED" and result["capture_kernel_drops"]==0
    assert "first_qualifying_frame" in result
    if stage=="enrollment":
        assert result["crossing_ns"]>result["reference_end_ns"]
    return record


def await_bank(out,service,meta,last_frame):
    ready=out/"BANK_READY.json"
    while True:
        if service.poll() is not None:
            raise RuntimeError("The original WSL login service exited before evaluation.")
        if shutil.disk_usage(out).free<=DISK_RESERVE:
            raise RuntimeError("D: reached the free-space reserve while sealing references.")
        if ready.is_file() and time.time_ns()>last_frame+60*NS:
            return json.loads(ready.read_bytes())
        publish_progress(out,stage="REFERENCE_SEALING",service_instance=meta["service_instance"],
                         service_pid=meta["service_pid"])
        time.sleep(1.)


def main(out):
    assert shutil.disk_usage(out).free>DISK_RESERVE
    assert json.loads((out/"QUICK_CHECK.json").read_bytes())["status"]=="PASS"
    assert json.loads((out/"ENGINEERING_SLICE.json").read_bytes())["status"]=="PASS"
    instance=secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix="p4login-"+instance+"-") as temp, ExitStack() as stack:
        ctl=Path(temp)
        (ctl/"credential").write_text(secrets.token_urlsafe(20))
        server,clients,endpoints=isolate(stack,"p4lf-"+instance[:8])
        service=spawn(stack,server,"serve",out,ctl)
        for _ in range(100):
            if (ctl/"ready").is_file():
                break
            assert service.poll() is None
            time.sleep(.025)
        assert (ctl/"ready").is_file()
        meta=dict(service_instance=instance,service_pid=int((ctl/"ready").read_text()),server_port=PORT,
                  endpoints=endpoints,kernel=os.uname().release,enrollment_uses_same_service=True)
        save_json(out/"COLLECTOR_IDENTITY.json",dict(boot=boot_id(),instance=instance,
            collector_pid=os.getpid(),collector_start=process_start(os.getpid()),
            service_pid=meta["service_pid"],service_start=process_start(meta["service_pid"])))
        first=phase(out,"enrollment",ctl,server,clients,plan_enrollment(),meta)
        seal=await_bank(out,service,meta,first["capture"]["last_frame_ns"])
        assert seal["status"]=="PASS" and seal["service_instance"]==instance
        assert seal["reference_end_ns"]==first["capture"]["reference_end_ns"]
        final=phase(out,"evaluation",ctl,server,clients,plan_evaluation(),meta)
        assert final["capture"]["first_qualifying_ns"]>first["capture"]["last_frame_ns"]+60*NS
    save_json(out/"COLLECTION_DONE.json",dict(status="PASS",service_instance=instance,namespaces_released=True))


if __name__=="__main__":
    mode=sys.argv[1]
    if mode=="serve":
        serve(*map(Path,sys.argv[2:]))
    elif mode=="client":
        client(Path(sys.argv[2]),Path(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]))
    elif mode=="probe":
        sys.exit(0 if keeper_is_live(Path(sys.argv[2])) else 1)
    else:
        dest=Path(sys.argv[2])
        signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))
        try:
            main(dest)
        except Exception as exc:
            save_json(dest/"COLLECTION_FAILURE.json",dict(error=str(exc) or repr(exc),trace=traceback.format_exc()))
            raise
