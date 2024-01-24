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
    graph: dict[str, list[str]]
    root_doc: str
    status: dict[str, DocsStatusEnum]
    version: str # commitId


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

# GET /repos/{repo_id}

class GetRepoResponse(BaseModel):
    repo: FirestoreRepoCreateModel

# GET /repos

class GetReposResponse(BaseModel):
    repos: list[FirestoreRepoCreateModel]