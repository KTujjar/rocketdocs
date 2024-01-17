import http.client
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from schemas.documentation_generation import GenerateFileDocsRequest, GenerateFileDocsResponse, \
    GetFileDocsResponse
from services.clients.github_client import GitHubClient, get_github_client
from services.documentation_service import DocumentationService, get_documentation_service

router = APIRouter()


@router.post("/file-docs", status_code=http.client.ACCEPTED)
async def generate_file_docs(
        generate_file_docs_request: GenerateFileDocsRequest,
        background_tasks: BackgroundTasks,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        github_client: GitHubClient = Depends(get_github_client)
) -> GenerateFileDocsResponse:
    try:
        if not generate_file_docs_request.github_url:
            raise HTTPException(status_code=http.client.UNPROCESSABLE_ENTITY,
                                detail="Required field 'github_url' is missing.")

        # TODO: create better validation of proper GitHub links
        github_client.extract_github_info(generate_file_docs_request.github_url)

        # add document to firebase
        doc_id = documentation_service.create_document_generation_job(
            background_tasks,
            generate_file_docs_request.github_url,
            generate_file_docs_request.model
        )

        return GenerateFileDocsResponse(
            message="Documentation generation has been started.",
            id=doc_id
        )
    except ValueError as e:
        raise HTTPException(status_code=http.client.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=http.client.INTERNAL_SERVER_ERROR)


@router.get("/file-docs/{doc_id}")
async def get_file_doc(
        doc_id: str,
        documentation_service: DocumentationService = Depends(get_documentation_service),
) -> GetFileDocsResponse:
    try:
        doc = documentation_service.get_documentation_with_content(doc_id)
        return GetFileDocsResponse(**doc)
    except ValueError as e:
        raise HTTPException(status_code=http.client.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logging.error(e)
