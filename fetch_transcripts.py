#!/usr/bin/env python3
"""Fetch all CreditCardBS YouTube video transcripts using yt-dlp + cookies."""

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import http.cookiejar

import requests
import yt_dlp

CHANNEL_URL = "https://www.youtube.com/@CreditCardBS/videos"
BASE_DIR = Path(__file__).parent
KB_DIR = BASE_DIR / "knowledge_base"
TRANSCRIPTS_DIR = KB_DIR / "transcripts"
INDEX_PATH = KB_DIR / "index.json"
COMBINED_PATH = KB_DIR / "all_transcripts.txt"
ERRORS_PATH = KB_DIR / "errors.log"
COOKIES_PATH = BASE_DIR / "cookies.txt"

SLEEP_BETWEEN_REQUESTS = 10.0


def slugify(title: str, max_length: int = 80) -> str:
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    if len(text) > max_length:
        text = text[:max_length].rsplit("-", 1)[0]
    return text


def make_filename(upload_date: str, title: str) -> str:
    if upload_date and len(upload_date) == 8:
        date_str = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        date_str = "0000-00-00"
    return f"{date_str}_{slugify(title)}.txt"


def format_date(upload_date: str) -> str:
    if upload_date and len(upload_date) == 8:
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return "unknown"


def enumerate_channel_videos() -> list[dict]:
    """Use yt-dlp to get all video metadata from the channel."""
    print("Enumerating channel videos...", file=sys.stderr)
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
    }
    if COOKIES_PATH.exists():
        ydl_opts["cookiefile"] = str(COOKIES_PATH)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(CHANNEL_URL, download=False)
        entries = info.get("entries", [])

    videos = []
    for entry in entries:
        videos.append({
            "video_id": entry.get("id", ""),
            "title": entry.get("title", "Unknown"),
            "upload_date": entry.get("upload_date", ""),
        })

    print(f"Found {len(videos)} videos on channel.", file=sys.stderr)
    return videos


def fetch_transcript(video_id: str) -> tuple[str | None, str | None, str | None]:
    """Fetch transcript for a single video. Returns (text, upload_date, error)."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "format": "sb0",
        "quiet": True,
        "no_warnings": True,
    }
    if COOKIES_PATH.exists():
        ydl_opts["cookiefile"] = str(COOKIES_PATH)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        upload_date = info.get("upload_date", "")
        auto_captions = info.get("automatic_captions", {})
        en_captions = auto_captions.get("en", auto_captions.get("en-orig", []))

        if not en_captions:
            return None, upload_date, "No English captions available"

        # Get json3 format URL
        cap_url = None
        for cap in en_captions:
            if cap.get("ext") == "json3":
                cap_url = cap["url"]
                break

        if not cap_url:
            return None, upload_date, "No json3 caption format available"

        # Load cookies for the caption request
        session = requests.Session()
        if COOKIES_PATH.exists():
            cj = http.cookiejar.MozillaCookieJar(str(COOKIES_PATH))
            cj.load(ignore_discard=True, ignore_expires=True)
            session.cookies = cj

        # Download and parse captions with retry for rate limiting
        for attempt in range(3):
            resp = session.get(cap_url, timeout=30)
            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            return None, upload_date, "Rate limited after 3 retries"

        cap_data = resp.json()

        texts = []
        for event in cap_data.get("events", []):
            for seg in event.get("segs", []):
                t = seg.get("utf8", "").strip()
                if t and t != "\n":
                    texts.append(t)

        text = " ".join(texts)
        return text, upload_date, None

    except Exception as e:
        return None, None, str(e)


def write_transcript_file(filepath: Path, metadata: dict, text: str):
    date_str = format_date(metadata.get("upload_date", ""))
    header = (
        f"---\n"
        f"title: \"{metadata['title']}\"\n"
        f"video_id: \"{metadata['video_id']}\"\n"
        f"url: \"https://www.youtube.com/watch?v={metadata['video_id']}\"\n"
        f"upload_date: \"{date_str}\"\n"
        f"---\n\n"
    )
    filepath.write_text(header + text, encoding="utf-8")


def write_index(videos: list[dict]):
    has_transcript = sum(1 for v in videos if v.get("has_transcript"))
    failed = sum(1 for v in videos if not v.get("has_transcript"))
    index = {
        "channel": "CreditCardBS",
        "channel_url": "https://www.youtube.com/@CreditCardBS",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_videos": len(videos),
        "transcripts_fetched": has_transcript,
        "transcripts_failed": failed,
        "videos": sorted(videos, key=lambda v: v.get("upload_date", "")),
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def write_combined(videos: list[dict]):
    sorted_vids = sorted(
        [v for v in videos if v.get("has_transcript")],
        key=lambda v: v.get("upload_date", ""),
    )
    separator = "=" * 80

    with open(COMBINED_PATH, "w", encoding="utf-8") as f:
        for video in sorted_vids:
            filepath = TRANSCRIPTS_DIR / video["filename"]
            if not filepath.exists():
                continue
            content = filepath.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                text = parts[2].strip() if len(parts) >= 3 else content
            else:
                text = content

            date_str = format_date(video.get("upload_date", ""))
            f.write(f"{separator}\n")
            f.write(f"TITLE: {video['title']}\n")
            f.write(f"VIDEO_ID: {video['video_id']}\n")
            f.write(f"URL: https://www.youtube.com/watch?v={video['video_id']}\n")
            f.write(f"DATE: {date_str}\n")
            f.write(f"{separator}\n\n")
            f.write(text)
            f.write("\n\n")


def load_existing_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {}


def resolve_filename_collision(filename: str, existing: set[str]) -> str:
    if filename not in existing:
        return filename
    base, ext = os.path.splitext(filename)
    counter = 2
    while f"{base}-{counter}{ext}" in existing:
        counter += 1
    return f"{base}-{counter}{ext}"


def main():
    if not COOKIES_PATH.exists():
        print("WARNING: cookies.txt not found. YouTube may block requests from cloud IPs.", file=sys.stderr)
        print("Export cookies from your browser and save as cookies.txt in the project root.", file=sys.stderr)

    KB_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing state
    existing_index = load_existing_index()
    existing_videos = {v["video_id"]: v for v in existing_index.get("videos", [])}
    existing_filenames = {v["filename"] for v in existing_videos.values() if "filename" in v}

    # Enumerate channel
    channel_videos = enumerate_channel_videos()

    # Find new videos + retry failed ones (excluding members-only)
    failed_retryable = {
        vid: v for vid, v in existing_videos.items()
        if not v.get("has_transcript") and v.get("error") and "members" not in v.get("error", "")
    }
    new_videos = [v for v in channel_videos if v["video_id"] not in existing_videos]
    retry_videos = [v for v in channel_videos if v["video_id"] in failed_retryable]
    # Remove retryable failures from existing so they get re-processed
    for v in retry_videos:
        existing_videos.pop(v["video_id"], None)
    to_fetch = new_videos + retry_videos
    print(
        f"Total: {len(channel_videos)} videos, {len(new_videos)} new, "
        f"{len(retry_videos)} retrying failed, {len(existing_videos)} already done.",
        file=sys.stderr,
    )

    if not to_fetch:
        print("Nothing to fetch. Regenerating combined file...", file=sys.stderr)
        all_videos = list(existing_videos.values())
        write_index(all_videos)
        write_combined(all_videos)
        print("Done.", file=sys.stderr)
        return

    errors_log = open(ERRORS_PATH, "a", encoding="utf-8")
    fetched = 0
    failed = 0

    for i, video in enumerate(to_fetch, 1):
        title_short = video["title"][:60]
        print(f"[{i}/{len(to_fetch)}] {title_short}...", file=sys.stderr)

        text, upload_date, error = fetch_transcript(video["video_id"])

        # Update upload_date if we got a better one from the full info
        if upload_date:
            video["upload_date"] = upload_date

        filename = make_filename(video["upload_date"], video["title"])
        filename = resolve_filename_collision(filename, existing_filenames)
        existing_filenames.add(filename)
        video["filename"] = filename

        if text:
            write_transcript_file(TRANSCRIPTS_DIR / filename, video, text)
            video["has_transcript"] = True
            video["error"] = None
            fetched += 1
            print(f"  OK ({len(text)} chars)", file=sys.stderr)
        else:
            video["has_transcript"] = False
            video["error"] = error
            failed += 1
            timestamp = datetime.now(timezone.utc).isoformat()
            errors_log.write(f"[{timestamp}] {video['video_id']} - {video['title']}: {error}\n")
            print(f"  FAIL: {error[:80]}", file=sys.stderr)

        if i < len(to_fetch):
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    errors_log.close()

    # Merge with existing
    for video in to_fetch:
        existing_videos[video["video_id"]] = video
    all_videos = list(existing_videos.values())

    print("Writing index.json...", file=sys.stderr)
    write_index(all_videos)
    print("Writing all_transcripts.txt...", file=sys.stderr)
    write_combined(all_videos)

    print(
        f"\nDone! Fetched {fetched} new transcripts, {failed} failed. "
        f"Total: {len(all_videos)} videos in index.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
