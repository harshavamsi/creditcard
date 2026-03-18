#!/usr/bin/env python3
"""Weekly cron job to fetch new CreditCardBS transcripts.

Checks for new videos on the channel, fetches their transcripts,
and updates the index + combined file. Designed to run unattended
from crontab for 1-2 new videos per week.

Usage: python3 update_transcripts.py
"""

import json
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

BASE_DIR = Path(__file__).parent
KB_DIR = BASE_DIR / "knowledge_base"
TRANSCRIPTS_DIR = KB_DIR / "transcripts"
INDEX_PATH = KB_DIR / "index.json"
COMBINED_PATH = KB_DIR / "all_transcripts.txt"
LOG_PATH = KB_DIR / "update.log"
CHANNEL_URL = "https://www.youtube.com/@CreditCardBS/videos"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def slugify(title: str, max_length: int = 80) -> str:
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
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
    ydl_opts = {"extract_flat": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(CHANNEL_URL, download=False)
    return [
        {
            "video_id": e.get("id", ""),
            "title": e.get("title", "Unknown"),
            "upload_date": e.get("upload_date", ""),
        }
        for e in info.get("entries", [])
    ]


def fetch_transcript(video_id: str) -> tuple[str | None, str | None, str | None]:
    """Fetch transcript using yt-dlp's native subtitle download."""
    import tempfile

    tmpdir = tempfile.mkdtemp()
    ydl_opts = {
        "skip_download": True,
        "format": "sb0",
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "subtitlesformat": "json3",
        "outtmpl": os.path.join(tmpdir, "%(id)s"),
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
            upload_date = info.get("upload_date", "")
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        # Find the subtitle file
        sub_file = None
        for f in os.listdir(tmpdir):
            if f.endswith(".json3"):
                sub_file = os.path.join(tmpdir, f)
                break

        if not sub_file:
            # Fallback: try extracting caption URL from info
            auto_captions = info.get("automatic_captions", {})
            en_captions = auto_captions.get("en", auto_captions.get("en-orig", []))
            if not en_captions:
                return None, upload_date, "No English captions available"

            cap_url = next(
                (c["url"] for c in en_captions if c.get("ext") == "json3"), None
            )
            if not cap_url:
                return None, upload_date, "No json3 caption format"

            import requests

            resp = requests.get(cap_url, timeout=30)
            if resp.status_code == 429:
                return None, upload_date, "Rate limited"
            resp.raise_for_status()
            cap_data = resp.json()
        else:
            with open(sub_file) as fh:
                cap_data = json.load(fh)

        texts = []
        for event in cap_data.get("events", []):
            for seg in event.get("segs", []):
                t = seg.get("utf8", "").strip()
                if t and t != "\n":
                    texts.append(t)

        return " ".join(texts), upload_date, None

    except Exception as e:
        return None, None, str(e)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


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
    INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


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


def main():
    log.info("Starting transcript update check")

    existing_index = {}
    if INDEX_PATH.exists():
        existing_index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    existing_videos = {v["video_id"]: v for v in existing_index.get("videos", [])}
    existing_filenames = {
        v["filename"] for v in existing_videos.values() if "filename" in v
    }

    try:
        channel_videos = enumerate_channel_videos()
    except Exception as e:
        log.error(f"Failed to enumerate channel: {e}")
        sys.exit(1)

    new_videos = [v for v in channel_videos if v["video_id"] not in existing_videos]

    if not new_videos:
        log.info(f"No new videos (channel has {len(channel_videos)})")
        return

    log.info(f"Found {len(new_videos)} new video(s)")

    fetched = 0
    for video in new_videos:
        log.info(f"Fetching: {video['title'][:60]}")

        text, upload_date, error = fetch_transcript(video["video_id"])
        if upload_date:
            video["upload_date"] = upload_date

        filename = make_filename(video["upload_date"], video["title"])
        if filename in existing_filenames:
            base, ext = os.path.splitext(filename)
            counter = 2
            while f"{base}-{counter}{ext}" in existing_filenames:
                counter += 1
            filename = f"{base}-{counter}{ext}"
        existing_filenames.add(filename)
        video["filename"] = filename

        if text:
            write_transcript_file(TRANSCRIPTS_DIR / filename, video, text)
            video["has_transcript"] = True
            video["error"] = None
            fetched += 1
            log.info(f"  OK ({len(text)} chars)")
        else:
            video["has_transcript"] = False
            video["error"] = error
            log.warning(f"  FAIL: {error}")

        existing_videos[video["video_id"]] = video

    all_videos = list(existing_videos.values())
    write_index(all_videos)
    write_combined(all_videos)
    log.info(f"Done. Fetched {fetched}/{len(new_videos)} new transcripts. Total: {len(all_videos)}")


if __name__ == "__main__":
    main()
