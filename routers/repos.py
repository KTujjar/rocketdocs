from typing import Dict, Any

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from starlette import status

from schemas.documentation_generation import (
    GenerateRepoDocsResponse,
    GetRepoResponse,
    GetReposResponse,
    ReposResponseModel,
    CreateRepoDocsRequest,
    CreateRepoDocsResponse,
    FirestoreRepo,
    LlmModelEnum,
    GetFileDocsResponse,
    DeleteRepoResponse,
    UploadRepoRequest,
    UploadRepoResponse,
)
from services.documentation_service import (
    DocumentationService,
    get_documentation_service,
)
from services.github_service import GithubService, get_github_service
from services.identifier_service import IdentifierService, get_identifier_service
from services.data_service import DataService, get_data_service
from services.rag_service.embedding_service import EmbeddingService, get_embedding_service
from services.rag_service.search_service import SearchService, get_search_service
from routers import utils

router = APIRouter()


# for now returns all repos ids, no users yet
@router.get("/repos")
async def get_repos(
    data_service: DataService = Depends(get_data_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
) -> GetReposResponse:
    user_id = user.get("uid")

    repos_dicts = data_service.get_user_repos(user_id)
    repos = [FirestoreRepo(**repo_dict) for repo_dict in repos_dicts]
    repos_formatted = [
        ReposResponseModel(
            name=repo.repo_name,
            id=repo.id,
            status=repo.status,
            docs_status=[{doc.id: doc.status} for doc in repo.docs.values()],
        )
        for repo in repos
    ]

    return GetReposResponse(repos=repos_formatted)


@router.get("/repos/{repo_id}")
async def get_repo(
    repo_id: str,
    data_service: DataService = Depends(get_data_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
) -> GetRepoResponse:
    user_id = user.get("uid")

    repo_dict = data_service.get_user_repo(user_id, repo_id)
    repo = FirestoreRepo(**repo_dict)
    repo_formatted = utils.format_repo(repo)

    return GetRepoResponse(repo=repo_formatted)


@router.delete("/repos/{repo_id}")
async def delete_repo(
    repo_id: str,
    data_service: DataService = Depends(get_data_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
) -> DeleteRepoResponse:
    user_id = user.get("uid")

    repo_id = data_service.batch_delete_user_repo(user_id, repo_id)
    embedding_service.delete_repo(repo_id)

    return DeleteRepoResponse(
        message=f"The data associated with id='{repo_id}' was deleted.", id=repo_id
    )


@router.get("/repos/{repo_id}/search")
async def search_repo(
    repo_id: str,
    query: str,
    search_service: SearchService = Depends(get_search_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
):
    user_id = user.get("uid")
    results = await search_service.search(repo_id, query, user_id)
    return results


@router.get("/repos/{repo_id}/{doc_id}")
async def get_repo_doc(
    repo_id: str,
    doc_id: str,
    data_service: DataService = Depends(get_data_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
) -> GetFileDocsResponse:
    user_id = user.get("uid")
    doc = data_service.get_user_documentation(user_id, doc_id)

    if doc.repo != repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document does not belong to the repo",
        )

    return GetFileDocsResponse(**doc.model_dump())


@router.post("/repos")
async def create_repo_docs(
    request: CreateRepoDocsRequest,
    background_tasks: BackgroundTasks,
    identifier_service: IdentifierService = Depends(get_identifier_service),
    github_service: GithubService = Depends(get_github_service),
    documentation_service: DocumentationService = Depends(get_documentation_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
    model: LlmModelEnum = LlmModelEnum.MIXTRAL,
) -> CreateRepoDocsResponse:
    user_id = user.get("uid")
    github_repo = github_service.get_repo_from_url(request.github_url)
    firestore_repo = identifier_service.identify(github_repo, user_id)
    documentation_service.enqueue_generate_repo_docs_job(
        background_tasks, firestore_repo, model
    )
    background_tasks.add_task(embedding_service.generate_markdown_embeddings_for_repo, firestore_repo.id, user_id)
    return CreateRepoDocsResponse(
        message="Documentation generation has been started.", id=firestore_repo.id
    )


@router.post("/repos/identify")
async def upload_repo(
    request: UploadRepoRequest,
    identifier_service: IdentifierService = Depends(get_identifier_service),
    github_service: GithubService = Depends(get_github_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
) -> UploadRepoResponse:
    user_id = user.get("uid")
    github_repo = github_service.get_repo_from_url(request.github_url)
    firestore_repo = identifier_service.identify(github_repo, user_id)

    return UploadRepoResponse(
        message="Files and folders have been identified for documentation.",
        id=firestore_repo.id,
        items_to_document=firestore_repo.get_identified_docs(),
    )


@router.post("/repos/{repo_id}/generate")
async def generate_repo_docs(
    repo_id: str,
    background_tasks: BackgroundTasks,
    documentation_service: DocumentationService = Depends(get_documentation_service),
    data_service: DataService = Depends(get_data_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    user: Dict[str, Any] = Depends(utils.get_user_token),
    model: LlmModelEnum = LlmModelEnum.MIXTRAL,
) -> GenerateRepoDocsResponse:
    user_id = user.get("uid")
    repo_dict = data_service.get_user_repo(user_id, repo_id)
    repo = FirestoreRepo(**repo_dict)

    documentation_service.enqueue_generate_repo_docs_job(background_tasks, repo, model)
    background_tasks.add_task(embedding_service.generate_markdown_embeddings_for_repo, repo.id, user_id)

    return GenerateRepoDocsResponse(
        message="Documentation generation has been started.", id=repo.id
    )
