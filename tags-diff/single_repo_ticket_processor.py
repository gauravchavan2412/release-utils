#!/usr/bin/env python3
"""
Single Repository Ticket Processor

This script processes one repository at a time, reading repository and tag combinations
and calling fetchTicketChangesInBuildsForRepo.py to generate ticket lists for each combination.

Usage:
    python single_repo_ticket_processor.py
    python single_repo_ticket_processor.py --input repos.txt
    python single_repo_ticket_processor.py --interactive
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime


class SingleRepoTicketProcessor:
    """Processes single repository ticket extraction requests."""
    
    def __init__(self):
        """Initialize the processor."""
        self.results = []
        self.failed_requests = []
    
    def parse_repo_input(self, input_line: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse a single input line into repository and tag information.
        
        Args:
            input_line: Input line in format "owner/repo:from_tag:to_tag" or "owner/repo from_tag to_tag"
            
        Returns:
            Tuple of (repo, from_tag, to_tag) or None if invalid
        """
        input_line = input_line.strip()
        if not input_line:
            return None
        
        # Try colon-separated format first: owner/repo:from_tag:to_tag
        if ':' in input_line:
            parts = input_line.split(':')
            if len(parts) == 3:
                repo, from_tag, to_tag = parts
                return (repo.strip(), from_tag.strip(), to_tag.strip())
        
        # Try space-separated format: owner/repo from_tag to_tag
        parts = input_line.split()
        if len(parts) == 3:
            repo, from_tag, to_tag = parts
            return (repo.strip(), from_tag.strip(), to_tag.strip())
        
        return None
    
    def call_fetch_tickets_script(self, repo: str, from_tag: str, to_tag: str, 
                                 output_file: str = None, verbose: bool = False) -> Tuple[bool, str, int]:
        """
        Call fetchTicketChangesInBuildsForRepo.py for a single repository.
        
        Args:
            repo: Repository name
            from_tag: Starting tag
            to_tag: Ending tag
            output_file: Optional output file for results
            verbose: Whether to enable verbose output
            
        Returns:
            Tuple of (success, output, ticket_count)
        """
        cmd = [
            sys.executable,
            'fetchTicketChangesInBuildsForRepo.py',
            repo,
            from_tag,
            to_tag
        ]
        
        if output_file:
            cmd.extend(['-o', output_file])
        
        if verbose:
            cmd.append('--verbose')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent
            )
            
            if result.returncode != 0:
                return False, result.stderr, 0
            
            # Extract ticket count from output
            ticket_count = self._extract_ticket_count(result.stdout, output_file)
            return True, result.stdout, ticket_count
            
        except Exception as e:
            return False, str(e), 0
    
    def _extract_ticket_count(self, output: str, output_file: str = None) -> int:
        """
        Extract ticket count from output or output file.
        
        Args:
            output: Console output from fetchTicketChangesInBuildsForRepo.py
            output_file: Optional output file path
            
        Returns:
            Number of tickets found
        """
        # If we have an output file, read from it
        if output_file and Path(output_file).exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                # Look for "Total tickets found: X" pattern
                match = re.search(r'Total tickets found:\s*(\d+)', content)
                if match:
                    return int(match.group(1))
                
                # Count tickets in the file
                ticket_pattern = re.compile(r'\[([A-Z]{2,6}-\d{1,6})\]')
                matches = ticket_pattern.findall(content)
                return len(set(matches))
                
            except Exception:
                pass
        
        # Fall back to console output
        # Look for "Extracted X Linear tickets" pattern
        match = re.search(r'Extracted (\d+) Linear tickets', output)
        if match:
            return int(match.group(1))
        
        # Count tickets in console output
        ticket_pattern = re.compile(r'\[([A-Z]{2,6}-\d{1,6})\]')
        matches = ticket_pattern.findall(output)
        return len(set(matches))
    
    def process_single_request(self, repo: str, from_tag: str, to_tag: str, 
                              output_file: str = None, verbose: bool = False) -> dict:
        """
        Process a single repository request.
        
        Args:
            repo: Repository name
            from_tag: Starting tag
            to_tag: Ending tag
            output_file: Optional output file
            verbose: Whether to enable verbose output
            
        Returns:
            Dictionary with processing results
        """
        print(f"Processing: {repo} ({from_tag} → {to_tag})")
        
        # Generate output file if not provided
        if not output_file:
            safe_repo_name = repo.replace('/', '_').replace(':', '_')
            output_file = f"tickets_{safe_repo_name}_{from_tag}_to_{to_tag}.txt"
        
        success, output, ticket_count = self.call_fetch_tickets_script(
            repo, from_tag, to_tag, output_file, verbose
        )
        
        result = {
            'repo': repo,
            'from_tag': from_tag,
            'to_tag': to_tag,
            'success': success,
            'ticket_count': ticket_count,
            'output_file': output_file,
            'timestamp': datetime.now().isoformat()
        }
        
        if success:
            self.results.append(result)
            print(f"  ✅ Found {ticket_count} tickets - saved to {output_file}")
        else:
            self.failed_requests.append(result)
            result['error'] = output
            print(f"  ❌ Failed: {output}")
        
        return result
    
    def process_from_file(self, input_file: str, verbose: bool = False) -> List[dict]:
        """
        Process multiple requests from an input file.
        
        Args:
            input_file: Path to input file
            verbose: Whether to enable verbose output
            
        Returns:
            List of processing results
        """
        try:
            with open(input_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except FileNotFoundError:
            print(f"Error: Input file '{input_file}' not found.", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error reading input file: {e}", file=sys.stderr)
            return []
        
        print(f"Processing {len(lines)} requests from {input_file}...")
        print("=" * 60)
        
        results = []
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):  # Skip empty lines and comments
                continue
            
            parsed = self.parse_repo_input(line)
            if not parsed:
                print(f"  [{i}] Invalid format: {line}")
                continue
            
            repo, from_tag, to_tag = parsed
            print(f"\n[{i}] ", end="")
            result = self.process_single_request(repo, from_tag, to_tag, verbose=verbose)
            results.append(result)
        
        return results
    
    def process_interactive(self) -> List[dict]:
        """
        Process requests interactively from user input.
        
        Returns:
            List of processing results
        """
        print("Interactive Repository Ticket Processor")
        print("=" * 50)
        print("Enter repository and tag combinations in format:")
        print("  owner/repo:from_tag:to_tag")
        print("  or")
        print("  owner/repo from_tag to_tag")
        print("\nType 'quit' or 'exit' to finish, 'help' for examples")
        print("-" * 50)
        
        results = []
        request_count = 0
        
        while True:
            try:
                user_input = input(f"\n[{request_count + 1}] Enter repo and tags: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                if user_input.lower() == 'help':
                    print("\nExamples:")
                    print("  appcd-dev/iac-gen:v0.56.0:v0.58.0")
                    print("  appcd-dev/appcd v0.67.0 v0.68.0")
                    print("  owner/repo main develop")
                    continue
                
                if not user_input:
                    continue
                
                parsed = self.parse_repo_input(user_input)
                if not parsed:
                    print("  ❌ Invalid format. Use: owner/repo:from_tag:to_tag")
                    continue
                
                repo, from_tag, to_tag = parsed
                result = self.process_single_request(repo, from_tag, to_tag)
                results.append(result)
                request_count += 1
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user.")
                break
            except EOFError:
                break
        
        return results
    
    def save_summary_report(self, output_file: str = None) -> bool:
        """
        Save a summary report of all processing results.
        
        Args:
            output_file: Path to output file (default: auto-generated)
            
        Returns:
            True if successful, False otherwise
        """
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"ticket_processing_summary_{timestamp}.txt"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write("SINGLE REPOSITORY TICKET PROCESSING SUMMARY\n")
                file.write("=" * 60 + "\n\n")
                file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                file.write(f"Total requests processed: {len(self.results) + len(self.failed_requests)}\n")
                file.write(f"Successful requests: {len(self.results)}\n")
                file.write(f"Failed requests: {len(self.failed_requests)}\n")
                file.write(f"Total tickets found: {sum(r['ticket_count'] for r in self.results)}\n\n")
                
                # Successful requests
                if self.results:
                    file.write("SUCCESSFUL REQUESTS\n")
                    file.write("-" * 30 + "\n")
                    for result in self.results:
                        file.write(f"{result['repo']} ({result['from_tag']} → {result['to_tag']}): {result['ticket_count']} tickets\n")
                        file.write(f"  Output file: {result['output_file']}\n")
                        file.write(f"  Processed: {result['timestamp']}\n\n")
                
                # Failed requests
                if self.failed_requests:
                    file.write("FAILED REQUESTS\n")
                    file.write("-" * 30 + "\n")
                    for result in self.failed_requests:
                        file.write(f"{result['repo']} ({result['from_tag']} → {result['to_tag']})\n")
                        file.write(f"  Error: {result.get('error', 'Unknown error')}\n")
                        file.write(f"  Attempted: {result['timestamp']}\n\n")
            
            return True
        except Exception as e:
            print(f"Error writing summary report: {e}", file=sys.stderr)
            return False


def main():
    """Main function to handle command-line arguments and process requests."""
    parser = argparse.ArgumentParser(
        description="Process single repository ticket extraction requests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python single_repo_ticket_processor.py --interactive
  
  # Process from file
  python single_repo_ticket_processor.py --input repos.txt
  
  # Process single request
  echo "appcd-dev/iac-gen:v0.56.0:v0.58.0" | python single_repo_ticket_processor.py
  
  # With verbose output
  python single_repo_ticket_processor.py --input repos.txt --verbose
        """
    )
    
    parser.add_argument(
        "--input", "-i",
        help="Input file containing repository and tag combinations (one per line)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--summary", "-s",
        help="Output file for summary report (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = SingleRepoTicketProcessor()
    
    # Process requests based on input method
    if args.interactive:
        results = processor.process_interactive()
    elif args.input:
        results = processor.process_from_file(args.input, args.verbose)
    else:
        # Read from stdin
        print("Reading repository and tag combinations from stdin...")
        print("Format: owner/repo:from_tag:to_tag or owner/repo from_tag to_tag")
        print("Press Ctrl+D (Unix) or Ctrl+Z (Windows) when done")
        print("-" * 50)
        
        results = []
        request_count = 0
        
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parsed = processor.parse_repo_input(line)
                if not parsed:
                    print(f"  [{request_count + 1}] Invalid format: {line}")
                    continue
                
                repo, from_tag, to_tag = parsed
                print(f"\n[{request_count + 1}] ", end="")
                result = processor.process_single_request(repo, from_tag, to_tag, verbose=args.verbose)
                results.append(result)
                request_count += 1
                
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
        except EOFError:
            pass
    
    # Print final summary
    print(f"\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total requests: {len(results)}")
    print(f"Successful: {len(processor.results)}")
    print(f"Failed: {len(processor.failed_requests)}")
    print(f"Total tickets found: {sum(r['ticket_count'] for r in processor.results)}")
    
    # Save summary report
    if results:
        summary_file = processor.save_summary_report(args.summary)
        if summary_file:
            print(f"\nSummary report saved to: {args.summary or 'ticket_processing_summary_*.txt'}")


if __name__ == "__main__":
    main()

