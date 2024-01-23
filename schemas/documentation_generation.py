from pydantic import BaseModel
from enum import Enum

class LlmModelEnum(str, Enum):
    MIXTRAL = 'mistralai/Mixtral-8x7B-Instruct-v0.1'
    MISTRAL = 'mistralai/Mistral-7B-Instruct-v0.1'
    MISTRAL_ORCA = 'Open-Orca/Mistral-7B-OpenOrca'
    LLAMA_7B = 'meta-llama/Llama-2-7b-chat-hf'


class DocsStatusEnum(str, Enum):
    STARTED = 'STARTED'
    COMPLETED = 'COMPLETED'


class GeneratedDocResponse(BaseModel):
    content: str


class FirestoreDocumentationCreateModel(BaseModel):
    bucket_url: str | None
    github_url: str
    status: DocsStatusEnum


class FirestoreDocumentationUpdateModel(BaseModel):
    bucket_url: str | None
    status: DocsStatusEnum


class FirestoreRepoCreateModel(BaseModel):
    graph: dict[str, list[str]] | None
    root_doc: str
    status: dict[str, DocsStatusEnum]
    version: str # commitId


class FirestoreDocumentationUpdateModel(BaseModel):
    bucket_url: str | None
    status: DocsStatusEnum


# POST /file-docs

class GenerateFileDocsRequest(BaseModel):
    github_url: str
    model: LlmModelEnum = LlmModelEnum.MIXTRAL


class GenerateFileDocsResponse(BaseModel):
    message: str
    id: str


# GET /file-docs/{id}

class GetFileDocsResponse(BaseModel):
    id: str
    github_url: str
    status: str
    content: str | None

# DELETE /file-docs/{id}
    
class DeleteFileDocsResponse(BaseModel):
    message: str
    id: str

# UPDATE /file-docs/{id}
    
class UpdateFileDocsRequest(BaseModel):
    model: LlmModelEnum = LlmModelEnum.MIXTRAL


class UpdateFileDocsResponse(BaseModel):
    message: str
    id: str

# GET /repos

class GetReposResponse(BaseModel):
    repos: list[str]

# GET /repos/{repo_id}
class RepoModel(BaseModel):
    graph: dict[str, list[str]] | None
    root_doc: str
    completion_status: str
    version: str # commitId

    @classmethod
    def from_firestore_model(self, firestore_model: FirestoreRepoCreateModel) -> 'RepoModel':
        # Convert the status field
        completion_status = self.calculate_completion_status(firestore_model.status)

        return self(
            graph=firestore_model.graph,
            root_doc=firestore_model.root_doc,
            completion_status=completion_status,
            version=firestore_model.version
        )
    
    # calculate the completion status e.g '3/5' for a repo
    def calculate_completion_status(status_dict: dict[str, DocsStatusEnum]) -> str:
        total_docs = len(status_dict)
        completed_docs = sum(1 for v in status_dict.values() if v == DocsStatusEnum.COMPLETED)

        return f"{completed_docs}/{total_docs}"


class GetRepoResponse(BaseModel):
    repo: RepoModel