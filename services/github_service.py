import os
import re
import sys
from urllib.parse import urlparse

from typing import Optional, List

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

    def get_file_from_url(self, github_url: str) -> ContentFile:
        owner, repo_name, file_path = self._extract_github_url_info(github_url)
        if not file_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid GitHub url")

        repo: Repository = self.github.get_repo(owner + "/" + repo_name)
        contents: ContentFile = repo.get_contents(file_path)
        return contents

    def get_repo_from_url(self, github_url: str) -> Repository:
        username, repo_name, _ = self._extract_github_url_info(github_url)
        return self.github.get_repo(username + "/" + repo_name)

    @staticmethod
    def get_repo_contents(repository: Repository, exclude: Optional[List[str]] = None) -> List[ContentFile]:
        all_content = []
        queue = repository.get_contents("")
        while queue:
            file_content = queue.pop(0)

            if exclude:
                if any(re.search(pattern, file_content.name) for pattern in exclude):
                    continue

            if file_content.type == "dir":
                queue.extend(repository.get_contents(file_content.path))
            all_content.append(file_content)

        return all_content

    @staticmethod
    def _extract_github_url_info(github_url):
        url_parts = urlparse(github_url)
        if url_parts.netloc != "github.com":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid GitHub url")

        path_parts = url_parts.path.strip('/').split('/')
        if len(path_parts) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid GitHub url")

        owner = path_parts[0]
        repository_name = path_parts[1]

        if len(path_parts) >= 4 and path_parts[2] == "blob":
            file_path = '/'.join(path_parts[4:])
        else:
            file_path = None

        return owner, repository_name, file_path


def get_github_service():
    github_api_key = os.getenv("GITHUB_API_KEY")
    return GithubService(token=github_api_key)


if __name__ == "__main__":
    load_dotenv()
    github = get_github_service()

    # content = github.get_file_from_url(
    #     "https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py"
    # )
    # print(content)

    # repo = github.get_repo_from_url("https://github.com/KTujjar/rocketdocs/tree/main")
    # contents = github.get_repo_contents(
    #     repo,
    #     exclude=[
    #         ".gitignore",
    #         ".dockerignore",
    #         ".env",
    #         "clients",
    #         "__init__.py",
    #         "Dockerfile",
    #         "README.md",
    #         "LICENSE",
    #         "requirements.txt"
    #     ]
    # )
    # print(contents)
