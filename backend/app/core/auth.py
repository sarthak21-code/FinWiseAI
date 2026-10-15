from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db, set_database_context
from app.models.user import UserIdentity

_bearer = HTTPBearer(auto_error=False)
_ALLOWED_ALGORITHMS = ("ES256", "RS256")


@dataclass(frozen=True)
class VerifiedPrincipal:
    id: str
    issuer: str
    subject: str


def _issuer() -> str:
    base = settings.supabase_url.rstrip("/")
    parts = urlsplit(base)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.path not in ("", "/")
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )
    return f"{base}/auth/v1"


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        jwks_url,
        cache_jwk_set=True,
        lifespan=300,
        timeout=5,
    )


def verify_access_token(token: str) -> tuple[str, dict[str, Any]]:
    issuer = _issuer()
    audience = settings.supabase_jwt_audience.strip()
    if not audience:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )
    jwks_url = f"{issuer}/.well-known/jwks.json"
    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    except PyJWKClientConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication keys are temporarily unavailable.",
        ) from exc
    except PyJWKClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=list(_ALLOWED_ALGORITHMS),
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iss", "sub", "aud"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or claims.get("role") != "authenticated":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return issuer, claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UserIdentity:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    issuer, claims = verify_access_token(credentials.credentials)
    subject = claims["sub"]
    # The identity claims come only from the verified JWT. RLS reads these
    # transaction-local settings while resolving the stable internal ID.
    set_database_context(db, issuer=issuer, subject=subject, operator=False)
    identity = db.execute(
        select(UserIdentity).where(
            UserIdentity.issuer == issuer,
            UserIdentity.subject == subject,
        )
    ).scalar_one_or_none()
    if identity is not None:
        set_database_context(db, identity_id=identity.id)
        return identity

    identity = UserIdentity(issuer=issuer, subject=subject)
    db.add(identity)
    try:
        db.commit()
        db.refresh(identity)
        set_database_context(db, identity_id=identity.id)
        return identity
    except IntegrityError:
        db.rollback()
        identity = db.execute(
            select(UserIdentity).where(
                UserIdentity.issuer == issuer,
                UserIdentity.subject == subject,
            )
        ).scalar_one_or_none()
        if identity is not None:
            set_database_context(db, identity_id=identity.id)
            return identity
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to establish account identity.",
        )
