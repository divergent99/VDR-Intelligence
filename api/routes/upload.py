# api/routes/upload.py
"""
Upload route:
  POST /upload — accept one or more VDR files, extract text, return ready-to-use payload
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List

from models.schemas import UploadResponse
from ingestion.extractor import extract_from_bytes, combine_uploads

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

SUPPORTED = {".pdf", ".docx", ".xlsx", ".xls"}


@router.post("", response_model=UploadResponse)
async def upload_files(files: List[UploadFile] = File(...)) -> UploadResponse:
    """
    Accept one or more VDR documents, extract their text, and return
    a combined payload ready to pass directly into POST /diligence/run.

    - Supports PDF, DOCX, XLSX, XLS
    - Multiple files are combined into one document_text string
    - doc_id is a SHA-256 of the combined text — matches the cache key
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    extracted: list[tuple[str, str]] = []

    for file in files:
        filename = file.filename or "unknown"
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in SUPPORTED:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{ext}' for '{filename}'. Allowed: {', '.join(SUPPORTED)}",
            )

        try:
            file_bytes = await file.read()
            text = extract_from_bytes(file_bytes, filename)
            extracted.append((filename, text))
            logger.info("Extracted '%s': %d chars", filename, len(text))
        except Exception as exc:
            logger.error("Failed to extract '%s': %s", filename, exc)
            raise HTTPException(
                status_code=422,
                detail=f"Failed to extract text from '{filename}': {exc}",
            )

    if not extracted:
        raise HTTPException(status_code=422, detail="No text could be extracted from the uploaded files.")

    # Combine all files into one string
    from ingestion.extractor import combine_uploads
    combined_text = combine_uploads(extracted)

    # doc_id = SHA-256 of combined text — same as the cache key pipeline uses
    doc_id = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()

    filenames = ", ".join(f for f, _ in extracted)
    logger.info("Upload complete: %d file(s), %d chars, doc_id=%s…", len(extracted), len(combined_text), doc_id[:12])

    return UploadResponse(
        doc_id=doc_id,
        filename=filenames,
        char_count=len(combined_text),
        extracted_text=combined_text,
    )