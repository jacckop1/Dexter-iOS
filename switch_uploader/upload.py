#!/usr/bin/env python3
"""One-off Switch IPA uploader to PERSONAL Telegram Saved Messages.

The only caption is FIXED_CAPTION. Filenames use name/version plus @iKiraPlus.
Source links are read from games.json, not from Telegram messages or bots.
"""

import asyncio
import json
import os
import re
import shutil
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

from fast_download import fast_download
from resilient_transfer import PART_SIZE, MAX_PARTS, upload_big_parts

CAPTION = (
    "لعبة نينتندو سويتش حصرية.\n\n"
    "- تتطلب آيفون 16 فما فوق.\n"
    "- تتطلب إصدار ios26 فما فوق.\n"
    "- قد تحتوي تحميل داخلي."
)
USER_TAG = "@iKiraPlus"
MANIFEST = Path(__file__).with_name("games.json")
MAX_FILE_BYTES = PART_SIZE * MAX_PARTS

# Only the five pending games are eligible. Solateria was already delivered.
# Order matters: first_two is Ready or Nowhere + Air Strike.
BATCH_SLICES = {
    "first_two": slice(0, 2),
    "last_three": slice(2, 5),
}

def selected_games(games: list["Game"], batch: str) -> list["Game"]:
    if batch not in BATCH_SLICES:
        raise RuntimeError("Invalid game selection: choose a configured batch or single game")
    if len(games) != 5:
        raise RuntimeError("Expected exactly five pending games")
    selected = games[BATCH_SLICES[batch]]
    if len(selected) not in (2, 3):
        raise RuntimeError("Unexpected number of selected games")
    return selected


@dataclass(frozen=True)
class Game:
    name: str
    version: str
    url: str
    icon: str
    filename: str


def safe_filename(value: str) -> str:
    clean = re.sub(r'[\\/\x00-\x1f<>:"|?*]', "_", value).strip(" .")
    if not clean or len(clean.encode("utf-8")) > 220:
        raise ValueError("Game filename is missing or too long")
    return clean


def load_games(path: Path = MANIFEST) -> list[Game]:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise RuntimeError("Manifest file is too large")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    rows = manifest.get("games") if isinstance(manifest, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("No IPA links configured yet: populate switch_uploader/games.json")
    if len(rows) > 60:
        raise RuntimeError("Too many games in one manual workflow")

    found = []
    seen_names = set()
    for n, record in enumerate(rows, start=1):
        if not isinstance(record, dict):
            raise RuntimeError(f"Game {n}: invalid manifest item")
        name = str(record.get("name", "")).strip()
        version = str(record.get("version", "")).strip()
        url = str(record.get("url", "")).strip()
        icon = str(record.get("icon", "")).strip()
        if not name or not version:
            raise RuntimeError(f"Game {n}: name and version are required")
        for label, address in (("IPA", url), ("icon", icon)):
            if label == "icon" and not address:
                continue
            u = urlsplit(address)
            if u.scheme not in ("https", "http") or not u.hostname:
                raise RuntimeError(f"Game {n}: invalid {label} URL")
        filename = safe_filename(f"{name} - {version} [ {USER_TAG} ].ipa")
        if filename.casefold() in seen_names:
            raise RuntimeError(f"Game {n}: duplicate filename")
        seen_names.add(filename.casefold())
        found.append(Game(name, version, url, icon, filename))
    return found


def inspect_remote(http: requests.Session, url: str) -> int:
    # HTTP Range is mandatory: avoids restarting large downloads after timeouts.
    with http.get(url, headers={"Range": "bytes=0-0",
                                "Accept-Encoding": "identity",
                                "User-Agent": "Mozilla/5.0"},
                  timeout=(15, 35), stream=True) as response:
        if response.status_code != 206:
            raise RuntimeError(f"Source does not support HTTP Range (HTTP {response.status_code})")
        match = re.fullmatch(r"bytes\s+0-0/(\d+)", response.headers.get("content-range", ""), re.I)
        if not match:
            raise RuntimeError("Source supplied no valid total file size")
        size = int(match.group(1))
        if size <= 0 or size > MAX_FILE_BYTES:
            raise RuntimeError("File is empty or exceeds the Premium upload ceiling")
        if response.headers.get("content-type", "").lower().startswith("text/html"):
            raise RuntimeError("Source supplied HTML, not IPA data")
        return size


async def send_game_document(client, uploaded, filename: str):
    """Send only the IPA with a clean filename/caption; NO document thumbnail.

    Cover/icon metadata is kept in games.json, but is never fetched or sent.
    Passing an uploaded InputFileBig with no 'thumb' argument prevents a custom
    thumbnail from being attached to the Telegram document.
    """
    return await client.send_file(
        "me", uploaded,
        caption=CAPTION,
        force_document=True,
        parse_mode=None,
        attributes=[DocumentAttributeFilename(file_name=filename)],
    )


def required_env(key: str) -> str:
    s = os.getenv(key, "").strip()
    if not s:
        raise RuntimeError(f"Missing GitHub Actions Secret {key}")
    return s


async def send_games() -> None:
    api_id = int(required_env("TG_API_ID"))
    api_hash = required_env("TG_API_HASH")
    user_session = required_env("TG_STRING_SESSION")
    client = TelegramClient(
        StringSession(user_session), api_id, api_hash,
        connection_retries=10, request_retries=8, auto_reconnect=True, timeout=30
    )
    await client.connect()
    try:
        me = await client.get_me()
        if not me or not await client.is_user_authorized() or getattr(me, "bot", False) or not getattr(me, "premium", False):
            raise RuntimeError("Active PERSONAL Telegram Premium account required")
        print("Authorized personal Telegram Premium account", flush=True)

        batch = os.getenv("GAME_BATCH", "").strip()
        games = selected_games(load_games(), batch)
        print(f"Selected {batch}: {len(games)} game(s) -> Saved Messages", flush=True)
        failures = []
        for i, game in enumerate(games, 1):
            label = f"switch-{i}"
            print(f"[{label}] START: {game.filename}", flush=True)
            try:
                with requests.Session() as http:
                    expected = await asyncio.to_thread(inspect_remote, http, game.url)
                    print(f"[{label}] HTTP Range confirmed, {expected:,} bytes", flush=True)
                    with tempfile.TemporaryDirectory(prefix="switch-ipa-") as folder:
                        base = Path(folder)
                        available = shutil.disk_usage(base).free
                        if available < expected + 600 * 1024 * 1024:
                            raise RuntimeError("Insufficient free disk space for this IPA")
                        out = base / game.filename
                        await asyncio.to_thread(
                            fast_download,
                            game.url, out, expected,
                            label=label,
                            connections=8, block_size=8 * 1024 * 1024,
                            idle_seconds=30
                        )
                        if out.stat().st_size != expected:
                            raise RuntimeError("Size mismatch after download")
                        print(f"[{label}] Download complete; uploading in 512-KiB Telegram parts", flush=True)
                        uploaded = await upload_big_parts(client, out, concurrency=6, label=label)
                        msg = await send_game_document(client, uploaded, game.filename)
                        if not msg:
                            raise RuntimeError("Telegram did not acknowledge Saved Messages delivery")
                        print(f"[{label}] SUCCESS: IPA sent to Saved Messages without a thumbnail", flush=True)
            except Exception as error:
                # Avoid logging signed IPA/icon URLs, sessions, or source content.
                details = str(error) if isinstance(error, RuntimeError) else type(error).__name__
                if "http" in details.lower() or "://" in details:
                    details = type(error).__name__
                print(f"[{label}] FAILED: {details}", flush=True)
                failures.append(i)
                # Continue: other games can still be uploaded, and each file
                # is cleaned up before the next file begins.

        if failures:
            raise RuntimeError(f"Upload incomplete: game numbers {failures}; successful files were already delivered")
        print("COMPLETE: all selected IPA files sent to Saved Messages", flush=True)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(send_games())
    except Exception as error:
        # Only print an exception class, never a signed source link or session.
        print("ERROR: " + type(error).__name__, flush=True)
        raise SystemExit(1)
