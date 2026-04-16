#!/usr/bin/env python3
"""
Scan a commit-diff log file for potential Linear ticket ID formats.

Reads the file written by process_all_repos.py (--commit-diff-log) and reports:
- All ticket-like patterns found (multiple regex formats)
- Which ones the current extractor would catch vs miss
- Suggestions for any missing formats

Usage:
  python scan_ticket_formats.py generated_files/commit_differences_with_messages.txt
  python scan_ticket_formats.py  # uses default path
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Current extractor pattern (same as process_all_repos): bracketed or word-boundary
CURRENT_PATTERN = re.compile(
    r'\[([A-Z]{2,6}-\d{1,6})\]'
    r'|(?:^|[\s(])([A-Z]{2,6}-\d{1,6})(?=[\s:|\)\]\-,]|$)',
    re.MULTILINE
)

# Additional patterns to detect other possible Linear/ticket formats
ADDITIONAL_PATTERNS = [
    ("Bracketed [XXX-N] (2-8 letters)", re.compile(r'\[([A-Z]{2,8}-\d{1,6})\]')),
    ("Unbracketed XXX-N at word boundary", re.compile(r'(?:^|[\s(])([A-Z]{2,8}-\d{1,6})(?=[\s:|\)\]\-,]|$)', re.MULTILINE)),
    ("#XXX-N (hash prefix)", re.compile(r'#([A-Z]{2,8}-\d{1,6})\b')),
    ("XXX-N (anywhere, 2-8 letters)", re.compile(r'\b([A-Z]{2,8}-\d{1,6})\b')),
    ("XXX-N (1 letter prefix e.g. E-123)", re.compile(r'\b([A-Z]{1,8}-\d{1,6})\b')),
    ("JIRA-style PROJ-123 (strict)", re.compile(r'\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b')),
]

def current_extractor_matches(text: str) -> Set[str]:
    """Return set of ticket IDs that the current extractor would find."""
    found = set()
    for m in CURRENT_PATTERN.findall(text):
        for g in (m if isinstance(m, tuple) else (m,)):
            if g:
                found.add(g)
    return found

def run_additional_patterns(text: str) -> List[Tuple[str, Set[str]]]:
    """Run each additional pattern and return (pattern_name, set of matches)."""
    results = []
    for name, pattern in ADDITIONAL_PATTERNS:
        found = set()
        for m in pattern.findall(text):
            for g in (m if isinstance(m, tuple) else (m,)):
                if g:
                    found.add(g)
        results.append((name, found))
    return results

def main() -> None:
    default_path = Path(__file__).parent / "generated_files" / "commit_differences_with_messages.txt"
    parser = argparse.ArgumentParser(
        description="Scan commit diff log for Linear ticket formats and compare with current extractor."
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=str(default_path),
        help=f"Commit diff log file (default: {default_path})"
    )
    args = parser.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        print("Run: make fetch_changes_between_tags_from_input (or process_all_repos.py) first to generate the log.", file=sys.stderr)
        sys.exit(1)
    text = path.read_text(encoding="utf-8", errors="replace")
    current = current_extractor_matches(text)
    additional = run_additional_patterns(text)
    found_by_others: Set[str] = set()
    for _, s in additional:
        found_by_others |= s
    missing = found_by_others - current
    print("=" * 70)
    print("Linear ticket format scan")
    print("=" * 70)
    print(f"File: {path}")
    print(f"Current extractor (process_all_repos) found: {len(current)} unique IDs")
    print()
    print("Current extractor matches (would be included in final output):")
    for t in sorted(current):
        print(f"  {t}")
    print()
    print("Additional patterns tried:")
    for name, s in additional:
        print(f"  {name}: {len(s)} matches")
        for t in sorted(s)[:30]:
            print(f"    {t}")
        if len(s) > 30:
            print(f"    ... and {len(s) - 30} more")
    print()
    if missing:
        print("Potentially MISSED by current extractor (matched by other patterns but not current):")
        for t in sorted(missing):
            print(f"  {t}")
        print()
        print("Suggestions: Current pattern matches [PROJ-N] and PROJ-N at word boundaries (2-6 letter prefix).")
        print("To include more formats, extend the regex in process_all_repos.py (ticket_pattern).")
    else:
        print("No ticket-like IDs found that the current extractor would miss.")
    print("=" * 70)

if __name__ == "__main__":
    main()
