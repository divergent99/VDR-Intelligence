# api/routes/chat.py
"""
Chat route:
  POST /diligence/{doc_id}/chat — Nova Q&A grounded in the diligence result
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from models.schemas import ChatRequest, ChatResponse, DiligenceResult
from api.dependencies import get_cached_result, get_bedrock_client
from pipeline.nova import invoke_nova, NovaInvokeError
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diligence", tags=["chat"])

SYSTEM_PROMPT_TEMPLATE = """You are NOVA, an elite M&A due diligence AI assistant with deep expertise in corporate finance, contract law, and regulatory compliance.

SCOPE RULES:
- You ONLY answer questions about this specific deal, M&A concepts, financial analysis, legal risks, compliance, and deal structuring.
- For greetings respond warmly but briefly — 1-2 sentences max — then offer to help with the deal.
- For anything unrelated to M&A or this deal, decline in one sentence: "I'm scoped to M&A due diligence — happy to help with anything about this deal."
- Never fabricate data. If the answer is not in the report, say so clearly.

RESPONSE FORMAT:
- Always use rich markdown formatting for analytical responses.
- Use **bold** for key terms, risk labels, financial figures, and important conclusions.
- Use bullet lists (- item) for enumerating risks, steps, flags, or recommendations.
- Use numbered lists (1. item) for prioritised actions or sequential steps.
- Use markdown tables for comparisons, score summaries, or structured data e.g.:
  | Area | Score | Risk Level |
  |------|-------|------------|
  | Financial | 85 | Low |
- Use `### headers` to structure longer analytical responses into clear sections.
- Use > blockquotes for direct deal-specific warnings or critical callouts.
- For simple one-liner questions answer in 1-2 sentences with no unnecessary structure.
- For analytical questions (risks, recommendations, comparisons) always use structured formatting.
- Never truncate mid-sentence. Complete every thought fully.

ANALYTICAL DEPTH:
- When asked about risks, quantify them where possible using data from the report (scores, percentages, counts).
- When asked for recommendations, provide specific, actionable advice tied to the deal data.
- When asked to compare areas (e.g. financial vs legal), use tables or structured comparisons.
- Always ground your answers in the deal report data — cite specific figures, flags, or findings.
- If asked "should we proceed", give a clear recommendation with supporting evidence from the report.

DEAL REPORT (your only source of truth):
{context}"""


def _build_context(result: DiligenceResult) -> str:
    """Serialise the diligence result into a compact context string for Nova."""
    context = {
        "synthesis":  result.synthesis_report.model_dump()  if result.synthesis_report  else {},
        "financial":  result.financial_analysis.model_dump() if result.financial_analysis else {},
        "contract":   result.contract_red_flags.model_dump() if result.contract_red_flags else {},
        "compliance": result.compliance_issues.model_dump()  if result.compliance_issues  else {},
    }
    # Cap context to avoid blowing Nova's input limit
    return json.dumps(context, indent=2)[:6000]


def _build_messages(request: ChatRequest) -> list[dict]:
    """Convert ChatRequest history + new message into Bedrock converse format."""
    messages = []
    for turn in request.history[-6:]:  # last 6 turns = 3 exchanges
        messages.append({"role": turn.role, "content": [{"text": turn.content}]})
    messages.append({"role": "user", "content": [{"text": request.message}]})
    return messages


# ─────────────────────────────────────────────
# POST /diligence/{doc_id}/chat
# ─────────────────────────────────────────────

@router.post("/{doc_id}/chat", response_model=ChatResponse)
def chat(
    doc_id: str,
    request: ChatRequest,
    result: DiligenceResult = Depends(get_cached_result),
    client=Depends(get_bedrock_client),
) -> ChatResponse:
    """
    Ask Nova anything about a specific diligence result.
    Answers are grounded solely in the cached report — no hallucination.

    - Pass the doc_id returned by POST /upload or POST /diligence/run
    - Include conversation history for multi-turn context
    """
    context = _build_context(result)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)
    messages = _build_messages(request)

    logger.info("POST /diligence/%s…/chat — message='%.80s'", doc_id[:12], request.message)

    try:
        response = client.converse(
            modelId=settings.nova_model_id,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={"maxTokens": 2048, "temperature": 0.2},
        )
        reply = response["output"]["message"]["content"][0]["text"]
        logger.info("Chat reply received (%d chars)", len(reply))

    except NovaInvokeError as exc:
        logger.error("Nova chat error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Nova invocation failed: {exc}")
    except Exception as exc:
        logger.error("Unexpected chat error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(reply=reply, doc_id=doc_id, job_id=doc_id)