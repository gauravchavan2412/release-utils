#!/usr/bin/env python3
"""
End-to-end monthly release flow (tags-diff directory):

  1. Clean generated_files
  2. Generate input.json — production version.json + appcd-dist .env at STACKGEN_TAG (raw)
  3. Fetch ticket changes → final_tag_differences.json
  4. Create Linear monthly release issue (unless --skip-ticket)

Run from repo:  python tags-diff/run_monthly_release.py v2026.2.7
Or from tags-diff: python run_monthly_release.py v2026.2.7
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from create_monthly_release_ticket import MonthlyTicketConfig
from release_pipeline.pipeline import run_monthly_release_pipeline


def _tags_diff_dir() -> Path:
    return Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Monthly release pipeline: clean → input → tickets → Linear issue",
    )
    p.add_argument(
        "stackgen_tag",
        help="appcd-dist tag for candidate .env (e.g. v2026.2.7); passed to generate_input_json --stackgen-tag",
    )
    p.add_argument(
        "--tags-diff-root",
        type=Path,
        default=None,
        help="tags-diff directory (default: directory containing this script)",
    )
    p.add_argument(
        "--skip-ticket",
        action="store_true",
        help="Stop after step 3 (no Linear issue)",
    )
    p.add_argument(
        "--dry-run-ticket",
        action="store_true",
        help="Step 4: print summary only (no issueCreate)",
    )
    p.add_argument(
        "--ticket-input",
        type=Path,
        default=None,
        help="Input JSON for step 4 (default: generated_files/final_tag_differences.json under tags-diff root)",
    )
    p.add_argument("--api-key", default=os.getenv("LINEAR_API_KEY"), help="Linear API key for step 4")
    p.add_argument("--template-name", default="Monthly Release")
    p.add_argument("--template-id", default="")
    p.add_argument("--assignee-query", default="gaurav")
    p.add_argument("--team-key", default="HZ")
    p.add_argument("--team-id", default="")
    p.add_argument("--title", default="")
    p.add_argument("--month-label", default="")
    return p


def main() -> int:
    args = build_parser().parse_args()
    root = (args.tags_diff_root or _tags_diff_dir()).resolve()

    ticket_config = None
    if not args.skip_ticket:
        t_in = args.ticket_input
        if t_in is None:
            t_in = root / "generated_files/final_tag_differences.json"
        ticket_config = MonthlyTicketConfig(
            input_path=t_in,
            api_key=args.api_key,
            template_name=args.template_name,
            template_id=args.template_id,
            assignee_query=args.assignee_query,
            team_key=args.team_key,
            team_id=args.team_id,
            title=args.title,
            month_label=args.month_label,
            dry_run=args.dry_run_ticket,
        )

    return run_monthly_release_pipeline(
        args.stackgen_tag,
        tags_diff_root=root,
        skip_ticket=args.skip_ticket,
        ticket_config=ticket_config,
    )


if __name__ == "__main__":
    sys.exit(main())
