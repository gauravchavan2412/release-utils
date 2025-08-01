# StackGen Release Utilities

A collection of Python utilities for managing StackGen deployments and version comparisons.

## Utilities

### 1. Version Fetcher (`fetch_version.py`)

Fetches version information from StackGen environments.

### 2. Version Comparator (`compare_versions.py`) 🆕

Compares deployed versions with repository `.env` file versions using GitHub API.

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up GitHub Personal Access Token (for version comparison):
```bash
export GITHUB_PAT=your_github_personal_access_token
# OR
export GH_TOKEN=your_github_personal_access_token
```

## Version Fetcher Usage

### Interactive Mode (Recommended)
```bash
python fetch_version.py
```

This will display a menu to select from predefined environments:
```
Available environments:
------------------------------
1. Production (cloud)
2. Staging (stage.dev)  
3. Development (main.dev)
4. Demo (demo.cloud)
------------------------------
Select environment [1-4]: 
```

### Command-line Mode
```bash
python fetch_version.py <env_name>
```

### Examples
```bash
# Interactive selection
python fetch_version.py

# Direct command-line usage
python fetch_version.py cloud
python fetch_version.py stage.dev
python fetch_version.py main.dev

# Force interactive mode even with argument
python fetch_version.py -i

# Verbose mode
python fetch_version.py -v cloud
python fetch_version.py -v  # Interactive with verbose
```

## Version Comparator Usage

### Basic Usage
```bash
python compare_versions.py owner/repo
```

### Full Example
```bash
python compare_versions.py myorg/myproject -e .env -b main -s cloud
```

### Interactive Environment Selection
```bash
python compare_versions.py owner/repo
# Will prompt for StackGen environment selection
```

### Examples
```bash
# Compare with default settings (.env file, main branch)
python compare_versions.py myorg/project

# Specify custom .env file path
python compare_versions.py myorg/project -e config/.env.production

# Use specific branch and environment
python compare_versions.py myorg/project -b develop -s stage.dev

# Verbose output for debugging
python compare_versions.py myorg/project -v

# Force specific StackGen environment
python compare_versions.py myorg/project -s cloud
```

## Version Fetcher Options

- `env_name`: Optional. The environment name to use in the URL. If not provided, interactive selection will be used.
- `-i, --interactive`: Force interactive environment selection even if env_name is provided
- `-v, --verbose`: Enable verbose output
- `-h, --help`: Show help message

## Version Comparator Options

- `repo`: Required. GitHub repository in format 'owner/repo'
- `-e, --env-file`: Path to .env file in repository (default: .env)
- `-b, --branch`: Branch to fetch .env file from (default: main)
- `-s, --stackgen-env`: StackGen environment name. If not provided, interactive selection is used.
- `-v, --verbose`: Enable verbose output
- `-h, --help`: Show help message

## Predefined Environments

The utilities include these predefined StackGen environments:
- **Production** (`cloud`)
- **Staging** (`stage.dev`)
- **Development** (`main.dev`)
- **Demo** (`demo.cloud`)

When using command-line mode with a custom environment name not in this list, the utility will ask for confirmation before proceeding.

## Environment Variables

### GitHub Authentication
- `GITHUB_PAT`: GitHub Personal Access Token (preferred)
- `GH_TOKEN`: Alternative GitHub token environment variable

## Version Comparison Features

### Supported .env Patterns
The comparator recognizes these version patterns in .env files:
- `SERVICE_VERSION=1.2.3`
- `VERSION_SERVICE=1.2.3`
- `SERVICE_TAG=v1.2.3`
- `IMAGE_SERVICE=repo:tag` (extracts tag as version)

### JSON Parsing
The comparator can handle various JSON structures from version endpoints:
- Direct key-value mappings
- Nested objects with version fields
- Complex nested structures

### Output Examples

**No Differences:**
```
============================================================
COMPARISON RESULTS
============================================================
✅ There is no difference in the deployed versions and latest version
============================================================
```

**With Differences:**
```
============================================================
COMPARISON RESULTS
============================================================
⚠️  VERSION DIFFERENCES DETECTED:

🔄 API:
   Deployed: v1.2.3
   Repository: v1.2.4

🔄 WEB:
   Deployed: v2.1.0
   Repository: v2.1.1
============================================================
```

## Error Handling

Both utilities include comprehensive error handling for:
- Network connectivity issues
- HTTP errors (404, 500, etc.)
- Request timeouts (30-second timeout)
- Invalid URLs
- GitHub API authentication errors
- JSON parsing errors
- Missing environment variables

## Security Notes

- GitHub PAT tokens should have appropriate repository read permissions
- Tokens are read from environment variables for security
- API calls include proper authentication headers
- Sensitive information is not logged in non-verbose mode 