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


class DocStatusEnum(str, Enum):
    NOT_STARTED = 'NOT STARTED'
    IN_PROGRESS = 'IN PROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class FirestoreDocType(str, Enum):
    FILE = 'file'
    DIRECTORY = 'dir'


class GeneratedDoc(BaseModel):
    relative_path: str
    usage: CompletionUsage
    extracted_data: Dict[str, Any]
    markdown_content: str


class FirestoreDoc(BaseModel):
    id: Optional[str] = None
    github_url: Optional[str] = None
    relative_path: Optional[str] = None
    type: Optional[FirestoreDocType] = None
    size: Optional[int] = None
    extracted_data: Optional[Dict[str, Any]] = None
    markdown_content: Optional[str] = None
    usage: Optional[CompletionUsage] = None
    status: Optional[DocStatusEnum] = None


class FirestoreRepo(BaseModel):
    id: Optional[str] = None
    dependencies: Optional[Dict[str, str | None]] = None
    root_doc: Optional[FirestoreDoc] = None  # {id: "doc_id_1", path: "/README.md", status: "COMPLETED"}
    docs: Optional[List[FirestoreDoc]] = None  # [{id: "doc_id_1", path: "/README.md", status: "COMPLETED"}, {id: "doc_id_2", path: "/README2.md", status: "STARTED"}]
    version: Optional[str] = None  # commitId
    repo_name: Optional[str] = None


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
    status: DocStatusEnum
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
    path: str
    type: FirestoreDocType
    completion_status: DocStatusEnum
    children: list['RepoNode'] = []


class RepoFormatted(BaseModel):
    name: str
    id: str
    tree: list[RepoNode]
    nodes_map: dict[str, RepoNode] = Field(exclude=True)  # id to RepoNode

    def insert_node(self,
                    parent: FirestoreDoc,
                    child: FirestoreDoc,
                    ) -> None:
        if parent.id in self.nodes_map.keys():
            child_node = RepoNode(
                id=child.id,
                path=child.relative_path,
                type=child.type,
                completion_status=child.status,
                children=[]
            )  # place holder type and status
            self.nodes_map[parent.id].children.append(child_node)
            self.nodes_map[child.id] = child_node
        else:
            # should only happen for root
            child_node = RepoNode(
                id=child.id,
                path=child.relative_path,
                type=child.type,
                completion_status=child.status,
                children=[]
            )  # place holder type and status
            parent_node = RepoNode(
                id=parent.id,
                path=parent.relative_path,
                type=parent.type,
                completion_status=parent.status,
                children=[child_node]
            )  # place holder type and status
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

class GetRepoResponse(BaseModel):
    repo: RepoFormatted


# GET /repos

class ReposResponseModel(BaseModel):
    name: str
    id: str
    status: List[Dict[str, DocStatusEnum]]


class GetReposResponse(BaseModel):
    repos: List[ReposResponseModel]
