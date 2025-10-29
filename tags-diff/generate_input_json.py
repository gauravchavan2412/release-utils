#!/usr/bin/env python3
"""
Generate Input JSON for Tag Comparison

This script creates a mapping of services to their version keys, fetches current deployed
versions from version.json and new versions from the GitHub .env file, then generates
an input.json file with current and new tag combinations.

Usage:
    python generate_input_json.py
    python generate_input_json.py --version-url https://stage.dev.stackgen.com/version.json
    python generate_input_json.py --env-url https://raw.githubusercontent.com/appcd-dev/appcd-dist/main/.env
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import ssl
from typing import Dict, Optional, Tuple
import re


# Service to version key and repository mapping
SERVICE_VERSION_MAP = {
    "ui": {
        "version_key": "APPCDUI_VERSION",
        "repository": "https://github.com/appcd-dev/appcd-ui"
    },
    "appcd": {
        "version_key": "APPCD_VERSION",
        "repository": "https://github.com/appcd-dev/appcd"
    },
    "iac-gen": {
        "version_key": "IACGEN_VERSION",
        "repository": "https://github.com/appcd-dev/iac-gen"
    },
    "exporter": {
        "version_key": "STACK_EXPORTER_VERSION",
        "repository": "https://github.com/appcd-dev/stack-exporter"
    },
    "vault": {
        "version_key": "STACKGEN_VAULT_VERSION",
        "repository": "https://github.com/appcd-dev/stackgen-vault"
    },
    "integrations": {
        "version_key": "INTEGRATIONS_VERSION",
        "repository": "https://github.com/appcd-dev/integrations"
    },
    "backstage-adapter": {
        "version_key": "BACKSTAGE_ADAPTER_VERSION",
        "repository": "https://github.com/appcd-dev/backstage-adapter"
    },
    "infra-catalog-tracker": {
        "version_key": "INFRA_CATALOG_TRACKER_VERSION",
        "repository": "https://github.com/appcd-dev/infra-catalog-tracker"
    },
    "sgai-orchestration": {
        "version_key": "SGAI_ORCHESTRATION",
        "repository": "https://github.com/appcd-dev/sgai-orchestration"
    },
    "deployment-manager": {
        "version_key": "DEPLOYMENT_MANAGER_VERSION",
        "repository": "https://github.com/appcd-dev/deployment-manager"
    },
    "notifications": {
        "version_key": "STACKGEN_NOTIFICATION",
        "repository": "https://github.com/appcd-dev/stackgen-notification"
    },
    "tf-module-service": {
        "version_key": "TF_MODULE_SERVICE_VERSION",
        "repository": "https://github.com/appcd-dev/tf-module-service"
    },
    "audit-manager": {
        "version_key": "AUDIT_MANAGER_VERSION",
        "repository": "https://github.com/appcd-dev/audit-manager"
    },
    "aiden": {
        "version_key": "AIDEN_VERSION",
        "repository": "https://github.com/appcd-dev/aiden"
    },
    "aiden-ui": {
        "version_key": "AIDEN_UI_VERSION",
        "repository": "https://github.com/appcd-dev/aiden-ui-v2"
    }
}


def fetch_url_content(url: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch content from
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (success, content)
    """
    try:
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        # Create SSL context that doesn't verify certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            content = response.read().decode('utf-8')
            return True, content
                
    except urllib.error.HTTPError as e:
        return False, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"URL Error: {e.reason}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def parse_version_json(content: str) -> Optional[Dict[str, str]]:
    """
    Parse version.json content.
    
    Args:
        content: Raw JSON content
        
    Returns:
        Dictionary of version keys and values
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse version.json: {e}", file=sys.stderr)
        return None


def parse_env_file(content: str) -> Dict[str, str]:
    """
    Parse .env file content.
    
    Args:
        content: Raw .env file content
        
    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    for line in content.split('\n'):
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        # Parse KEY=VALUE format
        match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$', line)
        if match:
            key, value = match.groups()
            # Remove quotes if present
            value = value.strip().strip('"').strip("'")
            env_vars[key] = value
    
    return env_vars


def generate_input_json(current_versions: Dict[str, str], new_versions: Dict[str, str]) -> list:
    """
    Generate input JSON structure with current and new tag combinations.
    
    Args:
        current_versions: Dictionary of currently deployed versions (from version.json)
                         Keys are service names (e.g., "ui", "appcd")
        new_versions: Dictionary of new versions from .env file
                     Keys are environment variable names (e.g., "APPCDUI_VERSION")
        
    Returns:
        List of dictionaries with service, repository, version_key, current_tag, and new_tag
    """
    result = []
    
    for service_name, service_info in SERVICE_VERSION_MAP.items():
        version_key = service_info["version_key"]
        repository = service_info["repository"]
        
        # Current versions use service names as keys (from version.json)
        # Default to v1.0.0 if version not found
        current_tag = current_versions.get(service_name, "v1.0.0")
        # New versions use environment variable names as keys (from .env)
        new_tag = new_versions.get(version_key, "")
        
        # Only include if at least one version exists
        if current_tag or new_tag:
            result.append({
                "service": service_name,
                "repository": repository,
                "version_key": version_key,
                "current_tag": current_tag,
                "new_tag": new_tag
            })
    
    return result


def read_local_env_file(file_path: str) -> Optional[Dict[str, str]]:
    """
    Read and parse a local .env file.
    
    Args:
        file_path: Path to the .env file
        
    Returns:
        Dictionary of environment variables or None if failed
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return parse_env_file(content)
    except Exception as e:
        print(f"❌ Failed to read local .env file: {e}", file=sys.stderr)
        return None


def main():
    """Main function to handle command-line arguments and generate input.json."""
    parser = argparse.ArgumentParser(
        description="Generate input.json with current and new version tags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate with default URLs
  python generate_input_json.py
  
  # Custom version.json URL
  python generate_input_json.py --version-url https://prod.example.com/version.json
  
  # Use local .env file
  python generate_input_json.py --env-file .env
  
  # Custom output file
  python generate_input_json.py --output my_input.json
        """
    )
    
    parser.add_argument(
        "--version-url",
        default="https://stage.dev.stackgen.com/version.json",
        help="URL to fetch current version.json from (default: stage.dev.stackgen.com)"
    )
    parser.add_argument(
        "--env-url",
        help="URL to fetch new .env file from (e.g., GitHub raw URL)"
    )
    parser.add_argument(
        "--env-file",
        help="Path to local .env file to use instead of URL"
    )
    parser.add_argument(
        "--output", "-o",
        default="generated_files/input_file/input.json",
        help="Output file path (default: generated_files/input_file/input.json)"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.env_url and not args.env_file:
        print("❌ Error: Either --env-url or --env-file must be provided", file=sys.stderr)
        print("\nExamples:")
        print("  python generate_input_json.py --env-file .env")
        print("  python generate_input_json.py --env-url https://raw.githubusercontent.com/.../main/.env")
        sys.exit(1)
    
    if args.env_url and args.env_file:
        print("⚠️  Warning: Both --env-url and --env-file provided. Using --env-file", file=sys.stderr)
    
    print("=" * 70)
    print("Generating Input JSON for Tag Comparison")
    print("=" * 70)
    
    # Fetch current versions from version.json
    print(f"\n📥 Fetching current versions from: {args.version_url}")
    success, content = fetch_url_content(args.version_url, args.timeout)
    
    if not success:
        print(f"❌ Failed to fetch version.json: {content}", file=sys.stderr)
        sys.exit(1)
    
    current_versions = parse_version_json(content)
    if current_versions is None:
        sys.exit(1)
    
    print(f"✅ Successfully fetched current versions ({len(current_versions)} keys)")
    
    # Fetch new versions from .env file (local or URL)
    new_versions = None
    
    if args.env_file:
        print(f"\n📥 Reading new versions from local file: {args.env_file}")
        new_versions = read_local_env_file(args.env_file)
    else:
        print(f"\n📥 Fetching new versions from: {args.env_url}")
        success, content = fetch_url_content(args.env_url, args.timeout)
        
        if not success:
            print(f"❌ Failed to fetch .env file: {content}", file=sys.stderr)
            sys.exit(1)
        
        new_versions = parse_env_file(content)
    
    if new_versions is None:
        sys.exit(1)
    
    print(f"✅ Successfully fetched new versions ({len(new_versions)} keys)")
    
    # Generate input JSON
    print(f"\n🔄 Generating input JSON...")
    input_data = generate_input_json(current_versions, new_versions)
    
    # Write to file
    output_path = args.output
    
    # Create directory if it doesn't exist
    from pathlib import Path
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(output_path, 'w') as f:
            if args.pretty:
                json.dump(input_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(input_data, f, ensure_ascii=False)
        
        print(f"✅ Successfully wrote {len(input_data)} service mappings to: {output_path}")
        
        # Display summary
        print("\n" + "=" * 70)
        print("Summary:")
        print("=" * 70)
        for item in input_data:
            status = "🔄" if item["current_tag"] != item["new_tag"] else "✓"
            print(f"{status} {item['service']:25} {item['current_tag']:20} → {item['new_tag']}")
        
        print("\n" + "=" * 70)
        print(f"✅ Input JSON generated successfully: {output_path}")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Failed to write output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

