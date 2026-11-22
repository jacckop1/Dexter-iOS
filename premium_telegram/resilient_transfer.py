"""Fault-tolerant in-job HTTP Range download and MTProto big-file upload.

The resume data lives on the CURRENT GitHub runner only. GitHub re-runs
create new machines and cannot restore downloads without external storage.
"""

import asyncio
import math
import secrets
import time
from pathlib import Path

import requests
from telethon.tl import functions, types

PART_SIZE = 512 * 1024
MAX_PARTS = 8000
HTTP_TIMEOUT = (20, 35)
TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
MAX_DOWNLOAD_SECONDS = 3 * 60 * 60
MAX_UPLOAD_SECONDS = 3 * 60 * 60


def _range(response: requests.Response, expected: int, offset: int) -> None:
    if response.status_code != 206:
        raise RuntimeError("The source does not honor HTTP Range: refusing to lose existing progress")
    value = response.headers.get("content-range", "")
    import re
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+)", value, flags=re.I)
    if not match:
        raise RuntimeError("Source returned an invalid Content-Range")
    start, end, total = (int(x) for x in match.groups())
    if start != offset or end < start or total != expected or end >= expected:
        raise RuntimeError("Source Content-Range changed or mismatched: cannot safely resume")


def download_resumable(session: requests.Session, url: str, target: Path,
                       expected: int, require_range: bool = True,
                       max_seconds: int = MAX_DOWNLOAD_SECONDS,
                       idle_seconds: int = 35) -> None:
    """Resume at exact on-disk byte offset on timeout/disconnect/5xx.

    Without Range, rejects the source before a large download begins.
    Never truncates existing data. Never retries from zero on transient failures.
    """
    if expected <= 0:
        raise ValueError("Expected file size must be > 0")
    stop = time.monotonic() + max_seconds
    failed = 0
    last_mark = -1
    if require_range is False:
        raise RuntimeError("This resilient transfer requires HTTP Range support")

    while True:
        offset = target.stat().st_size if target.exists() else 0
        if offset == expected:
            print(f"Download verified: {expected:,} bytes", flush=True)
            return
        if offset > expected:
            raise RuntimeError("Local file grew beyond expected size")
        if time.monotonic() >= stop:
            raise RuntimeError(f"Download time budget exceeded; {offset:,}/{expected:,} bytes retained only on this runner")

        headers = {
            "Range": f"bytes={offset}-",
            "Accept-Encoding": "identity",
            "User-Agent": "Mozilla/5.0",
        }
        temporary = False
        retry_after = 0
        try:
            # HTTP requests are always resumed, even the first from byte 0.
            with session.get(url, stream=True, headers=headers,
                             timeout=(HTTP_TIMEOUT[0], idle_seconds)) as response:
                if response.status_code in TRANSIENT_HTTP:
                    temporary = True
                    retry_after_raw = response.headers.get("retry-after", "")
                    if retry_after_raw.isdecimal():
                        retry_after = min(120, int(retry_after_raw))
                    print(f"Source HTTP {response.status_code}; retrying Range from {offset:,}", flush=True)
                elif response.status_code in (401, 403, 404, 410):
                    raise RuntimeError(f"Source HTTP {response.status_code}: link unavailable or expired")
                elif response.status_code not in (200, 206):
                    raise RuntimeError(f"Unexpected source HTTP {response.status_code}")
                else:
                    _range(response, expected, offset)
                    if (response.headers.get("content-type") or "").lower().startswith("text/html"):
                        raise RuntimeError("Source served an HTML page instead of IPA data")
                    with target.open("ab") as output:
                        for data in response.iter_content(chunk_size=1024 * 1024):
                            if not data:
                                continue
                            output.write(data)
                            current = output.tell()
                            if current > expected:
                                raise RuntimeError("Source sent more data than expected")
                            mark = min(100, current * 100 // expected // 5 * 5)
                            if mark > last_mark:
                                print(f"Download: {mark}% ({current:,}/{expected:,} bytes)", flush=True)
                                last_mark = mark
                    if target.stat().st_size == expected:
                        return
                    print("Source ended early; reconnecting with Range...", flush=True)
                    temporary = True
        except requests.RequestException as exc:
            # Never print a request exception: it can contain a signed URL.
            print(f"Connection interrupted ({type(exc).__name__}); resuming from disk", flush=True)
            temporary = True

        if not temporary:
            # Non-retryable corruption or access errors are raised above.
            raise RuntimeError("Source transfer ended unexpectedly")
        failed += 1
        # Repeated disconnections do not delete or reset partial bytes.
        delay = max(retry_after, min(60.0, 1.5 * (2 ** min(failed - 1, 6))))
        remaining = stop - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Download time budget exhausted; cannot recover without persistent storage")
        if failed % 5 == 0:
            print(f"Retrying interrupted source: {failed} attempts; offset={target.stat().st_size if target.exists() else 0:,}", flush=True)
        time.sleep(min(delay, remaining))


async def upload_big_parts(client, path: Path, concurrency: int = 3,
                           max_seconds: int = MAX_UPLOAD_SECONDS, label: str = "") -> types.InputFileBig:
    """A failed 512 KiB Telegram part is retried in-place, not from part zero.

    Concurrent part requests are idempotent for a fixed file_id/index/payload.
    This does not persist past a cancelled or restarted GitHub Actions job.
    """
    length = path.stat().st_size
    parts = math.ceil(length / PART_SIZE)
    if length <= 10 * 1024 * 1024:
        raise ValueError("Only large files should use upload_big_parts")
    if parts > MAX_PARTS:
        raise ValueError("Premium upload exceeds the 8000-part ceiling")
    if concurrency < 1 or concurrency > 6:
        raise ValueError("Upload concurrency must be 1..6")
    file_id = secrets.randbits(63) or 1
    done = 0
    last_mark = -1
    deadline = time.monotonic() + max_seconds
    lock = asyncio.Lock()

    async def worker(worker_index: int) -> None:
        nonlocal done, last_mark
        with path.open("rb") as handle:
            for part in range(worker_index, parts, concurrency):
                handle.seek(part * PART_SIZE)
                data = handle.read(PART_SIZE)
                if not data:
                    raise RuntimeError("Input IPA truncated while uploading")
                attempt = 0
                while True:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Telegram upload time budget exceeded; downloaded IPA remains on this runner")
                    try:
                        if not client.is_connected():
                            await client.connect()
                        request = functions.upload.SaveBigFilePartRequest(
                            file_id=file_id,
                            file_part=part,
                            file_total_parts=parts,
                            bytes=data,
                        )
                        ok = await asyncio.wait_for(client(request), timeout=90)
                        if not ok:
                            raise RuntimeError("Telegram rejected a file part")
                        break
                    except (asyncio.CancelledError, KeyboardInterrupt):
                        raise
                    except Exception as error:
                        # Permanent errors must fail immediately, not loop forever.
                        name = type(error).__name__
                        message = str(error)
                        if (name in {"FilePartsInvalidError", "FilePartInvalidError",
                                     "FilePartSizeInvalidError", "FilePartTooBigError",
                                     "AuthKeyUnregisteredError", "AuthKeyDuplicatedError", "SessionRevokedError",
                                     "UserDeactivatedError"} or
                                "FILE_PARTS_INVALID" in message or
                                "FILE_PART_SIZE_INVALID" in message or
                                "AUTH_KEY_UNREGISTERED" in message or
                                "AUTH_KEY_DUPLICATED" in message):
                            raise RuntimeError(f"Unrecoverable Telegram error: {name}") from None
                        attempt += 1
                        wait_s = min(45, 1.5 * (2 ** min(attempt - 1, 5)))
                        specified = getattr(error, "seconds", None)
                        if isinstance(specified, (int, float)) and specified > 0:
                            wait_s = max(wait_s, float(specified) + 2)
                        if attempt == 1 or attempt % 5 == 0:
                            print(f"[{label}] Telegram part {part + 1}/{parts} interrupted ({name}); "
                                  f"retrying same part (attempt {attempt})", flush=True)
                        if time.monotonic() + wait_s >= deadline:
                            raise RuntimeError("Telegram upload retry deadline reached") from None
                        await asyncio.sleep(wait_s)

                async with lock:
                    done += 1
                    mark = min(100, done * 100 // parts // 5 * 5)
                    if mark > last_mark:
                        print(f"[{label}] Telegram acknowledged: {mark}% ({done:,}/{parts:,} parts)", flush=True)
                        last_mark = mark

    await asyncio.gather(*(worker(i) for i in range(concurrency)))
    if done != parts:
        raise RuntimeError("Telegram part acknowledgement mismatch")
    print(f"[{label}] All {parts:,} Telegram parts acknowledged", flush=True)
    return types.InputFileBig(id=file_id, parts=parts, name=path.name)
