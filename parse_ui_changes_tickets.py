#!/usr/bin/env python3
"""
Parse a UI changes file and list all unique Linear ticket IDs (e.g. PLAT-1851, AE-1626).

Tickets may have any characters leading or trailing. The hyphen between project and number
is optional in the source (e.g. PLAT1851 or PLAT-1851); output is normalized to PROJ-N.

Usage:
  python parse_ui_changes_tickets.py
  python parse_ui_changes_tickets.py generated_files/ui-changes.txt
  python parse_ui_changes_tickets.py --file path/to/ui-changes.txt
"""

import argparse
import re
import sys
from pathlib import Path


def normalize_ticket(project: str, number: str) -> str:
    """Return ticket in standard form PROJ-N."""
    return f"{project}-{number}"


def extract_linear_tickets(text: str) -> set:
    """
    Extract all Linear-style ticket IDs from text.
    Handles leading/trailing characters and optional hyphen.
    Returns set of normalized IDs (PROJ-N format).
    """
    tickets = set()
    # Pattern 1: PROJ-N (2-8 letters, hyphen, 1-6 digits) - any context
    for m in re.finditer(r"([A-Z]{2,8})-(\d{1,6})\b", text):
        tickets.add(normalize_ticket(m.group(1), m.group(2)))
    # Pattern 2: PROJN with no hyphen (2-8 letters immediately followed by 1-6 digits, word boundary after)
    # Require non-letter before the project part to avoid matching mid-word
    for m in re.finditer(r"(?<![A-Za-z])([A-Z]{2,8})(\d{1,6})\b", text):
        tickets.add(normalize_ticket(m.group(1), m.group(2)))
    return tickets


def main() -> None:
    default_path = Path(__file__).parent / "generated_files" / "ui-changes.txt"
    parser = argparse.ArgumentParser(
        description="Parse UI changes file and list unique Linear tickets (e.g. PLAT-1851, AE-1626)."
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=str(default_path),
        help=f"UI changes file (default: {default_path})",
    )
    args = parser.parse_args()
    path = args.file
    path = Path(path)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = path.read_text(encoding="utf-8", errors="replace")
    tickets = extract_linear_tickets(text)
    for t in sorted(tickets):
        print(t)
    print(f"\nUnique ticket count: {len(tickets)}")


if __name__ == "__main__":
    main()
