#!/usr/bin/env python3
"""
Verify that appcd-dist's .env on main uses the latest Git tag for each repository
listed in generated_files/input_file/input.json.

For each entry with a GitHub repository URL and a version_key:
  1. Prints latest tag per repository (GitHub tags API; semver-like tags preferred).
  2. Reads version_key from appcd-dev/appcd-dist/.env on main and compares to that latest tag.
  3. Reports OK / mismatch / missing key / skipped (branch-only values like main).

Requires: pip install requests
Auth:    GITHUB_PAT, GH_TOKEN, or GITHUB_TOKEN (recommended for rate limits).

Usage:
  python verify_latest_tags_vs_appcd_dist_env.py
  python verify_latest_tags_vs_appcd_dist_env.py --input path/to/input.json
  python verify_latest_tags_vs_appcd_dist_env.py --verbose
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

APPCD_DIST = "appcd-dev/appcd-dist"
DEFAULT_INPUT = Path(__file__).parent / "generated_files" / "input_file" / "input.json"
BRANCH_ONLY = frozenset({"main", "master", "develop", "dev"})


def github_headers(token: Optional[str]) -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h


def repo_from_url(url: str) -> Optional[str]:
    """owner/repo from https://github.com/appcd-dev/foo or .../foo.git"""
    try:
        p = urlparse(url)
        path = p.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = path.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    except Exception:
        pass
    return None


def fetch_file_from_ref(repo: str, path: str, ref: str, token: Optional[str]) -> Optional[str]:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        r = requests.get(url, headers=github_headers(token), params={"ref": ref}, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"]).decode("utf-8")
    except requests.RequestException:
        return None
    return None


def parse_env(content: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$", line)
        if m:
            k, v = m.groups()
            env[k] = v.strip().strip('"').strip("'")
    return env


def _semver_tuple(name: str) -> Optional[Tuple[int, ...]]:
    """Parse v1.2.3 or 1.2.3 into a tuple of ints for comparison."""
    s = name.lstrip("vV")
    parts = re.split(r"[.\-]", s)
    nums: List[int] = []
    for p in parts:
        if p.isdigit():
            nums.append(int(p))
        else:
            break
    return tuple(nums) if nums else None


def get_latest_tag(repo: str, token: Optional[str], verbose: bool = False) -> Optional[str]:
    """
    Latest tag: among tags returned by GitHub (up to 100), prefer the highest
    semver-like tag (v* with numeric segments); else first tag on the page.
    """
    url = f"https://api.github.com/repos/{repo}/tags"
    try:
        r = requests.get(
            url, headers=github_headers(token), params={"per_page": 100}, timeout=30
        )
        r.raise_for_status()
        tags = [t.get("name", "") for t in r.json() if t.get("name")]
    except requests.RequestException as e:
        if verbose:
            print(f"  ⚠️  tags API failed for {repo}: {e}", file=sys.stderr)
        return None
    if not tags:
        return None
    semver_tags = [(t, _semver_tuple(t)) for t in tags]
    with_semver = [(t, st) for t, st in semver_tags if st is not None]
    if with_semver:
        with_semver.sort(key=lambda x: x[1], reverse=True)
        return with_semver[0][0]
    return tags[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare latest GitHub tags to appcd-dist main .env (from input.json)."
    )
    parser.add_argument(
        "--input",
        "-i",
        default=str(DEFAULT_INPUT),
        help=f"input.json path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--dist-repo",
        default=APPCD_DIST,
        help="Repo containing .env (default: appcd-dev/appcd-dist)",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch/ref for .env in dist repo (default: main)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    token = os.getenv("GITHUB_PAT") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        print(
            "Warning: No GITHUB_PAT/GH_TOKEN/GITHUB_TOKEN — API rate limits may apply.\n",
            file=sys.stderr,
        )

    with open(input_path, encoding="utf-8") as f:
        services = json.load(f)
    if not isinstance(services, list):
        print("Error: input JSON must be a list of service objects", file=sys.stderr)
        return 1

    env_content = fetch_file_from_ref(args.dist_repo, ".env", args.branch, token)
    if not env_content:
        print(
            f"Error: could not fetch .env from {args.dist_repo} ref={args.branch}",
            file=sys.stderr,
        )
        return 1

    env_vars = parse_env(env_content)

    print("=" * 72)
    print("Latest tags vs appcd-dist .env (main)")
    print("=" * 72)
    print(f"Input:     {input_path}")
    print(f".env from: {args.dist_repo} @ {args.branch}")
    print()

    # Phase 1: resolve and print latest tag per repository (from input list)
    print("Latest tags (GitHub, per service repository)")
    print("-" * 72)
    prepared: List[dict] = []
    for row in services:
        service = row.get("service", "?")
        version_key = row.get("version_key", "")
        repo_url = row.get("repository", "")
        repo = repo_from_url(repo_url) if repo_url else None

        if not version_key or not repo:
            prepared.append(
                {
                    "service": service,
                    "repo": repo,
                    "version_key": version_key,
                    "latest": None,
                    "env_val": env_vars.get(version_key) if version_key else None,
                    "reason_skip": "missing version_key or repository",
                }
            )
            print(f"  {service:22} {str(repo or '-'):40} latest: —  ({prepared[-1]['reason_skip']})")
            continue

        latest = get_latest_tag(repo, token, args.verbose)
        env_val = env_vars.get(version_key)
        prepared.append(
            {
                "service": service,
                "repo": repo,
                "version_key": version_key,
                "latest": latest,
                "env_val": env_val,
                "reason_skip": None,
            }
        )
        latest_disp = latest if latest is not None else "— (unresolved)"
        print(f"  {service:22} {repo:40} latest: {latest_disp}")

    print("-" * 72)
    print()

    # Phase 2: verify .env values against those latest tags
    print("Verification (.env value vs latest tag above)")
    print("-" * 72)

    mismatches = 0
    skipped = 0
    ok = 0

    for p in prepared:
        service = p["service"]
        repo = p["repo"]
        version_key = p["version_key"]
        latest = p["latest"]
        env_val = p["env_val"]

        if p["reason_skip"]:
            if args.verbose:
                print(f"○  {service:22} skip: {p['reason_skip']}")
            skipped += 1
            continue

        if env_val is None:
            print(f"❌ {service:22} {repo:40} MISSING_KEY {version_key} in .env")
            mismatches += 1
            continue

        if env_val.lower() in BRANCH_ONLY or not env_val.strip():
            if args.verbose:
                print(
                    f"○  {service:22} {repo:40} skip compare: .env={env_val!r} (branch/empty)"
                )
            skipped += 1
            continue

        if latest is None:
            print(f"❌ {service:22} {repo:40} NO_TAG     could not resolve latest tag")
            mismatches += 1
            continue

        if env_val == latest:
            print(f"✅ {service:22} {repo:40} {version_key}={env_val!r} == latest {latest!r}")
            ok += 1
        else:
            print(
                f"❌ {service:22} {repo:40} MISMATCH   .env={env_val!r}  latest_tag={latest!r}"
            )
            mismatches += 1

    print("-" * 72)
    print()
    print("=" * 72)
    print(f"OK: {ok}  Mismatch/missing: {mismatches}  Skipped: {skipped}")
    print("=" * 72)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
