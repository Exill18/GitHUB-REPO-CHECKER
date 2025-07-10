import requests
import os
from dotenv import load_dotenv
from datetime import datetime

# --- Setup ---
load_dotenv()

class GitHubAPI:
    """
    Handles all interactions with the GitHub API.
    """
    BASE_URL = "https://api.github.com"
    STATUS_URL = "https://www.githubstatus.com/api/v2/status.json"

    def __init__(self):
        """
        Initializes the API client with the GitHub Personal Access Token.
        """
        self.token = os.getenv("GITHUB_PAT")
        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}
        self.rate_limit_remaining = None
        self.rate_limit_reset_time = None

    def _parse_rate_limit_headers(self, headers):
        """
        Parses the rate limit headers from the API response.
        """
        if 'X-RateLimit-Remaining' in headers:
            self.rate_limit_remaining = int(headers['X-RateLimit-Remaining'])
        if 'X-RateLimit-Reset' in headers:
            self.rate_limit_reset_time = datetime.fromtimestamp(int(headers['X-RateLimit-Reset']))

    def check_status(self):
        """
        Checks the operational status of GitHub services.

        Returns:
            tuple: A tuple containing a boolean indicating if the status is okay,
                   and a status description string.
        """
        try:
            resp = requests.get(self.STATUS_URL, timeout=5)
            resp.raise_for_status()
            status_data = resp.json()
            description = status_data.get("status", {}).get("description", "Unknown")
            indicator = status_data.get("status", {}).get("indicator", "none")
            return indicator == "none", description
        except requests.exceptions.RequestException as e:
            return False, f"Could not verify GitHub status: {e}"

    def get_user(self, username):
        """
        Fetches a specific user's profile data.

        Args:
            username (str): The GitHub username to fetch.

        Returns:
            dict: A dictionary containing the user's data, or an error dictionary.
        """
        url = f"{self.BASE_URL}/users/{username}"
        try:
            response = requests.get(url, headers=self.headers)
            self._parse_rate_limit_headers(response.headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.exceptions.HTTPError as e:
            return {"success": False, "status_code": e.response.status_code, "headers": e.response.headers, "message": str(e)}
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Network error: {e}"}

    def stream_user_repos(self, username):
        """
        Fetches repositories for a given user, yielding each page of results as it arrives.

        Args:
            username (str): The GitHub username.

        Yields:
            dict: A dictionary containing a page of repositories, or an error dictionary.
        """
        page = 1
        while True:
            url = f"{self.BASE_URL}/users/{username}/repos?per_page=100&page={page}&sort=updated"
            try:
                response = requests.get(url, headers=self.headers)
                self._parse_rate_limit_headers(response.headers)
                response.raise_for_status()
                page_data = response.json()
                if not page_data:
                    break
                
                yield {"success": True, "data": page_data}
                page += 1

            except requests.exceptions.HTTPError as e:
                yield {"success": False, "status_code": e.response.status_code, "message": str(e)}
                break
            except requests.exceptions.RequestException as e:
                yield {"success": False, "message": f"Network error: {e}"}
                break