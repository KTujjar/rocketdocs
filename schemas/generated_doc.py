from pydantic import BaseModel


class GeneratedDocResponse(BaseModel):
    content: str
