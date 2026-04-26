import requests
import base64
from typing import Dict, Optional


class RepoManager:
    API = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get_user(self) -> dict:
        resp = requests.get(f"{self.API}/user", headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def create(self, name: str, description: str, private: bool = False) -> dict:
        """Create a new GitHub repo."""
        payload = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": False,
        }
        resp = requests.post(
            f"{self.API}/user/repos",
            json=payload,
            headers=self.headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def push_files(self, owner: str, repo: str, files: Dict[str, str]) -> None:
        """Push multiple files to a repo (creates each via Contents API)."""
        for filename, content in files.items():
            encoded = base64.b64encode(content.encode()).decode()
            payload = {
                "message": self._commit_message(filename),
                "content": encoded,
            }
            resp = requests.put(
                f"{self.API}/repos/{owner}/{repo}/contents/{filename}",
                json=payload,
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()

    def delete(self, owner: str, repo: str) -> bool:
        resp = requests.delete(
            f"{self.API}/repos/{owner}/{repo}",
            headers=self.headers,
            timeout=10,
        )
        return resp.status_code == 204

    def _commit_message(self, filename: str) -> str:
        messages = {
            ".env": "add environment configuration",
            "credentials": "add aws credentials",
            "config.json": "add production config",
            "deploy.sh": "add deployment script",
            "README.md": "initial commit",
        }
        return messages.get(filename, f"add {filename}")
