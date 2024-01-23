from typing import Dict, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from schemas.documentation_generation import GetRepoResponse, GetReposResponse, RepoModel
from services.clients.github_client import GitHubClient, get_github_client
from services.documentation_service import DocumentationService, get_documentation_service
from routers.utils.auth import get_user_token

router = APIRouter()

# for now returns all repos ids, no users yet
@router.get("/repos")
async def get_repos(
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetReposResponse:
    repos_ids = documentation_service.get_repos_ids_list()

    return GetReposResponse(repos=repos_ids)

# for now returns all repos
@router.get("/repos/{repo_id}")
async def get_repos(
        repo_id: str,
        documentation_service: DocumentationService = Depends(get_documentation_service),
        user: Dict[str, Any] = Depends(get_user_token),
) -> GetRepoResponse:
    repo = documentation_service.get_repo(repo_id)
    
    return GetRepoResponse(repo=RepoModel.from_firestore_model(repo))
