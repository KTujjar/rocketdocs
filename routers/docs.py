import http.client
import logging

from fastapi import APIRouter, Depends, HTTPException

from schemas.generated_doc import GenerateFileDocRequest, GeneratedDocResponse
from services.documentation_service import DocumentationService, get_documentation_service

router = APIRouter()


@router.post("/file-doc")
async def generate_file_doc(
        generate_file_doc_request: GenerateFileDocRequest,
        documentation_service: DocumentationService = Depends(get_documentation_service)
) -> GeneratedDocResponse:
    try:
        data = await documentation_service.generate_doc_for_github_file(file_url=generate_file_doc_request.url)
        return data
    except ValueError as e:
        raise HTTPException(status_code=http.client.BAD_REQUEST, detail=e.args[0])
    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=http.client.INTERNAL_SERVER_ERROR)
