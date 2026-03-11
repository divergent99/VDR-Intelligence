# api/dependencies.py
"""
Shared FastAPI dependencies injected via Depends().

Usage in a route:
    from api.dependencies import get_bedrock_client, get_cached_result

    @router.post("/run")
    def run(request: RunDiligenceRequest, client=Depends(get_bedrock_client)):
        ...
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session, create_engine, select

from config import Settings, get_settings
from models.schemas import DiligenceResult
from models.db import User, Project, ProjectAccess
from pipeline.cache import cache_get
from pipeline.nova import get_nova_client

logger = logging.getLogger(__name__)

# ── DATABASE SECRETS ─────────────────────────────────────────

engine = create_engine(
    get_settings().db_url, connect_args={"check_same_thread": False}
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_session():
    with Session(engine) as session:
        yield session

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[get_settings().jwt_algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise credentials_exception
    return user

def verify_project_access(doc_id: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """
    Google Docs-style access: anyone with the link (doc_id) can view.
    - If no DB record exists, auto-create with current user as owner.
    - If the owner no longer exists, transfer ownership.
    - If the user is neither owner nor collaborator, auto-add as collaborator.
    """
    project = session.exec(select(Project).where(Project.doc_id == doc_id)).first()

    if not project:
        project = Project(doc_id=doc_id, name="Imported Project", owner_id=current_user.id)
        session.add(project)
        session.commit()
        return True

    # Self-heal orphaned projects
    owner = session.exec(select(User).where(User.id == project.owner_id)).first()
    if not owner:
        project.owner_id = current_user.id
        session.add(project)
        session.commit()
        return True

    if project.owner_id == current_user.id:
        return True

    # Check if already a collaborator
    access = session.exec(
        select(ProjectAccess)
        .where(ProjectAccess.doc_id == doc_id)
        .where(ProjectAccess.user_id == current_user.id)
    ).first()

    if not access:
        # Auto-add as collaborator (anyone with the link gets access)
        access = ProjectAccess(doc_id=doc_id, user_id=current_user.id)
        session.add(access)
        session.commit()

    return True


# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────

def get_app_settings() -> Settings:
    """Inject the cached settings singleton."""
    return get_settings()


# ─────────────────────────────────────────────
# NOVA / BEDROCK CLIENT
# ─────────────────────────────────────────────

def get_bedrock_client():
    """
    Inject a boto3 bedrock-runtime client.
    boto3 handles connection pooling internally so this is cheap to call per request.
    """
    try:
        return get_nova_client()
    except Exception as exc:
        logger.error("Failed to initialise Bedrock client: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"AWS Bedrock client unavailable: {exc}. Check your AWS credentials in .env.",
        )


# ─────────────────────────────────────────────
# CACHE — resolve doc_id → DiligenceResult
# ─────────────────────────────────────────────

def get_cached_result(doc_id: str) -> DiligenceResult:
    """
    Resolve a doc_id path parameter into a DiligenceResult.
    Raises 404 if not found — use this in any route that needs a cached result.

    Usage:
        @router.get("/{doc_id}/dashboard")
        def dashboard(result: DiligenceResult = Depends(get_cached_result)):
            ...
    """
    cached = cache_get(doc_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No result found for doc_id '{doc_id[:12]}…'. "
                "Upload your documents and run the pipeline first."
            ),
        )
    return DiligenceResult(**cached)