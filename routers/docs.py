from typing import Dict, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from schemas.documentation_generation import GenerateFileDocsRequest, GenerateFileDocsResponse, \
    GetFileDocsResponse, DeleteFileDocsResponse, UpdateFileDocsResponse, LlmModelEnum
from services.data_service import get_data_service, DataService
from services.github_service import GithubService, get_github_service
from services.documentation_service import DocumentationService, get_documentation_service
from routers.utils.auth import get_user_token

router = APIRouter()


@router.post("/file-docs", status_code=status.HTTP_202_ACCEPTED)
async def generate_file_docs(
        request: GenerateFileDocsRequest,
        background_tasks: BackgroundTasks,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        github_service: GithubService = Depends(get_github_service),
        user: Dict[str, Any] = Depends(get_user_token),
        model: LlmModelEnum = LlmModelEnum.MIXTRAL
) -> GenerateFileDocsResponse:
    if not request.github_url:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Required field 'github_url' is missing.")

    github_file = github_service.get_file(request.github_url)
    doc_id = documentation_service.enqueue_generate_doc_job(
        background_tasks,
        github_file,
        model
    )

    return GenerateFileDocsResponse(
        message="Documentation generation has been started.",
        id=doc_id
    )


@router.get("/file-docs/{doc_id}")
async def get_file_docs(
        doc_id: str,
        data_service: DataService = Depends(get_data_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetFileDocsResponse:
    doc = data_service.get_documentation(doc_id)
    if not doc:
        raise 
    return GetFileDocsResponse(**doc)


@router.delete("/file-docs/{doc_id}")
async def delete_file_docs(
        doc_id: str,
        data_service: DataService = Depends(get_data_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> DeleteFileDocsResponse:
    data_service.delete_documentation(doc_id)

    return DeleteFileDocsResponse(
        message=f"The data associated with id='{doc_id}' was deleted.",
        id=doc_id
    )


@router.put("/file-docs/{doc_id}", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_file_docs(
        doc_id: str,
        background_tasks: BackgroundTasks,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
        model: LlmModelEnum = LlmModelEnum.MIXTRAL,
) -> UpdateFileDocsResponse:
    doc_id = documentation_service.regenerate_doc(
        background_tasks,
        doc_id,
        model
    )

    return UpdateFileDocsResponse(
        message="Documentation regeneration has been started.",
        id=doc_id
    )
