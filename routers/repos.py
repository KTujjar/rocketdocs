from typing import Dict, Any, List

from fastapi import APIRouter, Depends

from schemas.documentation_generation import GetRepoResponse, GetReposResponse, RepoFormatted, ReposResponseModel, \
    CreateRepoDocsRequest, CreateRepoDocsResponse
from services.documentation_service import DocumentationService, get_documentation_service
from routers.utils.auth import get_user_token
from services.github_service import GithubService, get_github_service
from services.identifier_service import IdentifierService, get_identifier_service

router = APIRouter()


# for now returns all repos ids, no users yet
@router.get("/repos")
async def get_repos(
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetReposResponse:
    user_id = user.get("uid")
    repos: List[ReposResponseModel] = documentation_service.get_user_repos(user_id)

    return GetReposResponse(repos=repos)


# for now returns all repos
@router.get("/repos/{repo_id}")
async def get_repo(
        repo_id: str,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetRepoResponse:
    user_id = user.get("uid")
    repo: RepoFormatted = documentation_service.get_user_repo(user_id, repo_id)
    

    return GetRepoResponse(repo=repo)


@router.post("/repos")
async def create_repo_docs(
        request: CreateRepoDocsRequest,
        identifier_service: IdentifierService = Depends(get_identifier_service),
        github_service: GithubService = Depends(get_github_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> CreateRepoDocsResponse:
    github_repo = github_service.get_repo_from_url(request.github_url)
    firestore_repo = identifier_service.identify(github_repo)

    return CreateRepoDocsResponse(
        message="Documentation generation has been started.",
        id=firestore_repo.id
    )

