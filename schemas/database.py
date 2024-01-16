from pydantic import BaseModel
from schemas.api import DocsStatusEnum

class FirestoreDocumentationCreateModel(BaseModel):
    bucket_url: str | None
    github_url: str
    status: DocsStatusEnum

class FirestoreDocumentationUpdateModel(BaseModel):
    bucket_url: str | None
    status: DocsStatusEnum
