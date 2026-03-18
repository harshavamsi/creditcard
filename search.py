#!/usr/bin/env python3
"""Search CreditCardBS transcripts by keyword."""

import argparse
import json
import re
import sys
from pathlib import Path

KB_DIR = Path(__file__).parent / "knowledge_base"
TRANSCRIPTS_DIR = KB_DIR / "transcripts"
INDEX_PATH = KB_DIR / "index.json"


def load_transcripts() -> list[dict]:
    """Load all transcript files with their metadata."""
    transcripts = []
    for filepath in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
        content = filepath.read_text(encoding="utf-8")
        metadata = {"filename": filepath.name}
        text = content

        # Parse YAML-like header
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if ": " in line:
                        key, val = line.split(": ", 1)
                        metadata[key.strip()] = val.strip().strip('"')
                text = parts[2].strip()

        transcripts.append({"metadata": metadata, "text": text})
    return transcripts


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def search(query: str, transcripts: list[dict], limit: int = 10) -> list[dict]:
    """Search transcripts for query terms. Returns ranked results."""
    terms = [t.lower() for t in query.split() if len(t) > 1]
    if not terms:
        return []

    results = []
    for transcript in transcripts:
        chunks = chunk_text(transcript["text"])
        for chunk in chunks:
            chunk_lower = chunk.lower()
            # All terms must appear
            if not all(term in chunk_lower for term in terms):
                continue
            # Score by total occurrences
            score = sum(chunk_lower.count(term) for term in terms)
            results.append({
                "score": score,
                "metadata": transcript["metadata"],
                "excerpt": chunk,
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def highlight(text: str, terms: list[str]) -> str:
    """Bold matching terms in text."""
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        text = pattern.sub(lambda m: f"\033[1;33m{m.group()}\033[0m", text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Search CreditCardBS transcripts")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Max results (default: 10)")
    args = parser.parse_args()

    if not TRANSCRIPTS_DIR.exists():
        print("No transcripts found. Run fetch_transcripts.py first.", file=sys.stderr)
        sys.exit(1)

    transcripts = load_transcripts()
    if not transcripts:
        print("No transcripts loaded.", file=sys.stderr)
        sys.exit(1)

    results = search(args.query, transcripts, args.limit)
    terms = [t.lower() for t in args.query.split() if len(t) > 1]

    if not results:
        print(f"No results for: {args.query}")
        return

    print(f"\n{len(results)} results for: \"{args.query}\"\n")
    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        title = meta.get("title", meta.get("filename", "Unknown"))
        date = meta.get("upload_date", "unknown")
        url = meta.get("url", "")
        excerpt = highlight(r["excerpt"], terms)

        print(f"--- Result {i} (score: {r['score']}) ---")
        print(f"Source: {title} ({date})")
        if url:
            print(f"URL: {url}")
        print()
        # Show a trimmed excerpt (first 300 chars)
        display = excerpt[:500] + "..." if len(excerpt) > 500 else excerpt
        print(display)
        print()


if __name__ == "__main__":
    main()
