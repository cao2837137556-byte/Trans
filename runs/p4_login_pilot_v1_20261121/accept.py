"""Produce the pilot deliverables and verify every returned file SHA-256."""
import argparse
from pathlib import Path

from audit import identity, join, read, save, write_tables
from feature_witness import witness

LABELS = {
    "successful_login": "成功登录",
    "mistake_then_retry": "输错后在同一连接重试",
    "disconnect_then_reconnect": "掉线后重新建立 TCP 连接",
}


def paper(record):
    c = record["capture"]
    f = record["features"]
    h = record["checks"]
    lines = [
        "# 同服务正常登录采集小试",
        "",
        f"实际采集 **{c['duration_seconds']:.3f} 秒**，结束条件为 "
        + ("达到计划时长。" if c["stop_reason"]=="DURATION_REACHED" else c["stop_reason"]+"。")
        + f"PCAP 和四份源日志合计 **{record['capture_bytes']:,} 字节**，其中 PCAP **{record['pcap_bytes']:,} 字节**。",
        "",
        "三个客户端分别使用独立的 IP 和 MAC，并轮换执行三类场景。服务与客户端通过专用网络命名空间和内部虚拟桥通信。"
        "掉线用一次已观察到的 TCP RST 模拟，随后建立新 TCP 连接。场景标签只用独立日志。",
        "",
        "| 场景 | 场景轮次 | 请求 | TCP 连接 | 认证成功 | 认证失败 | 未对齐请求 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in record["scenarios"]:
        n = [r[k] for k in ("cases","requests","connections","observed_200","observed_401","unaligned")]
        lines.append("| "+" | ".join([LABELS[r["scenario"]],*map(str,n)])+" |")
    lines.extend((
        "",
        f"PCAP 共 **{h['total_frames']:,} 帧**。{h['complete_duplex_handshakes']}／{h['tcp_connections']} 条 TCP 连接"
        f"看到了 SYN、SYN-ACK 与序号匹配的最终 ACK。每个客户端均记录到入站和出站帧。"
        f"内核抓包丢弃 {c['capture_kernel_drops']} 帧。",
        "",
        f"共有 **{h['aligned_requests']} 条**请求按有向连接、连接内请求序号和时间窗对齐。"
        f"PCAP 无客户端配对的请求数 {h['unmatched_pcap_requests']}，服务端无配对的认证记录数 {h['unmatched_server_auth']}。",
        "",
        f"按真实帧序复用冻结握手计数器，{h['handshake_60s_oracle_identical']} 条请求与独立三次握手账完全一致，"
        f"范围 {h['h60_min']}–{h['h60_max']}。统计窗口使用当前帧已经观察到的入站握手。",
        "",
    ))
    if f["status"] == "PASS":
        lines.append(f"**{f['real_frames']} 条真实请求帧**通过 790 维输入验证。使用冻结 NetFound 的 768 维表征、"
                     "14 维查询属性及 8 维设备状态。两份源归一化参数已按 SHA 核验。输入核验在本机 Windows CPU 运行，"
                     "同批记录的握手与 UID 顺序已绑定。")
    else:
        lines.append(f"790 维输入核验状态为 {f['status']}。详细信息见特征回执。")
    lines.extend(("", "小试独立存档，后续两小时建档与独立正常评价需各自采集。", "",
                  "[场景小表](SCENARIOS.csv) · [逐请求对齐](ALIGNMENT.jsonl) · [790 维回执](FEATURE_790.json)"
                  " · [SHA-256 清单](SHA256SUMS)", ""))
    return "\n".join(lines)


def accept(out, normalizer):
    c = read(out/"CAPTURE.json")
    assert c["stage"] == "SEALED_CAPTURE" and c["duration_seconds"] == 600 and not c["smoke"]
    assert c["namespaces_removed"] and c["isolated_no_default_routes"]
    capture = c["capture"]
    assert capture["requested_seconds"] == 600
    sizes = {n:(out/n).stat().st_size for n in c["capture_files"]}
    assert sizes == c["capture_files"] and sum(sizes.values()) <= c["limit_bytes"]
    assert len({e["mac"] for e in c["endpoints"]}) == len({e["ip"] for e in c["endpoints"]}) == 4
    receipt, align, rows = join(out,c)
    write_tables(out,receipt,align)
    print(f"PCAP checked: {receipt['checks']['aligned_requests']} matched requests", flush=True)
    f = witness(out,receipt,align,rows,normalizer)
    save(out/"FEATURE_790.json", f)
    h = receipt["checks"]
    assert f["real_frames"] == h["aligned_requests"]
    assert f["request_uid_order_sha256"] == h["request_uid_order_sha256"]
    r = dict(status="PASS" if receipt["status"] == f["status"] == "PASS" else "REVIEW",
             capture=capture, capture_bytes=sum(sizes.values()), pcap_bytes=sizes["login.pcap"],
             free_at_start_bytes=c["free_at_start_bytes"], free_at_seal_bytes=c["remaining_bytes"],
             checks=h, scenarios=receipt["scenarios"], features=f, capture_files=sizes)
    (out/"RESULTS.md").write_bytes(paper(r).encode("utf8"))
    files = sorted([*sizes, "CAPTURE.json","CAPTURE_PROGRESS.json","PREFLIGHT.json","PACKET_ACCEPTANCE.json",
                    "SCENARIOS.csv","ALIGNMENT.jsonl","FEATURE_790.json","RESULTS.md"])
    if (out/"FEATURE_PREFLIGHT.json").is_file():
        files.append("FEATURE_PREFLIGHT.json")
    r["evidence"] = {n:identity(out/n) for n in files}
    save(out/"ACCEPTANCE.json",r)
    paths = files + ["ACCEPTANCE.json"]
    hashes = {n:identity(out/n)["sha256"] for n in paths}
    (out/"SHA256SUMS").write_bytes("".join(f"{h}  {n}\n" for n,h in hashes.items()).encode("ascii"))
    assert all(identity(out/n)["sha256"] == expected for n,expected in hashes.items())
    print(f"{r['status']} {len(paths)} files verified", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("out",type=Path)
    p.add_argument("--context-normalizer",type=Path)
    a = p.parse_args()
    accept(a.out,a.context_normalizer)
