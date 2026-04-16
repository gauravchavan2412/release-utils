"""Paths and URLs for the release automation pipeline (repository root)."""

from pathlib import Path

# Production StackGen deployment — "current" tags to compare from
VERSION_JSON_PRODUCTION = "https://cloud.stackgen.com/version.json"

# Candidate "new" versions: always raw .env from appcd-dist at the user tag, e.g.
# https://raw.githubusercontent.com/appcd-dev/appcd-dist/v2026.3.12/.env
APPCD_DIST_RAW_ENV = (
    "https://raw.githubusercontent.com/appcd-dev/appcd-dist/{stackgen_tag}/.env"
)

GENERATED_DIR = "generated_files"
INPUT_JSON_REL = "generated_files/input_file/input.json"
FINAL_TAG_DIFF_REL = "generated_files/final_tag_differences.json"

GENERATE_INPUT_SCRIPT = "generate_input_json.py"
PROCESS_REPOS_SCRIPT = "process_all_repos.py"


def project_root() -> Path:
    """Repository root (parent of the release_pipeline package)."""
    return Path(__file__).resolve().parent.parent


def appcd_dist_raw_env_url(stackgen_tag: str) -> str:
    return APPCD_DIST_RAW_ENV.format(stackgen_tag=stackgen_tag.strip())


def final_tag_differences_path(root: Path) -> Path:
    """Default JSON input for Step 4 (monthly Linear ticket)."""
    return root / FINAL_TAG_DIFF_REL
