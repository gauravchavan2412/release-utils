"""Discrete pipeline steps: clean → generate input → fetch ticket diff → (optional) Linear ticket."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import config


@dataclass
class StepResult:
    step: int
    name: str
    ok: bool
    detail: str = ""

    def __str__(self) -> str:
        status = "OK" if self.ok else "FAILED"
        extra = f" — {self.detail}" if self.detail else ""
        return f"Step {self.step} [{status}] {self.name}{extra}"


def _run(cmd: List[str], cwd: Path, env: Optional[dict] = None) -> None:
    merged = {**os.environ, **(env or {})}
    p = subprocess.run(cmd, cwd=cwd, env=merged)
    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}"
        )


def step_clean_generated(tags_diff_root: Path) -> StepResult:
    """Step 1: Remove generated_files and local __pycache__ (same intent as `make clean`)."""
    gen = tags_diff_root / config.GENERATED_DIR
    if gen.is_dir():
        shutil.rmtree(gen)
    for rel in ("__pycache__", "release_pipeline/__pycache__"):
        pyc = tags_diff_root / rel
        if pyc.is_dir():
            shutil.rmtree(pyc)
    return StepResult(1, "Clean generated_files", True, f"removed {config.GENERATED_DIR}")


def step_generate_input(tags_diff_root: Path, stackgen_tag: str) -> StepResult:
    """
    Step 2: Build input.json from production version.json + appcd-dist .env at STACKGEN_TAG (raw).

    Equivalent to: make generate-input-custom with choices production (3) and .env raw (1).
    """
    out = tags_diff_root / config.INPUT_JSON_REL
    cmd = [
        sys.executable,
        str(tags_diff_root / config.GENERATE_INPUT_SCRIPT),
        "--version-url",
        config.VERSION_JSON_PRODUCTION,
        "--env-url",
        config.appcd_dist_raw_env_url(stackgen_tag),
        "--stackgen-tag",
        stackgen_tag.strip(),
        "--output",
        str(out),
        "--pretty",
    ]
    _run(cmd, cwd=tags_diff_root)
    if not out.is_file():
        raise RuntimeError(f"Expected output missing: {out}")
    return StepResult(
        2,
        "Generate input.json",
        True,
        f"production version.json + appcd-dist/{stackgen_tag}/.env → {config.INPUT_JSON_REL}",
    )


def step_fetch_ticket_changes(tags_diff_root: Path) -> StepResult:
    """Step 3: Run process_all_repos (same as `make fetch_changes_between_tags_from_input`)."""
    inp = tags_diff_root / config.INPUT_JSON_REL
    if not inp.is_file():
        raise RuntimeError(f"Missing input file: {inp}")
    out = tags_diff_root / config.FINAL_TAG_DIFF_REL
    cmd = [
        sys.executable,
        str(tags_diff_root / config.PROCESS_REPOS_SCRIPT),
        "--input",
        str(inp),
        "--output",
        str(out),
        "--verbose",
        "--pretty",
    ]
    _run(cmd, cwd=tags_diff_root)
    if not out.is_file():
        raise RuntimeError(f"Expected output missing: {out}")
    return StepResult(
        3,
        "Fetch ticket changes",
        True,
        str(config.FINAL_TAG_DIFF_REL),
    )


def step_create_monthly_release_ticket(cfg: object) -> StepResult:
    """Step 4: Create Linear monthly release issue."""
    from create_monthly_release_ticket import run_create_monthly_release

    code = run_create_monthly_release(cfg)
    dry = bool(getattr(cfg, "dry_run", False))
    ok = code == 0
    if dry and ok:
        detail = "dry-run only — not created in Linear"
    elif dry and not ok:
        detail = f"dry-run failed (exit {code})"
    elif ok:
        detail = "created in Linear"
    else:
        detail = f"not created (exit {code})"
    return StepResult(4, "Create monthly release ticket in Linear", ok, detail)
