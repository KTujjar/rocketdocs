from pydantic import BaseModel


class FirebaseDocumentationModel(BaseModel):
    bucket_url: str | None
    github_url: str