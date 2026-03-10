# api/main.py
"""
FastAPI application entry point.
Run with:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes.upload import router as upload_router
from api.routes.diligence import router as diligence_router
from api.routes.chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# LIFESPAN — startup / shutdown
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once on startup, once on shutdown.
    Warms up ChromaDB and validates the Bedrock client before accepting requests.
    """
    logger.info("VDR Intelligence API starting up...")
    logger.info("Nova model  : %s", settings.nova_model_id)
    logger.info("AWS region  : %s", settings.aws_region)
    logger.info("Cache path  : %s (enabled=%s)", settings.chroma_path, settings.cache_enabled)
    logger.info("CORS origins: %s", settings.cors_origins)

    # Warm up ChromaDB so first request isn't slow
    from pipeline.cache import _get_collection
    _get_collection()

    # Validate Bedrock client — fail fast if AWS creds are wrong
    try:
        from pipeline.nova import get_nova_client
        get_nova_client()
        logger.info("Bedrock client: OK")
    except Exception as exc:
        logger.warning("Bedrock client could not be initialised: %s", exc)
        logger.warning("Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env")

    logger.info("VDR Intelligence API ready on port %s", settings.api_port)

    yield

    logger.info("VDR Intelligence API shutting down...")


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────

app = FastAPI(
    title="VDR Intelligence API",
    description="M&A Due Diligence Orchestrator powered by Amazon Nova 2 via AWS Bedrock",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────

app.include_router(upload_router,    prefix=settings.api_prefix)
app.include_router(diligence_router, prefix=settings.api_prefix)
app.include_router(chat_router,      prefix=settings.api_prefix)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/health", tags=["health"])
def health():
    return {
        "status":  "ok",
        "model":   settings.nova_model_id,
        "region":  settings.aws_region,
        "cache":   settings.cache_enabled,
    }


@app.get("/", tags=["health"])
def root():
    return {
        "api":     "VDR Intelligence",
        "version": "1.0.0",
        "docs":    "/docs",
    }