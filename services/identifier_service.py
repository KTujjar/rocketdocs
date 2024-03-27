import os
import uuid

import firebase_admin
from github.ContentFile import ContentFile
from github.Repository import Repository
from magika import Magika

from schemas.documentation_generation import FirestoreRepo, FirestoreDoc, StatusEnum
from services.data_service import DataService, get_data_service

from dotenv import load_dotenv

from services.github_service import get_github_service


class IdentifierService:
    exclude_dirs: list[str] = [
        ".git",
        ".github",
        ".vscode",
        "node_modules",
        "venv",
        "patch",
        "packages/blobs",
        "dist",
    ]
    exclude_exts: list[str] = [
        ".min.js",
        ".min.js.map",
        ".min.css",
        ".min.css.map",
        ".tfstate",
        ".tfstate.backup",
        ".jar",
        ".ipynb",
        ".png",
        ".jpg",
        ".jpeg",
        ".download",
        ".gif",
        ".bmp",
        ".tiff",
        ".ico",
        ".mp3",
        ".wav",
        ".wma",
        ".ogg",
        ".flac",
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".patch",
        ".patch.disabled",
        ".wmv",
        ".m4a",
        ".m4v",
        ".3gp",
        ".3g2",
        ".rm",
        ".swf",
        ".flv",
        ".iso",
        ".bin",
        ".tar",
        ".zip",
        ".7z",
        ".gz",
        ".rar",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".svg",
        ".parquet",
        ".pyc",
        ".pub",
        ".pem",
        ".ttf",
        ".dfn",
        ".dfm",
        ".feature",
        "sweep.yaml",
        "pnpm-lock.yaml",
        "LICENSE",
        "poetry.lock",
    ]

    def __init__(self, data_service: DataService):
        self.data_service = data_service
        # self.include_pattern = r".*\.(py|js|ts|go|rb)$"
        self.magika = Magika()

    def identify(self, repository: Repository, user_id: str) -> FirestoreRepo:
        repo_id = str(uuid.uuid4())
        root = FirestoreDoc(
            id=str(uuid.uuid4()),
            github_url=repository.html_url,
            relative_path="",
            type="dir",
            status=StatusEnum.NOT_STARTED,
            repo=repo_id,
            owner=user_id,
        )

        docs = {root.id: root}
        dependencies = {root.id: None}

        queue = [root]
        while queue:
            parent = queue.pop(0)
            contents = repository.get_contents(parent.relative_path)
            for content in contents:
                if self._skip_node(content):
                    continue
                firestore_doc = FirestoreDoc(
                    id=str(uuid.uuid4()),
                    github_url=content.html_url,
                    relative_path=content.path,
                    type=content.type,
                    size=content.size or None,
                    status=StatusEnum.NOT_STARTED,
                    repo=repo_id,
                    owner=user_id,
                )
                docs[firestore_doc.id] = firestore_doc

                if content.type == "dir":
                    queue.append(firestore_doc)

                dependencies[firestore_doc.id] = parent.id

        repo = FirestoreRepo(
            id=repo_id,
            repo_name=repository.full_name,
            root_doc=root.id,
            status=StatusEnum.NOT_STARTED,
            dependencies=dependencies,
            docs=docs,
            owner=user_id,
        )
        self.data_service.batch_create_repo(repo)
        return repo

    def _skip_node(self, node: ContentFile) -> bool:
        if node.type == "file":
            is_invalid_filename = (
                node.name.startswith(("_", "."))
                or node.name.endswith(tuple(self.exclude_exts))
                # or re.search("test", node.name, re.IGNORECASE)
                # or not re.match(self.include_pattern, node.name)
            )

            # For some weird edge case:
            # 247,500 bytes is ~50k tokens (depending on the model).
            is_too_large = node.size > 247500

            if not is_invalid_filename and not is_too_large:
                file_info = self.magika.identify_bytes(node.decoded_content)
                is_code_file = file_info.output.group == "code"
                return not is_code_file
            else:
                return True
        if node.type == "dir":
            is_invalid_dirname = (
                node.name.startswith(".")
                or any(node.path.endswith(exclude_dir) for exclude_dir in self.exclude_dirs)
            )

            return is_invalid_dirname
        return False


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

    test_repo = github.get_repo_from_url("https://github.com/ryanata/rocketdocs-frontend")
    test_repo = identifier.identify(test_repo, "someone")
    # print(test_repo)
