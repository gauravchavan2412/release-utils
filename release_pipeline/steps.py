"""Discrete pipeline steps: clean → generate input → fetch ticket diff → (optional) Linear ticket."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional, Sequence

from . import config
from .constants import (
    LINEAR_TICKET_DETAIL_CREATED,
    LINEAR_TICKET_DETAIL_DRY_RUN,
    LINEAR_TICKET_DETAIL_SKIPPED,
    STEP_CLEAN_GENERATED,
    STEP_CREATE_LINEAR_TICKET,
    STEP_FETCH_TICKET_CHANGES,
    STEP_GENERATE_INPUT_JSON,
)


@dataclass
class StepResult:
    step: int
    name: str
    ok: bool
    detail: str = ""

    def __str__(self) -> str:
        status = "OK" if self.ok else "FAILED"
        suffix = f" — {self.detail}" if self.detail else ""
        return f"Step {self.step} [{status}] {self.name}{suffix}"


def find_step_result(
    step_results: Sequence[StepResult],
    step_number: int,
) -> Optional[StepResult]:
    """Return the first StepResult with the given step index."""
    for result in step_results:
        if result.step == step_number:
            return result
    return None


def _environment_with_overrides(
    overrides: Optional[Mapping[str, str]],
) -> dict[str, str]:
    """Copy of os.environ as a plain dict, with optional overrides (for subprocess)."""
    environment = dict(os.environ)
    if overrides:
        environment.update(overrides)
    return environment


def _run_command(
    command: List[str],
    *,
    working_directory: Path,
    environment_overrides: Optional[Mapping[str, str]] = None,
) -> None:
    completed = subprocess.run(
        command,
        cwd=working_directory,
        env=_environment_with_overrides(environment_overrides),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}"
        )


def _invoke_python_script(
    project_root: Path,
    script_filename: str,
    script_arguments: List[str],
) -> None:
    """Run `python <script>` from the repository root with the given argv tail."""
    command = [sys.executable, str(project_root / script_filename), *script_arguments]
    _run_command(command, working_directory=project_root)


def step_clean_generated(project_root: Path) -> StepResult:
    """Step 1: Remove generated_files and local __pycache__ (same intent as `make clean`)."""
    generated_dir = project_root / config.GENERATED_DIR
    if generated_dir.is_dir():
        shutil.rmtree(generated_dir)
    for relative_pycache in ("__pycache__", "release_pipeline/__pycache__"):
        pycache_dir = project_root / relative_pycache
        if pycache_dir.is_dir():
            shutil.rmtree(pycache_dir)
    return StepResult(
        STEP_CLEAN_GENERATED,
        "Clean generated_files",
        True,
        f"removed {config.GENERATED_DIR}",
    )


def step_generate_input(
    project_root: Path,
    stackgen_tag: str,
    *,
    version_json_url: str | None = None,
) -> StepResult:
    """
    Step 2: Build input.json from version.json (default: production) + appcd-dist .env at STACKGEN_TAG (raw).
    """
    stackgen_tag_stripped = stackgen_tag.strip()
    version_url_resolved = (version_json_url or "").strip() or config.VERSION_JSON_PRODUCTION
    output_path = project_root / config.INPUT_JSON_REL
    _invoke_python_script(
        project_root,
        config.GENERATE_INPUT_SCRIPT,
        [
            "--version-url",
            version_url_resolved,
            "--env-url",
            config.appcd_dist_raw_env_url(stackgen_tag_stripped),
            "--stackgen-tag",
            stackgen_tag_stripped,
            "--output",
            str(output_path),
            "--pretty",
        ],
    )
    if not output_path.is_file():
        raise RuntimeError(f"Expected output missing: {output_path}")
    return StepResult(
        STEP_GENERATE_INPUT_JSON,
        "Generate input.json",
        True,
        f"{version_url_resolved} + appcd-dist/{stackgen_tag_stripped}/.env → {config.INPUT_JSON_REL}",
    )


def step_fetch_ticket_changes(project_root: Path) -> StepResult:
    """Step 3: Run process_all_repos (same as `make fetch_changes_between_tags_from_input`)."""
    input_path = project_root / config.INPUT_JSON_REL
    if not input_path.is_file():
        raise RuntimeError(f"Missing input file: {input_path}")
    output_path = project_root / config.FINAL_TAG_DIFF_REL
    _invoke_python_script(
        project_root,
        config.PROCESS_REPOS_SCRIPT,
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--verbose",
            "--pretty",
        ],
    )
    if not output_path.is_file():
        raise RuntimeError(f"Expected output missing: {output_path}")
    return StepResult(
        STEP_FETCH_TICKET_CHANGES,
        "Fetch ticket changes",
        True,
        str(config.FINAL_TAG_DIFF_REL),
    )


def _linear_ticket_step_detail(exit_code: int, dry_run: bool) -> str:
    """Map create_monthly_release exit code + dry-run flag to a stable detail string."""
    success = exit_code == 0
    if dry_run and success:
        return LINEAR_TICKET_DETAIL_DRY_RUN
    if dry_run and not success:
        return f"dry-run failed (exit {exit_code})"
    if success:
        return LINEAR_TICKET_DETAIL_CREATED
    return f"not created (exit {exit_code})"


def step_create_monthly_release_ticket(ticket_config: "MonthlyTicketConfig") -> StepResult:
    """Step 4: Create Linear monthly release issue."""
    from create_monthly_release_ticket import run_create_monthly_release

    exit_code = run_create_monthly_release(ticket_config)
    dry_run = bool(getattr(ticket_config, "dry_run", False))
    detail = _linear_ticket_step_detail(exit_code, dry_run)
    return StepResult(
        STEP_CREATE_LINEAR_TICKET,
        "Create monthly release ticket in Linear",
        exit_code == 0,
        detail,
    )


def skipped_linear_ticket_step() -> StepResult:
    """Step 4 placeholder when --skip-ticket is used."""
    return StepResult(
        STEP_CREATE_LINEAR_TICKET,
        "Create monthly release ticket in Linear",
        True,
        LINEAR_TICKET_DETAIL_SKIPPED,
    )
