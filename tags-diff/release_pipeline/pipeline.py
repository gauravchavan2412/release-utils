"""Orchestrate monthly release: clean → generate input → fetch changes → create Linear ticket."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import List, Optional

from . import config
from .steps import StepResult, step_clean_generated, step_create_monthly_release_ticket
from .steps import step_fetch_ticket_changes, step_generate_input


def _final_status_line(*, skip_ticket: bool, results: List[StepResult]) -> str:
    """Single-line summary of whether a Linear issue was created."""
    if skip_ticket:
        return "Linear monthly release ticket: not created (step 4 skipped with --skip-ticket)"
    r4 = next((r for r in results if r.step == 4), None)
    if not r4:
        return "Linear monthly release ticket: unknown"
    detail = (r4.detail or "").lower()
    if "skipped" in detail:
        return "Linear monthly release ticket: not created (step skipped)"
    if r4.ok and "dry-run" in detail:
        return "Linear monthly release ticket: not created (dry-run only; no issueCreate)"
    if r4.ok and "created in linear" in detail:
        return "Linear monthly release ticket: created"
    if not r4.ok:
        return "Linear monthly release ticket: not created (failed — see logs above)"
    return f"Linear monthly release ticket: see step 4 — {r4.detail}"


def _banner(text: str) -> None:
    print(f"\n{'━' * 60}\n{text}\n{'━' * 60}\n")


def run_monthly_release_pipeline(
    stackgen_tag: str,
    *,
    tags_diff_root: Optional[Path] = None,
    skip_ticket: bool = False,
    ticket_config=None,
) -> int:
    """
    Run steps 1–3 always; step 4 when skip_ticket is False.

    If ticket_config is None and skip_ticket is False, defaults to final_tag_differences.json under root.
    """
    from create_monthly_release_ticket import MonthlyTicketConfig

    root = tags_diff_root or config.tags_diff_root()
    root = root.resolve()

    if not stackgen_tag or not stackgen_tag.strip():
        print("Error: stackgen_tag is required (e.g. v2026.2.7)", file=sys.stderr)
        return 1

    if not skip_ticket and ticket_config is None:
        ticket_config = MonthlyTicketConfig(
            input_path=root / config.FINAL_TAG_DIFF_REL,
        )

    results: List[StepResult] = []

    try:
        _banner(f"Step 1 — Clean {config.GENERATED_DIR}")
        results.append(step_clean_generated(root))

        _banner(f"Step 2 — Generate input (production + appcd-dist @ {stackgen_tag.strip()})")
        results.append(step_generate_input(root, stackgen_tag))

        _banner("Step 3 — Fetch tickets and details")
        results.append(step_fetch_ticket_changes(root))

        if skip_ticket:
            _banner("Step 4 — Skipped (--skip-ticket)")
            results.append(
                StepResult(
                    4,
                    "Create monthly release ticket in Linear",
                    True,
                    "skipped — not created in Linear",
                )
            )
        else:
            assert ticket_config is not None
            tc = ticket_config
            if not tc.input_path.is_absolute():
                tc = replace(tc, input_path=(root / tc.input_path).resolve())
            _banner("Step 4 — Create monthly release ticket in Linear")
            results.append(step_create_monthly_release_ticket(tc))
    except Exception as e:
        print(f"\n❌ Pipeline aborted: {e}", file=sys.stderr)
        return 1

    _banner("Pipeline summary")
    for r in results:
        print(r)

    _banner("Final status")
    print(_final_status_line(skip_ticket=skip_ticket, results=results))

    failed = [r for r in results if not r.ok]
    if failed:
        return 1
    print("\n✅ Monthly release pipeline completed successfully.")
    return 0
