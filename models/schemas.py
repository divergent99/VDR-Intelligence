"""
models/schemas.py
Pydantic v2 schemas for the VDR Intelligence M&A Due Diligence pipeline.
One model per LangGraph node + shared primitives + API request/response wrappers.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────
# ENUMS — used across all models
# ─────────────────────────────────────────────

class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    UNKNOWN  = "unknown"


class Trend(str, Enum):
    GROWING   = "growing"
    STABLE    = "stable"
    DECLINING = "declining"
    UNKNOWN   = "unknown"


class CashPosition(str, Enum):
    STRONG   = "strong"
    ADEQUATE = "adequate"
    WEAK     = "weak"
    UNKNOWN  = "unknown"


class DealRecommendation(str, Enum):
    PROCEED                 = "proceed"
    PROCEED_WITH_CONDITIONS = "proceed_with_conditions"
    DO_NOT_PROCEED          = "do_not_proceed"


class JobStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"


class DealArea(str, Enum):
    FINANCIAL  = "financial"
    LEGAL      = "legal"
    COMPLIANCE = "compliance"


# ─────────────────────────────────────────────
# NODE 1 — FINANCIAL ANALYSIS
# ─────────────────────────────────────────────

class FinancialSubscores(BaseModel):
    """Granular sub-dimension scores, each 0–100."""
    revenue_quality:     int = Field(50, ge=0, le=100)
    margin_health:       int = Field(50, ge=0, le=100)
    debt_sustainability: int = Field(50, ge=0, le=100)
    cash_adequacy:       int = Field(50, ge=0, le=100)
    earnings_quality:    int = Field(50, ge=0, le=100)


class FinancialAnalysis(BaseModel):
    """Output of the Financial Health Analysis node."""
    # Qualitative flags
    revenue_trend:   Trend        = Trend.UNKNOWN
    cash_position:   CashPosition = CashPosition.UNKNOWN

    # Key metrics (nullable — Nova may not find them in the docs)
    ebitda_margin:      Optional[str | float] = None   # Nova may return float or string
    debt_to_equity:     Optional[str | float] = None   # Nova may return float or string
    revenue_cagr_pct:   Optional[float] = Field(None, description="Historical revenue CAGR %")
    ebitda_margin_pct:  Optional[float] = Field(None, description="EBITDA margin %")
    debt_to_ebitda:     Optional[float] = Field(None, description="Net debt / EBITDA ratio")

    # Risk / positive narratives
    key_financial_risks:     list[str] = Field(default_factory=list)
    key_financial_positives: list[str] = Field(default_factory=list)

    # Scores
    financial_score:  int              = Field(50, ge=0, le=100, description="Overall financial health 0–100")
    scores:           FinancialSubscores = Field(default_factory=FinancialSubscores)
    confidence_score: float            = Field(0.8, ge=0.0, le=1.0)
    coverage_pct:     int              = Field(80, ge=0, le=100, description="% of financial docs reviewed")

    # Rolled-up rating
    overall_financial_health: RiskLevel = RiskLevel.UNKNOWN

    # Plain-English summary for API consumers / frontend
    summary: str = ""


# ─────────────────────────────────────────────
# NODE 2 — CONTRACT RED FLAGS
# ─────────────────────────────────────────────

class ContractFlag(BaseModel):
    """A single identified contract red flag."""
    clause:         str       = ""
    risk_level:     RiskLevel = RiskLevel.MEDIUM
    explanation:    str       = ""
    recommendation: str       = ""
    probability:    int       = Field(50, ge=0, le=100, description="Likelihood of materialising 0–100")
    impact:         int       = Field(50, ge=0, le=100, description="Business impact if it does 0–100")


class ContractRedFlags(BaseModel):
    """Output of the Contract Red Flag Detection node."""
    red_flags:               list[ContractFlag] = Field(default_factory=list)
    liability_exposure:      RiskLevel          = RiskLevel.UNKNOWN
    ip_ownership_issues:     bool               = False
    termination_risks:       list[str]          = Field(default_factory=list)
    indemnification_concerns: list[str]         = Field(default_factory=list)
    overall_contract_risk:   RiskLevel          = RiskLevel.UNKNOWN
    legal_score:             int                = Field(50, ge=0, le=100)
    coverage_pct:            int                = Field(80, ge=0, le=100)
    summary:                 str                = ""

    @model_validator(mode="after")
    def flag_count_sanity(self) -> ContractRedFlags:
        """Warn (non-fatal) if Nova returned no flags but rated risk as critical/high."""
        if (
            not self.red_flags
            and self.overall_contract_risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)
        ):
            # Append a synthetic placeholder so the UI always has something to show
            self.red_flags = [ContractFlag(
                clause="Unspecified high-risk clause",
                risk_level=self.overall_contract_risk,
                explanation="Nova rated overall contract risk as high/critical but returned no specific flags. Manual review required.",
                recommendation="Request full contract schedule from target and perform manual review.",
            )]
        return self


# ─────────────────────────────────────────────
# NODE 3 — COMPLIANCE
# ─────────────────────────────────────────────

class ComplianceIssues(BaseModel):
    """Output of the Regulatory Compliance Check node."""
    antitrust_concerns:             list[str]  = Field(default_factory=list)
    gdpr_data_privacy_issues:       bool       = False
    gdpr_details:                   Optional[str] = None
    jurisdictional_risks:           list[str]  = Field(default_factory=list)
    regulatory_approvals_needed:    list[str]  = Field(default_factory=list)
    industry_specific_regulations:  list[str]  = Field(default_factory=list)
    overall_compliance_risk:        RiskLevel  = RiskLevel.UNKNOWN
    blocking_issues:                list[str]  = Field(default_factory=list)
    compliance_score:               int        = Field(50, ge=0, le=100)
    coverage_pct:                   int        = Field(80, ge=0, le=100)
    summary:                        str        = ""


# ─────────────────────────────────────────────
# NODE 4 — SYNTHESIS
# ─────────────────────────────────────────────

class TopRedFlag(BaseModel):
    """One of the top-3 cross-domain risks surfaced by the synthesis node."""
    flag:     str       = ""
    severity: RiskLevel = RiskLevel.MEDIUM
    area:     DealArea  = DealArea.FINANCIAL


class RiskMatrix(BaseModel):
    """Per-area risk level ratings."""
    financial:  RiskLevel = RiskLevel.UNKNOWN
    legal:      RiskLevel = RiskLevel.UNKNOWN
    compliance: RiskLevel = RiskLevel.UNKNOWN
    overall:    RiskLevel = RiskLevel.UNKNOWN


class ScoreBreakdown(BaseModel):
    """Weighted composite scores per area + overall deal score."""
    financial:  int = Field(50, ge=0, le=100)
    legal:      int = Field(50, ge=0, le=100)
    compliance: int = Field(50, ge=0, le=100)
    overall:    int = Field(50, ge=0, le=100)

    @model_validator(mode="after")
    def validate_composite(self) -> ScoreBreakdown:
        """Recalculate overall if it looks like a default/placeholder."""
        computed = round(
            self.financial * 0.4
            + self.legal * 0.35
            + self.compliance * 0.25
        )
        # Only override if the supplied overall is the raw default (50)
        # so we don't clobber a deliberately calibrated value from Nova.
        if self.overall == 50:
            self.overall = computed
        return self


class DiligenceCoverage(BaseModel):
    """How thoroughly each document category was represented in the VDR."""
    financial_documents: int = Field(80, ge=0, le=100)
    legal_contracts:     int = Field(70, ge=0, le=100)
    compliance_docs:     int = Field(60, ge=0, le=100)
    ip_documents:        int = Field(40, ge=0, le=100)
    hr_documents:        int = Field(30, ge=0, le=100)


class DealRisk(BaseModel):
    """A single identified deal risk for the risk heatmap."""
    risk:        str      = ""
    probability: int      = Field(50, ge=0, le=100)
    impact:      int      = Field(50, ge=0, le=100)
    area:        DealArea = DealArea.FINANCIAL


class SynthesisReport(BaseModel):
    """Output of the Synthesis & Report Generation node."""
    deal_recommendation: DealRecommendation  = DealRecommendation.PROCEED_WITH_CONDITIONS
    overall_risk_rating: RiskLevel           = RiskLevel.UNKNOWN
    deal_score:          int                 = Field(50, ge=0, le=100)
    executive_summary:   str                 = ""
    top_3_red_flags:     list[TopRedFlag]    = Field(default_factory=list)
    risk_matrix:         RiskMatrix          = Field(default_factory=RiskMatrix)
    score_breakdown:     ScoreBreakdown      = Field(default_factory=ScoreBreakdown)
    diligence_coverage:  DiligenceCoverage   = Field(default_factory=DiligenceCoverage)
    recommended_conditions: list[str]        = Field(default_factory=list)
    next_steps:          list[str]           = Field(default_factory=list)
    deal_risks_summary:  list[DealRisk]      = Field(default_factory=list)


# ─────────────────────────────────────────────
# PIPELINE STATE — mirrors LangGraph TypedDict
# but as a Pydantic model for serialisation
# ─────────────────────────────────────────────

class DiligenceResult(BaseModel):
    """
    Full output of the 4-node pipeline.
    Stored in the job store and returned by GET /diligence/{job_id}.
    """
    doc_id:             Optional[str]              = None
    document_name:      str                        = ""
    financial_analysis: Optional[FinancialAnalysis] = None
    contract_red_flags: Optional[ContractRedFlags]  = None
    compliance_issues:  Optional[ComplianceIssues]  = None
    synthesis_report:   Optional[SynthesisReport]   = None
    error:              Optional[str]               = None


# ─────────────────────────────────────────────
# API REQUEST / RESPONSE WRAPPERS
# ─────────────────────────────────────────────

class RunDiligenceRequest(BaseModel):
    """POST /api/v1/diligence/run — kick off the pipeline."""
    document_text: str  = Field(..., min_length=50,  description="Extracted text from VDR documents")
    document_name: str  = Field("document", description="Human-readable label for this run")


class JobResponse(BaseModel):
    """Returned immediately after POST /run — client should poll /results/{job_id}."""
    job_id:  UUID
    status:  JobStatus
    message: str = ""


class DiligenceJobResponse(BaseModel):
    """GET /api/v1/diligence/{job_id} — full result once completed."""
    job_id:  UUID
    status:  JobStatus
    result:  Optional[DiligenceResult] = None
    error:   Optional[str]             = None


# ─────────────────────────────────────────────
# DASHBOARD PAYLOAD — pre-shaped for frontend
# ─────────────────────────────────────────────

class DashboardScores(BaseModel):
    """Flat score payload for chart rendering — no nesting the frontend has to unwrap."""
    deal_score:        int
    financial_score:   int
    legal_score:       int
    compliance_score:  int
    deal_recommendation: DealRecommendation
    overall_risk:      RiskLevel

    # Stat cards
    n_contract_flags:   int
    n_blocking_issues:  int
    n_approvals_needed: int

    # Sub-scores for financial bar chart
    financial_subscores: FinancialSubscores

    # Coverage for radar/bar chart
    diligence_coverage: DiligenceCoverage

    # Risk heatmap data
    deal_risks: list[DealRisk]

    # Top flags for the flag cards
    top_3_red_flags: list[TopRedFlag]

    # Summaries for text panels
    executive_summary:       str
    financial_summary:       str
    contract_summary:        str
    compliance_summary:      str
    recommended_conditions:  list[str]
    next_steps:              list[str]


# ─────────────────────────────────────────────
# CHAT REQUEST / RESPONSE
# ─────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:    str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """POST /api/v1/diligence/{job_id}/chat"""
    message: str               = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply:   str
    job_id:  Optional[str] = None
    doc_id:  Optional[str] = None


# ─────────────────────────────────────────────
# UPLOAD RESPONSE
# ─────────────────────────────────────────────

class UploadResponse(BaseModel):
    """POST /api/v1/upload — returns extracted text ready for /run."""
    doc_id:         str
    filename:       str
    char_count:     int
    extracted_text: str