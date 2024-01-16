from pydantic import BaseModel

# POST /file-docs

class GenerateFileDocsRequest(BaseModel):
    github_url: str

class GenerateFileDocsResponse(BaseModel):
    message: str
    id: str

# GET /file-docs/{id}
    
class GetFileDocsResponse(BaseModel):
    id: str
    status: str
    content: str | None