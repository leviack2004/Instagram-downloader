from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SUPPORTED_PATH_PREFIXES = ("p", "reel", "tv")


class InstagramAdapterError(Exception):
    def __init__(self, code: str, message: str, next_step: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.next_step = next_step


@dataclass
class MediaItem:
    media_type: Literal["image", "video"]
    url: str
    thumbnail_url: str
    index: int

    def to_dict(self, shortcode: str):
        extension = "mp4" if self.media_type == "video" else "jpg"
        return {
            "media_type": self.media_type,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "index": self.index,
            "filename": f"instagram_{shortcode}_{self.index}.{extension}",
        }


@dataclass
class MediaResult:
    normalized_url: str
    shortcode: str
    content_type: Literal["image", "video", "carousel"]
    items: list[MediaItem]

    def to_dict(self):
        return {
            "normalized_url": self.normalized_url,
            "shortcode": self.shortcode,
            "content_type": self.content_type,
            "items": [item.to_dict(self.shortcode) for item in self.items],
        }


def normalize_instagram_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not re.match(r"^https?://", candidate, re.IGNORECASE):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        raise InstagramAdapterError("invalid_url", "URL must start with http or https.", "Use a full Instagram URL.")

    host = parsed.netloc.lower()
    if host.startswith("m."):
        host = host[2:]
    if host not in ("instagram.com", "www.instagram.com"):
        raise InstagramAdapterError(
            "invalid_url",
            "This does not look like an Instagram URL.",
            "Paste a public post, reel, or tv link from instagram.com.",
        )

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise InstagramAdapterError("invalid_url", "Could not find a valid Instagram post path.", "Use links like /p/{id}/.")

    if path_parts[0] not in SUPPORTED_PATH_PREFIXES:
        raise InstagramAdapterError("unsupported_content", "That Instagram content type is not supported yet.", "Try a post, reel, or tv URL.")

    shortcode = path_parts[1]
    query = parse_qs(parsed.query)
    filtered = [f"{k}={v[0]}" for k, v in sorted(query.items()) if not k.startswith("utm_")]
    suffix = f"?{'&'.join(filtered)}" if filtered else ""
    return f"https://www.instagram.com/{path_parts[0]}/{shortcode}/{suffix}"


def _extract_media_urls(html: str) -> list[MediaItem]:
    videos = list(dict.fromkeys(re.findall(r'"video_url":"(https:[^\"]+)"', html)))
    images = list(dict.fromkeys(re.findall(r'"display_url":"(https:[^\"]+)"', html)))

    items: list[MediaItem] = []
    idx = 1
    for url in videos:
        decoded = bytes(url, "utf-8").decode("unicode_escape")
        thumb = bytes(images[0], "utf-8").decode("unicode_escape") if images else decoded
        items.append(MediaItem("video", decoded, thumb, idx))
        idx += 1
    for url in images:
        decoded = bytes(url, "utf-8").decode("unicode_escape")
        if any(i.url == decoded for i in items):
            continue
        items.append(MediaItem("image", decoded, decoded, idx))
        idx += 1
    return items


def resolve_instagram_media(normalized_url: str) -> MediaResult:
    path_parts = [part for part in urlparse(normalized_url).path.split("/") if part]
    shortcode = path_parts[1]

    request = Request(normalized_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=8) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        if exc.code == 429:
            raise InstagramAdapterError("upstream_rate_limited", "Instagram rate limited this request.", "Wait briefly and try again.") from exc
        if exc.code in (401, 403, 404):
            raise InstagramAdapterError("private_or_unavailable", "This post is private or unavailable.", "Verify the post is public and the URL is correct.") from exc
        raise InstagramAdapterError("upstream_failure", "Instagram returned an error.", "Please retry shortly.") from exc
    except URLError as exc:
        raise InstagramAdapterError("upstream_failure", "Instagram is temporarily unreachable.", "Please try again in a few moments.") from exc

    items = _extract_media_urls(html)
    if not items:
        raise InstagramAdapterError("unsupported_content", "Couldn't extract downloadable media from this link.", "Try another public post or reel URL.")

    content_type: Literal["image", "video", "carousel"] = "carousel" if len(items) > 1 else items[0].media_type
    return MediaResult(normalized_url, shortcode, content_type, items)
