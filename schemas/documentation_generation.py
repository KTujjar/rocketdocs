from typing import Dict, Any, List

from openai.types import CompletionUsage
from pydantic import BaseModel, constr, conlist, ValidationError
from enum import Enum

class LlmProvider(str, Enum):
    OPEN_AI = 'OPEN_AI'
    ANYSCALE = 'ANYSCALE'


class LlmModelEnum(str, Enum):
    MIXTRAL = 'mistralai/Mixtral-8x7B-Instruct-v0.1'
    MISTRAL = 'mistralai/Mistral-7B-Instruct-v0.1'
    MISTRAL_ORCA = 'Open-Orca/Mistral-7B-OpenOrca'
    LLAMA_7B = 'meta-llama/Llama-2-7b-chat-hf'


class DocsStatusEnum(str, Enum):
    STARTED = 'STARTED'
    COMPLETED = 'COMPLETED'


class GeneratedDoc(BaseModel):
    relative_path: str
    raw_content: str
    usage: CompletionUsage
    description: str | None
    insights: List[str] | None


# Blob storage objects

class BlobDoc(BaseModel):
    description: str
    insights: List[str]

    def to_markdown(self):
        markdown_output = f"## Description\n{self.description}\n## Insights\n"

        for i, insight in enumerate(self.insights, start=1):
            markdown_output += f"{i}. {insight}\n"

        return markdown_output


class FirestoreDocumentationCreateModel(BaseModel):
    bucket_url: str | None
    github_url: str
    relative_path: str
    status: DocsStatusEnum


class FirestoreDocumentationUpdateModel(BaseModel):
    bucket_url: str | None
    status: DocsStatusEnum
    relative_path: str
    usage: CompletionUsage


class FirestoreRepoCreateModel(BaseModel):
    graph: dict[str, list[str]]
    root_doc: str
    status: dict[str, DocsStatusEnum]
    version: str # commitId


# POST /file-docs

class GenerateFileDocsRequest(BaseModel):
    github_url: str


class GenerateFileDocsResponse(BaseModel):
    message: str
    id: str


# GET /file-docs/{id}

class GetFileDocsResponse(BaseModel):
    id: str
    github_url: str
    status: str
    relative_path: str
    content: str | None


# DELETE /file-docs/{id}

class DeleteFileDocsResponse(BaseModel):
    message: str
    id: str


# UPDATE /file-docs/{id}

# class UpdateFileDocsRequest(BaseModel):
#     model: LlmModelEnum = LlmModelEnum.MIXTRAL


class UpdateFileDocsResponse(BaseModel):
    message: str
    id: str


# LLM Generation Models

class LlmDocSchema(BaseModel):
    description: str
    insights: List[str]


# GitHub Models

class GitHubFile(BaseModel):
    name: str
    path: str
    sha: str
    size: int
    url: str
    html_url: str
    git_url: str
    download_url: str
    type: str
    content: str
    encoding: str

# GET /repos/{repo_id}

class RepoResponseModel(FirestoreRepoCreateModel):
    id: str

class GetRepoResponse(BaseModel):
    repo: RepoResponseModel

# GET /repos

class GetReposResponse(BaseModel):
    repos: list[RepoResponseModel]