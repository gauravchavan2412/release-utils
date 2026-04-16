import os
import requests
from requests.auth import HTTPBasicAuth
import sys

# Function to get commits between tags
def get_commit_messages(repo_url, tag1, tag2, token):
    # Extract owner and repo from the URL
    try:
        owner, repo = repo_url.rstrip('/').rsplit('/', 2)[-2:]
    except ValueError:
        print("The repository URL is not in the expected format.")
        return

    # Construct API URL
    api_url = f"https://github.com/appcd-dev/{repo}/compare/{tag1}...{tag2}"
    headers = {'Authorization': f'token {token}'}

    # Fetch commits
    response = requests.get(api_url, headers=headers)
    if response.status_code == 404:
        print("Tags or repository not found.")
    response.raise_for_status()
    commits = response.json().get('commits', [])

    # Print commit messages
    for commit in commits:
        print(commit.get('commit', {}).get('message', 'No message'))


if __name__ == "__main__":
    token = os.getenv('GITHUB_ACCESS_TOKEN')
    if not token:
        print("Missing environment variable: GITHUB_ACCESS_TOKEN")
    elif len(sys.argv) != 4:
        print("Usage: python diff_tags.py <repo_url> <tag1> <tag2>")
    else:
        repo_url = sys.argv[1]
        # get_commit_messages(sys.argv[1], "v\.0\.56\.0", "v\.0\.58\.0", token) 
        get_commit_messages(sys.argv[1], sys.argv[2], sys.argv[3], token) 