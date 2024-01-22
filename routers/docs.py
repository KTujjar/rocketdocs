from typing import Dict, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from schemas.documentation_generation import GenerateFileDocsRequest, GenerateFileDocsResponse, \
    GetFileDocsResponse, DeleteFileDocsResponse, UpdateFileDocsResponse, UpdateFileDocsRequest
from services.clients.github_client import GitHubClient, get_github_client
from services.documentation_service import DocumentationService, get_documentation_service
from routers.utils.auth import get_user_token

router = APIRouter()


@router.post("/file-docs", status_code=status.HTTP_202_ACCEPTED)
async def generate_file_docs(
        generate_file_docs_request: GenerateFileDocsRequest,
        background_tasks: BackgroundTasks,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        github_client: GitHubClient = Depends(get_github_client),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GenerateFileDocsResponse:
    if not generate_file_docs_request.github_url:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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


@router.get("/file-docs/{doc_id}")
async def get_file_docs(
        doc_id: str,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetFileDocsResponse:
    doc = documentation_service.get_documentation_with_content(doc_id)
    return GetFileDocsResponse(**doc)


@router.delete("/file-docs/{doc_id}")
async def delete_file_docs(
        doc_id: str,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> DeleteFileDocsResponse:
    documentation_service.delete_documentation(doc_id)

    return DeleteFileDocsResponse(
        id=doc_id,
        message=f"The data associated with id='{doc_id}' was deleted."
    )


@router.put("/file-docs/{doc_id}", status_code=status.HTTP_202_ACCEPTED)
async def update_file_docs(
        doc_id: str,
        update_file_docs_request: UpdateFileDocsRequest,
        background_tasks: BackgroundTasks,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> UpdateFileDocsResponse:

    doc_id = documentation_service.update_document_generation_job(
        background_tasks,
        doc_id,
        update_file_docs_request.model
    )

    return UpdateFileDocsResponse(
        message="Documentation regeneration has been started.",
        id=doc_id
    )