#!/usr/bin/env python3
"""
Linear Ticket Extractor for Git Tag Comparisons

This script calls compare_tags.py to get commit differences between two tags
and extracts Linear tickets from commit messages, saving them to a text file.

Linear tickets are expected to be in the format [ABCD-12345] within commit messages.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set
from pathlib import Path
import requests


class LinearTicketExtractor:
    """Extracts Linear tickets from commit messages by calling compare_tags.py."""
    
    def __init__(self, api_key: Optional[str] = None, debug: bool = False):
        """Initialize the extractor with the Linear ticket pattern."""
        # Pattern to match Linear tickets: [ABCD-12345] format
        # Where ABCD is 2-4 uppercase letters and 12345 is 1-6 digits
        self.ticket_pattern = re.compile(r'\[([A-Z]{2,6}-\d{1,6})\]')
        self.api_key = api_key or os.getenv('LINEAR_API_KEY')
        self.linear_api_url = "https://api.linear.app/graphql"
        self.debug = debug
    
    def call_compare_tags(self, repo: str, from_tag: str, to_tag: str, 
                         no_commits: bool = False, no_files: bool = False,
                         details: bool = False, verbose: bool = False) -> str:
        """
        Call compare_tags.py and return its output.
        
        Args:
            repo: Repository in format 'owner/repo'
            from_tag: Starting tag
            to_tag: Ending tag
            no_commits: Whether to skip commit list
            no_files: Whether to skip file changes
            details: Whether to show detailed diff information
            verbose: Whether to enable verbose output
            
        Returns:
            Output from compare_tags.py as string
        """
        # Build the command
        cmd = [
            sys.executable, 
            'compare_tags.py',
            repo,
            from_tag,
            to_tag
        ]
        
        if no_commits:
            cmd.append('--no-commits')
        if no_files:
            cmd.append('--no-files')
        if details:
            cmd.append('--details')
        if verbose:
            cmd.append('--verbose')
        
        try:
            # Run the command and capture output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent  # Run from tags-diff directory
            )
            
            if result.returncode != 0:
                print(f"Error running compare_tags.py: {result.stderr}", file=sys.stderr)
                return ""
            
            return result.stdout
            
        except FileNotFoundError:
            print("Error: compare_tags.py not found. Make sure it's in the parent directory.", file=sys.stderr)
            return ""
        except Exception as e:
            print(f"Error calling compare_tags.py: {e}", file=sys.stderr)
            return ""
    
    def extract_tickets_from_text(self, text: str) -> Set[str]:
        """
        Extract Linear tickets from a text string.
        
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
        if not self.api_key:
            return None
        
        # Use the issue query with the ticket identifier (not UUID)
        # Linear API v2022-03-04+ supports searching by identifier directly
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
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "variables": {"identifier": ticket_id}
        }
        
        try:
            if self.debug:
                print(f"\nDebug: Fetching {ticket_id}", file=sys.stderr)
                print(f"Debug: API URL: {self.linear_api_url}", file=sys.stderr)
                print(f"Debug: Headers: {{'Authorization': '***', 'Content-Type': 'application/json'}}", file=sys.stderr)
            
            response = requests.post(
                self.linear_api_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if self.debug:
                print(f"Debug: Response status: {response.status_code}", file=sys.stderr)
                print(f"Debug: Response body: {response.text[:500]}", file=sys.stderr)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for errors in the response
                if 'errors' in data:
                    error_msg = data['errors'][0].get('message', 'Unknown error')
                    print(f"Warning: Linear API error for {ticket_id}: {error_msg}", file=sys.stderr)
                    if self.debug:
                        print(f"Debug: Full error response: {json.dumps(data['errors'], indent=2)}", file=sys.stderr)
                    return None
                
                # Extract issue from response
                if 'data' in data and data['data'].get('issue'):
                    issue = data['data']['issue']
                    if self.debug:
                        print(f"Debug: Successfully fetched {ticket_id}: {issue.get('title', 'No title')}", file=sys.stderr)
                    return {
                        'id': issue['identifier'],
                        'title': issue['title'],
                        'state': issue['state']['name'] if issue.get('state') else 'Unknown',
                        'priority': issue.get('priority', 'Unknown'),
                        'assignee': issue['assignee']['name'] if issue.get('assignee') else 'Unassigned'
                    }
                else:
                    if self.debug:
                        print(f"Debug: No issue found in response for {ticket_id}", file=sys.stderr)
                        print(f"Debug: Response data: {json.dumps(data, indent=2)}", file=sys.stderr)
            elif response.status_code == 400:
                print(f"Warning: Bad request for {ticket_id}. The ticket ID might be invalid.", file=sys.stderr)
                if self.debug:
                    print(f"Debug: Response text: {response.text}", file=sys.stderr)
                return None
            elif response.status_code == 401:
                print(f"Error: Invalid Linear API key. Please check your LINEAR_API_KEY.", file=sys.stderr)
                return None
            else:
                print(f"Warning: Linear API returned status {response.status_code} for {ticket_id}", file=sys.stderr)
                if self.debug:
                    print(f"Debug: Response text: {response.text}", file=sys.stderr)
            
            return None
        except requests.exceptions.Timeout:
            print(f"Warning: Timeout fetching details for {ticket_id}", file=sys.stderr)
            return None
        except requests.exceptions.RequestException as e:
            print(f"Warning: Network error fetching details for {ticket_id}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Warning: Failed to fetch details for {ticket_id}: {e}", file=sys.stderr)
            return None
    
    def fetch_all_ticket_details(self, tickets: Set[str], verbose: bool = False) -> Dict[str, Optional[Dict[str, str]]]:
        """
        Fetch details for all tickets.
        
        Args:
            tickets: Set of ticket IDs
            verbose: Whether to show progress
            
        Returns:
            Dictionary mapping ticket IDs to their details
        """
        if not self.api_key:
            if verbose:
                print("Note: LINEAR_API_KEY not set. Ticket summaries will not be fetched.", file=sys.stderr)
            return {ticket: None for ticket in tickets}
        
        ticket_details = {}
        total = len(tickets)
        
        if verbose:
            print(f"\nFetching details for {total} tickets from Linear API...")
        
        for idx, ticket in enumerate(sorted(tickets), 1):
            if verbose:
                print(f"  [{idx}/{total}] Fetching {ticket}...", end='\r')
            
            details = self.fetch_ticket_details(ticket)
            ticket_details[ticket] = details
        
        if verbose:
            print()  # New line after progress
            successful = sum(1 for d in ticket_details.values() if d is not None)
            print(f"Successfully fetched {successful}/{total} ticket details.\n")
        
        return ticket_details
    
    def save_tickets_to_file(self, tickets: Set[str], output_file: str, 
                           repo: str, from_tag: str, to_tag: str,
                           ticket_details: Optional[Dict[str, Optional[Dict[str, str]]]] = None) -> bool:
        """
        Save extracted tickets to a text file with metadata.
        
        Args:
            tickets: Set of Linear tickets
            output_file: Path to output file
            repo: Repository name
            from_tag: Starting tag
            to_tag: Ending tag
            ticket_details: Optional dictionary of ticket details from Linear API
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Sort tickets for consistent output
            sorted_tickets = sorted(tickets)
            
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write("Linear Tickets Found in Git Tag Comparison\n")
                file.write("=" * 80 + "\n\n")
                file.write(f"Repository: {repo}\n")
                file.write(f"From Tag: {from_tag}\n")
                file.write(f"To Tag: {to_tag}\n")
                file.write(f"Extraction Date: {self._get_current_timestamp()}\n\n")
                
                if not sorted_tickets:
                    file.write("No Linear tickets found in the commit messages.\n")
                else:
                    file.write(f"Total tickets found: {len(sorted_tickets)}\n\n")
                    
                    file.write("Tickets:\n")
                    file.write("=" * 80 + "\n")
                    
                    for ticket in sorted_tickets:
                        details = ticket_details.get(ticket) if ticket_details else None
                        
                        if details:
                            file.write(f"\n{ticket}: {details['title']}\n")
                            file.write(f"  State: {details['state']} | Assignee: {details['assignee']}\n")
                        else:
                            file.write(f"\n{ticket}\n")
                            if ticket_details is not None:  # API was attempted but failed
                                file.write(f"  (Details not available)\n")
                    
                    file.write(f"\n\nSummary:\n")
                    file.write("=" * 80 + "\n")
                    file.write(f"Total unique tickets: {len(sorted_tickets)}\n")
                    
                    # Group by project prefix
                    projects = {}
                    for ticket in sorted_tickets:
                        prefix = ticket.split('-')[0]
                        if prefix not in projects:
                            projects[prefix] = []
                        projects[prefix].append(ticket)
                    
                    file.write(f"Projects involved: {', '.join(sorted(projects.keys()))}\n")
                    for prefix, project_tickets in sorted(projects.items()):
                        file.write(f"  - {prefix}: {len(project_tickets)} tickets\n")
            
            return True
        except Exception as e:
            print(f"Error writing to file '{output_file}': {e}", file=sys.stderr)
            return False
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as string."""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def print_tickets(self, tickets: Set[str], repo: str, from_tag: str, to_tag: str, 
                     verbose: bool = False, ticket_details: Optional[Dict[str, Optional[Dict[str, str]]]] = None):
        """
        Print extracted tickets to console.
        
        Args:
            tickets: Set of Linear tickets
            repo: Repository name
            from_tag: Starting tag
            to_tag: Ending tag
            verbose: Whether to show detailed information
            ticket_details: Optional dictionary of ticket details from Linear API
        """
        print(f"\nLinear Tickets Found in {repo} ({from_tag} → {to_tag})")
        print("=" * 80)
        
        if not tickets:
            print("No Linear tickets found in the commit messages.")
            return
        
        sorted_tickets = sorted(tickets)
        
        if verbose:
            print(f"Total tickets found: {len(sorted_tickets)}\n")
            
            for ticket in sorted_tickets:
                details = ticket_details.get(ticket) if ticket_details else None
                
                if details:
                    print(f"\n{ticket}: {details['title']}")
                    print(f"  State: {details['state']} | Assignee: {details['assignee']}")
                else:
                    print(f"\n{ticket}")
                    if ticket_details is not None:
                        print(f"  (Details not available)")
            
            # Group by project prefix
            projects = {}
            for ticket in sorted_tickets:
                prefix = ticket.split('-')[0]
                if prefix not in projects:
                    projects[prefix] = []
                projects[prefix].append(ticket)
            
            print(f"\n\nSummary by project:")
            for prefix, project_tickets in sorted(projects.items()):
                print(f"- {prefix}: {len(project_tickets)} tickets")
        else:
            print(f"Found {len(sorted_tickets)} Linear tickets:\n")
            
            for ticket in sorted_tickets:
                details = ticket_details.get(ticket) if ticket_details else None
                
                if details:
                    print(f"{ticket}: {details['title']}")
                else:
                    print(f"{ticket}")


def main():
    """Main function to handle command-line arguments and extract tickets."""
    parser = argparse.ArgumentParser(
        description="Extract Linear tickets from Git tag comparison using compare_tags.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract tickets between two tags and save to file
  python fetchTicketChangesInBuildsForRepo.py owner/repo v1.0.0 v1.1.0 -o tickets.txt
  
  # Extract tickets and display to console
  python fetchTicketChangesInBuildsForRepo.py owner/repo v1.0.0 v1.1.0 -v
  
  # Extract tickets with detailed commit information
  python fetchTicketChangesInBuildsForRepo.py owner/repo v1.0.0 v1.1.0 --details -o tickets.txt
        """
    )
    
    parser.add_argument(
        "repo",
        help="GitHub repository in format 'owner/repo'"
    )
    parser.add_argument(
        "from_tag",
        help="Starting tag/commit to compare from"
    )
    parser.add_argument(
        "to_tag", 
        help="Ending tag/commit to compare to"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file to save extracted tickets (default: display to console)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output when displaying to console"
    )
    parser.add_argument(
        "--no-commits",
        action="store_true",
        help="Don't show commit list (passed to compare_tags.py)"
    )
    parser.add_argument(
        "--no-files",
        action="store_true", 
        help="Don't show file changes (passed to compare_tags.py)"
    )
    parser.add_argument(
        "-d", "--details",
        action="store_true",
        help="Show detailed diff information (passed to compare_tags.py)"
    )
    parser.add_argument(
        "--pattern",
        default="[A-Z]{2,4}-\\d{1,6}",
        help="Custom regex pattern for ticket matching (default: [A-Z]{2,4}-\\d{1,6})"
    )
    parser.add_argument(
        "--api-key",
        help="Linear API key (defaults to LINEAR_API_KEY environment variable)"
    )
    parser.add_argument(
        "--no-fetch-details",
        action="store_true",
        help="Skip fetching ticket details from Linear API"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode to troubleshoot Linear API issues"
    )
    
    args = parser.parse_args()
    
    # Initialize extractor
    extractor = LinearTicketExtractor(api_key=args.api_key, debug=args.debug)
    
    # Override pattern if custom one provided
    if args.pattern != "[A-Z]{2,4}-\\d{1,6}":
        try:
            extractor.ticket_pattern = re.compile(f'\\[({args.pattern})\\]')
        except re.error as e:
            print(f"Error: Invalid regex pattern '{args.pattern}': {e}", file=sys.stderr)
            sys.exit(1)
    
    # Call compare_tags.py and get output
    print(f"Fetching commit differences between {args.from_tag} and {args.to_tag}...")
    output = extractor.call_compare_tags(
        args.repo,
        args.from_tag,
        args.to_tag,
        no_commits=args.no_commits,
        no_files=args.no_files,
        details=args.details,
        verbose=args.verbose
    )
    
    if not output:
        print("Failed to get output from compare_tags.py", file=sys.stderr)
        sys.exit(1)
    
    # Extract tickets from the output
    tickets = extractor.extract_tickets_from_text(output)
    
    if not tickets:
        print("No Linear tickets found in the commit messages.")
        sys.exit(0)
    
    # Fetch ticket details from Linear API
    ticket_details = None
    if not args.no_fetch_details:
        ticket_details = extractor.fetch_all_ticket_details(tickets, verbose=args.verbose)
    
    # Output results
    if args.output:
        success = extractor.save_tickets_to_file(
            tickets, args.output, args.repo, args.from_tag, args.to_tag, ticket_details
        )
        if success:
            print(f"Extracted {len(tickets)} Linear tickets and saved to '{args.output}'")
        else:
            sys.exit(1)
    else:
        extractor.print_tickets(tickets, args.repo, args.from_tag, args.to_tag, args.verbose, ticket_details)


if __name__ == "__main__":
    main()
