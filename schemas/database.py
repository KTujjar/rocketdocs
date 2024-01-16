from pydantic import BaseModel
from schemas.documentation_generation_enums import DocsStatusEnum

class FirestoreDocumentationCreateModel(BaseModel):
    bucket_url: str | None
    github_url: str
    status: DocsStatusEnum

class FirestoreDocumentationUpdateModel(BaseModel):
    bucket_url: str | None
    status: DocsStatusEnum
