# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a content/data repository containing transcripts from credit card and travel-related podcast episodes and videos. The primary purpose is to store, organize, and synthesize information about credit card strategies, travel rewards, and loyalty programs.

## Repository Structure

- `knowledge_base/` - Primary transcript store (AI-optimized, with metadata)
  - `transcripts/` - Individual transcript files with YAML metadata headers (`YYYY-MM-DD_title.txt`)
  - `index.json` - Master catalog of all episodes with metadata
  - `all_transcripts.txt` - Combined file with delimiters for bulk AI ingestion
- `transcripts/` - Legacy: 154 raw transcripts (no metadata)
- `summaries/` - Synthesized markdown guides compiled from multiple transcripts
- `fetch_transcripts.py` - Downloads audio from RSS feed and transcribes with Whisper (incremental)
- `search.py` - Keyword search across all transcripts
- `extract_transcripts.py` - Legacy script to split combined transcripts

## Common Tasks

### Fetch/update all transcripts
```bash
python fetch_transcripts.py
```
Incremental: re-run to fetch only new episodes. Uses Buzzsprout RSS + Whisper (tiny model).

### Search transcripts
```bash
python search.py "Hyatt hotels"
python search.py --limit 5 "chase sapphire bonus"
```

### AI analysis
Point Claude at `knowledge_base/all_transcripts.txt` or individual files in `knowledge_base/transcripts/` for deep analysis queries.

## Content Topics Covered

The transcripts cover: credit card product reviews, sign-up bonuses, earning strategies, airline/hotel loyalty programs (Hyatt, Marriott, United, American, Delta), transfer partners, lounge access, and travel hacks.

## Creating Summaries

When creating new summary guides in `summaries/`:
- Synthesize information from multiple relevant transcripts
- Use markdown formatting with clear sections
- Include specific details like annual fees, earning rates, and transfer ratios
- Note when information may become outdated (credit card benefits change frequently)
