"""Read a one-app or catalog JSON and prepare Telegram IPA artwork.

Never print remote JSON, signed download URLs, or login secrets in workflow logs.
"""
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024

URL_KEYS = ("ipaUrl", "ipaURL", "ipa_url", "downloadURL", "downloadUrl",
            "download_url", "downloadLink", "fileUrl", "file_url", "url")
ICON_KEYS = ("iconURL", "iconUrl", "icon_url", "icon", "artworkURL",
             "artworkUrl", "imageURL", "imageUrl", "image", "logo")
DESCRIPTION_KEYS = ("note", "description", "localizedDescription", "appDescription",
                    "longDescription", "notes", "subtitle")
NAME_KEYS = ("name", "title", "appName")
FILE_NAME_KEYS = ("fileName", "filename", "file_name")
ID_KEYS = ("id", "bundleIdentifier", "bundleID", "appId", "appID")


@dataclass(frozen=True)
class IpaMetadata:
    url: str
    description: str = ""
    icon_url: str = ""
    file_name: str = ""
    name: str = ""
    version: str = ""


def _str(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("url", "src", "href"):
            if isinstance(value.get(key), str):
                return value[key].strip()
    return ""


def _first(data: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _str(data.get(key))
        if value:
            return value
    return ""


def _objects(source) -> list[dict]:
    if isinstance(source, list):
        return [item for item in source if isinstance(item, dict)]
    if isinstance(source, dict):
        for field in ("apps", "applications", "games", "items", "data"):
            if field in source and isinstance(source[field], (list, dict)):
                candidates = _objects(source[field])
                if candidates:
                    return candidates
        if _first(source, URL_KEYS) or isinstance(source.get("versions"), list):
            return [source]
        objects = [value for value in source.values() if isinstance(value, dict)]
        if objects and all(_first(item, URL_KEYS) or isinstance(item.get("versions"), list) for item in objects):
            return objects
    return []


def _release(record: dict) -> dict:
    direct = _first(record, URL_KEYS)
    if direct:
        return record
    versions = record.get("versions")
    if isinstance(versions, list):
        preferred = _str(record.get("version"))
        entries = [item for item in versions if isinstance(item, dict) and _first(item, URL_KEYS)]
        if preferred:
            for item in entries:
                if _str(item.get("version")) == preferred:
                    return item
        if entries:
            return entries[0]
    return {}


def extract_item(payload, selector: str = "") -> IpaMetadata:
    items = _objects(payload)
    if not items:
        raise RuntimeError("JSON contains no recognizable IPA app record")
    if selector:
        normalized = selector.strip().casefold()
        matches = [item for item in items if any(_str(item.get(key)).casefold() == normalized
                   for key in (*ID_KEYS, *NAME_KEYS))]
        if len(matches) != 1 and selector.isdecimal():
            index = int(selector) - 1
            matches = [items[index]] if 0 <= index < len(items) else []
        if len(matches) != 1:
            raise RuntimeError("App selector did not uniquely identify an app in the JSON")
        item = matches[0]
    elif len(items) == 1:
        item = items[0]
    else:
        raise RuntimeError(f"JSON has {len(items)} apps. Supply app_selector (name, ID or 1-based index)")

    release = _release(item)
    url = _first(release, URL_KEYS) or _first(item, URL_KEYS)
    if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
        raise RuntimeError("Selected JSON app has no valid direct HTTP/HTTPS IPA URL")
    name = _first(item, NAME_KEYS) or _first(release, NAME_KEYS)
    version = _str(release.get("version")) or _str(item.get("version"))
    description = _first(item, DESCRIPTION_KEYS) or _first(release, DESCRIPTION_KEYS)
    icon_url = _first(item, ICON_KEYS) or _first(release, ICON_KEYS)
    if icon_url and (urlsplit(icon_url).scheme not in ("http", "https") or not urlsplit(icon_url).hostname):
        raise RuntimeError("JSON icon URL is not HTTP/HTTPS")

    filename = _first(item, FILE_NAME_KEYS) or _first(release, FILE_NAME_KEYS)
    if not filename and name:
        clean_name = re.sub(r'[\\/\x00-\x1f<>:"|?*]', "_", name).strip(" .")
        clean_version = re.sub(r'[\\/\x00-\x1f<>:"|?*]', "_", version).strip(" .")
        if clean_name:
            filename = (clean_name + (f" - v{clean_version.lstrip('vV')}" if clean_version else "") + ".ipa")
    return IpaMetadata(url=url, description=description, icon_url=icon_url,
                       file_name=filename, name=name, version=version)


def _read_bounded(response, max_bytes: int) -> bytes:
    response.raise_for_status()
    data = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise RuntimeError("Remote JSON or icon exceeds the allowed size")
    return bytes(data)


def load_json(http, source: str, selector: str = "") -> IpaMetadata:
    parsed = urlsplit(source)
    if parsed.scheme in ("http", "https"):
        with http.get(source, stream=True, timeout=(20, 60)) as response:
            raw = _read_bounded(response, MAX_JSON_BYTES)
    else:
        if parsed.scheme or source.startswith("/"):
            raise RuntimeError("JSON source must be an HTTPS URL or a relative repository path")
        path = (Path.cwd() / source).resolve()
        if not path.is_relative_to(Path.cwd().resolve()) or path.suffix.lower() != ".json":
            raise RuntimeError("JSON path must be a .json file inside this repository")
        if path.stat().st_size > MAX_JSON_BYTES:
            raise RuntimeError("JSON file exceeds 4 MiB")
        raw = path.read_bytes()
    try:
        parsed_json = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError):
        raise RuntimeError("Invalid UTF-8 JSON input") from None
    return extract_item(parsed_json, selector)


def write_thumb(http, icon_url: str, target: Path) -> Path:
    """Prepare a tiny JPEG thumbnail suitable for Telegram document thumbnails."""
    with http.get(icon_url, stream=True, timeout=(20, 60)) as response:
        content = _read_bounded(response, MAX_IMAGE_BYTES)
    try:
        with Image.open(io.BytesIO(content)) as incoming:
            incoming.load()
            incoming.thumbnail((320, 320))
            rgba = incoming.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, (0, 0), rgba.getchannel("A"))
            image = ImageOps.pad(background, (320, 320), color=(255, 255, 255))
    except (UnidentifiedImageError, OSError, ValueError):
        raise RuntimeError("Could not decode the icon image into a JPEG thumbnail") from None

    for dim in (320, 256, 192, 160):
        resized = image if dim == 320 else image.resize((dim, dim))
        for quality in (80, 65, 50, 35):
            buf = io.BytesIO()
            resized.save(buf, "JPEG", quality=quality, optimize=True)
            if buf.tell() < 19 * 1024:
                target.write_bytes(buf.getvalue())
                print(f"Icon thumbnail ready: {dim}x{dim} JPEG", flush=True)
                return target
    raise RuntimeError("Could not compress the icon to a Telegram thumbnail")


def caption_segments(description: str) -> list[str]:
    """Split preserving all characters, under Telegram's UTF-16 caption/text limits."""
    if not description:
        return [""]
    result = []
    current = ""
    units = 0
    limit = 1024
    for char in description:
        char_units = 2 if ord(char) > 0xFFFF else 1
        if units + char_units > limit and current:
            result.append(current)
            current = ""
            units = 0
            limit = 4096
        current += char
        units += char_units
    if current:
        result.append(current)
    return result
