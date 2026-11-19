"""Locate whitelisted existing bytes, accepting resumable authenticated chunks only for missing assets."""

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import shutil
from pathlib import Path
import threading
import time
import zlib

from common_ton import dump, require, sha

PORT = 18899


def locate(project, out, specs):
    found = {}
    candidates = {k: [] for k in specs}
    own = out / "assets"
    own.mkdir(exist_ok=True)
    for key, s in specs.items():
        candidates[key].extend([own / key, *[project / p for p in s["paths"]]])
    roots = [
        project / p
        for p in (
            "datasets",
            "data_external",
            "assets/raw",
            "inputs",
            "worktrees/kitnet-exp-mainline/datasets",
        )
    ]
    deadline = time.monotonic() + 70
    by_name = {}
    for key, s in specs.items():
        by_name.setdefault(s["file"], []).append(key)
    for root in roots:
        if not root.is_dir():
            continue
        for current, dirs, names in os.walk(root, followlinks=False):
            if time.monotonic() > deadline:
                break
            dirs[:] = [n for n in dirs if n not in (".git", "node_modules", "__pycache__")]
            for name in set(names) & by_name.keys():
                p = Path(current) / name
                for key in by_name[name]:
                    if p.stat().st_size == specs[key]["bytes"]:
                        candidates[key].append(p)
    for key, options in candidates.items():
        s = specs[key]
        for path in dict.fromkeys(options):
            if path.is_file() and path.stat().st_size == s["bytes"] and sha(path) == s["sha256"]:
                found[key] = dict(
                    path=str(path.resolve()), sha256=s["sha256"], bytes=s["bytes"], source="HPC_REUSE"
                )
                break
    return found


def ensure(project, out, specs, stage_state):
    found = locate(project, out, specs)
    initial = sorted(found)
    missing = set(specs) - set(found)
    free = shutil.disk_usage(out).free
    missing_bytes = sum(specs[k]["bytes"] for k in missing)
    dump(
        out / "ASSET_INVENTORY.json",
        dict(
            initially_verified=initial,
            initially_missing=sorted(missing),
            existing_input_bytes_to_transfer=missing_bytes,
            filesystem_free_bytes=free,
        ),
    )
    require(free > missing_bytes, "INSUFFICIENT_SPACE_FOR_REGISTERED_INPUTS")
    if missing:
        keyfile = out.parent / ".p04_tonpw18/token"
        token = keyfile.read_text().strip()
        lock = threading.Lock()

        def status():
            return dict(
                run=out.name,
                needed={
                    k: dict(
                        bytes=specs[k]["bytes"],
                        sha256=specs[k]["sha256"],
                        offset=(out / "assets" / (k + ".part")).stat().st_size
                        if (out / "assets" / (k + ".part")).exists()
                        else 0,
                    )
                    for k in sorted(missing)
                },
                verified=sorted(found),
            )

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def route(self):
                t, sep, action = self.path.lstrip("/").partition("/")
                require(sep and hmac.compare_digest(t, token), "AUTH")
                return action

            def send_json(self, value):
                b = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                try:
                    require(self.route() == "state", "ROUTE")
                    with lock:
                        self.send_json(status())
                except Exception as e:
                    self.send_error(409, str(e)[:120])

            def do_POST(self):
                try:
                    action = self.route()
                    require(action.startswith("put-"), "ROUTE")
                    k = action[4:]
                    length = int(self.headers["Content-Length"])
                    require(k in specs and 0 < length <= 8 * 1024**2, "FILE_SCOPE")
                    data = self.rfile.read(length)
                    require(len(data) == length, "CHUNK_LENGTH")
                    if self.headers.get("Content-Encoding") == "deflate":
                        decoder = zlib.decompressobj()
                        data = decoder.decompress(data, 8 * 1024**2 + 1)
                        require(
                            decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
                            "COMPRESSED_CHUNK",
                        )
                    length = len(data)
                    require(
                        0 < length <= 8 * 1024**2
                        and length == int(self.headers["X-Raw-Bytes"])
                        and hashlib.sha256(data).hexdigest() == self.headers["X-SHA256"],
                        "CHUNK_SHA",
                    )
                    with lock:
                        if k in found:
                            return self.send_json(dict(offset=specs[k]["bytes"], verified=True))
                        require(k in missing, "UNREGISTERED_INPUT")
                        tmp = out / "assets" / (k + ".part")
                        offset = tmp.stat().st_size if tmp.exists() else 0
                        require(
                            int(self.headers["X-Offset"]) == offset and offset + length <= specs[k]["bytes"],
                            "OFFSET",
                        )
                        with tmp.open("ab") as f:
                            f.write(data)
                        offset += length
                        if offset == specs[k]["bytes"]:
                            if sha(tmp) != specs[k]["sha256"]:
                                tmp.rename(tmp.with_name(tmp.name + ".sha-mismatch-" + str(time.time_ns())))
                                raise ValueError("COMPLETE_INPUT_SHA")
                            path = out / "assets" / k
                            os.replace(tmp, path)
                            found[k] = dict(
                                path=str(path),
                                sha256=specs[k]["sha256"],
                                bytes=offset,
                                source="EXISTING_LOCAL_FILE",
                            )
                            missing.remove(k)
                        self.send_json(dict(offset=offset, verified=k in found))
                except Exception as e:
                    self.send_error(409, str(e)[:160])

        with ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as server:
            bg = threading.Thread(target=server.serve_forever, daemon=True)
            bg.start()
            try:
                while True:
                    with lock:
                        s = status()
                    stage_state("AWAITING_EXISTING_ASSETS", inputs=s)
                    if not s["needed"]:
                        break
                    time.sleep(3)
            finally:
                server.shutdown()
                bg.join()
    dump(out / "VERIFIED_INPUTS.json", dict(status="PASS", inputs=found))
    return found
