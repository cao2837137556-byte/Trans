"""Collect an isolated, labeled normal-login trace in the existing Ubuntu WSL."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
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
from urllib.parse import parse_qs, urlencode

HERE = Path(__file__).resolve().parent
SERVER = "10.254.240.10"
SERVER_MAC = "02:04:24:00:00:10"
CLIENTS = ("10.254.240.21", "10.254.240.22", "10.254.240.23")
CLIENT_MACS = ("02:04:24:00:00:21", "02:04:24:00:00:22", "02:04:24:00:00:23")
PORT = 8080
DEVICE = "lab0"
CAPTURE_FILES = ("login.pcap", "server.jsonl", "client_1.jsonl", "client_2.jsonl", "client_3.jsonl")
BYTE_LIMIT = 100 * 2**20
DISK_RESERVE = 2 * 2**30
NS = 10**9
SCENARIOS = ("successful_login", "mistake_then_retry", "disconnect_then_reconnect")


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    tmp.replace(path)


def jsonl(record):
    return (json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


class Budget:
    """Serialize capture-file growth and check the actual D: free space."""

    def __init__(self, out, control):
        self.out = out
        self.control = control
        self.gate = control / "stop"

    def reason(self):
        return self.gate.read_text() if self.gate.is_file() else None

    def free(self):
        fs = os.statvfs(self.out)
        return fs.f_bavail * fs.f_frsize

    def sizes(self):
        return {n: (self.out/n).stat().st_size for n in CAPTURE_FILES}

    def check(self, size=0):
        if self.reason():
            return False
        if sum(self.sizes().values()) + size > BYTE_LIMIT:
            stop = "CAPTURE_SIZE_LIMIT"
        elif self.free() - size <= DISK_RESERVE:
            stop = "D_DRIVE_FREE_SPACE"
        else:
            return True
        self.gate.write_text(stop)
        return False

    def append(self, name, record):
        with (self.control/"budget.lock").open("ab") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not self.check(len(record)):
                return False
            with (self.out/name).open("ab", buffering=0) as f:
                if f.write(record) != len(record):
                    raise OSError("incomplete capture write")
            return True


def ip(*args):
    p = subprocess.run(["ip", *args], capture_output=True, text=True, check=False)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "ip exited without completing the operation")
    return p.stdout


def isolate(stack, prefix):
    bridge, server, *clients = names = [f"{prefix}-{v}" for v in ("sw","srv","c1","c2","c3")]
    ethers = []
    for name in names:
        ip("netns", "add", name)
        stack.callback(ip, "netns", "delete", name)
        ip("-n", name, "link", "set", "lo", "up")
    ip("-n", bridge, "link", "add", "testbr", "type", "bridge", "stp_state", "0")
    ip("-n", bridge, "link", "set", "testbr", "up")
    for idx, (name, addr, mac) in enumerate(zip([server, *clients], [SERVER,*CLIENTS], [SERVER_MAC,*CLIENT_MACS])):
        peer = f"sw{idx}"
        ip("-n", bridge, "link", "add", peer, "type", "veth", "peer", "name", DEVICE, "netns", name)
        ip("-n", bridge, "link", "set", peer, "master", "testbr")
        ip("-n", bridge, "link", "set", peer, "up")
        ip("-n", name, "link", "set", DEVICE, "address", mac)
        ip("-n", name, "address", "add", addr+"/24", "dev", DEVICE)
        ip("-n", name, "link", "set", DEVICE, "up")
        links = json.loads(ip("-n", name, "-j", "address", "show"))
        routes = json.loads(ip("-n", name, "-j", "route", "show"))
        assert {l["ifname"] for l in links} == {"lo",DEVICE}
        assert all(r["dev"] == DEVICE and r["dst"] == "10.254.240.0/24" for r in routes)
        found, = [l for l in links if l["ifname"] == DEVICE]
        assert found["address"] == mac and any(x["local"] == addr for x in found["addr_info"])
        ethers.append(dict(netns=name, mac=mac, ip=addr))
    assert not json.loads(ip("-n", bridge, "-j", "route", "show"))
    return server, clients, ethers


def open_capture(namespace):
    with open("/proc/self/ns/net", "rb") as home, open(f"/run/netns/{namespace}", "rb") as child:
        os.setns(child.fileno(), os.CLONE_NEWNET)
        try:
            raw = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
            raw.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*2**20)
            raw.setsockopt(socket.SOL_SOCKET, 35, 1)  # Linux SO_TIMESTAMPNS
            raw.bind((DEVICE, 0))
            return raw
        finally:
            os.setns(home.fileno(), os.CLONE_NEWNET)


class LoginHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.serial = 0
        self.socket_open_ns = time.time_ns()

    def log_message(self, *args):
        pass

    def finish_response(self, status, body, media):
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/login":
            self.send_error(404)
            return
        self.finish_response(200, b'<form method="post"><label>User <input name="username"></label>'
                             b'<label>Password <input name="password" type="password"></label>'
                             b'<button>Log in</button></form>', "text/html")

    def do_POST(self):
        if self.path != "/login" or self.headers.get_content_type() != "application/x-www-form-urlencoded":
            self.send_error(400)
            return
        n = int(self.headers["Content-Length"])
        if not 0 < n <= 1024:
            self.send_error(400)
            return
        f = parse_qs(self.rfile.read(n).decode("ascii"), strict_parsing=True, max_num_fields=4)
        accepted = (f.get("username") == ["pilot-user"]
                    and hmac.compare_digest(f.get("password", [""])[0], self.server.password))
        self.serial += 1
        status = 200 if accepted else 401
        event = dict(event="auth", peer=list(self.client_address), local=list(self.connection.getsockname()),
                     request_index=self.serial, socket_open_ns=self.socket_open_ns,
                     authenticated=accepted, status=status, decision_ns=time.time_ns())
        if self.server.budget.append("server.jsonl", jsonl(event)):
            self.finish_response(status, b"Login accepted" if accepted else b"Login refused", "text/plain")


def serve(out, ctl):
    with LoginServer((SERVER, PORT), LoginHandler) as server:
        server.password = (ctl/"credential").read_text()
        server.budget = Budget(out, ctl)
        (ctl/"ready").touch()
        server.serve_forever()


class LoginServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], ConnectionResetError):
            super().handle_error(request, client_address)


def perform(budget, label, round_number, idx, correct, unexpected):
    log = f"client_{idx+1}.jsonl"
    case = dict(scenario=label, scenario_id=f"{idx+1}-{round_number+1}", client=idx+1)
    opening = None
    conn = None
    peer = None

    def login(expect_success, request_index):
        nonlocal conn, opening, peer
        start = time.time_ns()
        status = error = None
        try:
            if request_index == 1:
                opening = start
                conn = http.client.HTTPConnection(SERVER, PORT, timeout=3, source_address=(CLIENTS[idx],0))
                conn.connect()
                conn.auto_open = False
                peer = conn.sock.getsockname()
            data = urlencode(dict(username="pilot-user", password=correct if expect_success else unexpected)).encode("ascii")
            conn.request("POST", "/login", data, {"Content-Type": "application/x-www-form-urlencoded",
                         "User-Agent": "Paper04 Login Pilot", "Accept": "text/html"})
            answer = conn.getresponse()
            answer.read()
            status = answer.status
        except (OSError, http.client.HTTPException) as exc:
            error = type(exc).__name__
        event = dict(**case, event="request", peer=peer, local=[SERVER,PORT], request_index=request_index,
                     connect_start_ns=opening, start_ns=start, done_ns=time.time_ns(),
                     expected_status=200 if expect_success else 401, observed_status=status, error=error)
        return budget.append(log, jsonl(event)) and status == event["expected_status"]

    try:
        if label == "successful_login":
            login(True, 1)
        elif label == "mistake_then_retry":
            if login(False, 1):
                time.sleep(.18)
                login(True, 2)
        elif login(True, 1):
            reset = time.time_ns()
            conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            conn.close()
            event = dict(**case, event="disconnect", peer=peer, local=[SERVER,PORT], time_ns=reset)
            if budget.append(log, jsonl(event)):
                time.sleep(.27)
                login(True, 1)
    finally:
        if conn is not None:
            conn.close()


def client(out, ctl, idx, start, duration, smoke):
    budget = Budget(out, ctl)
    password = (ctl/"credential").read_text()
    wrong = secrets.token_urlsafe(16)
    interval = 20 * NS
    offset = (250_000_000 + idx*450_000_000) if smoke else (250_000_000 + idx*4*NS)
    for i, target in enumerate(range(start+offset, start+(duration-1)*NS, interval)):
        time.sleep(max(0., (target-time.monotonic_ns())/NS))
        if budget.reason() or time.monotonic_ns() >= start+(duration-1)*NS:
            break
        perform(budget, SCENARIOS[(i+idx)%len(SCENARIOS)], i, idx, password, wrong)


def process(stack, namespace, *args):
    p = subprocess.Popen(["ip", "netns", "exec", namespace, sys.executable, "-B", str(HERE/"collect.py"), *map(str,args)])
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


def capture(raw, budget, start, seconds):
    delay = max(0., (start-time.monotonic_ns())/NS)
    time.sleep(delay)
    started = time.time_ns()
    deadline = start + seconds*NS
    packet_count = [0,0]  # received, sent as seen on the server interface
    first = last = None
    min_free = budget.free()
    assert budget.append("login.pcap", struct.pack("<IHHIIII", 0xa1b23c4d,2,4,0,0,65535,1))
    while time.monotonic_ns() < deadline:
        min_free = min(min_free, budget.free())
        with (budget.control/"budget.lock").open("ab") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not budget.check():
                break
        if not select.select([raw], [], [], .10)[0]:
            continue
        data, controls, flags, addr = raw.recvmsg(65535, socket.CMSG_SPACE(16))
        assert not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC)
        t, = [struct.unpack("@ll", v) for l,kind,v in controls if l == socket.SOL_SOCKET and kind == 35]
        ts = t[0]*NS + t[1]
        if ts < started:
            continue
        record = struct.pack("<IIII", *t, len(data), len(data)) + data
        if not budget.append("login.pcap", record):
            break
        packet_count[int(addr[2] == socket.PACKET_OUTGOING)] += 1
        first = ts if first is None else min(ts, first)
        last = ts if last is None else max(ts, last)
    ended = time.time_ns()
    elapsed = (time.monotonic_ns()-start)/NS
    _, dropped = struct.unpack("II", raw.getsockopt(263, 6, 8))  # SOL_PACKET, PACKET_STATISTICS
    return dict(start_ns=started, end_ns=ended, duration_seconds=elapsed, requested_seconds=seconds,
                pcap_first_ns=first, pcap_last_ns=last, captured_ingress=packet_count[0],
                captured_egress=packet_count[1], capture_kernel_drops=dropped, min_free_bytes=min_free,
                stop_reason=budget.reason() or "DURATION_REACHED")


def run(out, seconds, smoke):
    assert list(out.iterdir()) == []
    assert smoke or shutil.disk_usage(out).free > DISK_RESERVE
    for name in CAPTURE_FILES:
        (out/name).touch(exist_ok=False)
    free = shutil.disk_usage(out).free
    prefix = "p4lp-" + secrets.token_hex(4)
    with tempfile.TemporaryDirectory(prefix=prefix+"-") as temp, ExitStack() as stack:
        ctl = Path(temp)
        (ctl/"credential").write_text(secrets.token_urlsafe(20))
        budget = Budget(out, ctl)
        server, clients, endpoints = isolate(stack, prefix)
        daemon = process(stack, server, "serve", out, ctl)
        for _ in range(100):
            if (ctl/"ready").is_file():
                break
            assert daemon.poll() is None
            time.sleep(.025)
        assert (ctl/"ready").is_file()
        raw = stack.enter_context(open_capture(server))
        begin = time.monotonic_ns() + int(1.5*NS)
        workers = [process(stack, n, "client", out, ctl, i, begin, seconds, int(smoke)) for i,n in enumerate(clients)]
        manifest = dict(stage="CAPTURING", ubuntu_wsl_kernel=os.uname().release, started_utc=datetime.now(timezone.utc).isoformat(),
                        requires_netns_veth=True, server_interface=DEVICE, server_port=PORT, endpoints=endpoints,
                        isolated_no_default_routes=True, duration_seconds=seconds, smoke=smoke, limit_bytes=BYTE_LIMIT,
                        reserve_bytes=DISK_RESERVE, free_at_start_bytes=free)
        save_json(out/"CAPTURE_PROGRESS.json", manifest)
        print(f"CAPTURING {out}", flush=True)
        status = capture(raw, budget, begin, seconds)
        if status["stop_reason"] == "DURATION_REACHED":
            for worker in workers:
                assert worker.wait(timeout=5) == 0
        else:
            for worker in workers:
                if worker.poll() is None:
                    worker.terminate()
        manifest.update(stage="CAPTURED", capture=status)
        save_json(out/"CAPTURE_PROGRESS.json", manifest)
    manifest.update(stage="SEALED_CAPTURE", capture_files=budget.sizes(),
                    remaining_bytes=shutil.disk_usage(out).free, namespaces_removed=True)
    save_json(out/"CAPTURE.json", manifest)
    save_json(out/"CAPTURE_PROGRESS.json", manifest)
    print(f"CAPTURED {sum(manifest['capture_files'].values())} bytes", flush=True)


def main():
    cmd = sys.argv[1]
    if cmd == "serve":
        serve(*map(Path, sys.argv[2:]))
    elif cmd == "client":
        out, ctl = map(Path, sys.argv[2:4])
        client(out, ctl, *map(int, sys.argv[4:]))
    else:
        a = argparse.ArgumentParser()
        a.add_argument("mode", choices=["collect"])
        a.add_argument("out", type=Path)
        a.add_argument("--smoke", action="store_true")
        args = a.parse_args()
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        args.out.mkdir(parents=True, exist_ok=False)
        run(args.out, 5 if args.smoke else 600, args.smoke)


if __name__ == "__main__":
    main()
