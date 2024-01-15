from pydantic import BaseModel


class GenerateFileDocRequest(BaseModel):
    url: str


class GeneratedDocResponse(BaseModel):
    content: str
