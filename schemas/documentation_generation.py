from typing import Dict, Any, List, Optional

from openai.types import CompletionUsage
from pydantic import BaseModel, constr, conlist, ValidationError, Field
from enum import Enum
import json


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
    usage: CompletionUsage
    extracted_data: Dict[str, Any]
    markdown_content: str


class FirestoreDoc(BaseModel):
    github_url: Optional[str] = None
    relative_path: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None
    extracted_data: Optional[Dict[str, Any]] = None
    markdown_content: Optional[str] = None
    usage: Optional[CompletionUsage] = None
    status: Optional[DocsStatusEnum] = None


class FirestoreRepoDocModel(BaseModel):
    id: str
    name: str
    path: str
    status: DocsStatusEnum
    type: RepoNodeType


class FirestoreRepoCreateModel(BaseModel):
    dependencies: dict[str, str]
    root_doc: FirestoreRepoDocModel  # {id: "doc_id_1", path: "/README.md", status: "COMPLETED"}
    docs: list[
        FirestoreRepoDocModel]  # [{id: "doc_id_1", path: "/README.md", status: "COMPLETED"}, {id: "doc_id_2", path: "/README2.md", status: "STARTED"}]
    version: str  # commitId
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


# repo tree

class RepoNode(BaseModel):
    id: str
    name: str
    type: RepoNodeType
    completion_status: DocsStatusEnum
    children: list['RepoNode'] = []


class RepoFormatted(BaseModel):
    name: str
    id: str
    tree: list[RepoNode]
    nodes_map: dict[str, RepoNode] = Field(exclude=True)  # id to RepoNode

    def insert_node(self,
                    parent: FirestoreRepoDocModel,
                    child: FirestoreRepoDocModel,
                    ) -> RepoNode:
        if parent.id in self.nodes_map.keys():
            child_node = RepoNode(id=child.id, name=child.name, type=child.type, completion_status=child.status,
                                  children=[])  # place holder type and status
            self.nodes_map[parent.id].children.append(child_node)
            self.nodes_map[child.id] = child_node
        else:
            # should only happen for root
            child_node = RepoNode(id=child.id, name=child.name, type=child.type, completion_status=child.status,
                                  children=[])  # place holder type and status
            parent_node = RepoNode(id=parent.id, name=parent.name, type=parent.type, completion_status=parent.status,
                                   children=[child_node])  # place holder type and status
            self.nodes_map[parent.id] = parent_node
            self.nodes_map[child.id] = child_node
            self.tree.append(parent_node)

    def __str__(self):
        data_dict = self

        def custom_encoder(obj):
            if isinstance(obj, (RepoNode, RepoFormatted)):
                return obj.model_dump()
            else:
                return str(obj)

        # Convert the dictionary to a JSON string
        json_str = json.dumps(data_dict, indent=2, default=custom_encoder)

        return json_str


# GET /repos/{repo_id}

class RepoResponseModel(FirestoreRepoCreateModel):
    id: str


class GetRepoResponse(BaseModel):
    repo: RepoFormatted


# GET /repos

class ReposResponseModel(BaseModel):
    name: str
    id: str
    status: list[dict[str, DocsStatusEnum]]


class GetReposResponse(BaseModel):
    repos: list[ReposResponseModel]
