#!/usr/bin/env python3
"""
Version JSON Fetcher

This script fetches and displays the content from a version.json URL.
It can handle both JSON and plain text responses with proper formatting.

Usage:
    python fetch_version_json.py
    python fetch_version_json.py --url https://example.com/version.json
    python fetch_version_json.py --url https://stage.dev.stackgen.com/version.json --pretty
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import ssl
from typing import Optional


def fetch_url_content(url: str, timeout: int = 30) -> tuple[bool, str, Optional[dict]]:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch content from
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (success, content, parsed_json)
    """
    try:
        # Create request with proper headers
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        
        # Create SSL context that doesn't verify certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Fetch the content
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            content = response.read().decode('utf-8')
            
            # Try to parse as JSON
            try:
                parsed_json = json.loads(content)
                return True, content, parsed_json
            except json.JSONDecodeError:
                # Not valid JSON, return as plain text
                return True, content, None
                
    except urllib.error.HTTPError as e:
        return False, f"HTTP Error {e.code}: {e.reason}", None
    except urllib.error.URLError as e:
        return False, f"URL Error: {e.reason}", None
    except Exception as e:
        return False, f"Error: {str(e)}", None


def print_content(content: str, parsed_json: Optional[dict] = None, pretty: bool = False) -> None:
    """
    Print content to console with optional JSON formatting.
    
    Args:
        content: Raw content string
        parsed_json: Parsed JSON object (if available)
        pretty: Whether to use pretty formatting
    """
    if parsed_json is not None:
        print("JSON Content:")
        print("=" * 50)
        if pretty:
            print(json.dumps(parsed_json, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(parsed_json, ensure_ascii=False))
    else:
        print("Text Content:")
        print("=" * 50)
        print(content)


def main():
    """Main function to handle command-line arguments and fetch content."""
    parser = argparse.ArgumentParser(
        description="Fetch and display content from a version.json URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch from default URL
  python fetch_version_json.py
  
  # Fetch from custom URL
  python fetch_version_json.py --url https://example.com/version.json
  
  # Pretty print JSON
  python fetch_version_json.py --pretty
  
  # Custom timeout
  python fetch_version_json.py --timeout 60
        """
    )
    
    parser.add_argument(
        "--url", "-u",
        default="https://stage.dev.stackgen.com/version.json",
        help="URL to fetch content from (default: https://stage.dev.stackgen.com/version.json)"
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty print JSON content with indentation"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Always display raw content, don't try to parse as JSON"
    )
    
    args = parser.parse_args()
    
    print(f"Fetching content from: {args.url}")
    print(f"Timeout: {args.timeout} seconds")
    print("-" * 60)
    
    # Fetch content
    success, content, parsed_json = fetch_url_content(args.url, args.timeout)
    
    if not success:
        print(f"❌ Failed to fetch content: {content}", file=sys.stderr)
        sys.exit(1)
    
    # Display content
    if args.raw:
        print_content(content, None, args.pretty)
    else:
        print_content(content, parsed_json, args.pretty)
    
    # Additional info
    print("\n" + "-" * 60)
    print(f"Content length: {len(content)} characters")
    if parsed_json is not None:
        print(f"Content type: JSON")
        print(f"JSON keys: {list(parsed_json.keys()) if isinstance(parsed_json, dict) else 'Not a dictionary'}")
    else:
        print(f"Content type: Plain text")


if __name__ == "__main__":
    main()
