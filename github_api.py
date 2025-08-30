
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class GitHubAPI:
    BASE_URL = "https://api.github.com"
    STATUS_URL = "https://www.githubstatus.com/api/v2/status.json"

    def __init__(self):
        self.token = os.getenv("GITHUB_PAT")
        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}
        self.rate_limit_remaining = None
        self.rate_limit_reset_time = None

    def _parse_rate_limit_headers(self, headers):
        if 'X-RateLimit-Remaining' in headers:
            self.rate_limit_remaining = int(headers['X-RateLimit-Remaining'])
        if 'X-RateLimit-Reset' in headers:
            self.rate_limit_reset_time = datetime.fromtimestamp(int(headers['X-RateLimit-Reset']))

    def check_status(self):
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

    def stream_user_repos(self, name, entity_type="User"):
        page = 1
        base_path = "users" if entity_type.lower() == "user" else "orgs"
        while True:
            url = f"{self.BASE_URL}/{base_path}/{name}/repos?per_page=100&page={page}&sort=updated"
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
