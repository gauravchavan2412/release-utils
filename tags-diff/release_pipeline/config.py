"""Paths and URLs for the monthly release pipeline (tags-diff root)."""

from pathlib import Path

# Production StackGen deployment — "current" tags to compare from
VERSION_JSON_PRODUCTION = "https://cloud.stackgen.com/version.json"

# appcd-dist raw .env at the candidate release tag (same as make generate-input-custom option 1)
APPCD_DIST_RAW_ENV = (
    "https://raw.githubusercontent.com/appcd-dev/appcd-dist/{stackgen_tag}/.env"
)

GENERATED_DIR = "generated_files"
INPUT_JSON_REL = "generated_files/input_file/input.json"
FINAL_TAG_DIFF_REL = "generated_files/final_tag_differences.json"

GENERATE_INPUT_SCRIPT = "generate_input_json.py"
PROCESS_REPOS_SCRIPT = "process_all_repos.py"


def tags_diff_root() -> Path:
    """Directory containing Makefile, generate_input_json.py, etc."""
    return Path(__file__).resolve().parent.parent


def appcd_dist_raw_env_url(stackgen_tag: str) -> str:
    return APPCD_DIST_RAW_ENV.format(stackgen_tag=stackgen_tag.strip())
