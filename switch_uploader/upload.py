#!/usr/bin/env python3
"""One-off Switch IPA uploader to PERSONAL Telegram Saved Messages.

The only caption is FIXED_CAPTION. Filenames use name/version plus @iKiraPlus.
Source links are read from games.json, not from Telegram messages or bots.
"""

import asyncio
import io
import json
import os
import re
import shutil
import tempfile
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
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
ICON_MAX_BYTES = 5 * 1024 * 1024

# Solateria has already been delivered and was removed from games.json.
# Never include completed Solateria in any available selection.
BATCH_SLICES = {
    "remaining_four": slice(0, 4),
    "last_three": slice(1, 4),
    "ready_or_nowhere": slice(0, 1),
    "mario_vs_donkey_kong": slice(1, 2),
    "cult_of_the_lamb": slice(2, 3),
    "super_mario_3d_world": slice(3, 4),
}


def selected_games(games: list["Game"], batch: str) -> list["Game"]:
    if batch not in BATCH_SLICES:
        raise RuntimeError("Invalid game selection: choose a configured batch or single game")
    if len(games) != 4:
        raise RuntimeError("Expected exactly four remaining games")
    selected = games[BATCH_SLICES[batch]]
    if len(selected) not in (1, 3, 4):
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


def thumbnail(http: requests.Session, url: str, path: Path) -> Path | None:
    if not url:
        return None
    with http.get(url, stream=True, timeout=(15, 35)) as response:
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            raw.extend(chunk)
            if len(raw) > ICON_MAX_BYTES:
                raise RuntimeError("Icon image exceeds 5 MiB")
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            im.thumbnail((320, 320))
            rgba = im.convert("RGBA")
            canvas = Image.new("RGB", rgba.size, "white")
            canvas.paste(rgba, (0, 0), rgba.getchannel("A"))
            canvas = ImageOps.pad(canvas, (320, 320), color="white")
    except (UnidentifiedImageError, ValueError, OSError):
        raise RuntimeError("Invalid icon image") from None
    for size in (320, 256, 192, 160):
        image = canvas if size == 320 else canvas.resize((size, size))
        for quality in (80, 60, 40):
            buf = io.BytesIO()
            image.save(buf, format="JPEG", optimize=True, quality=quality)
            if buf.tell() < 19 * 1024:
                path.write_bytes(buf.getvalue())
                return path
    raise RuntimeError("Icon could not be compressed for Telegram")


def thumbnail_safely(http: requests.Session, url: str, path: Path,
                     label: str) -> Path | None:
    """Optional icon failure cannot prevent delivery of a multi-GB IPA.

    Retry transient HTTP limits; keep original icon URL in the manifest.
    Never print signed URLs or other request details.
    """
    for attempt in range(1, 4):
        try:
            return thumbnail(http, url, path)
        except (requests.RequestException, RuntimeError, OSError, ValueError) as error:
            code = getattr(getattr(error, "response", None), "status_code", None)
            retryable = (code in (429, 500, 502, 503, 504)
                         or isinstance(error, (requests.Timeout, requests.ConnectionError)))
            if retryable and attempt < 3:
                print(f"[{label}] Thumbnail temporarily unavailable "
                      f"(HTTP {code or 'network'}); retry {attempt}/2", flush=True)
                time.sleep(2 ** attempt)
                continue
            print(f"[{label}] WARNING: thumbnail unavailable "
                  f"(HTTP {code or type(error).__name__}); continuing without thumbnail",
                  flush=True)
            return None
    return None


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
                        thumb = (await asyncio.to_thread(
                            thumbnail_safely, http, game.icon, base / "icon.jpg", label
                        )) if game.icon else None
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
                        msg = await client.send_file(
                            "me", uploaded,
                            caption=CAPTION, thumb=str(thumb) if thumb else None,
                            force_document=True, parse_mode=None,
                            attributes=[DocumentAttributeFilename(file_name=game.filename)]
                        )
                        if not msg:
                            raise RuntimeError("Telegram did not acknowledge Saved Messages delivery")
                        print(f"[{label}] SUCCESS: sent to Saved Messages with fixed caption", flush=True)
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
