#!/usr/bin/env python3
"""
Utility to fetch version information from StackGen environments.

This script fetches the content from https://<env_name>.stackgen.com/version.json
where env_name can be provided as a command-line argument or selected interactively.
"""

import argparse
import sys
import requests
from enum import Enum
from typing import Optional


class Environment(Enum):
    """Predefined environment names for StackGen."""
    PRODUCTION = "cloud"
    STAGING = "stage.dev"
    DEVELOPMENT = "main.dev"
    DEMO = "demo.cloud"
    
    @classmethod
    def get_display_names(cls) -> list[tuple[str, str]]:
        """Get a list of (display_name, value) tuples for menu display."""
        return [
            ("Production", cls.PRODUCTION.value),
            ("Staging", cls.STAGING.value),
            ("Development", cls.DEVELOPMENT.value),
            ("Demo", cls.DEMO.value),
        ]


def select_environment_interactively() -> str:
    """
    Display a menu for environment selection and return the selected environment.
    
    Returns:
        The selected environment name
    """
    environments = Environment.get_display_names()
    
    print("\nAvailable environments:")
    print("-" * 30)
    
    for i, (display_name, env_value) in enumerate(environments, 1):
        print(f"{i}. {display_name} ({env_value})")
    
    print("-" * 30)
    
    while True:
        try:
            choice = input(f"Select environment [1-{len(environments)}]: ").strip()
            
            if not choice:
                continue
                
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(environments):
                selected_env = environments[choice_num - 1][1]
                print(f"Selected: {environments[choice_num - 1][0]} ({selected_env})")
                return selected_env
            else:
                print(f"Please enter a number between 1 and {len(environments)}")
                
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(0)


def fetch_version_content(env_name: str) -> Optional[str]:
    """
    Fetch content from the version.json endpoint for the given environment.
    
    Args:
        env_name: The environment name to use in the URL
        
    Returns:
        The response content as string, or None if request failed
    """
    url = f"https://{env_name}.stackgen.com/version.json"
    
    try:
        print(f"Fetching content from: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching content from {url}: {e}", file=sys.stderr)
        return None


def main():
    """Main function to handle command-line arguments and fetch content."""
    parser = argparse.ArgumentParser(
        description="Fetch version information from StackGen environments"
    )
    parser.add_argument(
        "env_name",
        nargs="?",  # Make env_name optional
        help="Environment name (e.g., 'prod', 'staging', 'dev'). If not provided, will show interactive menu."
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Force interactive environment selection"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Determine environment name
    if args.interactive or args.env_name is None:
        # Use interactive selection
        env_name = select_environment_interactively()
    else:
        # Use command-line argument
        env_name = args.env_name
        
        # Validate against known environments if provided
        valid_envs = [env.value for env in Environment]
        if env_name not in valid_envs:
            print(f"Warning: '{env_name}' is not in the predefined environment list.")
            print(f"Valid environments: {', '.join(valid_envs)}")
            confirm = input("Continue anyway? (y/N): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("Operation cancelled.")
                sys.exit(0)
    
    if args.verbose:
        print(f"Environment: {env_name}")
    
    content = fetch_version_content(env_name)
    
    if content is not None:
        print("\n" + "="*50)
        print("RESPONSE CONTENT:")
        print("="*50)
        print(content)
        print("="*50)
    else:
        print("Failed to fetch content.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 