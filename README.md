# StackGen release-utils

Python utilities for StackGen version checks, tag-to-tag diffs, and **monthly release automation** (input generation, Linear ticket extraction, optional Linear issue creation).

All tag-diff and pipeline scripts live in the **repository root** (no `tags-diff/` subdirectory).

---

## Prerequisites

```bash
pip install -r requirements.txt
```

For GitHub API calls (rate limits, private repos):

```bash
export GITHUB_PAT=ghp_...   # or GH_TOKEN / GITHUB_TOKEN
```

For Linear-enriched output (`process_all_repos`, monthly ticket body):

```bash
export LINEAR_API_KEY=lin_api_...
```

Optional `make setup` copies `env.template` → `.env` for local `LINEAR_API_KEY`.

---

## Tag diff & monthly release (main flow)

### Outputs (generated, gitignored)

| Path | Purpose |
|------|---------|
| `generated_files/input_file/input.json` | Service → repo → current/new tags |
| `generated_files/final_tag_differences.json` | Consolidated tickets + projects |
| `generated_files/commit_differences_with_messages.txt` | Raw commit compare logs (optional) |

### Makefile (from repo root)

| Target | Purpose |
|--------|---------|
| `make help` | List targets |
| `make setup` | `.env` from template + Linear smoke test |
| `make generate-input STACKGEN_TAG=v2026.3.12` | Production `version.json` + **raw** appcd-dist `.env` at that tag |
| `make generate-input-custom STACKGEN_TAG=vX.Y.Z` | Interactive **version.json** only; `.env` is always raw at that tag |
| `make fetch_changes_between_tags_from_input` | Run `process_all_repos.py` on `input.json` |
| `make full-workflow STACKGEN_TAG=<tag>` | `generate-input` then `fetch_changes...` |
| `make monthly-release STACKGEN_TAG=vX.Y.Z` | Full pipeline: clean → prod input → tickets → **Linear issue** |
| `make monthly-release-no-ticket STACKGEN_TAG=vX.Y.Z` | Steps 1–3 only (no Linear create) |
| `make clean` | Remove `generated_files/` + local `__pycache__` |
| `make test-linear` | Linear API test |

### One-shot pipeline (`run_monthly_release.py`)

Non-interactive: **production** `version.json` (`https://cloud.stackgen.com/version.json`), appcd-dist **raw** `.env` at your tag, then tickets, then optional Linear ticket.

```bash
# Full flow (needs LINEAR_API_KEY for step 4)
python run_monthly_release.py v2026.2.7

# Use stage/demo deployed versions instead (optional)
python run_monthly_release.py v2026.2.7 --version-json-url https://stage.dev.stackgen.com/version.json

# CI / artifacts only
python run_monthly_release.py v2026.2.7 --skip-ticket

# Preview Linear body without creating
python run_monthly_release.py v2026.2.7 --dry-run-ticket
```

Use `--project-root` if the script is not run from the repo root.

`make generate-input STACKGEN_TAG=<tag>` loads new versions from  
`https://raw.githubusercontent.com/appcd-dev/appcd-dist/<tag>/.env` (always the raw URL). Override deployed `version.json` with `VERSION_URL=...` if needed.  
`make monthly-release` / `monthly-release-no-ticket` use the same raw `.env` pattern; optional **`VERSION_JSON_URL=...`** only changes which **version.json** URL is used.

### Monthly Linear issue (`create_monthly_release_ticket.py`)

Creates an issue from `generated_files/final_tag_differences.json` (after a successful fetch step). Configure template, team (`--team-key HZ`), assignee, etc. See `python create_monthly_release_ticket.py --help`.

### Other CLI tools

| Script | Role |
|--------|------|
| `verify_latest_tags_vs_appcd_dist_env.py` | Compare latest GitHub tags vs appcd-dist `main` `.env` |
| `parse_ui_changes_tickets.py` | Parse ticket IDs from text |
| `scan_ticket_formats.py` | Scan files for ticket ID patterns |
| `fetchTicketChangesInBuildsForRepo.py` | Single-repo ticket extraction via `compare_tags.py` |
| `compare_tags.py` | GitHub compare API between two tags |
| `fetch_version_json.py` | Fetch/print a `version.json` URL |
| `test_linear_api.py` | Linear connectivity |

---

## Original version utilities (repo root)

These predate the tag-diff stack and remain unchanged in behavior:

- **`fetch_version.py`** — fetch StackGen environment `version.json` (interactive or CLI).
- **`compare_versions.py`** — compare deployed versions vs repo `.env` via GitHub.

Examples:

```bash
python fetch_version.py
python fetch_version.py cloud

python compare_versions.py owner/repo
```

---

## GitHub Actions

Workflow **Monthly release (tag diff)** (`.github/workflows/tags-diff-release.yml`):

- Manual dispatch: `stackgen_candidate_tag` (required); optional `version_json_url` to override production `version.json`
- Runs `python run_monthly_release.py "<tag>" --skip-ticket` (plus `--version-json-url` when set)
- Uploads artifact `monthly-release-generated-files` from `generated_files/`

Set repository secret **GITHUB_PAT** for GitHub API; optional **LINEAR_API_KEY** for richer JSON.

---

## Package layout

```
release_pipeline/   # Orchestration: steps, pipeline, config, constants
run_monthly_release.py
create_monthly_release_ticket.py
generate_input_json.py
process_all_repos.py
compare_tags.py
…
Makefile
env.template
```

---

## Security

- Tokens only via environment variables or CI secrets—never commit `.env`.
- GitHub PAT should have read access to repos you compare.
