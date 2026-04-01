#!/usr/bin/env python3
"""
Simple test script to validate Linear API connection and fetch a test ticket.
Use this to debug Linear API issues before running the main script.
"""

import os
import sys
import json
import requests
import argparse


def test_linear_connection(api_key: str, ticket_id: str = None):
    """Test Linear API connection and optionally fetch a ticket."""
    
    print("Testing Linear API Connection...")
    print("=" * 60)
    
    # Test 1: Check if API key is set
    if not api_key:
        print("❌ FAILED: No API key provided")
        print("   Set LINEAR_API_KEY environment variable or pass --api-key")
        return False
    
    print(f"✓ API key found (starts with: {api_key[:10]}...)")
    
    # Test 2: Verify API key by fetching viewer info
    print("\nTest 1: Verifying API key...")
    viewer_query = """
    query {
        viewer {
            id
            name
            email
        }
    }
    """
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            "https://api.linear.app/graphql",
            headers=headers,
            json={"query": viewer_query},
            timeout=10
        )
        
        if response.status_code == 401:
            print("❌ FAILED: Invalid API key (401 Unauthorized)")
            print("   Get a new API key from: https://linear.app/settings/api")
            return False
        
        if response.status_code != 200:
            print(f"❌ FAILED: API returned status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        data = response.json()
        
        if 'errors' in data:
            print(f"❌ FAILED: API returned errors")
            print(f"   Errors: {json.dumps(data['errors'], indent=2)}")
            return False
        
        if 'data' in data and data['data'].get('viewer'):
            viewer = data['data']['viewer']
            print(f"✓ API key is valid!")
            print(f"  Logged in as: {viewer.get('name', 'Unknown')}")
            print(f"  Email: {viewer.get('email', 'Unknown')}")
        else:
            print("❌ FAILED: Unexpected response format")
            print(f"   Response: {json.dumps(data, indent=2)}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ FAILED: Request timed out")
        print("   Check your internet connection")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ FAILED: Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        return False
    
    # Test 3: Fetch a specific ticket if provided
    if ticket_id:
        print(f"\nTest 2: Fetching ticket {ticket_id}...")
        
        issue_query = """
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
                project {
                    name
                }
            }
        }
        """
        
        try:
            response = requests.post(
                "https://api.linear.app/graphql",
                headers=headers,
                json={
                    "query": issue_query,
                    "variables": {"identifier": ticket_id}
                },
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"❌ FAILED: API returned status {response.status_code}")
                return False
            
            data = response.json()
            
            if 'errors' in data:
                print(f"❌ FAILED: API returned errors")
                print(f"   Errors: {json.dumps(data['errors'], indent=2)}")
                return False
            
            if 'data' in data and data['data'].get('issue'):
                issue = data['data']['issue']
                print(f"✓ Successfully fetched ticket!")
                print(f"  ID: {issue['identifier']}")
                print(f"  Title: {issue['title']}")
                print(f"  State: {issue['state']['name'] if issue.get('state') else 'Unknown'}")
                print(f"  Assignee: {issue['assignee']['name'] if issue.get('assignee') else 'Unassigned'}")
                print(f"  Project: {issue['project']['name'] if issue.get('project') else 'Unknown'}")
            else:
                print(f"❌ FAILED: Ticket {ticket_id} not found")
                print("   Possible reasons:")
                print("   - Ticket doesn't exist in your Linear workspace")
                print("   - You don't have permission to view this ticket")
                print("   - Ticket ID format is incorrect (should be PROJ-123)")
                if 'data' in data:
                    print(f"   Response data: {json.dumps(data, indent=2)}")
                return False
                
        except Exception as e:
            print(f"❌ FAILED: Error fetching ticket: {e}")
            return False
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! Linear API is working correctly.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Test Linear API connection and validate setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with environment variable
  export LINEAR_API_KEY=lin_api_xxx
  python test_linear_api.py
  
  # Test with API key argument
  python test_linear_api.py --api-key lin_api_xxx
  
  # Test and fetch a specific ticket
  python test_linear_api.py --api-key lin_api_xxx --ticket ENG-1234
        """
    )
    
    parser.add_argument(
        "--api-key",
        help="Linear API key (defaults to LINEAR_API_KEY environment variable)"
    )
    parser.add_argument(
        "--ticket",
        help="Optional: Test ticket ID to fetch (e.g., ENG-1234)"
    )
    
    args = parser.parse_args()
    
    api_key = args.api_key or os.getenv('LINEAR_API_KEY')
    
    success = test_linear_connection(api_key, args.ticket)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

