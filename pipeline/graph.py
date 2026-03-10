# pipeline/graph.py
"""
LangGraph pipeline — wires the 4 nodes into a compiled graph
and exposes run_diligence() as the single public entrypoint.

Flow: financial → contract → compliance → synthesis
"""

from __future__ import annotations

import logging
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from models.schemas import DiligenceResult
from pipeline.cache import cache_get, cache_set, doc_hash
from pipeline.nodes.financial  import financial_node
from pipeline.nodes.contract   import contract_node
from pipeline.nodes.compliance import compliance_node
from pipeline.nodes.synthesis  import synthesis_node

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# LANGGRAPH STATE
# TypedDict required by LangGraph; nodes read/write this dict.
# Pydantic models are serialised to dict before storing here.
# ─────────────────────────────────────────────

class DiligenceState(TypedDict):
    document_text:      str
    document_name:      str
    financial_analysis: Optional[dict]
    contract_red_flags: Optional[dict]
    compliance_issues:  Optional[dict]
    synthesis_report:   Optional[dict]
    error:              Optional[str]


# ─────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────

def build_graph():
    """Compile and return the LangGraph pipeline."""
    graph = StateGraph(DiligenceState)

    graph.add_node("financial",  financial_node)
    graph.add_node("contract",   contract_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("synthesis",  synthesis_node)

    graph.add_edge(START,        "financial")
    graph.add_edge("financial",  "contract")
    graph.add_edge("contract",   "compliance")
    graph.add_edge("compliance", "synthesis")
    graph.add_edge("synthesis",  END)

    return graph.compile()


# Compiled graph singleton — built once, reused across calls
_pipeline = None

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_graph()
    return _pipeline


# ─────────────────────────────────────────────
# PUBLIC ENTRYPOINT
# ─────────────────────────────────────────────

def run_diligence(document_text: str, document_name: str = "document") -> DiligenceResult:
    """
    Run the full 4-node due diligence pipeline.

    - Checks the ChromaDB cache first (same doc = instant return)
    - Invokes the LangGraph pipeline on a cache miss
    - Stores result in cache before returning
    - Always returns a DiligenceResult (never raises — errors are captured in .error)

    Args:
        document_text:  Extracted text from VDR documents (pre-truncated by ingestion layer)
        document_name:  Human-readable label for logging/cache metadata

    Returns:
        Validated DiligenceResult Pydantic model
    """
    key = doc_hash(document_text)

    # ── Cache check ──────────────────────────────────────────────
    cached = cache_get(key)
    if cached:
        logger.info("Cache hit for '%s' — skipping Nova pipeline", document_name)
        return DiligenceResult(**cached)

    # ── Run pipeline ─────────────────────────────────────────────
    logger.info("Starting pipeline for '%s' (key=%s…)", document_name, key[:12])

    initial_state: DiligenceState = {
        "document_text":      document_text,
        "document_name":      document_name,
        "financial_analysis": None,
        "contract_red_flags": None,
        "compliance_issues":  None,
        "synthesis_report":   None,
        "error":              None,
    }

    try:
        final_state = _get_pipeline().invoke(initial_state)
    except Exception as exc:
        logger.error("Pipeline invocation failed for '%s': %s", document_name, exc)
        result = DiligenceResult(document_name=document_name, error=str(exc))
        return result

    result = DiligenceResult(
        document_name      =document_name,
        financial_analysis =final_state.get("financial_analysis"),
        contract_red_flags =final_state.get("contract_red_flags"),
        compliance_issues  =final_state.get("compliance_issues"),
        synthesis_report   =final_state.get("synthesis_report"),
        error              =final_state.get("error"),
    )

    # ── Store in cache ───────────────────────────────────────────
    cache_set(key, result.model_dump())
    logger.info("Pipeline complete for '%s' (key=%s…)", document_name, key[:12])

    return result