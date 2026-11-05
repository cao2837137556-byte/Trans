#!/usr/bin/env python3
"""CKDA D0 fixed resource pilot for the frozen E3 and I1 candidates.

The pilot reads only the frozen fit-prefix manifest.  It selects the first
100 non-empty candidate-encodable sessions in source/member/event order, or
stops at 100,000 raw packets, whichever happens first.  E3 uses the official
netFound tokenizer and model classes without modifying the encoder.  Forward
outputs are checked for shape/finite values and immediately discarded.

No labels, scores, attack families, select/report data, FINAL data, or
embedding values are read or persisted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Iterator


CONTRACT_SHA256 = "ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5"
NETFOUND_CHECKPOINT_SHA256 = "e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105"
FINAL_MARKERS = ("cooler-motor", "seed37", "seed_37", "seed-37", "seed47", "seed_47", "seed-47")
MAX_SESSIONS = 100
MAX_RAW_PACKETS = 100_000
RUNS = 3

PILOT_FIELDS = (
    "candidate_id",
    "status",
    "pilot_raw_packets",
    "pilot_candidate_tokens",
    "pilot_peak_rss_bytes",
    "pilot_peak_vram_bytes",
    "pilot_median_raw_packets_per_second",
    "pilot_median_candidate_tokens_per_second",
    "projected_nonfinal_wall_seconds",
    "custom_adapter_files",
    "custom_adapter_loc",
    "input_sha256",
    "config_sha256",
    "checkpoint_sha256",
    "forward_shape_sha256",
    "forward_finite",
    "performance_embeddings_persisted",
    "labels_read",
    "final_files_opened",
)

TSHARK_FIELDS = (
    "frame.number",
    "frame.time_epoch",
    "frame.len",
    "ip.src",
    "ip.dst",
    "ipv6.src",
    "ipv6.dst",
    "ip.proto",
    "ipv6.nxt",
    "ip.hdr_len",
    "ip.dsfield",
    "ip.len",
    "ip.flags",
    "ip.ttl",
    "ipv6.tclass",
    "ipv6.plen",
    "ipv6.hlim",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
    "tcp.window_size_value",
    "tcp.seq_raw",
    "tcp.ack_raw",
    "tcp.urgent_pointer",
    "udp.srcport",
    "udp.dstport",
    "udp.length",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def fail_if_final(value: Any, context: str) -> None:
    text = str(value).replace("\\", "/").lower()
    hit = next((marker for marker in FINAL_MARKERS if marker in text), None)
    if hit is not None:
        raise RuntimeError(
            "CKDA_D0_ENGINEERING_FAILURE_FINAL_EXCLUSION "
            f"context={context} marker={hit}"
        )


def parse_int(value: Any, default: int = 0) -> int:
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text, 0)
    except ValueError:
        return int(float(text))


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(str(value).strip())
    except ValueError:
        return default
    return result if math.isfinite(result) else default


def canonical_session(row: dict[str, str]) -> tuple[Any, ...] | None:
    src4, dst4 = row.get("ip.src", "").strip(), row.get("ip.dst", "").strip()
    src6, dst6 = row.get("ipv6.src", "").strip(), row.get("ipv6.dst", "").strip()
    src, dst = (src4, dst4) if src4 or dst4 else (src6, dst6)
    if not src or not dst:
        return None
    proto = parse_int(row.get("ip.proto") or row.get("ipv6.nxt"), 0)
    if proto == 6:
        src_port = parse_int(row.get("tcp.srcport"), 0)
        dst_port = parse_int(row.get("tcp.dstport"), 0)
    elif proto == 17:
        src_port = parse_int(row.get("udp.srcport"), 0)
        dst_port = parse_int(row.get("udp.dstport"), 0)
    else:
        src_port = dst_port = 0
    return proto, *sorted(((src, src_port), (dst, dst_port)))


def tshark_command(tshark: str, read_path: str, packet_limit: int) -> list[str]:
    if packet_limit <= 0:
        raise ValueError("packet_limit must be positive")
    command = [
        str(tshark), "-n", "-r", read_path, "-c", str(packet_limit),
        "-T", "fields", "-E", "header=y", "-E", "separator=/t",
        "-E", "quote=d", "-E", "occurrence=f",
    ]
    for field in TSHARK_FIELDS:
        command.extend(["-e", field])
    return command


def iter_tshark(
    tshark: str,
    container_path: Path,
    member: str,
    dataset_kind: str,
    packet_limit: int,
) -> Iterator[dict[str, str]]:
    archive: zipfile.ZipFile | None = None
    stderr = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    if dataset_kind == "gotham_zip":
        archive = zipfile.ZipFile(Path(container_path))
        if member not in set(archive.namelist()):
            archive.close()
            raise RuntimeError(f"planned archive member missing: {member}")
        process = subprocess.Popen(
            tshark_command(tshark, "-", packet_limit),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=False,
        )
        producer_error: list[BaseException] = []

        def feed() -> None:
            assert archive is not None and process.stdin is not None
            try:
                with archive.open(member) as raw:
                    while True:
                        block = raw.read(1024 * 1024)
                        if not block:
                            break
                        process.stdin.write(block)
            except BrokenPipeError:
                # Expected when -c stops at the frozen prefix boundary.
                pass
            except BaseException as exc:
                producer_error.append(exc)
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass

        producer = threading.Thread(target=feed, daemon=True)
        producer.start()
    elif dataset_kind == "direct_pcap":
        path = Path(container_path)
        if not path.is_file():
            raise RuntimeError(f"planned fit PCAP missing: {path}")
        process = subprocess.Popen(
            tshark_command(tshark, str(path), packet_limit),
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        producer = None
        producer_error = []
    else:
        raise RuntimeError(f"unknown dataset_kind: {dataset_kind}")

    assert process.stdout is not None
    if dataset_kind == "gotham_zip":
        import io
        stream = io.TextIOWrapper(process.stdout, encoding="utf-8", errors="replace", newline="")
    else:
        stream = process.stdout
    reader = csv.DictReader(stream, delimiter="\t", quotechar='"')
    if tuple(reader.fieldnames or ()) != TSHARK_FIELDS:
        process.kill()
        raise RuntimeError(f"TShark field header drift: {reader.fieldnames}")
    try:
        for row in reader:
            yield {field: row.get(field, "") for field in TSHARK_FIELDS}
    finally:
        stream.close()
        code = process.wait()
        if producer is not None:
            producer.join(timeout=30)
        stderr.seek(0)
        error_text = stderr.read().strip()
        stderr.close()
        if archive is not None:
            archive.close()
    if producer_error:
        raise RuntimeError(f"failed to stream PCAP member: {producer_error[0]}")
    if code != 0:
        raise RuntimeError(f"TShark exited {code}: {error_text[-2000:]}")


def collect_candidate_sessions(
    cutoffs: list[dict[str, str]],
    tshark: str,
    candidate: str,
) -> OrderedDict[str, list[dict[str, str]]]:
    sessions: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    raw_packets = 0
    for plan in cutoffs:
        for field in ("source_id", "container_path", "pcap_member"):
            fail_if_final(plan[field], f"pilot_{field}")
        identity = f"{plan['source_id']}\x1f{plan['pcap_member']}"
        limit = int(plan["fit_cutoff_event_position_inclusive"]) + 1
        decoded = 0
        for position, row in enumerate(
            iter_tshark(
                tshark,
                Path(plan["container_path"]),
                plan["pcap_member"],
                plan["dataset_kind"],
                limit,
            )
        ):
            decoded += 1
            key = canonical_session(row)
            if key is None:
                continue
            proto = int(key[0])
            if candidate == "E3" and proto not in {6, 17}:
                continue
            digest = hashlib.sha256(repr((identity, key)).encode("utf-8")).hexdigest()
            if digest not in sessions:
                if len(sessions) >= MAX_SESSIONS:
                    break
                sessions[digest] = []
            sessions[digest].append(row)
            raw_packets += 1
            if raw_packets >= MAX_RAW_PACKETS or len(sessions) >= MAX_SESSIONS:
                break
        if decoded > limit:
            raise RuntimeError("pilot decoded beyond frozen prefix")
        if raw_packets >= MAX_RAW_PACKETS or len(sessions) >= MAX_SESSIONS:
            break
    if not sessions or raw_packets <= 0:
        raise RuntimeError(f"empty resource pilot input for {candidate}")
    return sessions


def uint_tokens(value: int, count: int) -> list[int]:
    width = 2 * count
    mask = (1 << (8 * width)) - 1
    data = (int(value) & mask).to_bytes(width, byteorder="big", signed=False)
    return [int.from_bytes(data[offset:offset + 2], "big") for offset in range(0, width, 2)]


def netfound_flow(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Translate one causal prefix session to the official netFound fields."""
    if not rows:
        raise ValueError("empty session")
    protocol = parse_int(rows[0].get("ip.proto") or rows[0].get("ipv6.nxt"), 0)
    if protocol not in {6, 17}:
        raise ValueError(f"unsupported netFound protocol: {protocol}")
    first_src = (rows[0].get("ip.src") or rows[0].get("ipv6.src") or "").strip()
    prepared: list[dict[str, Any]] = []
    absolute_seq = parse_int(rows[0].get("tcp.seq_raw"), 0)
    first_ack = parse_int(rows[0].get("tcp.ack_raw"), 0)
    absolute_ack = first_ack
    if protocol == 6 and absolute_ack == 0 and len(rows) > 1:
        absolute_ack = parse_int(rows[1].get("tcp.seq_raw"), 0)

    for row in rows:
        src = (row.get("ip.src") or row.get("ipv6.src") or "").strip()
        ipv4 = bool(row.get("ip.src", "").strip())
        timestamp = parse_float(row.get("frame.time_epoch"), 0.0)
        ip_hl = parse_int(row.get("ip.hdr_len"), 20 if ipv4 else 40)
        ip_tos = parse_int(row.get("ip.dsfield") if ipv4 else row.get("ipv6.tclass"), 0)
        ip_tl = parse_int(row.get("ip.len"), 0)
        if not ipv4:
            ip_tl = parse_int(row.get("ipv6.plen"), 0) + 40
        ip_flags = parse_int(row.get("ip.flags"), 0) if ipv4 else 0
        ip_ttl = parse_int(row.get("ip.ttl") if ipv4 else row.get("ipv6.hlim"), 0)
        values = [
            *uint_tokens(ip_hl, 1),
            *uint_tokens(ip_tos, 1),
            *uint_tokens(ip_tl, 1),
            *uint_tokens(ip_flags, 1),
            *uint_tokens(ip_ttl, 1),
        ]
        if protocol == 6:
            seq = parse_int(row.get("tcp.seq_raw"), 0)
            ack = parse_int(row.get("tcp.ack_raw"), 0)
            if src == first_src:
                seq = (seq - absolute_seq) & 0xFFFFFFFF
                ack = 0 if absolute_ack == 0 else (ack - absolute_ack) & 0xFFFFFFFF
            else:
                seq = (seq - absolute_ack) & 0xFFFFFFFF
                ack = (ack - absolute_seq) & 0xFFFFFFFF
            values.extend(
                [
                    *uint_tokens(parse_int(row.get("tcp.flags"), 0), 1),
                    *uint_tokens(parse_int(row.get("tcp.window_size_value"), 0), 1),
                    *uint_tokens(seq, 2),
                    *uint_tokens(ack, 2),
                    *uint_tokens(parse_int(row.get("tcp.urgent_pointer"), 0), 1),
                ]
            )
        else:
            values.extend(uint_tokens(parse_int(row.get("udp.length"), 0), 1))
        # Official preprocessing carries six payload tokens, then the frozen
        # no-payload checkpoint tokenizer removes them.  Zero placeholders
        # preserve that exact interface without reading payload bytes.
        values.extend([0] * 6)
        prepared.append(
            {
                "timestamp": timestamp,
                "forward": src == first_src,
                "bytes": ip_tl,
                "tokens": values,
            }
        )

    by_direction: list[list[dict[str, Any]]] = []
    for forward in (True, False):
        direction_rows = [value for value in prepared if value["forward"] == forward]
        bursts: list[list[dict[str, Any]]] = []
        for value in direction_rows:
            if not bursts or value["timestamp"] - bursts[-1][-1]["timestamp"] > 0.010:
                bursts.append([])
            bursts[-1].append(value)
        by_direction.extend(bursts)
    bursts = sorted(by_direction, key=lambda values: values[0]["timestamp"])[:12]
    bursts = [values[:6] for values in bursts]
    first_time = min(value["timestamp"] for value in prepared)
    previous_burst_time = first_time
    burst_tokens: list[list[int]] = []
    directions: list[bool] = []
    byte_sums: list[int] = []
    iats: list[int] = []
    counts: list[int] = []
    for index, burst in enumerate(bursts):
        burst_time = burst[0]["timestamp"]
        iat_ns = 0 if index == 0 else int(round((burst_time - previous_burst_time) * 1e9))
        previous_burst_time = burst_time
        burst_tokens.append([token for packet in burst for token in packet["tokens"]])
        directions.append(bool(burst[0]["forward"]))
        byte_sums.append(sum(int(packet["bytes"]) for packet in burst))
        iats.append(max(0, iat_ns))
        counts.append(len(burst))
    return {
        "flow_duration": max(0, int(round((max(value["timestamp"] for value in prepared) - first_time) * 1e6))),
        "burst_tokens": burst_tokens,
        "directions": directions,
        "bytes": byte_sums,
        "iats": iats,
        "counts": counts,
        "protocol": protocol,
    }


def import_netfound(source_root: Path):
    import logging
    import types
    import transformers  # noqa: F401 - initialize optional-dependency probes before shims

    src = str(Path(source_root) / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    # The official model modules import their training-only dataset/tensorboard
    # utility layer at module import time.  D0 uses neither.  These narrow
    # compatibility shims keep the official tokenizer/model/encoder bytes
    # unchanged while avoiding a large, unused pyarrow/datasets dependency.
    if "datasets.formatting.formatting" not in sys.modules:
        datasets = types.ModuleType("datasets")
        formatting_pkg = types.ModuleType("datasets.formatting")
        formatting = types.ModuleType("datasets.formatting.formatting")
        formatting.LazyBatch = dict
        datasets.formatting = formatting_pkg
        formatting_pkg.formatting = formatting
        sys.modules.setdefault("datasets", datasets)
        sys.modules.setdefault("datasets.formatting", formatting_pkg)
        sys.modules.setdefault("datasets.formatting.formatting", formatting)
    if "modules.utils" not in sys.modules:
        utility = types.ModuleType("modules.utils")
        utility.GLOBAL_STEP = 0
        utility.TB_WRITER = None
        utility.get_logger = lambda name=None, **_: logging.getLogger(name or "netFound")
        sys.modules["modules.utils"] = utility
    from modules.netFoundConfigBase import netFoundConfig  # type: ignore
    from modules.netFoundDataCollator import SimpleDataCollator  # type: ignore
    from modules.netFoundModels import netFoundLanguageModelling  # type: ignore
    from modules.netFoundTokenizer import netFoundTokenizer  # type: ignore
    return netFoundConfig, SimpleDataCollator, netFoundLanguageModelling, netFoundTokenizer


class PeakRSS:
    def __init__(self) -> None:
        self.peak = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        import psutil
        process = psutil.Process(os.getpid())

        def sample() -> None:
            while not self._stop.wait(0.02):
                self.peak = max(self.peak, int(process.memory_info().rss))

        self.peak = int(process.memory_info().rss)
        self._thread = threading.Thread(target=sample, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)


def pilot_i1(sessions: OrderedDict[str, list[dict[str, str]]], eligible: int) -> dict[str, Any]:
    raw_packets = sum(len(rows) for rows in sessions.values())
    input_hash = sha256_json(
        [
            (digest, [(row.get("frame.number"), row.get("frame.time_epoch"), row.get("frame.len")) for row in rows])
            for digest, rows in sessions.items()
        ]
    )
    elapsed: list[float] = []
    shape_hashes: list[str] = []
    peak_rss = 0
    # One untimed warm-up of the fixed direction/length/protocol/IAT token interface.
    _ = [canonical_session(rows[0]) for rows in list(sessions.values())[:1]]
    for _run in range(RUNS):
        with PeakRSS() as peak:
            started = time.perf_counter()
            shapes = []
            for rows in sessions.values():
                previous = None
                tokens = []
                for row in rows:
                    current = parse_float(row.get("frame.time_epoch"), 0.0)
                    iat_us = 0 if previous is None else max(0, int(round((current - previous) * 1e6)))
                    previous = current
                    key = canonical_session(row)
                    tokens.append((int(key[0]) if key else 0, parse_int(row.get("frame.len"), 0), iat_us))
                shapes.append((len(tokens), 3))
            duration = time.perf_counter() - started
        peak_rss = max(peak_rss, peak.peak)
        elapsed.append(duration)
        shape_hashes.append(sha256_json(shapes))
    median = statistics.median(elapsed)
    return {
        "candidate_id": "I1",
        "status": "PASS",
        "pilot_raw_packets": raw_packets,
        "pilot_candidate_tokens": raw_packets,
        "pilot_peak_rss_bytes": peak_rss,
        "pilot_peak_vram_bytes": "",
        "pilot_median_raw_packets_per_second": f"{raw_packets / median:.12f}",
        "pilot_median_candidate_tokens_per_second": f"{raw_packets / median:.12f}",
        "projected_nonfinal_wall_seconds": f"{eligible / (raw_packets / median):.12f}",
        "custom_adapter_files": "0",
        "custom_adapter_loc": "0",
        "input_sha256": input_hash,
        "config_sha256": sha256_json({"token_fields": ["direction", "frame_len", "protocol", "iat_us"]}),
        "checkpoint_sha256": "NOT_APPLICABLE_D0_UNTRAINED",
        "forward_shape_sha256": sha256_json(shape_hashes),
        "forward_finite": "true",
        "performance_embeddings_persisted": 0,
        "labels_read": 0,
        "final_files_opened": 0,
        "_session_count": len(sessions),
        "_run_seconds": elapsed,
    }


def pilot_e3(
    sessions: OrderedDict[str, list[dict[str, str]]],
    eligible: int,
    source_root: Path,
    checkpoint_dir: Path,
) -> dict[str, Any]:
    import torch
    netFoundConfig, SimpleDataCollator, netFoundLanguageModelling, netFoundTokenizer = import_netfound(source_root)
    model_file = Path(checkpoint_dir) / "model.safetensors"
    config_file = Path(checkpoint_dir) / "config.json"
    if sha256_file(model_file) != NETFOUND_CHECKPOINT_SHA256:
        raise RuntimeError("netFound checkpoint SHA mismatch")
    config = netFoundConfig.from_pretrained(str(checkpoint_dir), local_files_only=True)
    config.pretraining = False
    config.compile = False
    model = netFoundLanguageModelling.from_pretrained(
        str(checkpoint_dir), config=config, local_files_only=True
    )
    model.to(device="cpu", dtype=torch.float32)
    model.eval()
    tokenizer = netFoundTokenizer(config=config)
    tokenizer.pretraining = True
    tokenizer.raw_labels = False
    collator = SimpleDataCollator(pad_token_id=tokenizer.pad_token_id)

    raw_flows = [netfound_flow(rows) for rows in sessions.values()]
    dataset = {key: [flow[key] for flow in raw_flows] for key in raw_flows[0]}
    encoded = tokenizer(dataset)
    examples = [{key: value[index] for key, value in encoded.items()} for index in range(len(raw_flows))]
    batches = [collator(examples[offset:offset + 4]) for offset in range(0, len(examples), 4)]
    raw_packets = sum(len(rows) for rows in sessions.values())
    candidate_tokens = int(sum(int(batch["attention_mask"].sum().item()) for batch in batches))
    input_hash = sha256_json(
        [
            (digest, [(row.get("frame.number"), row.get("frame.time_epoch"), row.get("frame.len")) for row in rows])
            for digest, rows in sessions.items()
        ]
    )

    def forward(batch: Any) -> tuple[tuple[int, ...], bool]:
        with torch.inference_mode():
            seq_len = int(batch["input_ids"].shape[1])
            position_ids = torch.arange(seq_len).unsqueeze(0).expand(batch["input_ids"].shape[0], -1)
            output = model.base_transformer(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                position_ids=position_ids,
                direction=batch["direction"].to(torch.float32),
                iats=batch["iats"].to(torch.float32),
                bytes=batch["bytes"].to(torch.float32),
                pkt_count=batch["pkt_count"].to(torch.float32),
                protocol=batch["protocol"],
                dataset_burst_sizes=batch["dataset_burst_sizes"],
                return_dict=True,
            ).last_hidden_state
            shape = tuple(int(value) for value in output.shape)
            finite = bool(torch.isfinite(output).all().item())
            del output
            return shape, finite

    # Exactly one untimed warm-up.
    warm_shape, warm_finite = forward(batches[0])
    if not warm_finite:
        raise RuntimeError("netFound warm-up produced nonfinite output")
    elapsed: list[float] = []
    shape_hashes: list[str] = []
    peak_rss = 0
    for _run in range(RUNS):
        shapes = []
        with PeakRSS() as peak:
            started = time.perf_counter()
            for batch in batches:
                shape, finite = forward(batch)
                if not finite:
                    raise RuntimeError("netFound pilot produced nonfinite output")
                shapes.append(shape)
            duration = time.perf_counter() - started
        peak_rss = max(peak_rss, peak.peak)
        elapsed.append(duration)
        shape_hashes.append(sha256_json(shapes))
    median = statistics.median(elapsed)
    loc = 0
    with Path(__file__).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            loc += int(bool(stripped) and not stripped.startswith("#"))
    return {
        "candidate_id": "E3",
        "status": "PASS",
        "pilot_raw_packets": raw_packets,
        "pilot_candidate_tokens": candidate_tokens,
        "pilot_peak_rss_bytes": peak_rss,
        "pilot_peak_vram_bytes": "",
        "pilot_median_raw_packets_per_second": f"{raw_packets / median:.12f}",
        "pilot_median_candidate_tokens_per_second": f"{candidate_tokens / median:.12f}",
        "projected_nonfinal_wall_seconds": f"{eligible / (raw_packets / median):.12f}",
        "custom_adapter_files": Path(__file__).name,
        "custom_adapter_loc": loc,
        "input_sha256": input_hash,
        "config_sha256": sha256_file(config_file),
        "checkpoint_sha256": NETFOUND_CHECKPOINT_SHA256,
        "forward_shape_sha256": sha256_json([warm_shape, *shape_hashes]),
        "forward_finite": "true",
        "performance_embeddings_persisted": 0,
        "labels_read": 0,
        "final_files_opened": 0,
        "_session_count": len(sessions),
        "_run_seconds": elapsed,
    }


def run(args: argparse.Namespace) -> None:
    if sha256_file(Path(args.contract)) != CONTRACT_SHA256:
        raise RuntimeError("FROZEN contract SHA drift")
    cutoffs = read_csv(Path(args.cutoffs))
    if not cutoffs:
        raise RuntimeError("empty fit-prefix manifest")
    census = json.loads(Path(args.census).read_text(encoding="utf-8"))
    if census.get("status") != "CKDA_D0_DATA_CENSUS_COMPLETE":
        raise RuntimeError("census is not terminal")
    if int(census.get("final_files_opened", -1)) != 0 or int(census.get("raw_label_columns_read", -1)) != 0:
        raise RuntimeError("census data boundary failure")

    rows: list[dict[str, Any]] = []
    # E3 is the only external candidate surviving the static hard gates.
    e3_sessions = collect_candidate_sessions(cutoffs, args.tshark, "E3")
    rows.append(
        pilot_e3(
            e3_sessions,
            int(census["fit_encodable_unique_packets"]["E3"]),
            Path(args.netfound_source),
            Path(args.netfound_checkpoint),
        )
    )
    if census.get("i1_data_gate") == "PASS":
        i1_sessions = collect_candidate_sessions(cutoffs, args.tshark, "I1")
        rows.append(
            pilot_i1(i1_sessions, int(census["fit_encodable_unique_packets"]["I1"]))
        )
    public_rows = [{field: row[field] for field in PILOT_FIELDS} for row in rows]
    write_csv(Path(args.out), public_rows, PILOT_FIELDS)
    measurements = {
        "status": "CKDA_D0_RESOURCE_PILOT_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "runs_per_candidate": RUNS,
        "warmup_runs_per_candidate": 1,
        "selection_rule": "first_100_nonempty_sessions_or_100000_raw_packets",
        "embedding_values_persisted": 0,
        "labels_read": 0,
        "final_files_opened": 0,
        "candidates": {
            row["candidate_id"]: {
                "session_count": row["_session_count"],
                "raw_packets": row["pilot_raw_packets"],
                "candidate_tokens": row["pilot_candidate_tokens"],
                "run_seconds": row["_run_seconds"],
                "input_sha256": row["input_sha256"],
                "config_sha256": row["config_sha256"],
                "checkpoint_sha256": row["checkpoint_sha256"],
                "forward_shape_sha256": row["forward_shape_sha256"],
                "forward_finite": row["forward_finite"],
            }
            for row in rows
        },
    }
    measurements_path = Path(args.out).with_name("ckda_d0_resource_pilot_measurements.json")
    temp = measurements_path.with_name(f".{measurements_path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(measurements, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, measurements_path)
    print(json.dumps({"status": "CKDA_D0_RESOURCE_PILOT_COMPLETE", "candidates": [row["candidate_id"] for row in rows]}, indent=2))


def contract_test(_: argparse.Namespace) -> None:
    assert len(PILOT_FIELDS) == 19
    assert canonical_session({"ip.src": "10.0.0.2", "ip.dst": "10.0.0.1", "ip.proto": "6", "tcp.srcport": "2", "tcp.dstport": "1"}) == canonical_session({"ip.src": "10.0.0.1", "ip.dst": "10.0.0.2", "ip.proto": "6", "tcp.srcport": "1", "tcp.dstport": "2"})
    assert uint_tokens(0x12345678, 2) == [0x1234, 0x5678]
    sample = {
        field: "" for field in TSHARK_FIELDS
    }
    sample.update({
        "frame.number": "1", "frame.time_epoch": "1.0", "frame.len": "60",
        "ip.src": "10.0.0.1", "ip.dst": "10.0.0.2", "ip.proto": "6",
        "ip.hdr_len": "20", "ip.len": "60", "ip.ttl": "64",
        "tcp.srcport": "1", "tcp.dstport": "2", "tcp.flags": "0x02",
        "tcp.window_size_value": "1024", "tcp.seq_raw": "100", "tcp.ack_raw": "0",
    })
    flow = netfound_flow([sample])
    assert flow["protocol"] == 6 and len(flow["burst_tokens"]) == 1
    assert len(flow["burst_tokens"][0]) == 18
    print(json.dumps({"status": "PASS", "tests": 4}, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    test = sub.add_parser("contract-test")
    test.set_defaults(func=contract_test)
    pilot = sub.add_parser("run")
    pilot.add_argument("--contract", type=Path, required=True)
    pilot.add_argument("--cutoffs", type=Path, required=True)
    pilot.add_argument("--census", type=Path, required=True)
    pilot.add_argument("--netfound-source", type=Path, required=True)
    pilot.add_argument("--netfound-checkpoint", type=Path, required=True)
    pilot.add_argument("--tshark", default="tshark")
    pilot.add_argument("--out", type=Path, required=True)
    pilot.set_defaults(func=run)
    return result


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
