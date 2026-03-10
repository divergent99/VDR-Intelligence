# api/routes/diligence.py
"""
Diligence routes:
  POST /diligence/run              — run pipeline, return full result
  GET  /diligence/{doc_id}         — fetch cached result by doc_id
  GET  /diligence/{doc_id}/dashboard — flat pre-shaped payload for frontend charts
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from models.schemas import (
    RunDiligenceRequest,
    DiligenceResult,
    DashboardScores,
    FinancialSubscores,
    DiligenceCoverage,
    RiskLevel,
    DealRecommendation,
    DealRisk,
    TopRedFlag,
)
from pipeline.graph import run_diligence
from pipeline.cache import cache_get
from api.dependencies import get_cached_result

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diligence", tags=["diligence"])


# ─────────────────────────────────────────────
# POST /diligence/run
# ─────────────────────────────────────────────

@router.post("/run", response_model=DiligenceResult)
def run(request: RunDiligenceRequest) -> DiligenceResult:
    """
    Run the full 4-node due diligence pipeline synchronously.
    Pass the extracted_text returned by POST /upload directly here.
    Cache hit = instant return, no Nova calls made.
    """
    logger.info(
        "POST /diligence/run — document='%s' (%d chars)",
        request.document_name, len(request.document_text),
    )
    import hashlib
    doc_id = hashlib.sha256(request.document_text.encode()).hexdigest()
    result = run_diligence(request.document_text, request.document_name)
    result.doc_id = doc_id
    return result


# ─────────────────────────────────────────────
# GET /diligence/{doc_id}
# ─────────────────────────────────────────────

@router.get("/{doc_id}", response_model=DiligenceResult)
def get_result(result: DiligenceResult = Depends(get_cached_result)) -> DiligenceResult:
    """
    Fetch a previously cached diligence result by doc_id (SHA-256 of document text).
    Use this to reload results without re-running the pipeline.
    """
    return result


# ─────────────────────────────────────────────
# GET /diligence/{doc_id}/dashboard
# ─────────────────────────────────────────────

@router.get("/{doc_id}/dashboard", response_model=DashboardScores)
def get_dashboard(result: DiligenceResult = Depends(get_cached_result)) -> DashboardScores:
    """
    Return a flat, pre-shaped payload for frontend chart rendering.
    Every value the UI needs is top-level — no nested unwrapping required.
    """
    return _build_dashboard(result)


# ─────────────────────────────────────────────
# HELPER — DiligenceResult → DashboardScores
# ─────────────────────────────────────────────

def _build_dashboard(result: DiligenceResult) -> DashboardScores:
    """
    Flatten a DiligenceResult into a DashboardScores payload.
    Provides safe defaults for every field so the frontend
    never receives nulls for chart data.
    """
    syn  = result.synthesis_report
    fin  = result.financial_analysis
    con  = result.contract_red_flags
    comp = result.compliance_issues

    # ── Scores ───────────────────────────────────────────────────
    deal_score       = syn.deal_score       if syn else 50
    financial_score  = fin.financial_score  if fin else 50
    legal_score      = con.legal_score      if con else 50
    compliance_score = comp.compliance_score if comp else 50

    deal_recommendation = syn.deal_recommendation if syn else DealRecommendation.PROCEED_WITH_CONDITIONS
    overall_risk        = syn.overall_risk_rating  if syn else RiskLevel.UNKNOWN

    # ── Stat cards ───────────────────────────────────────────────
    n_contract_flags   = len(con.red_flags)                    if con  else 0
    n_blocking_issues  = len(comp.blocking_issues)             if comp else 0
    n_approvals_needed = len(comp.regulatory_approvals_needed) if comp else 0

    # ── Financial sub-scores ─────────────────────────────────────
    financial_subscores = fin.scores if fin else FinancialSubscores()

    # ── Diligence coverage ───────────────────────────────────────
    diligence_coverage = syn.diligence_coverage if syn else DiligenceCoverage()

    # ── Risk heatmap ─────────────────────────────────────────────
    deal_risks: list[DealRisk] = syn.deal_risks_summary if syn else []

    # ── Top red flags ────────────────────────────────────────────
    top_3_red_flags: list[TopRedFlag] = syn.top_3_red_flags if syn else []

    # ── Summaries ────────────────────────────────────────────────
    executive_summary      = syn.executive_summary   if syn  else ""
    financial_summary      = fin.summary             if fin  else ""
    contract_summary       = con.summary             if con  else ""
    compliance_summary     = comp.summary            if comp else ""
    recommended_conditions = syn.recommended_conditions if syn else []
    next_steps             = syn.next_steps             if syn else []

    return DashboardScores(
        deal_score=deal_score,
        financial_score=financial_score,
        legal_score=legal_score,
        compliance_score=compliance_score,
        deal_recommendation=deal_recommendation,
        overall_risk=overall_risk,
        n_contract_flags=n_contract_flags,
        n_blocking_issues=n_blocking_issues,
        n_approvals_needed=n_approvals_needed,
        financial_subscores=financial_subscores,
        diligence_coverage=diligence_coverage,
        deal_risks=deal_risks,
        top_3_red_flags=top_3_red_flags,
        executive_summary=executive_summary,
        financial_summary=financial_summary,
        contract_summary=contract_summary,
        compliance_summary=compliance_summary,
        recommended_conditions=recommended_conditions,
        next_steps=next_steps,
    )