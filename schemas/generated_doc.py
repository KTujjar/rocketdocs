from pydantic import BaseModel

class GeneratedDocRequest(BaseModel):
    url: str

class GeneratedDocResponse(BaseModel):
    content: str