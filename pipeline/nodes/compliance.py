# pipeline/nodes/compliance.py
"""
Node 3 — Regulatory Compliance Check.
Calls Nova with extended thinking and returns a validated ComplianceIssues model.
"""

from __future__ import annotations

import logging

from models.schemas import ComplianceIssues, RiskLevel
from pipeline.nova import get_nova_client, invoke_nova_json, NovaInvokeError
from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an M&A regulatory compliance expert.
Identify regulatory, antitrust, and jurisdictional risks in M&A documents.
Always respond in valid JSON only. No preamble, no markdown.
CRITICAL: Every string value MUST be wrapped in double quotes. Never write unquoted text as a value."""

USER_PROMPT_TEMPLATE = """Assess this M&A document for regulatory and compliance risks.

DOCUMENT:
{document_text}

Return a JSON object with this exact structure:
{{
    "antitrust_concerns": ["concern1", "concern2"],
    "gdpr_data_privacy_issues": true,
    "gdpr_details": "details if applicable or null",
    "jurisdictional_risks": ["risk1", "risk2"],
    "regulatory_approvals_needed": ["approval1", "approval2"],
    "industry_specific_regulations": ["regulation1", "regulation2"],
    "overall_compliance_risk": "critical|high|medium|low",
    "blocking_issues": ["issue1"],
    "compliance_score": 50,
    "coverage_pct": 75,
    "summary": "2-3 sentence plain English summary"
}}

SCORING RULES:
- compliance_score: 0-100 overall compliance health (100=fully compliant, 0=deal-blocking issues)
- coverage_pct: how thoroughly you could assess compliance from available docs (0-100)"""


def compliance_node(state: dict) -> dict:
    """
    LangGraph node — regulatory compliance check.

    Reads:   state["document_text"]
    Writes:  state["compliance_issues"]  (ComplianceIssues instance, serialised to dict)
    """
    logger.info("Node: Regulatory Compliance Check — starting")
    client = get_nova_client()

    user_prompt = USER_PROMPT_TEMPLATE.format(
        document_text=state["document_text"][: settings.node_char_limit]
    )

    try:
        raw = invoke_nova_json(client, SYSTEM_PROMPT, user_prompt, use_extended_thinking=True)

        result = ComplianceIssues(
            antitrust_concerns=raw.get("antitrust_concerns", []),
            gdpr_data_privacy_issues=bool(raw.get("gdpr_data_privacy_issues", False)),
            gdpr_details=raw.get("gdpr_details"),
            jurisdictional_risks=raw.get("jurisdictional_risks", []),
            regulatory_approvals_needed=raw.get("regulatory_approvals_needed", []),
            industry_specific_regulations=raw.get("industry_specific_regulations", []),
            overall_compliance_risk=RiskLevel(raw.get("overall_compliance_risk", "unknown")),
            blocking_issues=raw.get("blocking_issues", []),
            compliance_score=int(raw.get("compliance_score", 50)),
            coverage_pct=int(raw.get("coverage_pct", 75)),
            summary=raw.get("summary", ""),
        )
        logger.info(
            "Node: Regulatory Compliance Check — complete (score=%d, blocking=%d)",
            result.compliance_score, len(result.blocking_issues),
        )

    except (NovaInvokeError, Exception) as exc:
        logger.error("Node: Regulatory Compliance Check — failed: %s", exc)
        result = ComplianceIssues(summary=f"Compliance analysis failed: {exc}")

    return {**state, "compliance_issues": result.model_dump()}