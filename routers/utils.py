import logging
from typing import Dict, Any
from collections import deque

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth

from schemas.documentation_generation import (
    FirestoreRepo,
    RepoFormatted,
    StatusEnum,
    FirestoreDoc,
)


def get_user_token(
    res: Response,
    credential: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> Dict[str, Any]:
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Bearer realm="auth_required"'},
        )
    try:
        decoded_token = auth.verify_id_token(credential.credentials)
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication from Firebase. {e}",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    res.headers["WWW-Authenticate"] = 'Bearer realm="auth_required"'
    return decoded_token


def format_repo(repo_response: FirestoreRepo) -> RepoFormatted:
    root_doc: str = repo_response.root_doc
    repo_name: str = repo_response.repo_name
    repo_id: str = repo_response.id
    owner_id: str = repo_response.owner
    repo_status: StatusEnum = repo_response.status
    dependencies: dict[str, str] = repo_response.dependencies
    docs: list[FirestoreDoc] = list(repo_response.docs.values())

    repo_formatted = RepoFormatted(
        name=repo_name,
        id=repo_id,
        owner_id=owner_id,
        tree=[],
        nodes_map={},
        status=repo_status,
    )

    def find_doc_by_id(doc_list: list[FirestoreDoc], doc_id) -> FirestoreDoc | None:
        for doc in doc_list:
            if doc.id == doc_id:
                return doc
        return None

    def process_node(parent_id, child_id):
        parent_data: FirestoreDoc = find_doc_by_id(docs, parent_id)
        child_data: FirestoreDoc = find_doc_by_id(docs, child_id)

        repo_formatted.insert_node(parent_data, child_data)

    def bfs(root):
        used = set()

        if not root:
            return
        queue = deque([root])

        while queue:
            node = queue.popleft()
            for child, parent in dependencies.items():
                if parent == node and child not in used:
                    process_node(parent, child)
                    queue.append(child)
                    used.add(child)

    bfs(root_doc)

    return repo_formatted
