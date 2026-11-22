#!/usr/bin/env python3
"""Temporary, manually-triggered large IPA uploader. No files are committed."""

import asyncio
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename
from metadata import load_json, write_thumb, caption_segments
from resilient_transfer import download_resumable, upload_big_parts

PART_SIZE = 512 * 1024
PREMIUM_MAX_PARTS = 8000
MAX_BYTES = PART_SIZE * PREMIUM_MAX_PARTS
CHUNK_SIZE = 4 * 1024 * 1024
ATTEMPTS = 5
TIMEOUT = (25, 120)


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing GitHub Actions secret: {name}")
    return value


def filename_safe(value: str) -> str:
    name = re.sub(r'[\\/\x00-\x1f<>:"|?*]', "_", value).strip(" .")
    if len(name) > 180:
        name = name[:176].rstrip(" .") + ".ipa"
    if not name or not name.lower().endswith(".ipa"):
        raise RuntimeError("File name must end with .ipa; supply file_name in Run workflow")
    return name


def server_filename(response: requests.Response, url: str) -> str:
    header = response.headers.get("content-disposition", "")
    match = re.search(r"filename\*=UTF-8''([^;]+)", header, re.I)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    match = re.search(r'filename="?([^";]+)', header, re.I)
    if match:
        return match.group(1)
    return unquote(Path(urlsplit(response.url or url).path).name)


def inspect_source(session: requests.Session, url: str, override: str) -> tuple[int, str, bool]:
    if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
        raise RuntimeError("A direct HTTP/HTTPS download URL is required")
    headers = {"Range": "bytes=0-0", "Accept-Encoding": "identity", "User-Agent": "Mozilla/5.0"}
    with session.get(url, headers=headers, stream=True, timeout=TIMEOUT) as response:
        if response.status_code not in (200, 206):
            raise RuntimeError(f"Source refused the download: HTTP {response.status_code}")
        ranged = response.status_code == 206
        if ranged:
            m = re.fullmatch(r"bytes\s+0-0/(\d+)", response.headers.get("content-range", ""), re.I)
            if not m:
                raise RuntimeError("Invalid HTTP Content-Range from source")
            size = int(m.group(1))
        else:
            raw = response.headers.get("content-length", "")
            size = int(raw) if raw.isdecimal() else 0
        if size <= 0:
            raise RuntimeError("Source did not provide a valid Content-Length / Content-Range")
        if size > MAX_BYTES:
            raise RuntimeError(f"File exceeds Premium part ceiling ({MAX_BYTES} bytes)")
        file_name = filename_safe(override or server_filename(response, url))
        if response.headers.get("content-type", "").lower().startswith("text/html"):
            raise RuntimeError("Source returned HTML, not an IPA download")
    return size, file_name, ranged


def download_source(session: requests.Session, url: str, target: Path,
                    expected: int, ranged: bool) -> None:
    if not ranged:
        raise RuntimeError("Source does not support Range; refusing unsafe restart from zero")
    download_resumable(session, url, target, expected)



def auth_values() -> tuple[int, str, str]:
    try:
        api_id = int(env_required("TG_API_ID"))
    except ValueError as exc:
        raise RuntimeError("TG_API_ID must be a number") from exc
    return api_id, env_required("TG_API_HASH"), env_required("TG_STRING_SESSION")


async def check_premium(api_id: int, api_hash: str, session: str) -> None:
    client = TelegramClient(StringSession(session), api_id, api_hash, connection_retries=5)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("The StringSession is not authorized; generate a fresh local session")
        me = await client.get_me()
        if not me or getattr(me, "bot", False):
            raise RuntimeError("This must be a PERSONAL Telegram account, not a bot session")
        if not getattr(me, "premium", False):
            raise RuntimeError("The connected Telegram account does not report an active Premium subscription")
        print("Telegram login verified: personal Premium account (identity hidden)", flush=True)
    finally:
        await client.disconnect()


async def upload_to_telegram(api_id: int, api_hash: str, session: str,
                             target: Path, destination: str,
                             description: str = "", thumb_path: Path | None = None) -> None:
    client = TelegramClient(StringSession(session), api_id, api_hash,
                            connection_retries=5, request_retries=5, timeout=30)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session expired")
        progress = -1

        def on_progress(current: int, total: int) -> None:
            nonlocal progress
            mark = min(100, (current * 100 // total) // 5 * 5) if total else 0
            if mark > progress:
                progress = mark
                print(f"Telegram upload: {mark}%", flush=True)

        print("Starting MTProto upload with 512 KiB parts", flush=True)
        if target.stat().st_size > 10 * 1024 * 1024:
            uploaded = await upload_big_parts(client, target, concurrency=3)
        else:
            uploaded = await client.upload_file(
                str(target), part_size_kb=512, file_name=target.name,
                progress_callback=on_progress,
            )
        print("All parts uploaded; publishing the document...", flush=True)
        segments = caption_segments(description)
        sent = await client.send_file(
            destination,
            uploaded,
            caption=segments[0],
            thumb=str(thumb_path) if thumb_path else None,
            force_document=True,
            parse_mode=None,
            attributes=[DocumentAttributeFilename(file_name=target.name)],
        )
        if not sent:
            raise RuntimeError("Telegram returned no sent message")
        for rest in segments[1:]:
            await client.send_message(destination, rest, parse_mode=None, link_preview=False)
        print(f"Description: {len(description)} characters; icon: {'yes' if thumb_path else 'none'}", flush=True)
        print("SUCCESS: IPA delivered by personal Premium account", flush=True)
    finally:
        await client.disconnect()


def main() -> None:
    api_id, api_hash, session = auth_values()
    asyncio.run(check_premium(api_id, api_hash, session))
    if os.getenv("VERIFY_ONLY", "").lower() == "true":
        print("Verification complete; no file downloaded", flush=True)
        return

    pubg_target = os.getenv("PUBG_TARGET", "").strip().lower()
    allowed_pubg = {
        "gl": ("APP-5874636765", "Pubg GL Hack"),
        "kr": ("APP-1167550679", "Pubg KR Hack"),
    }
    if pubg_target and pubg_target not in allowed_pubg:
        raise RuntimeError("Only PUBG GL Hack or PUBG KR Hack is permitted in this workflow")

    direct_url = (os.getenv("SOURCE_URL_INPUT") or os.getenv("SOURCE_URL_SECRET") or "").strip()
    metadata_source = (os.getenv("METADATA_SOURCE_INPUT") or
                       os.getenv("METADATA_SOURCE_SECRET") or "").strip()
    destination = os.getenv("DESTINATION", "me").strip()
    if destination not in ("me", "@ikiraplus1"):
        raise RuntimeError("Unsupported destination")
    if pubg_target:
        if direct_url or metadata_source or os.getenv("FILE_NAME", "").strip():
            raise RuntimeError("PUBG workflow accepts no external source or file-name override")
        if destination != "me":
            raise RuntimeError("PUBG workflow sends to Saved Messages only")
        metadata_source = "premium_telegram/pubg_targets.json"
    elif direct_url and metadata_source:
        raise RuntimeError("Choose either a direct IPA URL or JSON metadata source, not both")

    with requests.Session() as http:
        description = ""
        icon_url = ""
        requested_name = os.getenv("FILE_NAME", "").strip()
        if metadata_source:
            record = load_json(http, metadata_source,
                               allowed_pubg[pubg_target][0] if pubg_target
                               else os.getenv("APP_SELECTOR", "").strip())
            if pubg_target:
                expected_id, expected_name = allowed_pubg[pubg_target]
                if record.name != expected_name or not record.version:
                    raise RuntimeError("PUBG JSON entry does not match the allowed game or lacks version")
                if not record.description or not record.icon_url:
                    raise RuntimeError("PUBG JSON entry requires note and icon")
                requested_name = filename_safe(
                    f"{record.name} - {record.version} [ @iKiraPlus ].ipa"
                )
            url = record.url
            description = record.description
            icon_url = record.icon_url
            requested_name = requested_name or record.file_name
            print("Selected one IPA entry from JSON metadata", flush=True)
        else:
            url = direct_url
        if not url:
            raise RuntimeError("Provide a direct IPA URL or JSON metadata source")
        size, name, ranged = inspect_source(http, url, requested_name)
        parts = (size + PART_SIZE - 1) // PART_SIZE
        if pubg_target and not ranged:
            raise RuntimeError("PUBG IPA link does not support Range: cannot guarantee byte-resume")
        if parts > PREMIUM_MAX_PARTS:
            raise RuntimeError("Too many Telegram parts for Premium")
        print(f"Source verified: {name}; {size:,} bytes; {parts:,} parts; Range={ranged}", flush=True)
        with tempfile.TemporaryDirectory(prefix="premium-ipa-") as temp_dir:
            free = shutil.disk_usage(temp_dir).free
            if free < size + 512 * 1024 * 1024:
                raise RuntimeError("Insufficient free disk space on GitHub runner")
            thumb = write_thumb(http, icon_url, Path(temp_dir) / "app-thumb.jpg") if icon_url else None
            file = Path(temp_dir) / name
            download_source(http, url, file, size, ranged)
            print("Download finished; preparing Telegram transfer", flush=True)
            asyncio.run(upload_to_telegram(api_id, api_hash, session, file, destination,
                                           description=description, thumb_path=thumb))
    print("Temporary download removed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never show signed URLs or a StringSession in public workflow logs.
        print(f"ERROR: {str(error) if isinstance(error, RuntimeError) else type(error).__name__}", flush=True)
        raise SystemExit(1)
