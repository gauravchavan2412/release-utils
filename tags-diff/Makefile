.PHONY: help setup generate-input generate-input-custom fetch_changes_between_tags_from_input clean test-linear

# Configuration
PYTHON := python3
VERSION_URL := https://stage.dev.stackgen.com/version.json
ENV_URL := https://raw.githubusercontent.com/appcd-dev/appcd-dist/main/.env
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
	@echo "  make generate-input                        - Generate input.json (default: stage)"
	@echo "  make generate-input-custom                 - Generate input.json with environment selection"
	@echo "  make fetch_changes_between_tags_from_input - Extract ticket changes between versions"
	@echo "  make full-workflow                         - Run complete workflow (generate + process)"
	@echo "  make test-linear                           - Test Linear API connection"
	@echo "  make clean                                 - Remove generated files"
	@echo ""
	@echo "Configuration:"
	@echo "  VERSION_URL = $(VERSION_URL)"
	@echo "  ENV_URL     = $(ENV_URL)"
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

# Generate input.json by comparing deployed version vs new version
generate-input:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Generating input.json..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "📥 Fetching deployed versions from: $(VERSION_URL)"
	@echo "📥 Fetching new versions from: $(ENV_URL)"
	@echo ""
	@$(PYTHON) generate_input_json.py \
		--version-url "$(VERSION_URL)" \
		--env-url "$(ENV_URL)" \
		--output "$(INPUT_FILE)" \
		--pretty
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Generated: $(INPUT_FILE)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Custom URLs for generate-input
generate-input-custom:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Generating input.json with custom URLs..."
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
	echo ""; \
	read -p "Enter .env file URL [$(ENV_URL)]: " env_url; \
	env_url=$${env_url:-$(ENV_URL)}; \
	echo ""; \
	$(PYTHON) generate_input_json.py \
		--version-url "$$version_url" \
		--env-url "$$env_url" \
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

# Clean generated files
clean:
	@echo "🧹 Cleaning generated files..."
	@rm -rf generated_files/
	@rm -rf __pycache__
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

