# Release Utils - Extract Ticket Changes Between Versions

Simple tool to compare version tags across repositories and extract Linear ticket changes.

---

## Quick Start

```bash
cd tags-diff

# Run complete workflow
make full-workflow
```

Output: `generated_files/final_tag_differences.json`

---

## Table of Contents

- [Setup](#setup)
- [Workflow 1: Generate Input File](#workflow-1-generate-input-file)
- [Workflow 2: Process Repos & Extract Tickets](#workflow-2-process-repos--extract-tickets)
- [Makefile Commands](#makefile-commands)
- [Linear API Setup](#linear-api-setup-optional)
- [Troubleshooting](#troubleshooting)

---

## Setup

### Prerequisites

```bash
pip install requests
```

### Initial Setup

```bash
make setup
```

This creates a `.env` file from the template.

---

## Workflow 1: Generate Input File

### What It Does

Compares **deployed versions** (from `version.json`) with **new versions** (from `.env` file) to create input file.

```
Deployed version.json  +  New .env file  →  generated_files/input_file/input.json
```

### Run It

```bash
make generate-input
```

**Default URLs:**
- Deployed: `https://stage.dev.stackgen.com/version.json`
- New: `https://raw.githubusercontent.com/appcd-dev/appcd-dist/main/.env`

### Custom URLs

Use the interactive menu to select from predefined environments:

```bash
make generate-input-custom
```

This will present you with options:
1. **Stage** - https://stage.dev.stackgen.com/version.json
2. **Demo** - https://demo.cloud.stackgen.com/version.json
3. **Production** - https://cloud.stackgen.com/version.json
4. **Custom URL** - Enter your own URL

Or run directly with Python:

```bash
python generate_input_json.py \
  --version-url "https://your-url/version.json" \
  --env-url "https://your-url/.env" \
  --pretty
```

### Output

Saved to: `generated_files/input_file/input.json`

```json
[
  {
    "service": "appcd",
    "repository": "https://github.com/appcd-dev/appcd",
    "current_tag": "v2025.10.4",
    "new_tag": "v2025.10.5"
  },
  {
    "service": "iac-gen",
    "repository": "https://github.com/appcd-dev/iac-gen",
    "current_tag": "v0.58.1",
    "new_tag": "v0.59.0"
  }
]
```

Shows which services changed:
```
🔄 appcd      v2025.10.4  →  v2025.10.5  (changed)
🔄 iac-gen    v0.58.1     →  v0.59.0     (changed)
✓  ui         v0.20.0     →  v0.20.0     (no change)
```

---

## Workflow 2: Process Repos & Extract Tickets

### What It Does

For each service that changed:
1. Compares the two Git tags
2. Extracts commits between them
3. Finds Linear tickets (format: `[ENG-1234]`)
4. Fetches ticket details from Linear API (if configured)
5. Saves everything to one JSON file

```
input.json  →  Compare tags  →  Extract tickets  →  final_tag_differences.json
```

### Run It

```bash
make fetch_changes_between_tags_from_input
```

**Requires:** Input file from Workflow 1

### Output

Saved to: `generated_files/final_tag_differences.json`

### Output Format

```json
{
  "metadata": {
    "generated_at": "2025-10-27 14:30:45",
    "total_services": 13,
    "services_with_changes": 3,
    "total_unique_tickets": 15
  },
  "services": [
    {
      "service": "appcd",
      "repository": "appcd-dev/appcd",
      "current_tag": "v2025.10.4",
      "new_tag": "v2025.10.5",
      "commits_ahead": 25,
      "tickets": [
        {
          "id": "ENG-1234",
          "title": "Add user authentication feature",
          "state": "Done",
          "assignee": "John Doe"
        },
        {
          "id": "ENG-1235",
          "title": "Fix bug in payment processing",
          "state": "In Progress",
          "assignee": "Jane Smith"
        }
      ],
      "ticket_count": 2
    }
  ],
  "all_tickets": [
    "ENG-1234",
    "ENG-1235",
    "PROD-456"
  ]
}
```

**With Linear API:** Full ticket details (title, state, assignee)  
**Without Linear API:** Only ticket IDs

---

## Makefile Commands

```bash
make help                                  # Show all commands
make setup                                 # Initial setup
make generate-input                        # Workflow 1: Generate input.json (default URLs)
make generate-input-custom                 # Workflow 1: Generate with environment selection menu
make fetch_changes_between_tags_from_input # Workflow 2: Extract tickets
make full-workflow                         # Run both workflows
make test-linear                           # Test Linear API
make clean                                 # Remove generated files
make config                                # Show current configuration
```

---

## Linear API Setup (Optional)

To get ticket **titles and details** (not just IDs):

### 1. Get API Key

Go to: https://linear.app/settings/api

### 2. Add to .env

```bash
echo "LINEAR_API_KEY=lin_api_your_key_here" >> .env
source .env
```

### 3. Test It

```bash
make test-linear
```

**Without Linear API:** You'll still get ticket IDs, just without summaries.

---

## Troubleshooting

### "Input file not found"

Run Workflow 1 first:
```bash
make generate-input
```

### Linear Tickets Show No Details

1. Check API key:
   ```bash
   echo $LINEAR_API_KEY
   ```

2. Test connection:
   ```bash
   make test-linear
   ```

3. If API key is not set, add it to `.env`:
   ```bash
   LINEAR_API_KEY=lin_api_your_key_here
   ```

### "Failed to fetch version.json"

Check URL or use local file:
```bash
python generate_input_json.py --version-file ./version.json --env-file ./.env
```

### GitHub Rate Limiting

Add GitHub token to `.env`:
```bash
GITHUB_TOKEN=ghp_your_token_here
```

---

## Configuration

### Makefile Variables

Edit `Makefile` to change defaults:

```makefile
VERSION_URL := https://stage.dev.stackgen.com/version.json
ENV_URL := https://raw.githubusercontent.com/appcd-dev/appcd-dist/main/.env
```

### Service Mappings

Services are defined in `generate_input_json.py`:

```python
SERVICE_VERSION_MAP = {
    "ui": {
        "version_key": "APPCDUI_VERSION",
        "repository": "https://github.com/appcd-dev/appcd-ui"
    },
    "appcd": {
        "version_key": "APPCD_VERSION",
        "repository": "https://github.com/appcd-dev/appcd"
    },
    ...
}
```

To add a new service, add it to this dictionary.

---

## Examples

### Standard Release Process

```bash
# Generate input comparing stage vs main
make generate-input

# Review what changed
cat generated_files/input_file/input.json | jq '.[] | select(.current_tag != .new_tag)'

# Extract tickets
make fetch_changes_between_tags_from_input

# Result: generated_files/final_tag_differences.json
```

### Compare Different Environments

Use the interactive menu to select an environment:

```bash
# Interactive menu with predefined environments
make generate-input-custom
# Select: 1 for Stage, 2 for Demo, 3 for Production, or 4 for Custom

# Extract tickets
make fetch_changes_between_tags_from_input
```

Or use Python directly:

```bash
python generate_input_json.py \
  --version-url "https://cloud.stackgen.com/version.json" \
  --env-url "https://raw.githubusercontent.com/org/repo/staging/.env" \
  --pretty

make fetch_changes_between_tags_from_input
```

### Single Repository Comparison

```bash
python fetchTicketChangesInBuildsForRepo.py \
  appcd-dev/appcd \
  v2025.10.4 \
  v2025.10.5 \
  --verbose
```

---

## How It Works

### Workflow 1: Generate Input

```
1. Fetch deployed versions from version.json
2. Fetch new versions from .env file
3. Map services to GitHub repositories
4. Compare versions
5. Save to generated_files/input_file/input.json
```

### Workflow 2: Process Repos

```
For each service with changes:
  1. Compare Git tags (v1.0.0...v2.0.0)
  2. Extract commit messages
  3. Find Linear tickets: [ENG-1234], [PROD-456]
  4. Call Linear API to get ticket details
  5. Aggregate results

Output: ticket_changes_<version>.json
```

---

## Files

```
tags-diff/
├── Makefile                                  # Workflow automation
├── README.md                                 # This file
├── env.template                              # Environment template
│
├── generate_input_json.py                    # Workflow 1
├── process_all_repos.py                      # Workflow 2
├── fetchTicketChangesInBuildsForRepo.py      # Single repo processor
├── compare_tags.py                           # Git tag comparison
├── test_linear_api.py                        # Test utility
│
├── input.json                                # Generated by Workflow 1
└── ticket_changes_<version>.json             # Generated by Workflow 2
```

---

## Support

**Test Linear API:**
```bash
python test_linear_api.py --ticket ENG-1234
```

**Debug mode:**
```bash
python fetchTicketChangesInBuildsForRepo.py owner/repo v1.0 v2.0 --debug
```

**Skip Linear API:**
```bash
python process_all_repos.py --no-fetch-details
```
