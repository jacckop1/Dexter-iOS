"""Fast resumable multi-connection HTTP Range downloads for GitHub-hosted Ubuntu.

Eight independent range connections per IPA (configurable) write into one
sparse file. A disconnected request reconnects at its exact byte offset;
downloaded bytes are never reset inside the current process / runner.
"""

from concurrent.futures import ThreadPoolExecutor
import math
import os
from pathlib import Path
import queue
import re
import threading
import time

import requests


TRANSIENT = {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
PER_RANGE_BYTES = 32 * 1024 * 1024
STREAM_BYTES = 256 * 1024
DOWNLOAD_BUDGET = 3 * 60 * 60


def _content_range_valid(value: str, start: int, end: int, total: int) -> bool:
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+)", value, re.I)
    return bool(match and tuple(map(int, match.groups())) == (start, end, total))


def fast_download(url: str, target: Path, expected: int, *, label: str = "",
                  connections: int = 8, block_size: int = PER_RANGE_BYTES,
                  max_seconds: int = DOWNLOAD_BUDGET, idle_seconds: int = 30) -> None:
    """Write non-overlapping bounded ranges in parallel; restart failed range at same offset.

    Each range has its own retry loop and requests.Session. No temporary copy
    of the entire file. The sparse target needs no double-disk allocation.
    Must finish on same GitHub runner; not persistent across job restarts.
    """
    if expected <= 0 or not 1 <= connections <= 12 or block_size < STREAM_BYTES:
        raise ValueError("Invalid expected size, connection count or block size")
    if target.exists():
        raise RuntimeError("Parallel output file already exists; refusing to overwrite or reset")
    target.parent.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + max_seconds
    start_time = time.monotonic()
    pending = queue.Queue()
    for start in range(0, expected, block_size):
        pending.put((start, min(expected - 1, start + block_size - 1)))
    count_ranges = math.ceil(expected / block_size)
    done_bytes = 0
    finished_ranges = 0
    progress_threshold = 5
    lock = threading.Lock()
    stop_event = threading.Event()

    def mark(size: int, completed: bool = False) -> None:
        nonlocal done_bytes, finished_ranges, progress_threshold
        with lock:
            done_bytes += size
            if completed:
                finished_ranges += 1
            pct = min(100, done_bytes * 100 // expected)
            elapsed = max(0.001, time.monotonic() - start_time)
            rate = done_bytes / elapsed / 1048576
            eta = int((expected - done_bytes) / (rate * 1048576)) if rate > 0 else 0
            while pct >= progress_threshold:
                value = progress_threshold
                print(
                    f"::notice title={label.upper()} Download {value}%::"
                    f"[{label}] Download {value}% | {done_bytes / 1048576:.1f} / "
                    f"{expected / 1048576:.1f} MiB | {rate:.2f} MiB/s | ETA {eta}s",
                    flush=True,
                )
                progress_threshold += 5

    def worker() -> None:
        with requests.Session() as session:
            while not stop_event.is_set():
                try:
                    low, high = pending.get_nowait()
                except queue.Empty:
                    return
                offset = low
                consecutive_errors = 0
                try:
                    while offset <= high and not stop_event.is_set():
                        if time.monotonic() >= deadline:
                            raise RuntimeError(f"[{label}] Download deadline reached")

                        # After repeated timeouts, split the remaining work
                        # into smaller HTTP requests without discarding bytes.
                        request_end = (
                            min(high, offset + 1024 * 1024 - 1)
                            if consecutive_errors >= 2 else high
                        )
                        headers = {
                            "Range": f"bytes={offset}-{request_end}",
                            "Accept-Encoding": "identity",
                            "User-Agent": "Mozilla/5.0",
                            **({"Connection": "close"} if consecutive_errors >= 2 else {}),
                        }
                        interrupted = False
                        retry_after = 0
                        try:
                            with session.get(
                                url, headers=headers, stream=True,
                                timeout=(15, min(idle_seconds, 18) if consecutive_errors >= 2 else idle_seconds)
                            ) as response:
                                if response.status_code in TRANSIENT:
                                    interrupted = True
                                    raw = response.headers.get("retry-after", "")
                                    if raw.isdecimal():
                                        retry_after = min(90, int(raw))
                                elif response.status_code in (401, 403, 404, 410):
                                    raise RuntimeError(f"[{label}] Source HTTP {response.status_code}: unavailable")
                                elif response.status_code != 206:
                                    raise RuntimeError(f"[{label}] Source ignored Range: HTTP {response.status_code}")
                                else:
                                    if not _content_range_valid(
                                        response.headers.get("content-range", ""),
                                        offset, request_end, expected
                                    ):
                                        raise RuntimeError(f"[{label}] Source Content-Range mismatch")
                                    if response.headers.get("content-type", "").lower().startswith("text/html"):
                                        raise RuntimeError(f"[{label}] Source returned HTML instead of an IPA")

                                    for chunk in response.iter_content(chunk_size=STREAM_BYTES):
                                        if stop_event.is_set():
                                            return
                                        if not chunk:
                                            continue
                                        if offset + len(chunk) > request_end + 1:
                                            raise RuntimeError(f"[{label}] Source exceeded requested HTTP range")
                                        # os.pwrite is Linux-specific, so parallel ranges never
                                        # move a shared file pointer or overwrite other blocks.
                                        written = 0
                                        while written < len(chunk):
                                            n = os.pwrite(fd, chunk[written:], offset + written)
                                            if n <= 0:
                                                raise OSError("Cannot write to runner disk")
                                            written += n
                                        offset += len(chunk)
                                        mark(len(chunk))
                                    # A shortened request may finish before the
                                    # original assigned range does: immediately
                                    # continue from the new offset, no penalty.
                                    if offset > request_end:
                                        consecutive_errors = 0
                                        continue
                                    if offset <= high:
                                        interrupted = True
                        except requests.RequestException as error:
                            # Never print the exception text; signed URLs may occur in it.
                            print(f"[{label}] Connection pause ({type(error).__name__}); "
                                  f"resume byte {offset:,}", flush=True)
                            interrupted = True

                        if offset > high:
                            break
                        if not interrupted:
                            raise RuntimeError(f"[{label}] Range stopped without recoverable reason")
                        consecutive_errors += 1
                        delay = max(retry_after, min(18.0, 1.5 * (2 ** min(consecutive_errors - 1, 5))))
                        if time.monotonic() + delay >= deadline:
                            raise RuntimeError(f"[{label}] Download retry time exceeded")
                        if consecutive_errors == 1 or consecutive_errors % 5 == 0:
                            print(f"[{label}] Range {low:,}-{high:,}: "
                                  f"reconnecting at byte {offset:,} (attempt {consecutive_errors})", flush=True)
                        # Short cooldown after 429 / errors; not a data reset.
                        if stop_event.wait(delay):
                            return
                    mark(0, completed=True)
                except BaseException:
                    stop_event.set()
                    raise

    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        os.ftruncate(fd, expected)
        print(f"[{label}] Download using {connections} parallel HTTP Range connections "
              f"({count_ranges} ranges), total {expected / 1048576:.1f} MiB", flush=True)
        with ThreadPoolExecutor(max_workers=min(connections, count_ranges)) as pool:
            futures = [pool.submit(worker) for _ in range(min(connections, count_ranges))]
            for future in futures:
                try:
                    future.result()
                except BaseException:
                    stop_event.set()
                    raise
        if done_bytes != expected or finished_ranges != count_ranges:
            raise RuntimeError(f"[{label}] Incomplete transfer: {done_bytes:,}/{expected:,} bytes")
        os.fsync(fd)
        print(f"[{label}] Download verified: 100% ({expected:,} bytes)", flush=True)
    except BaseException:
        # Keep partial runner file for debugging until temp directory is cleaned up.
        raise
    finally:
        os.close(fd)
