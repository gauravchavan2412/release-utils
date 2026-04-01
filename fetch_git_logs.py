import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent


class GitLogFetcher:
    def __init__(self, repo_url, tag1, tag2):
        self.repo_url = repo_url
        self.tag1 = tag1
        self.tag2 = tag2

    def fetch_and_parse_logs(self):
        try:
            diff_tags_script = _REPO_ROOT / "diff_tags.py"
            result = subprocess.run(
                [sys.executable, str(diff_tags_script), self.repo_url, self.tag1, self.tag2],
                check=True, capture_output=True, text=True
            )

            # Parse commit messages
            commit_messages = result.stdout.splitlines()
            for message in commit_messages:
                print(message)

        except subprocess.CalledProcessError as e:
            print(f"Error: {e.stderr}")


# Example usage:
# fetcher = GitLogFetcher('<repo_url>', '<tag1>', '<tag2>')
# fetcher.fetch_and_parse_logs()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python fetch_git_logs.py <repo_url> <tag1> <tag2>")
    else:
        fetcher = GitLogFetcher(sys.argv[1], sys.argv[2], sys.argv[3])
        fetcher.fetch_and_parse_logs()
