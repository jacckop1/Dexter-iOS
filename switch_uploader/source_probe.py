#!/usr/bin/env python3
"""One-off SAFE source status probe. Reads HTTP response headers only; no IPA data."""
import json
from pathlib import Path

import requests
items=json.loads(Path("switch_uploader/games.json").read_text(encoding="utf-8"))["games"]
for i, item in enumerate(items,1):
    print(f"\nSOURCE {i}: {item['name']} ({item['version']})",flush=True)
    try:
        with requests.get(item["url"],stream=True,allow_redirects=True,timeout=(15,22),
                          headers={"Range":"bytes=0-0","Accept-Encoding":"identity",
                                   "User-Agent":"Mozilla/5.0"}) as response:
            print("status:",response.status_code,flush=True)
            print("content-range:",response.headers.get("Content-Range","(none)"),flush=True)
            print("content-length:",response.headers.get("Content-Length","(none)"),flush=True)
            print("content-type:",response.headers.get("Content-Type","(none)"),flush=True)
            print("transfer-encoding:",response.headers.get("Transfer-Encoding","(none)"),flush=True)
            print("redirects:",len(response.history),flush=True)
            print("redirect-statuses:",[r.status_code for r in response.history],flush=True)
            print("final-host:",requests.utils.urlparse(response.url).hostname,flush=True)
    except requests.RequestException as error:
        print("request-error:",type(error).__name__,flush=True)

# Image URLs are intentionally not fetched because the uploader does not
# attach thumbnails or cover photos to the IPA files.
