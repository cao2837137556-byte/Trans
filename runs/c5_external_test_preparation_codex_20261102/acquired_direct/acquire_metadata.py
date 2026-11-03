"""Bounded official metadata acquisition; no browser credentials or raw data."""
from __future__ import annotations
import hashlib
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIMIT = 2 * 1024 * 1024

class Links(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.links, self.forms = base, [], []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(urllib.parse.urljoin(self.base, a["href"]))
        if tag in ("form", "input", "select", "option"):
            self.forms.append({"tag": tag, **a})

def fetch(opener, name, url):
    started = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "CICIoMT2024-metadata-research/1.0", "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1"})
    try:
        try:
            response = opener.open(req, timeout=25)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            data = response.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise RuntimeError("metadata size limit exceeded")
            status, final_url = response.status, response.geturl()
            headers = {k: v for k, v in response.headers.items() if k.lower() not in {"set-cookie", "cookie", "authorization", "proxy-authorization"}}
        path = ROOT / (name + ".html")
        path.write_bytes(data)
        parser = Links(final_url)
        parser.feed(data.decode("utf-8", errors="replace"))
        return {"name": name, "requested_url": url, "final_url": final_url,
                "status": status, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "headers": headers, "path": path.name, "links": list(dict.fromkeys(parser.links)),
                "forms": parser.forms, "elapsed_seconds": round(time.monotonic() - started, 3)}
    except Exception as exc:
        return {"name": name, "requested_url": url, "error": type(exc).__name__ + ": " + str(exc),
                "elapsed_seconds": round(time.monotonic() - started, 3)}

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    result = {"created_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "official HTML metadata only; ordinary independent session; no registration submission",
              "requests": []}
    for name, url in [
        ("registration_root", "https://cicresearch.ca/IOTDataset/CICIoMT2024/"),
        ("profiling_browse", "https://cicresearch.ca/IOTDataset/CICIoMT2024/browse.php?p=WiFI_and_MQTT%2Fprofiling"),
        ("official_dataset_description", "https://www.unb.ca/cic/datasets/iomt-dataset-2024.html"),
    ]:
        row = fetch(opener, name, url)
        result["requests"].append(row)
        (ROOT / "HTTP_RECEIPT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(row, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
