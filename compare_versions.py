#!/usr/bin/env python3
"""
Version Comparison Utility

This script fetches .env file content from a GitHub repository using GitHub PAT token
and compares it with the deployed version information from StackGen environments.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, Optional, Tuple
import requests
from fetch_version import fetch_version_content, Environment
from service_mapping import ServiceMapper


class GitHubEnvFetcher:
    """Handles fetching .env file content from GitHub repository."""
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize with GitHub PAT token.
        
        Args:
            token: GitHub Personal Access Token. If None, will try to get from env variables.
        """
        self.token = token or os.getenv('GITHUB_PAT') or os.getenv('GH_LOCAL_UTILS_TOKEN')
        if not self.token:
            raise ValueError(
                "GitHub PAT token not found. Set GITHUB_PAT or GH_TOKEN environment variable "
                "or pass token directly."
            )
        
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def fetch_env_file(self, repo: str, file_path: str = ".env", branch: str = "main") -> str:
        """
        Fetch .env file content from GitHub repository.
        
        Args:
            repo: Repository in format 'owner/repo'
            file_path: Path to .env file in repository
            branch: Branch name to fetch from
            
        Returns:
            Content of the .env file
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        params = {'ref': branch}
        
        try:
            print(f"Fetching {file_path} from {repo} (branch: {branch})")
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('encoding') == 'base64':
                import base64
                content = base64.b64decode(data['content']).decode('utf-8')
                return content
            else:
                raise ValueError(f"Unexpected encoding: {data.get('encoding')}")
                
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to fetch {file_path} from {repo}: {e}")


class VersionComparator:
    """Handles comparison between deployed versions and repository versions."""
    
    @staticmethod
    def parse_env_content(env_content: str) -> Dict[str, str]:
        """
        Parse .env file content and extract version information.
        
        Args:
            env_content: Content of .env file
            
        Returns:
            Dictionary mapping service names to versions
        """
        versions = {}
        
        # Look for VERSION patterns in .env file
        version_patterns = [
            r'(\w+)_VERSION\s*=\s*["\']?([^\s"\']+)["\']?',  # SERVICE_VERSION=1.2.3
            r'VERSION_(\w+)\s*=\s*["\']?([^\s"\']+)["\']?',  # VERSION_SERVICE=1.2.3
            r'(\w+)_TAG\s*=\s*["\']?([^\s"\']+)["\']?',      # SERVICE_TAG=v1.2.3
            r'IMAGE_(\w+)\s*=\s*["\']?[^:]+:([^\s"\']+)["\']?',  # IMAGE_SERVICE=repo:tag
            r'(SGAI_ORCHESTRATION|STACKGEN_NOTIFICATIONS|APPCD_ANALYZER|SGAI_KNOWLEDGE|SGAI_CONTROL)\s*=\s*["\']?([^\s"\']+)["\']?'  # Special cases
        ]
        
        for line in env_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            for pattern in version_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
                        service_name = match.group(1).lower()
                        version = match.group(2).strip()
                        versions[service_name] = version
                        break
        
        return versions
    
    @staticmethod
    def parse_version_json(version_content: str) -> Dict[str, str]:
        """
        Parse version.json content and extract version information.
        
        Args:
            version_content: JSON content from version endpoint
            
        Returns:
            Dictionary mapping service names to versions
        """
        try:
            data = json.loads(version_content)
            versions = {}
            
            # Handle different possible JSON structures
            if isinstance(data, dict):
                for key, value in data.items():
                    # Direct version mapping
                    if isinstance(value, str):
                        versions[key.lower()] = value
                    # Nested object with version field
                    elif isinstance(value, dict) and 'version' in value:
                        versions[key.lower()] = value['version']
                    # Handle arrays or other structures
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if 'version' in sub_key.lower() and isinstance(sub_value, str):
                                versions[f"{key.lower()}_{sub_key.lower()}"] = sub_value
            
            return versions
            
        except json.JSONDecodeError as e:
            # If not JSON, try to parse as plain text
            print(f"Warning: Could not parse as JSON ({e}), treating as plain text")
            return {"content": version_content.strip()}
    
    @staticmethod
    def compare_versions(deployed_versions: Dict[str, str], 
                        repo_versions: Dict[str, str]) -> Tuple[Dict[str, Dict[str, str]], bool]:
        """
        Compare deployed versions with repository versions using service mapping.
        
        Args:
            deployed_versions: Versions from deployed environment
            repo_versions: Versions from repository .env file
            
        Returns:
            Tuple of (comparison_results, has_differences)
            comparison_results maps service_name -> service_comparison_data
        """
        mapper = ServiceMapper()
        unified_comparison = mapper.create_unified_comparison(repo_versions, deployed_versions)
        
        differences = {}
        matches = {}
        env_only = {}
        deployed_only = {}
        
        for service, data in unified_comparison.items():
            env_ver = data["env_version"]
            deployed_ver = data["deployed_version"]
            
            if env_ver is None:
                deployed_only[service] = data
            elif deployed_ver is None:
                env_only[service] = data
            elif env_ver != deployed_ver:
                differences[service] = data
            else:
                matches[service] = data
        
        results = {
            "differences": differences,
            "matches": matches,
            "env_only": env_only,
            "deployed_only": deployed_only
        }
        
        has_differences = len(differences) > 0 or len(env_only) > 0 or len(deployed_only) > 0
        
        return results, has_differences


def main():
    """Main function to handle command-line arguments and perform comparison."""
    parser = argparse.ArgumentParser(
        description="Compare deployed versions with repository .env file versions"
    )
    parser.add_argument(
        "repo",
        help="GitHub repository in format 'owner/repo'"
    )
    parser.add_argument(
        "-e", "--env-file",
        default=".env",
        help="Path to .env file in repository (default: .env)"
    )
    parser.add_argument(
        "-b", "--branch",
        default="main",
        help="Branch to fetch .env file from (default: main)"
    )
    parser.add_argument(
        "-s", "--stackgen-env",
        help="StackGen environment name. If not provided, will use interactive selection."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize GitHub fetcher
        if args.verbose:
            print("Initializing GitHub API client...")
        
        github_fetcher = GitHubEnvFetcher()
        
        # Get StackGen environment
        if args.stackgen_env:
            # Validate against known environments
            valid_envs = [env.value for env in Environment]
            if args.stackgen_env not in valid_envs:
                print(f"Warning: '{args.stackgen_env}' is not in the predefined environment list.")
                print(f"Valid environments: {', '.join(valid_envs)}")
                confirm = input("Continue anyway? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    print("Operation cancelled.")
                    sys.exit(0)
            stackgen_env = args.stackgen_env
        else:
            # Use interactive selection from fetch_version module
            from fetch_version import select_environment_interactively
            stackgen_env = select_environment_interactively()
        
        print(f"\n{'='*60}")
        print(f"COMPARING VERSIONS")
        print(f"{'='*60}")
        print(f"Repository: {args.repo}")
        print(f"Env file: {args.env_file}")
        print(f"Branch: {args.branch}")
        print(f"StackGen Environment: {stackgen_env}")
        print(f"{'='*60}")
        
        # Fetch .env file content
        env_content = github_fetcher.fetch_env_file(args.repo, args.env_file, args.branch)
        
        if args.verbose:
            print(f"\n.env file content preview:")
            print("-" * 40)
            print(env_content[:500] + ("..." if len(env_content) > 500 else ""))
            print("-" * 40)
        
        # Fetch deployed version content
        deployed_content = fetch_version_content(stackgen_env)
        if not deployed_content:
            print("Failed to fetch deployed version information.")
            sys.exit(1)
        
        if args.verbose:
            print(f"\nDeployed version content:")
            print("-" * 40)
            print(deployed_content)
            print("-" * 40)
        
        # Parse versions
        comparator = VersionComparator()
        repo_versions = comparator.parse_env_content(env_content)
        deployed_versions = comparator.parse_version_json(deployed_content)
        
        if args.verbose:
            print(f"\nParsed repository versions: {repo_versions}")
            print(f"Parsed deployed versions: {deployed_versions}")
        
        # Compare versions
        comparison_results, has_differences = comparator.compare_versions(deployed_versions, repo_versions)
        
        print(f"\n{'='*60}")
        print("COMPARISON RESULTS")
        print(f"{'='*60}")
        
        if has_differences:
            differences = comparison_results["differences"]
            env_only = comparison_results["env_only"]
            deployed_only = comparison_results["deployed_only"]
            matches = comparison_results["matches"]
            
            if differences:
                print("⚠️  VERSION DIFFERENCES DETECTED:")
                print()
                
                for service, data in differences.items():
                    env_name = data["env_name"] or "N/A"
                    deployed_name = data["deployed_name"] or "N/A"
                    env_ver = data["env_version"] or "N/A"
                    deployed_ver = data["deployed_version"] or "N/A"
                    
                    print(f"🔄 {env_name.upper()} → {deployed_name.upper()}:")
                    print(f"   Repository (.env): {env_ver}")
                    print(f"   Deployed: {deployed_ver}")
                    print()
            
            if env_only:
                print("📝 SERVICES ONLY IN .ENV:")
                print()
                for service, data in env_only.items():
                    print(f"   {data['env_name']}: {data['env_version']} (not deployed)")
                print()
            
            if deployed_only:
                print("🚀 SERVICES ONLY IN DEPLOYED:")
                print()
                for service, data in deployed_only.items():
                    print(f"   {data['deployed_name']}: {data['deployed_version']} (not in .env)")
                print()
                
            # Show matching services in verbose mode
            if args.verbose and matches:
                print("✅ MATCHING VERSIONS:")
                print()
                for service, data in matches.items():
                    env_name = data["env_name"]
                    deployed_name = data["deployed_name"]
                    version = data["env_version"]
                    print(f"   {env_name} → {deployed_name}: {version}")
                print()
        else:
            print("✅ There is no difference in the deployed versions and latest version")
        
        print(f"{'='*60}")
        
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 