from typing import Dict, Any, List, Optional

from openai.types import CompletionUsage
from pydantic import BaseModel, constr, conlist, ValidationError, Field
from enum import Enum


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
    extracted_data: Dict[str, Any]
    markdown_content: str


# Blob storage objects

# class BlobDoc(BaseModel):
#     description: str
#     insights: List[str]
#
#     def to_markdown(self):
#         markdown_output = f"## Description\n{self.description}\n## Insights\n"
#
#         for i, insight in enumerate(self.insights, start=1):
#             markdown_output += f"{i}. {insight}\n"
#
#         return markdown_output


# class FirestoreDocumentationCreateModel(BaseModel):
#     bucket_url: str | None
#     github_url: str
#     relative_path: str
#     status: DocsStatusEnum
#
#
# class FirestoreDocumentationUpdateModel(BaseModel):
#     bucket_url: str | None
#     status: DocsStatusEnum
#     relative_path: str
#     usage: CompletionUsage


class FirestoreDoc(BaseModel):
    github_url: Optional[str] = None
    relative_path: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None
    extracted_data: Optional[Dict[str, Any]] = None
    markdown_content: Optional[str] = None
    usage: Optional[CompletionUsage] = None
    status: Optional[DocsStatusEnum] = None
    # extracted_data: Dict[str, Any] | None = None
    # markdown_content: str | None = None
    # usage: CompletionUsage | None = None
    # status: DocsStatusEnum | None = None


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
    markdown_content: str | None


# DELETE /file-docs/{id}

class DeleteFileDocsResponse(BaseModel):
    message: str
    id: str


# UPDATE /file-docs/{id}

class UpdateFileDocsResponse(BaseModel):
    message: str
    id: str


# LLM Generation Models

class LlmDocSchema(BaseModel):
    description: str = Field("Around 100 words about the code's purpose")
    dependencies: List[str] = Field("Outside dependencies the code uses")


# GitHub Models

# class GitHubFile(BaseModel):
#     name: str
#     path: str
#     sha: str
#     size: int
#     url: str
#     html_url: str
#     git_url: str
#     download_url: str
#     type: str
#     content: str
#     encoding: str
