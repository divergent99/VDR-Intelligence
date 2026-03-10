# pipeline/nodes/synthesis.py
"""
Node 4 — Synthesis & Report Generation.
Reads outputs from all 3 prior nodes, calls Nova, returns a validated SynthesisReport.
"""

from __future__ import annotations

import json
import logging

from models.schemas import (
    SynthesisReport, TopRedFlag, RiskMatrix, ScoreBreakdown,
    DiligenceCoverage, DealRisk, RiskLevel, DealRecommendation, DealArea,
)
from pipeline.nova import get_nova_client, invoke_nova_json, NovaInvokeError
from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior M&A partner writing an executive due diligence report.
Synthesise financial, legal, and compliance findings into a clear executive summary.
Always respond in valid JSON only. No preamble, no markdown."""

USER_PROMPT_TEMPLATE = """Synthesise these M&A due diligence findings into an executive report.

FINANCIAL ANALYSIS:
{financial_analysis}

CONTRACT RED FLAGS:
{contract_red_flags}

COMPLIANCE ISSUES:
{compliance_issues}

Return a JSON object with this exact structure:
{{
    "deal_recommendation": "proceed|proceed_with_conditions|do_not_proceed",
    "overall_risk_rating": "critical|high|medium|low",
    "deal_score": 42,
    "executive_summary": "3-5 sentence plain English summary for C-suite",
    "top_3_red_flags": [
        {{"flag": "description", "severity": "critical|high|medium", "area": "financial|legal|compliance"}}
    ],
    "risk_matrix": {{
        "financial": "critical|high|medium|low",
        "legal": "critical|high|medium|low",
        "compliance": "critical|high|medium|low",
        "overall": "critical|high|medium|low"
    }},
    "score_breakdown": {{
        "financial": 65,
        "legal": 35,
        "compliance": 45,
        "overall": 42
    }},
    "diligence_coverage": {{
        "financial_documents": 85,
        "legal_contracts": 70,
        "compliance_docs": 60,
        "ip_documents": 40,
        "hr_documents": 30
    }},
    "recommended_conditions": ["condition1", "condition2"],
    "next_steps": ["step1", "step2", "step3"],
    "deal_risks_summary": [
        {{"risk": "short risk name", "probability": 70, "impact": 85, "area": "financial|legal|compliance"}}
    ]
}}

SCORING RULES (judges will scrutinise these):
- deal_score: 0-100 weighted composite. Formula: financial*0.4 + legal*0.35 + compliance*0.25
- score_breakdown.*: 0-100 per area. 0=catastrophic, 25=critical, 50=significant concerns, 75=manageable, 100=clean
- diligence_coverage.*: 0-100 how thoroughly that document type was covered in the VDR
- deal_risks_summary: top 5 risks with probability (0-100) and impact (0-100)
- Be calibrated: critical financial issues should score 15-30, not 65"""


def synthesis_node(state: dict) -> dict:
    """
    LangGraph node — synthesis & report generation.

    Reads:   state["financial_analysis"], state["contract_red_flags"], state["compliance_issues"]
    Writes:  state["synthesis_report"]  (SynthesisReport instance, serialised to dict)
    """
    logger.info("Node: Synthesis & Report Generation — starting")
    client = get_nova_client()

    user_prompt = USER_PROMPT_TEMPLATE.format(
        financial_analysis=json.dumps(state.get("financial_analysis") or {}, indent=2),
        contract_red_flags=json.dumps(state.get("contract_red_flags") or {}, indent=2),
        compliance_issues= json.dumps(state.get("compliance_issues")  or {}, indent=2),
    )

    try:
        raw = invoke_nova_json(client, SYSTEM_PROMPT, user_prompt, use_extended_thinking=True)

        # ── Top 3 red flags ──────────────────────────────────────
        top_flags = [
            TopRedFlag(
                flag=f.get("flag", ""),
                severity=RiskLevel(f.get("severity", "medium")),
                area=DealArea(f.get("area", "financial")),
            )
            for f in raw.get("top_3_red_flags", [])
        ]

        # ── Risk matrix ──────────────────────────────────────────
        rm_raw = raw.get("risk_matrix", {})
        risk_matrix = RiskMatrix(
            financial =RiskLevel(rm_raw.get("financial",  "unknown")),
            legal     =RiskLevel(rm_raw.get("legal",      "unknown")),
            compliance=RiskLevel(rm_raw.get("compliance", "unknown")),
            overall   =RiskLevel(rm_raw.get("overall",    "unknown")),
        )

        # ── Score breakdown (validator auto-recalculates overall if needed) ──
        sb_raw = raw.get("score_breakdown", {})
        score_breakdown = ScoreBreakdown(
            financial =int(sb_raw.get("financial",  50)),
            legal     =int(sb_raw.get("legal",      50)),
            compliance=int(sb_raw.get("compliance", 50)),
            overall   =int(sb_raw.get("overall",    50)),
        )

        # ── Coverage ─────────────────────────────────────────────
        cov_raw = raw.get("diligence_coverage", {})
        coverage = DiligenceCoverage(
            financial_documents=int(cov_raw.get("financial_documents", 80)),
            legal_contracts    =int(cov_raw.get("legal_contracts",     70)),
            compliance_docs    =int(cov_raw.get("compliance_docs",     60)),
            ip_documents       =int(cov_raw.get("ip_documents",        40)),
            hr_documents       =int(cov_raw.get("hr_documents",        30)),
        )

        # ── Deal risks for heatmap ───────────────────────────────
        deal_risks = [
            DealRisk(
                risk       =r.get("risk", ""),
                probability=int(r.get("probability", 50)),
                impact     =int(r.get("impact", 50)),
                area       =DealArea(r.get("area", "financial")),
            )
            for r in raw.get("deal_risks_summary", [])
        ]

        deal_score = int(raw.get("deal_score", score_breakdown.overall))
        if deal_score >= 70:
            recommendation = DealRecommendation.PROCEED
        elif deal_score >= 45:
            recommendation = DealRecommendation.PROCEED_WITH_CONDITIONS
        else:
            recommendation = DealRecommendation.DO_NOT_PROCEED

        result = SynthesisReport(
            deal_recommendation=recommendation,
            overall_risk_rating=RiskLevel(raw.get("overall_risk_rating", "unknown")),
            deal_score         =deal_score,
            executive_summary  =raw.get("executive_summary", ""),
            top_3_red_flags    =top_flags,
            risk_matrix        =risk_matrix,
            score_breakdown    =score_breakdown,
            diligence_coverage =coverage,
            recommended_conditions=raw.get("recommended_conditions", []),
            next_steps         =raw.get("next_steps", []),
            deal_risks_summary =deal_risks,
        )
        logger.info(
            "Node: Synthesis — complete (deal_score=%d, recommendation=%s)",
            result.deal_score, result.deal_recommendation,
        )

    except (NovaInvokeError, Exception) as exc:
        logger.error("Node: Synthesis & Report Generation — failed: %s", exc)
        result = SynthesisReport(
            executive_summary=f"Synthesis failed: {exc}",
        )

    return {**state, "synthesis_report": result.model_dump()}