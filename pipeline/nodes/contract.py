# pipeline/nodes/contract.py
"""
Node 2 — Contract Red Flag Detection.
Calls Nova with extended thinking and returns a validated ContractRedFlags model.
"""

from __future__ import annotations

import logging

from models.schemas import ContractRedFlags, ContractFlag, RiskLevel
from pipeline.nova import get_nova_client, invoke_nova_json, NovaInvokeError
from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior M&A legal counsel specialising in contract risk.
Identify red flags and high-risk clauses in M&A documents.
Always respond in valid JSON only. No preamble, no markdown.
CRITICAL: Every string value MUST be wrapped in double quotes. Never write unquoted text as a value."""

USER_PROMPT_TEMPLATE = """Review this M&A document for contract red flags and high-risk clauses.

DOCUMENT:
{document_text}

Return a JSON object with this exact structure:
{{
    "red_flags": [
        {{
            "clause": "clause name or description",
            "risk_level": "critical|high|medium|low",
            "explanation": "why this is risky",
            "recommendation": "what to negotiate or watch out for",
            "probability": 75,
            "impact": 85
        }}
    ],
    "liability_exposure": "high|medium|low",
    "ip_ownership_issues": true,
    "termination_risks": ["risk1", "risk2"],
    "indemnification_concerns": ["concern1", "concern2"],
    "overall_contract_risk": "critical|high|medium|low",
    "legal_score": 45,
    "coverage_pct": 80,
    "summary": "2-3 sentence plain English summary"
}}

SCORING RULES:
- legal_score: 0-100 overall legal health (100=clean contracts, 0=catastrophic exposure)
- red_flags[].probability: 0-100 likelihood this risk materialises
- red_flags[].impact: 0-100 business impact if it does materialise
- coverage_pct: how thoroughly you could review contracts from the docs (0-100)"""


def contract_node(state: dict) -> dict:
    """
    LangGraph node — contract red flag detection.

    Reads:   state["document_text"]
    Writes:  state["contract_red_flags"]  (ContractRedFlags instance, serialised to dict)
    """
    logger.info("Node: Contract Red Flag Detection — starting")
    client = get_nova_client()

    user_prompt = USER_PROMPT_TEMPLATE.format(
        document_text=state["document_text"][: settings.node_char_limit]
    )

    try:
        raw = invoke_nova_json(client, SYSTEM_PROMPT, user_prompt, use_extended_thinking=True)

        flags = [
            ContractFlag(
                clause=f.get("clause", ""),
                risk_level=RiskLevel(f.get("risk_level", "medium")),
                explanation=f.get("explanation", ""),
                recommendation=f.get("recommendation", ""),
                probability=int(f.get("probability", 50)),
                impact=int(f.get("impact", 50)),
            )
            for f in raw.get("red_flags", [])
        ]

        result = ContractRedFlags(
            red_flags=flags,
            liability_exposure=RiskLevel(raw.get("liability_exposure", "unknown")),
            ip_ownership_issues=bool(raw.get("ip_ownership_issues", False)),
            termination_risks=raw.get("termination_risks", []),
            indemnification_concerns=raw.get("indemnification_concerns", []),
            overall_contract_risk=RiskLevel(raw.get("overall_contract_risk", "unknown")),
            legal_score=int(raw.get("legal_score", 50)),
            coverage_pct=int(raw.get("coverage_pct", 80)),
            summary=raw.get("summary", ""),
        )
        logger.info(
            "Node: Contract Red Flag Detection — complete (%d flags, score=%d)",
            len(flags), result.legal_score,
        )

    except (NovaInvokeError, Exception) as exc:
        logger.error("Node: Contract Red Flag Detection — failed: %s", exc)
        result = ContractRedFlags(summary=f"Contract analysis failed: {exc}")

    return {**state, "contract_red_flags": result.model_dump()}