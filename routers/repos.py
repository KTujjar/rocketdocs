from typing import Dict, Any, List

from fastapi import APIRouter, Depends

from schemas.documentation_generation import GetRepoResponse, GetReposResponse, RepoFormatted, ReposResponseModel
from services.documentation_service import DocumentationService, get_documentation_service
from routers.utils.auth import get_user_token

router = APIRouter()


# for now returns all repos ids, no users yet
@router.get("/repos")
async def get_repos(
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetReposResponse:
    repos: List[ReposResponseModel] = documentation_service.get_repos()

    return GetReposResponse(repos=repos)


# for now returns all repos
@router.get("/repos/{repo_id}")
async def get_repo(
        repo_id: str,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetRepoResponse:
    repo: RepoFormatted = documentation_service.get_repo(repo_id)

    return GetRepoResponse(repo=repo)
