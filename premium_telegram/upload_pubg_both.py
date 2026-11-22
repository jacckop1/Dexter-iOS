#!/usr/bin/env python3
"""Concurrent PUBG transfers with ONE MTProto client and ONE GitHub runner.

Do not use one StringSession on different runners at the same time.
"""

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

from metadata import caption_segments, load_json, write_thumb
from resilient_transfer import MAX_PARTS, PART_SIZE, download_resumable, upload_big_parts
from uploader import auth_values, filename_safe, inspect_source


TARGETS = {
    "gl": ("APP-5874636765", "Pubg GL Hack"),
    "kr": ("APP-1167550679", "Pubg KR Hack"),
}
JSON_PATH = "premium_telegram/pubg_targets.json"


@dataclass(frozen=True)
class Job:
    key: str
    name: str
    url: str
    filename: str
    size: int
    note: str
    icon: str


def prepare(key: str) -> Job:
    app_id, expected_name = TARGETS[key]
    with requests.Session() as http:
        item = load_json(http, JSON_PATH, app_id)
        if item.name != expected_name or not item.version or not item.description or not item.icon_url:
            raise RuntimeError(f"{key}: missing or changed PUBG name/version/note/icon")
        filename = filename_safe(f"{item.name} - {item.version} [ @iKiraPlus ].ipa")
        size, _, range_supported = inspect_source(http, item.url, filename)
        if not range_supported:
            raise RuntimeError(f"{key}: source does not support HTTP Range; safe resume impossible")
        if (size + PART_SIZE - 1) // PART_SIZE > MAX_PARTS:
            raise RuntimeError(f"{key}: IPA exceeds Telegram Premium part limit")
        return Job(key=key, name=item.name, url=item.url, filename=filename,
                   size=size, note=item.description, icon=item.icon)


def download_job(job: Job, folder: Path) -> tuple[Path, Path]:
    with requests.Session() as http:
        thumb = write_thumb(http, job.icon, folder / f"{job.key}-thumb.jpg")
        file = folder / job.filename
        print(f"[{job.key}] Thumbnail ready; downloading {job.size:,} bytes", flush=True)
        download_resumable(http, job.url, file, job.size, require_range=True)
        if file.stat().st_size != job.size:
            raise RuntimeError(f"{job.key}: downloaded file size does not match expected size")
        return file, thumb


async def upload_job(client, job: Job, folder: Path) -> None:
    file, thumb = await asyncio.to_thread(download_job, job, folder)
    print(f"[{job.key}] Full IPA downloaded; starting MTProto part upload", flush=True)
    uploaded = await upload_big_parts(client, file, concurrency=2)
    print(f"[{job.key}] Parts uploaded; sending to Saved Messages", flush=True)
    chunks = caption_segments(job.note)
    message = await client.send_file(
        "me", uploaded, caption=chunks[0], thumb=str(thumb),
        force_document=True, parse_mode=None,
        attributes=[DocumentAttributeFilename(file_name=job.filename)],
    )
    if not message:
        raise RuntimeError(f"{job.key}: Telegram did not confirm the sent message")
    for rest in chunks[1:]:
        await client.send_message("me", rest, parse_mode=None, link_preview=False)
    print(f"[{job.key}] SUCCESS: {job.filename}; caption and thumbnail sent", flush=True)
    file.unlink(missing_ok=True)
    thumb.unlink(missing_ok=True)


async def main_async() -> None:
    selected = (os.getenv("PUBG_SELECTION") or "both").strip().lower()
    if selected not in ("both", "gl", "kr"):
        raise RuntimeError("Choose only both, gl, or kr")
    keys = ["gl", "kr"] if selected == "both" else [selected]
    api_id, api_hash, session = auth_values()
    client = TelegramClient(StringSession(session), api_id, api_hash,
                            connection_retries=10, request_retries=6,
                            auto_reconnect=True, timeout=30)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Personal Telegram session is not authorized")
        me = await client.get_me()
        if not me or getattr(me, "bot", False) or not getattr(me, "premium", False):
            raise RuntimeError("Active personal Telegram Premium account required")
        print("One Telegram Premium session verified for this runner", flush=True)
        if os.getenv("VERIFY_ONLY", "true").strip().lower() == "true":
            print("Verification complete; no IPA files downloaded", flush=True)
            return

        jobs = await asyncio.gather(*(asyncio.to_thread(prepare, key) for key in keys))
        print("Sources: " + ", ".join(f"{j.key}={j.size:,} bytes" for j in jobs), flush=True)
        with tempfile.TemporaryDirectory(prefix="pubg-parallel-") as temp:
            folder = Path(temp)
            free = shutil.disk_usage(temp).free
            required = sum(job.size for job in jobs) + 768 * 1024 * 1024
            if free < required:
                raise RuntimeError(
                    f"Insufficient disk for both games: {free:,} B available; "
                    f"{required:,} B required. Choose one game at a time."
                )
            results = await asyncio.gather(
                *(upload_job(client, job, folder) for job in jobs),
                return_exceptions=True,
            )
            failures = []
            for job, result in zip(jobs, results):
                if isinstance(result, BaseException):
                    # Never print requests exception objects containing signed URLs.
                    err = str(result) if isinstance(result, RuntimeError) else type(result).__name__
                    print(f"[{job.key}] FAILED ({type(result).__name__}): {err}", flush=True)
                    failures.append(job.key)
            if failures:
                raise RuntimeError("Incomplete game(s): " + ", ".join(failures) +
                                   ". Successful files may already be in Saved Messages.")
            print("ALL REQUESTED PUBG FILES DELIVERED", flush=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except Exception as error:
        print(f"ERROR: {str(error) if isinstance(error, RuntimeError) else type(error).__name__}", flush=True)
        raise SystemExit(1)
