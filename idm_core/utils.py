"""
Shared utility functions for URL normalization, header processing, and media detection.
"""

import os
import urllib.parse
from typing import Any, Dict, Optional, Tuple


def is_youtube_url(url: str) -> bool:
    """Check if the given URL belongs to YouTube."""
    if not url:
        return False
    lower = url.lower()
    return "youtube.com" in lower or "youtu.be" in lower


def infer_youtube_filename(url: str, default: str = "video.mp4") -> str:
    """
    Infer a clean video filename (.mp4) from a YouTube URL
    (watch, shorts, embed, live, or youtu.be).
    """
    if not url:
        return default

    parsed = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed.query)
    video_id = query_params.get("v", [""])[0]

    if not video_id:
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            last = path_parts[-1]
            if last not in ["watch", "shorts", "live", "embed"]:
                video_id = last

    if video_id:
        base = os.path.splitext(video_id)[0]
        return f"{base}.mp4"

    return default


def normalize_youtube_videoplayback_url(
    url: str, headers: Optional[Dict[str, Any]] = None
) -> Tuple[str, Optional[str]]:
    """
    Detects if a URL is a raw Google Video / YouTube DASH chunk (videoplayback)
    with an authentic YouTube video referer, and normalizes it to the full YouTube URL
    and inferred video filename.

    Returns:
        (normalized_url, inferred_filename_or_None)
    """
    headers = headers or {}
    referer = ""
    for k, v in headers.items():
        if k.lower() in ["referer", "page_url"] and v:
            referer = str(v)
            break

    if not referer:
        return url, None

    is_yt_video_referer = is_youtube_url(referer) and any(
        x in referer for x in ["/watch", "/shorts", "/live", "/embed", "youtu.be"]
    )

    if ("videoplayback" in url or "googlevideo.com" in url) and is_yt_video_referer:
        filename = infer_youtube_filename(referer)
        return referer, filename

    return url, None
