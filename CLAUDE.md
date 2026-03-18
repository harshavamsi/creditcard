# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a content/data repository containing transcripts from credit card and travel-related podcast episodes and videos. The primary purpose is to store, organize, and synthesize information about credit card strategies, travel rewards, and loyalty programs.

## Repository Structure

- `transcripts/` - 154 text files containing raw transcripts (named by topic, e.g., `amex_platinum_refresh_is_now_live.txt`)
- `summaries/` - Synthesized markdown guides compiled from multiple transcripts
- `all_transcripts_combined.txt` - Single file with all transcripts concatenated
- `extract_transcripts.py` - Python script to split combined transcripts into individual files

## Common Tasks

### Extract transcripts from combined file
```bash
python extract_transcripts.py
```
Note: The script currently outputs to `organized_transcripts/` directory (hardcoded path).

### Search transcripts for specific topics
```bash
grep -ri "chase sapphire" transcripts/
```

## Content Topics Covered

The transcripts cover: credit card product reviews, sign-up bonuses, earning strategies, airline/hotel loyalty programs (Hyatt, Marriott, United, American, Delta), transfer partners, lounge access, and travel hacks.

## Creating Summaries

When creating new summary guides in `summaries/`:
- Synthesize information from multiple relevant transcripts
- Use markdown formatting with clear sections
- Include specific details like annual fees, earning rates, and transfer ratios
- Note when information may become outdated (credit card benefits change frequently)
