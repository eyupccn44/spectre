import requests
from typing import Dict, Optional


class GistManager:
    API = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def create(
        self,
        files: Dict[str, str],
        description: str,
        public: bool = True,
    ) -> dict:
        """Create a GitHub Gist with multiple files. Returns gist data."""
        payload = {
            "description": description,
            "public": public,
            "files": {name: {"content": content} for name, content in files.items()},
        }
        resp = requests.post(
            f"{self.API}/gists",
            json=payload,
            headers=self.headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def delete(self, gist_id: str) -> bool:
        resp = requests.delete(
            f"{self.API}/gists/{gist_id}",
            headers=self.headers,
            timeout=10,
        )
        return resp.status_code == 204

    def get(self, gist_id: str) -> dict:
        resp = requests.get(
            f"{self.API}/gists/{gist_id}",
            headers=self.headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def list_mine(self) -> list:
        resp = requests.get(
            f"{self.API}/gists",
            headers=self.headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
