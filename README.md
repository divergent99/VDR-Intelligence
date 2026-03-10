# VDR Intelligence

M&A Due Diligence Orchestrator powered by Amazon Nova 2 with Extended Thinking.

Built for the **Amazon Nova Hackathon 2026**.

---

## Overview

VDR Intelligence is a full-stack AI application that automates M&A due diligence by running a 4-agent LangGraph pipeline against Virtual Data Room (VDR) documents. It produces structured financial, legal, and compliance analysis with a weighted deal score and executive recommendation.

**Stack:** FastAPI · LangGraph · Amazon Bedrock (Nova 2) · Dash · ChromaDB · Pydantic v2

---

## Architecture

```
vdr_intelligence/
├── api/                    # FastAPI backend (port 8000)
│   ├── main.py
│   ├── dependencies.py
│   └── routes/
│       ├── upload.py       # POST /api/v1/upload
│       ├── diligence.py    # POST /api/v1/diligence/run
│       └── chat.py         # POST /api/v1/diligence/{doc_id}/chat
├── pipeline/               # LangGraph 4-node pipeline
│   ├── graph.py
│   ├── nova.py             # Bedrock invoke + json-repair
│   ├── cache.py            # ChromaDB result cache
│   └── nodes/
│       ├── financial.py
│       ├── contract.py
│       ├── compliance.py
│       └── synthesis.py
├── ingestion/
│   └── extractor.py        # PDF / DOCX / XLSX text extraction
├── models/
│   └── schemas.py          # Pydantic v2 models
├── frontend/               # Dash frontend (port 8050)
│   ├── app.py
│   ├── api_client.py
│   ├── theme.py
│   ├── charts.py
│   ├── layout.py
│   └── callbacks/
│       ├── pipeline.py
│       ├── chat.py
│       └── toggle.py
└── config.py               # pydantic-settings, reads .env
```

### Pipeline

```
Document Text
     │
     ├──> Node 1: Financial Analysis      (Nova 2 + Extended Thinking)
     ├──> Node 2: Contract Red Flags      (Nova 2 + Extended Thinking)
     ├──> Node 3: Compliance Issues       (Nova 2 + Extended Thinking)
     │
     └──> Node 4: Synthesis & Scoring    (Nova 2 + Extended Thinking)
               │
               └──> Deal Score (0-100) · Recommendation · Risk Matrix
```

Weights: Financial × 0.4 + Legal × 0.35 + Compliance × 0.25

Cache: SHA-256 of document text → ChromaDB. Repeat runs return instantly.

---

## Requirements

- Python 3.11
- AWS account with Amazon Bedrock access
- Nova 2 model enabled in your AWS region (`us-east-1` recommended)

---

## Setup

**1. Clone and create virtualenv**

```powershell
git clone https://github.com/your-org/vdr-intelligence.git
cd vdr_intelligence
py -3.11 -m venv .venv
.venv\Scripts\Activate
pip install -r requirements.txt
pip install json-repair
```

**2. Configure environment**

```powershell
cp .env.example .env
```

Edit `.env`:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
NOVA_MODEL_ID=us.amazon.nova-2-lite-v1:0
```

**3. Run**

Terminal 1 — FastAPI backend:
```powershell
uvicorn api.main:app --reload --port 8000
```

Terminal 2 — Dash frontend:
```powershell
python -m frontend.app
```

Open: http://localhost:8050

---

## Usage

1. Drop PDF / DOCX / XLSX files into the upload zone, or paste a local folder path
2. Click **Run Pipeline** — Nova 2 runs all 4 agents with Extended Thinking
3. Review the deal score, risk heatmap, area breakdowns, and red flags
4. Use the **Ask About This Deal** chat to interrogate the report with NOVA

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/upload` | Upload files, returns extracted text + doc_id |
| POST | `/api/v1/diligence/run` | Run full pipeline, returns DiligenceResult |
| GET | `/api/v1/diligence/{doc_id}` | Fetch cached result |
| GET | `/api/v1/diligence/{doc_id}/dashboard` | Flat chart-ready payload |
| POST | `/api/v1/diligence/{doc_id}/chat` | Chat with NOVA about the deal |

Interactive docs: http://localhost:8000/docs

---

## Configuration

All settings are in `.env` / `config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_ACCESS_KEY_ID` | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | — | AWS credentials |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `NOVA_MODEL_ID` | `us.amazon.nova-2-lite-v1:0` | Nova model string |
| `NOVA_MAX_TOKENS` | `4096` | Max tokens per node call |
| `NOVA_THINKING_MAX_TOKENS` | `10000` | Extended thinking budget |
| `NOVA_THINKING_EFFORT` | `medium` | `low` / `medium` / `high` |
| `DOC_CHAR_LIMIT` | `40000` | Max chars ingested from VDR |
| `NODE_CHAR_LIMIT` | `8000` | Max chars per node prompt |
| `CACHE_ENABLED` | `true` | Toggle ChromaDB cache |
| `CHROMA_PATH` | `./vdr_cache` | Cache storage path |

---

## Notes

- Pipeline runtime: ~2-4 minutes per document set (Extended Thinking enabled)
- Cache hit returns in <1 second
- Supported document formats: PDF, DOCX, XLSX
- `json-repair` is required separately: `pip install json-repair`