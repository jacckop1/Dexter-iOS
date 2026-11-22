#!/usr/bin/env python3
"""Safe remote HEAD/Range probes of the two fixed PUBG URLs. No user credentials."""
import traceback
from pathlib import Path
from upload_pubg_both import prepare

failures = []
for key in ("gl","kr"):
    print(f"[{key}] Source inspection starting",flush=True)
    try:
        j=prepare(key)
        print(f"[{key}] PASS: {j.size:,} B, note={len(j.note)} chars, icon supplied",flush=True)
    except Exception as error:
        frames=traceback.extract_tb(error.__traceback__)
        safe=[f"{Path(x.filename).name}:{x.lineno} ({x.name})" for x in frames
              if Path(x.filename).name in {"upload_pubg_both.py","uploader.py","metadata.py","pubg_source_preflight.py"}]
        print(f"[{key}] ERROR TYPE: {type(error).__name__}",flush=True)
        print(f"[{key}] SOURCE LOCATION: "+" > ".join(safe[-8:]),flush=True)
        if isinstance(error,AttributeError):
            print(f"[{key}] ATTRIBUTE DETAIL: {str(error)[:200]}",flush=True)
        if isinstance(error,RuntimeError):
            print(f"[{key}] RUNTIME DETAIL: {str(error)[:200]}",flush=True)
        failures.append(key)
if failures:
    raise SystemExit(1)
print("Both PUBG source preflights successful — no IPAs downloaded",flush=True)
