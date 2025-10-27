#!/usr/bin/env python3
"""
Git Tag Comparison Utility

This script compares differences between two Git tags in a repository
using the GitHub API and displays commits, file changes, and statistics.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import requests


class GitHubTagComparator:
    """Handles comparison between Git tags using GitHub API."""
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize with GitHub PAT token.
        
        Args:
            token: GitHub Personal Access Token. If None, will try to get from env variables.
        """
        self.token = token or os.getenv('GITHUB_PAT') or os.getenv('GH_TOKEN')
        if not self.token:
            raise ValueError(
                "GitHub PAT token not found. Set GITHUB_PAT or GH_TOKEN environment variable "
                "or pass token directly."
            )
        
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = "https://api.github.com"
    
    def get_tag_info(self, repo: str, tag: str) -> Optional[Dict]:
        """
        Get information about a specific tag.
        
        Args:
            repo: Repository in format 'owner/repo'
            tag: Tag name
            
        Returns:
            Tag information dictionary or None if not found
        """
        url = f"{self.base_url}/{repo}/git/refs/tags/{tag}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Try getting it as a lightweight tag
                url = f"{self.base_url}/repos/{repo}/git/tags/{tag}"
                response = requests.get(url, headers=self.headers, timeout=30)
                if response.status_code == 200:
                    return response.json()
            return None
        except requests.RequestException as e:
            print(f"Error fetching tag {tag}: {e}")
            return None
    
    def get_comparison(self, repo: str, base: str, head: str) -> Optional[Dict]:
        """
        Get comparison between two references (tags/commits).
        
        Args:
            repo: Repository in format 'owner/repo'
            base: Base reference (from tag)
            head: Head reference (to tag)
            
        Returns:
            Comparison data dictionary or None if failed
        """
        url = f"{self.base_url}/repos/{repo}/compare/{base}...{head}"
        
        try:
            print(f"Fetching comparison between {base} and {head}...")
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching comparison: {e}")
            return None
    
    def get_commits_between_tags(self, repo: str, base: str, head: str) -> List[Dict]:
        """
        Get commits between two tags.
        
        Args:
            repo: Repository in format 'owner/repo'
            base: Base tag
            head: Head tag
            
        Returns:
            List of commit dictionaries
        """
        comparison = self.get_comparison(repo, base, head)
        if comparison:
            return comparison.get('commits', [])
        return []
    
    def format_commit_info(self, commit: Dict) -> str:
        """
        Format commit information for display.
        
        Args:
            commit: Commit dictionary from GitHub API
            
        Returns:
            Formatted commit string
        """
        sha = commit['sha'][:7]
        message = commit['commit']['message'].split('\n')[0]  # First line only
        author = commit['commit']['author']['name']
        date = commit['commit']['author']['date']
        
        # Format date
        try:
            dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
            formatted_date = dt.strftime('%Y-%m-%d %H:%M')
        except:
            formatted_date = date
        
        return f"  {sha} - {message} ({author}, {formatted_date})"
    
    def format_file_changes(self, files: List[Dict], show_details: bool = False) -> str:
        """
        Format file changes for display.
        
        Args:
            files: List of file change dictionaries
            show_details: Whether to show detailed diff information
            
        Returns:
            Formatted file changes string
        """
        output = []
        
        for file_data in files:
            filename = file_data['filename']
            status = file_data['status']
            additions = file_data.get('additions', 0)
            deletions = file_data.get('deletions', 0)
            changes = file_data.get('changes', 0)
            
            # Status icon
            status_icon = {
                'added': '✅',
                'modified': '🔄',
                'removed': '❌',
                'renamed': '🔄'
            }.get(status, '🔄')
            
            line = f"  {status_icon} {filename} ({status})"
            
            if changes > 0:
                line += f" [+{additions}/-{deletions}]"
            
            output.append(line)
            
            # Show patch details if requested
            if show_details and file_data.get('patch'):
                output.append("    Diff preview:")
                patch_lines = file_data['patch'].split('\n')[:10]  # First 10 lines
                for patch_line in patch_lines:
                    output.append(f"    {patch_line}")
                if len(file_data['patch'].split('\n')) > 10:
                    output.append("    ... (truncated)")
                output.append("")
        
        return '\n'.join(output)
    
    def compare_tags(self, repo: str, from_tag: str, to_tag: str, 
                    show_commits: bool = True, show_files: bool = True, 
                    show_details: bool = False) -> Dict:
        """
        Compare two tags and return formatted results.
        
        Args:
            repo: Repository in format 'owner/repo'
            from_tag: Starting tag
            to_tag: Ending tag  
            show_commits: Whether to show commit list
            show_files: Whether to show file changes
            show_details: Whether to show detailed diff information
            
        Returns:
            Dictionary with comparison results
        """
        # Validate tags exist
        from_tag_info = self.get_tag_info(repo, from_tag)
        to_tag_info = self.get_tag_info(repo, to_tag)
        
        if not from_tag_info:
            print(f"Warning: Tag '{from_tag}' not found. Assuming it's a commit SHA or branch.")
        if not to_tag_info:
            print(f"Warning: Tag '{to_tag}' not found. Assuming it's a commit SHA or branch.")
        
        # Get comparison
        comparison = self.get_comparison(repo, from_tag, to_tag)
        if not comparison:
            return {"error": "Failed to get comparison data"}
        
        results = {
            "repo": repo,
            "from_tag": from_tag,
            "to_tag": to_tag,
            "status": comparison.get('status', 'unknown'),
            "ahead_by": comparison.get('ahead_by', 0),
            "behind_by": comparison.get('behind_by', 0),
            "total_commits": comparison.get('total_commits', 0),
            "commits": comparison.get('commits', []),
            "files": comparison.get('files', [])
        }
        
        return results


def print_comparison_summary(results: Dict):
    """Print a summary of the comparison results."""
    repo = results['repo']
    from_tag = results['from_tag']
    to_tag = results['to_tag']
    status = results['status']
    ahead_by = results['ahead_by']
    behind_by = results['behind_by']
    total_commits = results['total_commits']
    
    print(f"\n{'='*80}")
    print(f"TAG COMPARISON SUMMARY")
    print(f"{'='*80}")
    print(f"Repository: {repo}")
    print(f"From: {from_tag}")
    print(f"To: {to_tag}")
    print(f"Status: {status}")
    
    if status == 'identical':
        print("✅ Tags are identical - no differences found")
        return
    
    print(f"Commits ahead: {ahead_by}")
    print(f"Commits behind: {behind_by}")
    print(f"Total commits: {total_commits}")
    print(f"Files changed: {len(results['files'])}")


def print_commits(commits: List[Dict]):
    """Print commit information."""
    if not commits:
        print("\n📝 No commits found")
        return
    
    print(f"\n📝 COMMITS ({len(commits)}):")
    print("-" * 60)
    
    comparator = GitHubTagComparator()
    for commit in commits:
        print(comparator.format_commit_info(commit))


def print_file_changes(files: List[Dict], show_details: bool = False):
    """Print file changes information."""
    if not files:
        print("\n📁 No file changes found")
        return
    
    # Calculate statistics
    total_additions = sum(f.get('additions', 0) for f in files)
    total_deletions = sum(f.get('deletions', 0) for f in files)
    
    added_files = len([f for f in files if f['status'] == 'added'])
    modified_files = len([f for f in files if f['status'] == 'modified'])
    deleted_files = len([f for f in files if f['status'] == 'removed'])
    
    print(f"\n📁 FILE CHANGES ({len(files)} files):")
    print("-" * 60)
    print(f"Added: {added_files}, Modified: {modified_files}, Deleted: {deleted_files}")
    print(f"Total changes: +{total_additions}/-{total_deletions}")
    print()
    
    comparator = GitHubTagComparator()
    print(comparator.format_file_changes(files, show_details))


def main():
    """Main function to handle command-line arguments and perform comparison."""
    parser = argparse.ArgumentParser(
        description="Compare differences between two Git tags in a repository"
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
        "--no-commits",
        action="store_true",
        help="Don't show commit list"
    )
    parser.add_argument(
        "--no-files",
        action="store_true", 
        help="Don't show file changes"
    )
    parser.add_argument(
        "-d", "--details",
        action="store_true",
        help="Show detailed diff information for files"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize comparator
        if args.verbose:
            print("Initializing GitHub API client...")
        
        comparator = GitHubTagComparator()
        
        # Perform comparison
        results = comparator.compare_tags(
            args.repo,
            args.from_tag,
            args.to_tag,
            show_commits=not args.no_commits,
            show_files=not args.no_files,
            show_details=args.details
        )
        
        if "error" in results:
            print(f"Error: {results['error']}")
            sys.exit(1)
        
        # Output results
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print_comparison_summary(results)
            
            if not args.no_commits:
                print_commits(results['commits'])
            
            if not args.no_files:
                print_file_changes(results['files'], args.details)
            
            print(f"\n{'='*80}")
        
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