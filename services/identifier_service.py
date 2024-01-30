import os
import re
import uuid

import firebase_admin
from github.Repository import Repository

from schemas.documentation_generation import FirestoreRepo, FirestoreDoc, DocStatusEnum
from services.clients.anyscale_client import get_anyscale_client
from services.data_service import DataService, get_data_service

from dotenv import load_dotenv

from services.clients.llm_client import LLMClient
from services.github_service import GithubService, get_github_service


class IdentifierService:
    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.exclude_files = [
            re.compile(pattern) for pattern in [
                "README.md",
                ".gitignore",
                ".dockerignore",
                "__init__.py",
                "Dockerfile",
                "LICENSE",
                "requirements.txt",
                "test"
            ]
        ]

    def identify(self, repository: Repository) -> str:
        root = FirestoreDoc(
            id=str(uuid.uuid4()),
            github_url=repository.html_url,
            relative_path="",
            type="dir",
            status=DocStatusEnum.NOT_STARTED
        )

        docs = [root]
        dependencies = {root.id: None}

        queue = [root]
        while queue:
            parent = queue.pop(0)
            contents = repository.get_contents(parent.relative_path)

            for content in contents:
                if any(pattern.match(content.name) for pattern in self.exclude_files):
                    continue

                firestore_doc = FirestoreDoc(
                    id=str(uuid.uuid4()),
                    github_url=content.html_url,
                    relative_path=content.path,
                    type=content.type,
                    size=content.size or None,
                    status=DocStatusEnum.NOT_STARTED
                )
                docs.append(firestore_doc)

                if content.type == "dir":
                    queue.append(firestore_doc)

                dependencies[firestore_doc.id] = parent.id

        repo = FirestoreRepo(
            id=str(uuid.uuid4()),
            dependencies=dependencies,
            docs=docs,
            repo_name=repository.full_name,
            root_doc=root.id
        )
        repo_id = self.data_service.batch_create_repo(repo)
        return repo_id


def get_identifier_service() -> IdentifierService:
    data_service = get_data_service()
    return IdentifierService(data_service)


# For manually testing this file
if __name__ == "__main__":
    load_dotenv()
    firebase_app = firebase_admin.initialize_app(
        credential=None,
        options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
    )

    github = get_github_service()
    identifier = get_identifier_service()

    test_repo = github.get_repo_from_url("https://github.com/KTujjar/rocketdocs")
    identifier.identify(test_repo)
