# frontend/api_client.py
"""
HTTP client for the VDR Intelligence FastAPI backend.
Dash app imports from here instead of calling the pipeline directly.
"""

from __future__ import annotations

import logging
import requests

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT  = 300  # pipeline can take a while with extended thinking


def upload_files(file_tuples: list[tuple[str, bytes]]) -> dict:
    """
    Upload one or more files to POST /upload.

    Args:
        file_tuples: List of (filename, file_bytes) tuples.

    Returns:
        UploadResponse dict with keys: doc_id, filename, char_count, extracted_text
    """
    files = [
        ("files", (filename, file_bytes, _mime(filename)))
        for filename, file_bytes in file_tuples
    ]
    resp = requests.post(f"{BASE_URL}/upload", files=files, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def run_diligence(document_text: str, document_name: str = "document") -> dict:
    """
    Call POST /diligence/run synchronously.

    Returns:
        DiligenceResult dict with financial_analysis, contract_red_flags,
        compliance_issues, synthesis_report
    """
    resp = requests.post(
        f"{BASE_URL}/diligence/run",
        json={"document_text": document_text, "document_name": document_name},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_dashboard(doc_id: str) -> dict:
    """
    Call GET /diligence/{doc_id}/dashboard.

    Returns:
        DashboardScores dict — flat, chart-ready payload.
    """
    resp = requests.get(f"{BASE_URL}/diligence/{doc_id}/dashboard", timeout=30)
    resp.raise_for_status()
    return resp.json()


def chat(doc_id: str, message: str, history: list[dict]) -> str:
    """
    Call POST /diligence/{doc_id}/chat.

    Args:
        doc_id:   SHA-256 doc hash from upload or run response
        message:  User message
        history:  List of {"role": "user"|"assistant", "content": "..."} dicts

    Returns:
        Nova's reply string
    """
    resp = requests.post(
        f"{BASE_URL}/diligence/{doc_id}/chat",
        json={"message": message, "history": history},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["reply"]


def extract_from_folder(folder_path: str) -> dict:
    """
    Folder path extraction still runs locally (no file transfer needed).
    Calls the ingestion layer directly, then hits /run.

    Returns:
        DiligenceResult dict
    """
    from ingestion.extractor import extract_from_folder as _extract
    import os, hashlib
    text = _extract(folder_path)
    name = os.path.basename(folder_path)
    result = run_diligence(text, name)
    result["doc_id"] = hashlib.sha256(text.encode()).hexdigest()
    return result


def _mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "pdf":  "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls":  "application/vnd.ms-excel",
    }.get(ext, "application/octet-stream")