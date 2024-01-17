import http.client
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from schemas.documentation_generation import DocsStatusEnum, GenerateFileDocsRequest, GenerateFileDocsResponse, \
    GetFileDocsResponse
from services.clients.github_client import GitHubClient, get_github_client
from services.documentation_service import DocumentationService, get_documentation_service
from services.clients.firebase_client import FirebaseClient, get_firebase_client

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

        # validate no error is thrown
        github_client.extract_github_info(generate_file_docs_request.github_url)

        # add document to firebase
        document_ref = documentation_service.create_document_generation_job(
            background_tasks,
            generate_file_docs_request.github_url
        )

        return GenerateFileDocsResponse(
            message="Documentation generation has been started.",
            id=document_ref.id
        )
    except ValueError as e:
        raise HTTPException(status_code=http.client.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=http.client.INTERNAL_SERVER_ERROR)


@router.get("/file-docs/{id}")
async def get_file_docs(
        id: str,
        firebase_client: FirebaseClient = Depends(get_firebase_client),
) -> GetFileDocsResponse:
    try:
        document_dict = firebase_client.get_document(firebase_client.TEST_COLLECTION, id).to_dict()

        if not document_dict:
            raise HTTPException(status_code=http.client.NOT_FOUND, detail=f"Document {id} not found.")

        status = DocsStatusEnum(document_dict.get("status"))
        blob_url = document_dict.get("bucket_url")

        # if it is completed get the content, otherwise return None
        content = None
        if status == DocsStatusEnum.COMPLETED:
            content = firebase_client.get_blob(blob_url).download_as_string()

        return GetFileDocsResponse(
            id=id,
            status=status,
            content=content
        )
    except ValueError as e:
        raise HTTPException(status_code=http.client.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=http.client.INTERNAL_SERVER_ERROR)
