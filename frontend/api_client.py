# frontend/api_client.py
"""
HTTP client for the VDR Intelligence FastAPI backend.
Dash app imports from here instead of calling the pipeline directly.
"""

from __future__ import annotations

import logging
import requests

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8001/api/v1"
TIMEOUT  = 300  # pipeline can take a while with extended thinking


def _headers(token: str | None) -> dict:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def register(email: str, password: str) -> dict:
    resp = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password}, timeout=10)
    resp.raise_for_status()
    return resp.json()

def login(email: str, password: str) -> dict:
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_my_projects(token: str) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/projects/me", headers=_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()

def share_project(token: str, doc_id: str, email: str) -> dict:
    resp = requests.post(f"{BASE_URL}/projects/{doc_id}/share", json={"email": email}, headers=_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def upload_files(file_tuples: list[tuple[str, bytes]], token: str = None) -> dict:
    files = [
        ("files", (filename, file_bytes, _mime(filename)))
        for filename, file_bytes in file_tuples
    ]
    resp = requests.post(f"{BASE_URL}/upload", files=files, headers=_headers(token), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def run_diligence(document_text: str, document_name: str = "document", token: str = None) -> dict:
    resp = requests.post(
        f"{BASE_URL}/diligence/run",
        json={"document_text": document_text, "document_name": document_name},
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_diligence(doc_id: str, token: str = None) -> dict:
    resp = requests.get(f"{BASE_URL}/diligence/{doc_id}", headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_dashboard(doc_id: str, token: str = None) -> dict:
    resp = requests.get(f"{BASE_URL}/diligence/{doc_id}/dashboard", headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_chat_history(token: str, doc_id: str) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/diligence/{doc_id}/chat", headers=_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_from_folder(folder_path: str, token: str = None) -> dict:
    import os
    SUPPORTED_EXTS = {".pdf", ".docx", ".xlsx", ".xls"}
    file_tuples: list[tuple[str, bytes]] = []
    for root, _dirs, filenames in os.walk(folder_path):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTS:
                full = os.path.join(root, fname)
                with open(full, "rb") as f:
                    file_tuples.append((fname, f.read()))
    if not file_tuples:
        raise ValueError(f"No supported files found in '{folder_path}'")
    return upload_files(file_tuples, token)


def _mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "pdf":  "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls":  "application/vnd.ms-excel",
    }.get(ext, "application/octet-stream")