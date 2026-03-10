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

from fastapi import Depends, HTTPException

from config import Settings, get_settings
from models.schemas import DiligenceResult
from pipeline.cache import cache_get
from pipeline.nova import get_nova_client

logger = logging.getLogger(__name__)


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