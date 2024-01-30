import os
from urllib.parse import urlparse

from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException, status
from github import Github, Auth
from github.ContentFile import ContentFile
from github.Repository import Repository


class GithubService:
    def __init__(self, token: Optional[str] = None):
        if not token:
            self.auth = None
        else:
            self.auth = Auth.Token(token)
        self.github = Github(auth=self.auth)

    def get_file(self, github_url: str) -> ContentFile:
        username, repo_name, file_path = self._extract_github_info(github_url)

        repo: Repository = self.github.get_repo(username + "/" + repo_name)
        contents: ContentFile = repo.get_contents(file_path)
        return contents

    @staticmethod
    def _extract_github_info(github_url):
        url_parts = urlparse(github_url)
        path_parts = url_parts.path.strip('/').split('/')

        if len(path_parts) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid GitHub url")

        username = path_parts[0]
        repository_name = path_parts[1]
        file_path = '/'.join(path_parts[4:])

        return username, repository_name, file_path


def get_github_service():
    github_api_key = os.getenv("GITHUB_API_KEY")
    return GithubService(token=github_api_key)


if __name__ == "__main__":
    load_dotenv()
    github = get_github_service()
    content = github.get_file("https://github.com/carlos-jmh/miniDiscord/blob/main/chat/storage.go")
    print(content)
