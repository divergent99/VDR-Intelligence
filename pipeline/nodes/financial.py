# pipeline/nodes/financial.py
"""
Node 1 — Financial Health Analysis.
Calls Nova with extended thinking and returns a validated FinancialAnalysis model.
"""

from __future__ import annotations

import logging

from models.schemas import FinancialAnalysis, FinancialSubscores, RiskLevel, Trend, CashPosition
from pipeline.nova import get_nova_client, invoke_nova_json, NovaInvokeError
from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior M&A financial analyst.
Analyse the provided document and extract key financial health indicators.
Always respond in valid JSON only. No preamble, no markdown.
CRITICAL: Every string value MUST be wrapped in double quotes. Never write unquoted text as a value."""

USER_PROMPT_TEMPLATE = """Analyse this M&A document for financial health indicators.

DOCUMENT:
{document_text}

Return a JSON object with this exact structure:
{{
    "revenue_trend": "growing|stable|declining|unknown",
    "ebitda_margin": "percentage or unknown",
    "debt_to_equity": "ratio or unknown",
    "cash_position": "strong|adequate|weak|unknown",
    "key_financial_risks": ["risk1", "risk2"],
    "key_financial_positives": ["positive1", "positive2"],
    "overall_financial_health": "strong|moderate|weak|critical",
    "confidence_score": 0.85,
    "financial_score": 65,
    "scores": {{
        "revenue_quality": 70,
        "margin_health": 55,
        "debt_sustainability": 40,
        "cash_adequacy": 60,
        "earnings_quality": 65
    }},
    "revenue_cagr_pct": 8.5,
    "ebitda_margin_pct": 12.3,
    "debt_to_ebitda": 3.2,
    "coverage_pct": 85,
    "summary": "2-3 sentence plain English summary"
}}

SCORING RULES (be accurate, not generous):
- financial_score: 0-100 overall financial health. 0=catastrophic, 50=mediocre, 100=excellent.
- scores.*: 0-100 per sub-dimension. Base on actual data found in documents.
- revenue_cagr_pct: historical revenue CAGR % (number only, null if unknown)
- ebitda_margin_pct: EBITDA margin % (number only, null if unknown)
- debt_to_ebitda: net debt / EBITDA ratio (number only, null if unknown)
- coverage_pct: how much of the financial picture you could assess (0-100)"""


def _nova_to_risk_level(val: str) -> RiskLevel:
    mapping = {
        "strong": RiskLevel.LOW,
        "moderate": RiskLevel.MEDIUM,
        "weak": RiskLevel.HIGH,
        "critical": RiskLevel.CRITICAL,
    }
    return mapping.get(str(val).lower(), RiskLevel.UNKNOWN)


def financial_node(state: dict) -> dict:
    """
    LangGraph node — financial health analysis.

    Reads:   state["document_text"]
    Writes:  state["financial_analysis"]  (FinancialAnalysis instance, serialised to dict)
    """
    logger.info("Node: Financial Health Analysis — starting")
    client = get_nova_client()

    user_prompt = USER_PROMPT_TEMPLATE.format(
        document_text=state["document_text"][: settings.node_char_limit]
    )

    try:
        raw = invoke_nova_json(client, SYSTEM_PROMPT, user_prompt, use_extended_thinking=True)

        # Map Nova's free-text health label to RiskLevel
        overall_health_raw = raw.pop("overall_financial_health", "unknown")

        analysis = FinancialAnalysis(
            revenue_trend=Trend(raw.get("revenue_trend", "unknown")),
            cash_position=CashPosition(raw.get("cash_position", "unknown")),
            ebitda_margin=raw.get("ebitda_margin"),
            debt_to_equity=raw.get("debt_to_equity"),
            revenue_cagr_pct=raw.get("revenue_cagr_pct"),
            ebitda_margin_pct=raw.get("ebitda_margin_pct"),
            debt_to_ebitda=raw.get("debt_to_ebitda"),
            key_financial_risks=raw.get("key_financial_risks", []),
            key_financial_positives=raw.get("key_financial_positives", []),
            financial_score=int(raw.get("financial_score", 50)),
            scores=FinancialSubscores(**raw.get("scores", {})),
            confidence_score=float(raw.get("confidence_score", 0.8)),
            coverage_pct=int(raw.get("coverage_pct", 80)),
            overall_financial_health=_nova_to_risk_level(overall_health_raw),
            summary=raw.get("summary", ""),
        )
        logger.info("Node: Financial Health Analysis — complete (score=%d)", analysis.financial_score)

    except (NovaInvokeError, Exception) as exc:
        logger.error("Node: Financial Health Analysis — failed: %s", exc)
        analysis = FinancialAnalysis(
            summary=f"Financial analysis failed: {exc}",
            overall_financial_health=RiskLevel.UNKNOWN,
        )

    return {**state, "financial_analysis": analysis.model_dump()}