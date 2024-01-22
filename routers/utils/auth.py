import logging
from typing import Dict, Any

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth


def get_user_token(
        res: Response,
        credential: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
) -> Dict[str, Any]:
    if not credential:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={'WWW-Authenticate': 'Bearer realm="auth_required"'})
    try:
        decoded_token = auth.verify_id_token(credential.credentials)
    except Exception as e:
        logging.error(e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid authentication from Firebase. {e}",
                            headers={'WWW-Authenticate': 'Bearer error="invalid_token"'})
    res.headers['WWW-Authenticate'] = 'Bearer realm="auth_required"'
    return decoded_token
