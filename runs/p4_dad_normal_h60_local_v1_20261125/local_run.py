"""Run the approved formal replay and publish a local, self-refreshing HTML file."""

import argparse
import ctypes
import hashlib
import html
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "p4_login_formal_v1_20261121"))
from progress import open_shared

STAGES = {"VERIFYING": "核验冻结资产", "READING": "读入因果帧前缀", "ENCODING": "计算冻结 netFound 编码",
          "SCORING": "比较原 CCNR 和相对握手", "PREFLIGHT_PASS": "预检通过",
          "ACCEPTED": "正式回检已验收", "STOP": "回检已停止"}


def render(out):
    with open_shared(out / "RUN_STATUS.json") as stream:
        data = json.load(stream)
    phase = {"preflight": "小切片", "formal": "正式"}.get(data.get("phase"), "")
    stage = STAGES.get(data["stage"], data["stage"])
    title = " · ".join(v for v in (phase, stage) if v)
    if data.get("error"):
        title += " · " + str(data["error"])
    if data["stage"] == "ENCODING":
        count = data["encoded"] + data["chunk_done"]
        details = f"已编码 {count:,} 个位置"
    elif data.get("queries"):
        details = f"{data['queries']:,} 条正常查询"
    else:
        details = {"mon": "周一建档与建档后", "sun": "周日纯正常"}.get(data.get("day"), "")
    links = []
    for file, name in (("PREFLIGHT.json", "真实小切片回执"), ("NORMAL_METRICS.csv", "两天配对结果"),
                       ("ACCEPTANCE.json", "正式验收回执"), ("SHA256SUMS", "SHA-256 清单")):
        if (out / file).is_file():
            links.append(f'<a href="{file}">{name}</a>')
    refresh = '' if data["stage"] in ("ACCEPTED", "STOP") else '<meta http-equiv="refresh" content="5">'
    body = f"""<!doctype html><html lang="zh"><meta charset="utf-8">{refresh}
<meta name="viewport" content="width=device-width, initial-scale=1"><title>DAD 正常回检</title>
<style>:root{{font:16px/1.7 system-ui,sans-serif;color-scheme:light dark}}
main{{max-width:38rem;margin:8vh auto;padding:1rem}}a{{margin-right:1.3rem}}</style>
<main><h1>DAD 正常回检</h1><p>{html.escape(title)}</p><p>{html.escape(details)}</p>
<p>{' '.join(links)}</p></main></html>"""
    target = out / "PROGRESS.html"
    temp = out / "PROGRESS.html.tmp"
    temp.write_text(body,encoding="utf8")
    try:
        temp.replace(target)
    except PermissionError:
        # A file preview can hold the previous HTML briefly. Scoring continues.
        pass


def formal(out):
    with (out / ".local_run.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        preflight=json.loads((out/"PREFLIGHT.json").read_bytes())
        assert preflight["status"] == "PASS"
        for file,key in (("INPUTS.json","contract"),("PREFLIGHT_METRICS.csv","table"),
                         ("PREFLIGHT_DECISIONS.npz","decisions")):
            assert hashlib.sha256((out/file).read_bytes()).hexdigest()==preflight[key]["sha256"]
        with open_shared(out/"RUN_STATUS.json") as stream:
            state=json.load(stream)
        if state["stage"]=="ACCEPTED":
            for file,key in (("SHA256SUMS","manifest"),("ACCEPTANCE.json","receipt")):
                assert hashlib.sha256((out/file).read_bytes()).hexdigest()==state[key]["sha256"]
            render(out)
            return
        environment=os.environ.copy()
        for setting in ("OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","OMP_NUM_THREADS"):
            environment[setting]="4"
        power = ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            with (out/"formal.out").open("ab") as stdout, (out/"formal.err").open("ab") as stderr:
                worker = subprocess.Popen([sys.executable,"-X","utf8","-B",str(HERE/"replay.py"),"formal",str(out)],
                                          stdout=stdout,stderr=stderr,env=environment)
                while worker.poll() is None:
                    render(out)
                    time.sleep(3)
            render(out)
            if worker.returncode:
                raise SystemExit(worker.returncode)
        finally:
            if power:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out",type=Path)
    parser.add_argument("--formal",action="store_true")
    args = parser.parse_args()
    if args.formal:
        formal(args.out.resolve())
    else:
        render(args.out.resolve())
