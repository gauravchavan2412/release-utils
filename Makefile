.PHONY: help setup generate-input generate-input-custom generate-custom-input-file fetch_changes_between_tags_from_input clean test-linear monthly-release monthly-release-no-ticket

# Configuration
PYTHON := python3
# Deployed "current" versions — default production (override: VERSION_URL=...)
VERSION_URL := https://cloud.stackgen.com/version.json
# New versions: raw .env from appcd-dist at STACKGEN_TAG (required for generate-input), e.g.
# https://raw.githubusercontent.com/appcd-dev/appcd-dist/v2026.3.12/.env
APPCD_DIST_RAW_ENV = https://raw.githubusercontent.com/appcd-dev/appcd-dist/$(STACKGEN_TAG)/.env
INPUT_FILE := generated_files/input_file/input.json
OUTPUT_FILE := generated_files/final_tag_differences.json
ENV_FILE := .env

# Default target
help:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Release Utils - Tag Comparison & Ticket Extraction"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@echo "  make setup                                 - Set up environment and test Linear API"
	@echo "  make generate-input STACKGEN_TAG=<tag>    - input.json (prod version.json + raw appcd-dist .env at tag)"
	@echo "  make generate-input-custom STACKGEN_TAG=<tag> - Generate input.json (STACKGEN_TAG required)"
	@echo "  make generate-custom-input-file            - input.json from appcd-dist .env between FROM_REF and TO_REF"
	@echo "  make fetch_changes_between_tags_from_input - Extract ticket changes between versions"
	@echo "  make monthly-release STACKGEN_TAG=<tag>    - Full pipeline: clean → prod input + .env → tickets → Linear"
	@echo "  make monthly-release-no-ticket STACKGEN_TAG=<tag> - Steps 1–3 only (no Linear issue)"
	@echo "  make full-workflow                         - Run complete workflow (generate + process)"
	@echo "  make test-linear                           - Test Linear API connection"
	@echo "  make clean                                 - Remove generated files"
	@echo ""
	@echo "Configuration:"
	@echo "  VERSION_URL  = $(VERSION_URL)"
	@echo "  (generate-input) STACKGEN_TAG required — .env = appcd-dist raw at that tag"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Setup environment and test Linear API
setup:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Setting up environment..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "⚠️  .env file not found. Creating from template..."; \
		cp env.template $(ENV_FILE); \
		echo ""; \
		echo "📝 Please edit .env and add your LINEAR_API_KEY"; \
		echo "   Get your key from: https://linear.app/settings/api"; \
		echo ""; \
	else \
		echo "✅ .env file exists"; \
	fi
	@echo ""
	@echo "Testing Linear API connection..."
	@$(PYTHON) test_linear_api.py || echo "⚠️  Linear API not configured. Set LINEAR_API_KEY in .env"

# Generate input.json: production version.json + raw .env at appcd-dist tag STACKGEN_TAG
generate-input:
	@if [ -z "$(STACKGEN_TAG)" ]; then \
		echo "❌ STACKGEN_TAG is required (e.g. v2026.3.12)."; \
		echo "   New versions come from: https://raw.githubusercontent.com/appcd-dev/appcd-dist/<tag>/.env"; \
		exit 1; \
	fi
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Generating input.json..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "📥 Deployed versions (version.json): $(VERSION_URL)"
	@echo "📥 New versions (.env): $(APPCD_DIST_RAW_ENV)"
	@echo ""
	@$(PYTHON) generate_input_json.py \
		--version-url "$(VERSION_URL)" \
		--env-url "$(APPCD_DIST_RAW_ENV)" \
		--stackgen-tag "$(STACKGEN_TAG)" \
		--output "$(INPUT_FILE)" \
		--pretty
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Generated: $(INPUT_FILE)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Custom URLs for generate-input (STACKGEN_TAG is required)
generate-input-custom:
	@if [ -z "$(STACKGEN_TAG)" ]; then \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo "❌ Error: STACKGEN_TAG is required for generate-input-custom"; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo ""; \
		echo "Usage: make generate-input-custom STACKGEN_TAG=<tag>"; \
		echo "Example: make generate-input-custom STACKGEN_TAG=v2026.2.7"; \
		echo ""; \
		echo "STACKGEN_TAG is the appcd-dist tag used to fetch the .env file (e.g. v2026.2.7)."; \
		echo ""; \
		exit 1; \
	fi
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Generating input.json with custom URLs (STACKGEN_TAG=$(STACKGEN_TAG))..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Select version.json URL:"
	@echo "  1. Stage       - https://stage.dev.stackgen.com/version.json"
	@echo "  2. Demo        - https://demo.cloud.stackgen.com/version.json"
	@echo "  3. Production  - https://cloud.stackgen.com/version.json"
	@echo "  4. Custom URL"
	@echo ""
	@read -p "Enter choice [1-4] (default: 1): " choice; \
	choice=$${choice:-1}; \
	case $$choice in \
		1) version_url="https://stage.dev.stackgen.com/version.json" ;; \
		2) version_url="https://demo.cloud.stackgen.com/version.json" ;; \
		3) version_url="https://cloud.stackgen.com/version.json" ;; \
		4) read -p "Enter custom version.json URL: " version_url ;; \
		*) echo "Invalid choice, using default"; version_url="$(VERSION_URL)" ;; \
	esac; \
	echo ""; \
	echo "Selected version.json: $$version_url"; \
	echo "📥 New versions (.env, raw at tag): $(APPCD_DIST_RAW_ENV)"; \
	echo ""; \
	$(PYTHON) generate_input_json.py \
		--version-url "$$version_url" \
		--env-url "$(APPCD_DIST_RAW_ENV)" \
		--stackgen-tag "$(STACKGEN_TAG)" \
		--output "$(INPUT_FILE)" \
		--pretty

# Generate input.json by comparing appcd-dist .env between two refs/tags/branches
generate-custom-input-file:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Generating custom input.json from appcd-dist .env refs..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@from_ref="$(FROM_REF)"; \
	to_ref="$(TO_REF)"; \
	if [ -z "$$from_ref" ]; then \
		read -p "Enter FROM_REF (base tag/branch): " from_ref; \
	fi; \
	if [ -z "$$to_ref" ]; then \
		read -p "Enter TO_REF (target tag/branch): " to_ref; \
	fi; \
	if [ -z "$$from_ref" ] || [ -z "$$to_ref" ]; then \
		echo "❌ Both FROM_REF and TO_REF are required."; \
		echo "Usage: make generate-custom-input-file FROM_REF=<tag-or-branch> TO_REF=<tag-or-branch>"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "Comparing appcd-dist refs: $$from_ref → $$to_ref"; \
	echo "Output: $(INPUT_FILE)"; \
	echo ""; \
	$(PYTHON) generate_custom_input_file.py \
		--from-ref "$$from_ref" \
		--to-ref "$$to_ref" \
		--output "$(INPUT_FILE)" \
		--pretty

# Process all repos and extract ticket changes
fetch_changes_between_tags_from_input:
	@if [ ! -f "$(INPUT_FILE)" ]; then \
		echo "❌ Error: $(INPUT_FILE) not found. Run 'make generate-input' first."; \
		exit 1; \
	fi
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Processing all repositories and extracting ticket changes..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@$(PYTHON) process_all_repos.py \
		--input "$(INPUT_FILE)" \
		--verbose \
		--pretty
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Processing complete! Check the output file above."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run complete workflow: generate input + process changes
full-workflow: generate-input fetch_changes_between_tags_from_input
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Full workflow completed successfully!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test Linear API connection
test-linear:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Testing Linear API Connection..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@if [ -z "$$LINEAR_API_KEY" ]; then \
		echo "⚠️  LINEAR_API_KEY not set in environment."; \
		echo ""; \
		echo "To enable Linear ticket summaries:"; \
		echo "  1. Get your API key from: https://linear.app/settings/api"; \
		echo "  2. Add it to .env file: LINEAR_API_KEY=lin_api_xxx"; \
		echo "  3. Load it: source .env  OR  export \$$(cat .env | xargs)"; \
		echo ""; \
		echo "Testing without API key..."; \
		echo ""; \
		$(PYTHON) test_linear_api.py; \
	else \
		echo "✅ LINEAR_API_KEY is set"; \
		echo ""; \
		$(PYTHON) test_linear_api.py; \
	fi

# Full monthly release pipeline (see run_monthly_release.py)
# Optional: VERSION_JSON_URL=https://stage.dev.stackgen.com/version.json (default: production)
monthly-release:
	@if [ -z "$(STACKGEN_TAG)" ]; then \
		echo "Usage: make monthly-release STACKGEN_TAG=v2026.2.7"; \
		echo "Optional: VERSION_JSON_URL=<url> (default: production cloud.stackgen.com)"; \
		exit 1; \
	fi
	@EXTRA=""; \
	if [ -n "$(VERSION_JSON_URL)" ]; then EXTRA="--version-json-url $(VERSION_JSON_URL)"; fi; \
	$(PYTHON) run_monthly_release.py "$(STACKGEN_TAG)" $$EXTRA

monthly-release-no-ticket:
	@if [ -z "$(STACKGEN_TAG)" ]; then \
		echo "Usage: make monthly-release-no-ticket STACKGEN_TAG=v2026.2.7"; \
		echo "Optional: VERSION_JSON_URL=<url>"; \
		exit 1; \
	fi
	@EXTRA="--skip-ticket"; \
	if [ -n "$(VERSION_JSON_URL)" ]; then EXTRA="$$EXTRA --version-json-url $(VERSION_JSON_URL)"; fi; \
	$(PYTHON) run_monthly_release.py "$(STACKGEN_TAG)" $$EXTRA

# Clean generated files
clean:
	@echo "🧹 Cleaning generated files..."
	@rm -rf generated_files/
	@rm -rf __pycache__ release_pipeline/__pycache__
	@echo "✅ Cleaned!"

# Show current configuration
config:
	@echo "Current Configuration:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "VERSION_URL    = $(VERSION_URL)"
	@echo "ENV_URL        = $(ENV_URL)"
	@echo "INPUT_FILE     = $(INPUT_FILE)"
	@echo "LINEAR_API_KEY = $${LINEAR_API_KEY:+Set (hidden)}$${LINEAR_API_KEY:-Not set}"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

