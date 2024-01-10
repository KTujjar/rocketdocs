from fastapi import APIRouter, Depends

from schemas.generated_doc import GeneratedDocRequest, GeneratedDocResponse 
from services.documentation_service import DocumentationService, get_documentation_service

router = APIRouter()

@router.post("/docs")
def hello_world(
        generated_doc_request: GeneratedDocRequest,
        documentation_service: DocumentationService = Depends(get_documentation_service)
) -> GeneratedDocResponse:
    data = documentation_service.generate_doc_for_github_file(file_url=generated_doc_request.url)
    return data
