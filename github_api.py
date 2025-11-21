
import requests
import os
import logging
from typing import Dict, Any, Tuple, Generator, Optional
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logger = logging.getLogger(__name__)

class GitHubAPI:
    BASE_URL = "https://api.github.com"
    STATUS_URL = "https://www.githubstatus.com/api/v2/status.json"

    def __init__(self) -> None:
        self.token: Optional[str] = os.getenv("GITHUB_PAT")
        self.headers: Dict[str, str] = {"Authorization": f"token {self.token}"} if self.token else {}
        self.rate_limit_remaining: Optional[int] = None
        self.rate_limit_reset_time: Optional[datetime] = None
        
        if self.token:
            logger.info("GitHub API initialized with token")
        else:
            logger.warning("GitHub API initialized without token - rate limits will be lower")

    def _parse_rate_limit_headers(self, headers: Dict[str, str]) -> None:
        """Parse rate limit information from response headers."""
        try:
            if 'X-RateLimit-Remaining' in headers:
                self.rate_limit_remaining = int(headers['X-RateLimit-Remaining'])
                logger.debug(f"Rate limit remaining: {self.rate_limit_remaining}")
            if 'X-RateLimit-Reset' in headers:
                self.rate_limit_reset_time = datetime.fromtimestamp(int(headers['X-RateLimit-Reset']))
                logger.debug(f"Rate limit resets at: {self.rate_limit_reset_time}")
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")

    def check_status(self) -> Tuple[bool, str]:
        """Check GitHub's operational status.
        
        Returns:
            Tuple of (is_operational: bool, description: str)
        """
        try:
            logger.debug("Checking GitHub status")
            resp = requests.get(self.STATUS_URL, timeout=5)
            resp.raise_for_status()
            status_data = resp.json()
            
            # Validate response structure
            if not isinstance(status_data, dict) or "status" not in status_data:
                logger.error("Invalid status response format")
                return False, "Invalid status response format"
            
            status_info = status_data.get("status", {})
            description = status_info.get("description", "Unknown")
            indicator = status_info.get("indicator", "none")
            
            is_operational = indicator == "none"
            logger.info(f"GitHub status: {description} (operational: {is_operational})")
            return is_operational, description
            
        except requests.exceptions.Timeout:
            error_msg = "Timeout while checking GitHub status"
            logger.error(error_msg)
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error while checking GitHub status"
            logger.error(error_msg)
            return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Could not verify GitHub status: {e}"
            logger.error(error_msg)
            return False, error_msg
        except ValueError as e:
            error_msg = f"Invalid JSON response from GitHub status: {e}"
            logger.error(error_msg)
            return False, error_msg

    def get_user(self, username: str) -> Dict[str, Any]:
        """Get user or organization information from GitHub.
        
        Args:
            username: GitHub username or organization name
            
        Returns:
            Dictionary with success status and either data or error information
        """
        # Input validation
        if not username or not isinstance(username, str):
            logger.error("Invalid username provided")
            return {"success": False, "message": "Username must be a non-empty string"}
            
        username = username.strip()
        if not username:
            logger.error("Empty username after stripping")
            return {"success": False, "message": "Username cannot be empty"}
            
        # Basic username validation (GitHub usernames can contain alphanumeric chars and hyphens)
        if not all(c.isalnum() or c == '-' for c in username):
            logger.warning(f"Username contains potentially invalid characters: {username}")
        
        url = f"{self.BASE_URL}/users/{username}"
        logger.debug(f"Fetching user data for: {username}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            self._parse_rate_limit_headers(response.headers)
            response.raise_for_status()
            
            user_data = response.json()
            logger.info(f"Successfully fetched data for user: {username}")
            return {"success": True, "data": user_data}
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error for user {username}: {e}"
            logger.error(error_msg)
            return {
                "success": False, 
                "status_code": e.response.status_code, 
                "headers": e.response.headers, 
                "message": str(e)
            }
        except requests.exceptions.Timeout:
            error_msg = f"Timeout while fetching user {username}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        except requests.exceptions.ConnectionError:
            error_msg = f"Connection error while fetching user {username}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error while fetching user {username}: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        except ValueError as e:
            error_msg = f"Invalid JSON response for user {username}: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

    def stream_user_repos(self, name: str, entity_type: str = "User") -> Generator[Dict[str, Any], None, None]:
        """Stream repositories for a user or organization.
        
        Args:
            name: Username or organization name
            entity_type: Either 'User' or 'Organization'
            
        Yields:
            Dictionary with success status and either repository data or error information
        """
        # Input validation
        if not name or not isinstance(name, str):
            logger.error("Invalid name provided for repository streaming")
            yield {"success": False, "message": "Name must be a non-empty string"}
            return
            
        name = name.strip()
        if not name:
            logger.error("Empty name after stripping")
            yield {"success": False, "message": "Name cannot be empty"}
            return
            
        if entity_type not in ["User", "Organization", "user", "org"]:
            logger.warning(f"Unknown entity type: {entity_type}, defaulting to 'User'")
            entity_type = "User"
        
        page = 1
        base_path = "users" if entity_type.lower() in ["user"] else "orgs"
        total_repos_fetched = 0
        
        logger.info(f"Starting to stream repositories for {entity_type.lower()}: {name}")
        
        while True:
            url = f"{self.BASE_URL}/{base_path}/{name}/repos?per_page=100&page={page}&sort=updated"
            logger.debug(f"Fetching page {page} for {name}")
            
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                self._parse_rate_limit_headers(response.headers)
                response.raise_for_status()
                
                page_data = response.json()
                
                # Validate response is a list
                if not isinstance(page_data, list):
                    logger.error(f"Expected list of repositories, got {type(page_data)}")
                    yield {"success": False, "message": "Invalid response format from GitHub API"}
                    break
                
                if not page_data:
                    logger.info(f"Finished streaming repositories for {name}. Total: {total_repos_fetched}")
                    break
                
                total_repos_fetched += len(page_data)
                logger.debug(f"Fetched {len(page_data)} repositories on page {page}")
                yield {"success": True, "data": page_data}
                page += 1
                
                # Safety check to prevent infinite loops
                if page > 1000:  # GitHub has a max of 100k repos per user, so 1000 pages is safe
                    logger.warning(f"Reached maximum page limit (1000) for {name}")
                    break
                
            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP error while streaming repos for {name} (page {page}): {e}"
                logger.error(error_msg)
                yield {"success": False, "status_code": e.response.status_code, "message": str(e)}
                break
            except requests.exceptions.Timeout:
                error_msg = f"Timeout while streaming repos for {name} (page {page})"
                logger.error(error_msg)
                yield {"success": False, "message": error_msg}
                break
            except requests.exceptions.ConnectionError:
                error_msg = f"Connection error while streaming repos for {name} (page {page})"
                logger.error(error_msg)
                yield {"success": False, "message": error_msg}
                break
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error while streaming repos for {name} (page {page}): {e}"
                logger.error(error_msg)
                yield {"success": False, "message": error_msg}
                break
            except ValueError as e:
                error_msg = f"Invalid JSON response for {name} (page {page}): {e}"
                logger.error(error_msg)
                yield {"success": False, "message": error_msg}
                break
