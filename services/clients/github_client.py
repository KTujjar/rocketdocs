import base64
import os
from urllib.parse import urlparse

import requests

from typing import Optional

from dotenv import load_dotenv


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.repos_api_url = "https://api.github.com/repos/"

    def read_file(self, github_url: str) -> str:
        username, repo_name, file_path = self.extract_github_info(github_url)

        headers = {}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        url = self.repos_api_url + f'{username}/{repo_name}/contents/{file_path}'
        request = requests.get(url, headers)
        request.raise_for_status()

        data = request.json()
        if "type" in data and data["type"] == "dir":
            raise ValueError(f"{github_url} is a folder, not a file.")

        file_content = data["content"]
        file_content_encoding = data.get('encoding')
        if file_content_encoding == 'base64':
            file_content = base64.b64decode(file_content).decode()
        else:
            raise RuntimeError("Could not decode file content")

        return file_content

    @staticmethod
    def extract_github_info(github_url):
        url_parts = urlparse(github_url)
        path_parts = url_parts.path.strip('/').split('/')

        if len(path_parts) < 2:
            raise ValueError("Invalid GitHub url")

        username = path_parts[0]
        repository_name = path_parts[1]
        file_path = '/'.join(path_parts[4:])

        return username, repository_name, file_path


def get_github_client():
    github_api_key = os.getenv("GITHUB_API_KEY")
    return GitHubClient(token=github_api_key)


if __name__ == "__main__":
    load_dotenv()
    github = get_github_client()
    content = github.read_file("https://github.com/carlos-jmh/miniDiscord/blob/main/chat/storage.go")
    print(content)
