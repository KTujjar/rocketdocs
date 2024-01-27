from typing import Dict, Any, List

from openai.types import CompletionUsage
from pydantic import BaseModel, constr, conlist, ValidationError
from enum import Enum
import json

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

class RepoNodeType(str, Enum):
    FILE = 'FILE'
    FOLDER = 'FOLDER'


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

class FirestoreRepoDocModel(BaseModel):
    id: str
    path: str
    status: DocsStatusEnum
    type: RepoNodeType

class FirestoreRepoCreateModel(BaseModel):
    dependencies: dict[str, str]
    root_doc: FirestoreRepoDocModel       # {id: "doc_id_1", path: "/README.md", status: "COMPLETED"}
    docs: list[FirestoreRepoDocModel]     # [{id: "doc_id_1", path: "/README.md", status: "COMPLETED"}, {id: "doc_id_2", path: "/README2.md", status: "STARTED"}]
    version: str # commitId
    repo_name: str


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

# repo tree
    
class RepoNode(BaseModel):
    id: str
    name: str
    type: RepoNodeType
    completion_status: DocsStatusEnum
    children: list['RepoNode'] = []



class RepoFormatted(BaseModel):
    repo_name: str
    tree: list[RepoNode]
    nodes_map: dict[str, RepoNode] # id to RepoNode

    def insert_node(self, 
        parent: FirestoreRepoDocModel, 
        child: FirestoreRepoDocModel,
        
    ) -> RepoNode:
        if parent.id in self.nodes_map.keys():
            child_node = RepoNode(id=child.id, name=child.id, type=child.type, completion_status=child.status, children=[]) # place holder type and status
            self.nodes_map[parent.id].children.append(child_node)
            self.nodes_map[child.id] = child_node
        else:
            # should only happen for root?
            child_node = RepoNode(id=child.id, name=child.id, type=child.type, completion_status=child.status, children=[]) # place holder type and status
            parent_node = RepoNode(id=parent.id, name=parent.id, type=parent.type, completion_status=parent.status, children=[child_node]) # place holder type and status
            self.nodes_map[parent.id] = parent_node
            self.nodes_map[child.id] = child_node
            self.tree.append(parent_node)

    def __str__(self):
        data_dict = self

        def custom_encoder(obj):
            if isinstance(obj, (RepoNode, RepoFormatted)):
                return obj.dict()
            else:
                return str(obj)
    
        # Convert the dictionary to a JSON string
        json_str = json.dumps(data_dict, indent=2, default=custom_encoder)


        return json_str
