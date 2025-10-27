#!/usr/bin/env python3
"""
Process All Repositories from input.json

This script reads input.json, calls fetchTicketChangesInBuildsForRepo.py for each
repository that has version changes, and generates a consolidated JSON output with
all Linear tickets found across all services.

Usage:
    python process_all_repos.py
    python process_all_repos.py --input input.json --output changes.json
    python process_all_repos.py --skip-unchanged
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
import requests


class RepositoryProcessor:
    """Process multiple repositories and extract Linear tickets from version changes."""
    
    def __init__(self, skip_unchanged: bool = True, verbose: bool = False, 
                 fetch_linear_details: bool = True):
        """
        Initialize the processor.
        
        Args:
            skip_unchanged: Skip repositories where current_tag == new_tag
            verbose: Enable verbose output
            fetch_linear_details: Whether to fetch ticket details from Linear API
        """
        self.skip_unchanged = skip_unchanged
        self.verbose = verbose
        self.fetch_linear_details = fetch_linear_details
        self.ticket_pattern = re.compile(r'\[([A-Z]{2,6}-\d{1,6})\]')
        self.linear_api_key = os.getenv('LINEAR_API_KEY')
        self.linear_api_url = "https://api.linear.app/graphql"
    
    def extract_repo_path(self, repo_url: str) -> Optional[str]:
        """
        Extract owner/repo path from GitHub URL.
        
        Args:
            repo_url: Full GitHub repository URL
            
        Returns:
            Repository path in format 'owner/repo' or None if invalid
        """
        try:
            # Parse the URL
            parsed = urlparse(repo_url)
            # Extract path and remove leading/trailing slashes
            path = parsed.path.strip('/')
            # Remove .git suffix if present
            if path.endswith('.git'):
                path = path[:-4]
            return path
        except Exception as e:
            print(f"Error parsing repository URL '{repo_url}': {e}", file=sys.stderr)
            return None
    
    def call_compare_tags(self, repo: str, from_tag: str, to_tag: str) -> str:
        """
        Call compare_tags.py directly and return its output.
        
        Args:
            repo: Repository in format 'owner/repo'
            from_tag: Starting tag
            to_tag: Ending tag
            
        Returns:
            Output from compare_tags.py as string
        """
        cmd = [
            sys.executable,
            'compare_tags.py',
            repo,
            from_tag,
            to_tag
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode != 0:
                if self.verbose:
                    print(f"  ⚠️  Warning: compare_tags.py returned error: {result.stderr}", file=sys.stderr)
                return ""
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Warning: Timeout fetching changes for {repo}", file=sys.stderr)
            return ""
        except FileNotFoundError:
            print("Error: compare_tags.py not found", file=sys.stderr)
            return ""
        except Exception as e:
            print(f"  ⚠️  Warning: Error calling compare_tags.py for {repo}: {e}", file=sys.stderr)
            return ""
    
    def extract_tickets_from_text(self, text: str) -> Set[str]:
        """
        Extract Linear tickets from text.
        
        Args:
            text: Text containing commit messages
            
        Returns:
            Set of unique Linear tickets found
        """
        tickets = set()
        matches = self.ticket_pattern.findall(text)
        for match in matches:
            tickets.add(match)
        return tickets
    
    def fetch_ticket_details(self, ticket_id: str) -> Optional[Dict[str, str]]:
        """
        Fetch ticket details from Linear API.
        
        Args:
            ticket_id: Linear ticket ID (e.g., 'PROJ-123')
            
        Returns:
            Dictionary with ticket details or None if fetch fails
        """
        if not self.linear_api_key:
            return None
        
        query = """
        query IssueByIdentifier($identifier: String!) {
            issue(id: $identifier) {
                id
                identifier
                title
                state {
                    name
                }
                priority
                assignee {
                    name
                }
            }
        }
        """
        
        headers = {
            "Authorization": self.linear_api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "variables": {"identifier": ticket_id}
        }
        
        try:
            response = requests.post(
                self.linear_api_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'errors' in data:
                    return None
                
                if 'data' in data and data['data'].get('issue'):
                    issue = data['data']['issue']
                    return {
                        'id': issue['identifier'],
                        'title': issue['title'],
                        'state': issue['state']['name'] if issue.get('state') else 'Unknown',
                        'priority': issue.get('priority', 0),
                        'assignee': issue['assignee']['name'] if issue.get('assignee') else 'Unassigned'
                    }
            
            return None
        except Exception:
            return None
    
    def fetch_all_ticket_details(self, tickets: Set[str]) -> Dict[str, Optional[Dict[str, str]]]:
        """
        Fetch details for all tickets from Linear API.
        
        Args:
            tickets: Set of ticket IDs
            
        Returns:
            Dictionary mapping ticket IDs to their details
        """
        if not self.fetch_linear_details or not self.linear_api_key:
            return {ticket: None for ticket in tickets}
        
        ticket_details = {}
        total = len(tickets)
        
        if self.verbose and total > 0:
            print(f"\n📋 Fetching Linear ticket details for {total} unique tickets...")
        
        for idx, ticket in enumerate(sorted(tickets), 1):
            if self.verbose and total > 0:
                print(f"  [{idx}/{total}] Fetching {ticket}...", end='\r')
            
            details = self.fetch_ticket_details(ticket)
            ticket_details[ticket] = details
        
        if self.verbose and total > 0:
            successful = sum(1 for d in ticket_details.values() if d is not None)
            print(f"\n  ✅ Successfully fetched {successful}/{total} ticket details\n")
        
        return ticket_details
    
    def should_process_service(self, service: Dict) -> bool:
        """
        Determine if a service should be processed.
        
        Args:
            service: Service dictionary from input.json
            
        Returns:
            True if service should be processed
        """
        current = service.get('current_tag', '')
        new = service.get('new_tag', '')
        
        # Skip if both tags are empty
        if not current and not new:
            return False
        
        # Skip if tags are the same and skip_unchanged is True
        if self.skip_unchanged and current == new:
            return False
        
        return True
    
    def process_service(self, service: Dict) -> Optional[Dict]:
        """
        Process a single service and extract ticket changes.
        
        Args:
            service: Service dictionary from input.json
            
        Returns:
            Dictionary with service info and tickets, or None if failed
        """
        service_name = service.get('service', 'unknown')
        repo_url = service.get('repository', '')
        current_tag = service.get('current_tag', '')
        new_tag = service.get('new_tag', '')
        version_key = service.get('version_key', '')
        
        # Extract repo path
        repo_path = self.extract_repo_path(repo_url)
        if not repo_path:
            print(f"  ❌ Invalid repository URL for {service_name}", file=sys.stderr)
            return None
        
        print(f"  📦 Processing {service_name} ({current_tag} → {new_tag})...")
        
        # Handle empty current_tag - might be a new service
        if not current_tag and new_tag:
            print(f"     ℹ️  New service detected, skipping (no previous version to compare)")
            return {
                'service': service_name,
                'repository': repo_url,
                'repo_path': repo_path,
                'version_key': version_key,
                'current_tag': current_tag,
                'new_tag': new_tag,
                'status': 'new_service',
                'tickets': [],
                'ticket_count': 0,
                'error': None
            }
        
        # Handle empty new_tag
        if not new_tag:
            print(f"     ℹ️  No new version specified, skipping")
            return {
                'service': service_name,
                'repository': repo_url,
                'repo_path': repo_path,
                'version_key': version_key,
                'current_tag': current_tag,
                'new_tag': new_tag,
                'status': 'no_new_version',
                'tickets': [],
                'ticket_count': 0,
                'error': None
            }
        
        # Call compare_tags.py
        output = self.call_compare_tags(repo_path, current_tag, new_tag)
        
        if not output:
            return {
                'service': service_name,
                'repository': repo_url,
                'repo_path': repo_path,
                'version_key': version_key,
                'current_tag': current_tag,
                'new_tag': new_tag,
                'status': 'error',
                'tickets': [],
                'ticket_count': 0,
                'error': 'Failed to fetch commits or no commits found'
            }
        
        # Extract tickets
        tickets = self.extract_tickets_from_text(output)
        sorted_tickets = sorted(tickets)
        
        if tickets:
            print(f"     ✅ Found {len(tickets)} tickets")
        else:
            print(f"     ℹ️  No tickets found")
        
        return {
            'service': service_name,
            'repository': repo_url,
            'repo_path': repo_path,
            'version_key': version_key,
            'current_tag': current_tag,
            'new_tag': new_tag,
            'status': 'success',
            'tickets': sorted_tickets,
            'ticket_count': len(tickets),
            'error': None
        }
    
    def process_all_services(self, services: List[Dict]) -> Dict:
        """
        Process all services and generate consolidated report.
        
        Args:
            services: List of service dictionaries from input.json
            
        Returns:
            Dictionary with all results and summary
        """
        print("=" * 70)
        print("Processing All Repositories")
        print("=" * 70)
        
        results = []
        total_services = len(services)
        processed = 0
        skipped = 0
        failed = 0
        total_tickets = set()
        
        for i, service in enumerate(services, 1):
            print(f"\n[{i}/{total_services}] {service.get('service', 'unknown')}")
            
            if not self.should_process_service(service):
                print(f"  ⏭️  Skipping (no changes)")
                skipped += 1
                continue
            
            result = self.process_service(service)
            if result:
                results.append(result)
                if result['status'] == 'success':
                    processed += 1
                    total_tickets.update(result['tickets'])
                elif result['status'] == 'error':
                    failed += 1
            else:
                failed += 1
        
        # Generate summary
        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Total services: {total_services}")
        print(f"Processed: {processed}")
        print(f"Skipped (no changes): {skipped}")
        print(f"Failed: {failed}")
        print(f"Unique tickets across all services: {len(total_tickets)}")
        
        # Group tickets by project
        projects = {}
        for ticket in total_tickets:
            prefix = ticket.split('-')[0]
            if prefix not in projects:
                projects[prefix] = []
            projects[prefix].append(ticket)
        
        if projects:
            print(f"\nTickets by project:")
            for prefix in sorted(projects.keys()):
                print(f"  - {prefix}: {len(projects[prefix])} tickets")
        
        # Collect all unique tickets
        all_tickets_set = set()
        for result in results:
            if result["status"] == "success":
                for ticket in result["tickets"]:
                    all_tickets_set.add(ticket)
        
        # Fetch Linear details for all unique tickets
        ticket_details_map = self.fetch_all_ticket_details(all_tickets_set)
        
        # Build all_tickets array as strings: "TICKET-ID: Summary"
        all_tickets = []
        for ticket_id in sorted(all_tickets_set):
            details = ticket_details_map.get(ticket_id)
            if details and details.get('title'):
                # Format: "AE-1234: Ticket Summary"
                all_tickets.append(f"{ticket_id}: {details['title']}")
            else:
                # If no details available, just include the ID
                all_tickets.append(ticket_id)
        
        # Group tickets by project (still using IDs for backward compatibility)
        tickets_by_project = {}
        for ticket_id in sorted(all_tickets_set):
            prefix = ticket_id.split('-')[0]
            if prefix not in tickets_by_project:
                tickets_by_project[prefix] = []
            tickets_by_project[prefix].append(ticket_id)
        
        for prefix in tickets_by_project:
            tickets_by_project[prefix] = sorted(tickets_by_project[prefix])
        
        # Generate output structure
        return {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_services': total_services,
                'processed': processed,
                'skipped': skipped,
                'failed': failed,
                'total_unique_tickets': len(all_tickets_set)
            },
            'services': results,
            'all_tickets': all_tickets,
            'tickets_by_project': tickets_by_project
        }


def main():
    """Main function to handle command-line arguments and process repositories."""
    parser = argparse.ArgumentParser(
        description="Process all repositories from input.json and extract ticket changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all repositories with changes
  python process_all_repos.py
  
  # Process all repositories including unchanged ones
  python process_all_repos.py --include-unchanged
  
  # Custom input and output files
  python process_all_repos.py --input custom_input.json --output results.json
  
  # Verbose output
  python process_all_repos.py --verbose
        """
    )
    
    parser.add_argument(
        "--input", "-i",
        default="generated_files/input_file/input.json",
        help="Input JSON file (default: generated_files/input_file/input.json)"
    )
    parser.add_argument(
        "--output", "-o",
        default="generated_files/final_tag_differences.json",
        help="Output JSON file (default: generated_files/final_tag_differences.json)"
    )
    parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include services with no version changes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output"
    )
    parser.add_argument(
        "--no-fetch-details",
        action="store_true",
        help="Skip fetching ticket details from Linear API"
    )
    
    args = parser.parse_args()
    
    # Read input file
    try:
        with open(args.input, 'r') as f:
            services = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(services, list):
        print("Error: Input JSON must be an array of service objects", file=sys.stderr)
        sys.exit(1)
    
    # Use output file from args
    output_file = args.output
    
    # Create output directory if it doesn't exist
    output_dir = Path(output_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.verbose:
        print(f"📝 Output file: {output_file}")
    
    # Initialize processor
    processor = RepositoryProcessor(
        skip_unchanged=not args.include_unchanged,
        verbose=args.verbose,
        fetch_linear_details=not args.no_fetch_details if hasattr(args, 'no_fetch_details') else True
    )
    
    # Process all services
    results = processor.process_all_services(services)
    
    # Write output
    try:
        with open(output_file, 'w') as f:
            if args.pretty:
                json.dump(results, f, indent=2, ensure_ascii=False)
            else:
                json.dump(results, f, ensure_ascii=False)
        
        print(f"\n✅ Results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

