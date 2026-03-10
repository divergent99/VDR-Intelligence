# frontend/layout.py
"""
All Dash layout builders — html/dcc components only, no callbacks, no chart logic.
build_layout(theme) is the single entry point called from app.py.
"""

from __future__ import annotations

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from frontend.theme import (
    C, DARK_C, LIGHT_C, MONO, BEBAS, DM,
    score_label, score_color, level_color, card_shadow, set_theme,
)

QUICK_QUESTIONS = [
    "What is the biggest risk in this deal?",
    "Should we proceed or walk away?",
    "What are the top 3 contract red flags?",
    "Are there any uncapped liability clauses?",
    "Summarise the financial health",
    "Is the debt level sustainable post-acquisition?",
    "What conditions should we attach?",
    "What escrow or holdback would you recommend?",
    "What regulatory approvals are needed?",
    "Are there any GDPR or data privacy issues?",
]

QQ_CATEGORIES = [
    ("DEAL ASSESSMENT",  0, 2),
    ("RISK & LEGAL",     2, 4),
    ("FINANCIAL",        4, 6),
    ("DEAL STRUCTURING", 6, 8),
    ("COMPLIANCE",       8, 10),
]


# ─────────────────────────────────────────────
# SHARED COMPONENT HELPERS
# ─────────────────────────────────────────────

SCORE_DESCRIPTIONS = {
    ("FINANCIAL", "excellent"):     "Revenue is compounding strongly, EBITDA margins are healthy, debt levels are conservative, and cash generation is robust. The balance sheet presents no material concerns and supports the proposed valuation.",
    ("FINANCIAL", "strong"):        "Solid top-line growth with adequate margins and a manageable debt profile. Minor inefficiencies exist but do not threaten deal economics.",
    ("FINANCIAL", "moderate"):      "Performance is acceptable but uneven — margins show compression or inconsistency, cash flow coverage is thin, or revenue quality contains one-time items. Warrants a purchase price adjustment discussion.",
    ("FINANCIAL", "elevated risk"): "Multiple financial warning signs detected: declining margins, elevated debt-to-EBITDA, weak cash generation, or earnings quality concerns.",
    ("FINANCIAL", "high risk"):     "Significant financial distress indicators present. The company may be burning cash, carrying unsustainable leverage, or reporting inflated earnings.",
    ("FINANCIAL", "critical risk"): "Severe financial instability. Evidence of near-term liquidity crisis, potential insolvency risk, or material misstatement.",
    ("LEGAL", "excellent"):         "All reviewed contracts are well-structured with balanced terms, clear IP ownership, and no material liability exposure.",
    ("LEGAL", "strong"):            "Contracts are generally clean with only minor clauses requiring negotiation. IP ownership is clear, and no significant indemnification risks identified.",
    ("LEGAL", "moderate"):          "Several clauses flagged as above-market or one-sided. Targeted renegotiation before signing is advisable.",
    ("LEGAL", "elevated risk"):     "Multiple high-risk provisions identified: uncapped liability exposure, unfavourable IP terms, or problematic change-of-control triggers.",
    ("LEGAL", "high risk"):         "Significant legal exposure across several contract types. Liability could materially exceed deal value in adverse scenarios.",
    ("LEGAL", "critical risk"):     "Deal-threatening legal exposure. Evidence of undisclosed litigation or fundamental IP ownership disputes.",
    ("COMPLIANCE", "excellent"):    "The target is fully compliant across all applicable jurisdictions with no open regulatory actions and all licences in good standing.",
    ("COMPLIANCE", "strong"):       "Minor regulatory items noted but no blocking issues. Required approvals are routine and GDPR obligations are substantially met.",
    ("COMPLIANCE", "moderate"):     "Several regulatory approvals required that may extend the deal timeline by 3–6 months. Data privacy compliance requires attention.",
    ("COMPLIANCE", "elevated risk"):"Multiple regulatory approvals required with material antitrust risk. One or more blocking issues identified.",
    ("COMPLIANCE", "high risk"):    "Blocking compliance issues present — including potential antitrust intervention or unresolved GDPR enforcement exposure.",
    ("COMPLIANCE", "critical risk"):"Severe regulatory exposure that may render the transaction impermissible.",
    ("OVERALL", "excellent"):       "Highly attractive acquisition opportunity. Strong performance across all diligence dimensions with no material blockers.",
    ("OVERALL", "strong"):          "Solid deal with manageable risks. Minor conditions recommended. Value creation thesis is intact.",
    ("OVERALL", "moderate"):        "Proceed with conditions. Multiple areas require targeted remediation. The deal is viable but requires active risk management.",
    ("OVERALL", "elevated risk"):   "Significant risks across two or more dimensions. Substantial conditions or price renegotiation needed before proceeding.",
    ("OVERALL", "high risk"):       "High probability of value erosion post-close. Compounding risks are difficult to mitigate through standard deal structures.",
    ("OVERALL", "critical risk"):   "Do not proceed under current terms. Critical issues across multiple dimensions make this acquisition highly likely to destroy value.",
}

def _score_description(area: str, score: int) -> str:
    tier = score_label(score).lower()
    key = (area.upper(), tier)
    result = SCORE_DESCRIPTIONS.get(key)
    if not result:
        return f"{tier.title()} — {area} score {score}/100"
    return result



def card(children, extra: dict = None):
    s = {
        "background": C["surf"], "border": f"1px solid {C['border']}",
        "borderRadius": "14px", "padding": "18px 20px", "boxShadow": card_shadow(),
    }
    if extra:
        s.update(extra)
    return html.Div(children, style=s)


def sec(title: str, tooltip_text: str = None, tooltip_id: str = None):
    els = [html.Span("▸ ", style={"color": C["accent"]}), html.Span(title)]
    if tooltip_id and tooltip_text:
        els.append(html.Span(" ⓘ", id=tooltip_id, style={
            "color": "rgba(108,99,255,0.6)", "fontSize": "10px",
            "cursor": "help", "marginLeft": "4px",
        }))
    row = html.Div(els, style={
        "fontFamily": MONO, "fontSize": "9px", "fontWeight": "700",
        "letterSpacing": "0.2em", "textTransform": "uppercase",
        "color": C["muted"], "display": "flex", "alignItems": "center",
    })
    children = [row]
    if tooltip_id and tooltip_text:
        children.append(dbc.Tooltip(tooltip_text, target=tooltip_id, placement="right",
            style={"fontFamily": MONO, "fontSize": "10px", "lineHeight": "1.6",
                   "maxWidth": "240px", "background": C["surf2"],
                   "border": f"1px solid {C['border']}", "borderRadius": "8px",
                   "padding": "10px 12px", "color": C["text"]}))
    return html.Div(children, style={"marginBottom": "14px"})


def badge(text: str, col: str):
    return html.Span(text, style={
        "fontFamily": MONO, "fontSize": "9px", "fontWeight": "700",
        "letterSpacing": "0.14em", "textTransform": "uppercase",
        "color": col, "background": col + "1a",
        "border": f"1px solid {col}44", "borderRadius": "4px", "padding": "2px 8px",
    })


def deal_banner(rec: str):
    cfg = {
        "proceed":                 ("PROCEED",               C["proceed"], "✓"),
        "proceed_with_conditions": ("PROCEED W/ CONDITIONS", C["cond"],   "⚠"),
        "do_not_proceed":          ("DO NOT PROCEED",        C["stop"],   "✕"),
    }
    txt, col, icon = cfg.get(rec, ("UNKNOWN", C["muted"], "?"))
    return html.Div([
        html.Div(icon, style={"fontSize": "32px", "color": col, "marginBottom": "4px"}),
        html.Div("DEAL RECOMMENDATION", style={"fontFamily": MONO, "fontSize": "8px",
            "letterSpacing": "0.25em", "color": col + "aa", "marginBottom": "3px"}),
        html.Div(txt, style={"fontFamily": BEBAS, "fontSize": "24px",
            "color": col, "letterSpacing": "0.05em"}),
    ], style={"background": col + "10", "border": f"1.5px solid {col}44",
              "borderRadius": "12px", "padding": "16px 14px", "textAlign": "center"})


def led_score_card(area: str, level: str, score: int, tid: str, tip: str):
    sc = score_color(score)
    return html.Div([
        html.Div([
            daq.Indicator(value=True, color=sc, size=14, style={"display": "inline-block"}),
            html.Span(" ⓘ", id=tid, style={"color": "rgba(108,99,255,0.6)",
                "fontSize": "9px", "cursor": "help", "marginLeft": "5px"}),
            dbc.Tooltip(tip, target=tid, placement="top",
                style={"fontFamily": MONO, "fontSize": "10px", "lineHeight": "1.6",
                       "maxWidth": "200px", "background": C["surf2"],
                       "border": f"1px solid {C['border']}", "borderRadius": "8px",
                       "padding": "8px 10px", "color": C["text"]}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
        html.Div(str(score), style={"fontFamily": BEBAS, "fontSize": "40px",
            "color": sc, "lineHeight": "1", "letterSpacing": "0.02em"}),
        html.Div(score_label(score), style={"fontFamily": MONO, "fontSize": "8px",
            "color": sc, "letterSpacing": "0.12em", "marginTop": "2px",
            "fontWeight": "700", "opacity": "0.9"}),
        html.Div(str(_score_description(area, score) or f"{score_label(score)} score"), style={"fontFamily": DM, "fontSize": "11px",
            "color": C["text"], "lineHeight": "1.55", "marginTop": "8px", "flexGrow": "1", "opacity": "0.7"}),
        html.Div(style={"height": "1px", "background": C["border"], "margin": "10px 0 8px"}),
        html.Div(area, style={"fontFamily": MONO, "fontSize": "8px",
            "color": C["muted"], "letterSpacing": "0.18em"}),
    ], style={"flex": "1", "background": C["surf"], "border": f"1px solid {sc}33",
              "borderRadius": "12px", "padding": "14px 12px", "display": "flex",
              "flexDirection": "column", "boxShadow": card_shadow()})


def stat_card(lbl: str, val, col: str, sub: str, tid: str, tip: str):
    return html.Div([
        html.Div([
            html.Span(lbl, style={"fontFamily": MONO, "fontSize": "9px",
                "letterSpacing": "0.18em", "textTransform": "uppercase", "color": C["muted"]}),
            html.Span(" ⓘ", id=tid, style={"color": "rgba(108,99,255,0.47)",
                "fontSize": "9px", "cursor": "help", "marginLeft": "4px"}),
            dbc.Tooltip(tip, target=tid, placement="top",
                style={"fontFamily": MONO, "fontSize": "10px", "lineHeight": "1.6",
                       "maxWidth": "220px", "background": C["surf2"],
                       "border": f"1px solid {C['border']}", "borderRadius": "8px",
                       "padding": "10px 12px", "color": C["text"]}),
        ], style={"marginBottom": "8px", "display": "flex", "alignItems": "center"}),
        html.Div(str(val), style={"fontFamily": BEBAS, "fontSize": "38px",
            "lineHeight": "1", "letterSpacing": "0.02em", "color": col}),
        html.Div(sub, style={"fontFamily": MONO, "fontSize": "9px",
            "color": C["muted"], "marginTop": "3px"}),
    ], style={"background": C["surf"], "border": f"1px solid {col}22",
              "borderRadius": "10px", "padding": "14px 12px", "flex": "1",
              "minWidth": "90px", "boxShadow": card_shadow()})


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

def _upload_card():
    return card([
        sec("Virtual Data Room"),
        dcc.Upload(id="upload-docs", multiple=True,
            children=html.Div([
                html.Div("⬆", style={"fontSize": "24px", "color": C["accent"], "marginBottom": "4px"}),
                html.Div("Drop files", style={"fontFamily": DM, "fontWeight": "600",
                    "fontSize": "13px", "color": C["text"]}),
                html.Div("PDF · DOCX · XLSX", style={"fontFamily": MONO, "fontSize": "9px",
                    "color": C["muted"], "letterSpacing": "0.1em"}),
            ], style={"textAlign": "center", "padding": "2px"}),
            style={"border": f"1.5px dashed {C['accent']}44", "borderRadius": "10px",
                   "padding": "18px 12px", "cursor": "pointer",
                   "background": C["accent"] + "08", "marginBottom": "10px"}),
        html.Div(id="file-list"),
        html.Div("— or folder path —", style={"fontFamily": MONO, "fontSize": "9px",
            "color": C["muted"], "textAlign": "center", "letterSpacing": "0.1em",
            "margin": "8px 0 6px"}),
        dcc.Input(id="folder-path", type="text", placeholder=r"C:\Users\...\VDR",
            style={"width": "100%", "background": C["bg"], "border": f"1px solid {C['border']}",
                   "borderRadius": "8px", "padding": "8px 12px", "color": C["text"],
                   "fontFamily": MONO, "fontSize": "10px", "marginBottom": "12px"}),
        html.Button([html.Span("◈  "), "RUN PIPELINE"], id="run-btn", n_clicks=0,
            className="run-btn",
            style={"width": "100%",
                   "background": f"linear-gradient(135deg,{C['accent']},{C['cyan']})",
                   "border": "none", "borderRadius": "10px", "padding": "12px",
                   "color": "#07070f", "fontFamily": BEBAS, "fontSize": "16px",
                   "letterSpacing": "0.1em", "cursor": "pointer"}),
        html.Div(id="pipeline-progress", style={"marginTop": "10px"}),
    ], extra={"marginBottom": "14px"})


def _chat_card():
    return card([
        sec("Ask About This Deal",
            "Ask Nova anything about this deal. Answers are grounded in the diligence report only.",
            "tt-chat"),
        html.Div(id="chat-messages",
            style={"height": "280px", "overflowY": "auto", "display": "flex",
                   "flexDirection": "column", "gap": "8px", "marginBottom": "10px",
                   "paddingRight": "2px"},
            children=[html.Div([
                html.Div("NOVA", style={"fontFamily": MONO, "fontSize": "9px",
                    "color": C["cyan"], "letterSpacing": "0.15em", "marginBottom": "3px"}),
                html.Div("Run the pipeline first, then ask me anything about this deal.",
                    style={"fontFamily": MONO, "fontSize": "11px",
                           "color": C["muted"], "lineHeight": "1.6"}),
            ], style={"background": C["surf2"], "border": f"1px solid {C['border']}",
                      "borderRadius": "10px", "padding": "10px 12px"})]),
        html.Div([
            dcc.Input(id="chat-input", type="text", n_submit=0,
                placeholder="e.g. What is the biggest liability risk?",
                style={"flex": "1", "background": C["bg"],
                       "border": f"1px solid {C['border']}", "borderRadius": "8px",
                       "padding": "9px 12px", "color": C["text"],
                       "fontFamily": MONO, "fontSize": "11px"}),
            html.Button("→", id="chat-send", n_clicks=0,
                style={"background": C["accent"], "border": "none", "borderRadius": "8px",
                       "padding": "9px 15px", "color": "white", "fontFamily": BEBAS,
                       "fontSize": "18px", "cursor": "pointer", "marginLeft": "8px"}),
        ], style={"display": "flex"}),
    ], extra={"marginBottom": "14px"})


def _quick_questions_card():
    items = []
    for category, start, end in QQ_CATEGORIES:
        items.append(html.Div(category, style={"fontFamily": MONO, "fontSize": "8px",
            "color": C["accent"], "letterSpacing": "0.2em",
            "marginBottom": "6px", "marginTop": "6px"}))
        for i in range(start, end):
            items.append(html.Div(QUICK_QUESTIONS[i],
                id={"type": "quick-q", "index": i}, n_clicks=0,
                className="quick-q-btn",
                style={"fontFamily": MONO, "fontSize": "10px", "color": C["muted"],
                       "background": C["surf2"], "border": f"1px solid {C['border']}",
                       "borderRadius": "6px", "padding": "8px 10px", "marginBottom": "6px",
                       "cursor": "pointer", "lineHeight": "1.5", "transition": "all .15s"}))
    return card(items, extra={"flexGrow": "1"})


def sidebar():
    return html.Div([
        _upload_card(),
        _chat_card(),
        _quick_questions_card(),
    ], style={"width": "296px", "flexShrink": "0", "display": "flex", "flexDirection": "column"})


# ─────────────────────────────────────────────
# MAIN PANEL STATES
# ─────────────────────────────────────────────

def empty_state():
    return html.Div([
        html.Div("◈", style={"fontFamily": BEBAS, "fontSize": "72px",
            "color": C["accent"] + "22", "textAlign": "center"}),
        html.Div("UPLOAD YOUR VDR DOCUMENTS", style={"fontFamily": BEBAS, "fontSize": "24px",
            "color": C["muted"], "textAlign": "center", "letterSpacing": "0.08em"}),
        html.Div("Drop files or enter a folder path, then run the pipeline",
            style={"fontFamily": MONO, "fontSize": "10px", "color": C["border"],
                   "textAlign": "center", "marginTop": "8px"}),
    ], id="empty-state", style={"paddingTop": "130px"})


def loading_screen():
    steps = [
        ("📊", C["cyan"],   "Financial Health Analysis"),
        ("🚩", C["high"],   "Contract Red Flag Detection"),
        ("⚖",  C["medium"], "Regulatory Compliance Check"),
        ("📝", C["accent"], "Synthesis & Report Generation"),
    ]
    return html.Div([
        html.Div(className="spinner"),
        html.Div("ANALYSING DOCUMENTS", className="pulse", style={"fontFamily": BEBAS,
            "fontSize": "26px", "color": C["text"], "textAlign": "center",
            "letterSpacing": "0.1em", "marginBottom": "4px"}),
        html.Div("AMAZON NOVA 2 · EXTENDED THINKING · 4-AGENT PIPELINE",
            style={"fontFamily": MONO, "fontSize": "9px", "color": C["cyan"],
                   "textAlign": "center", "letterSpacing": "0.18em", "marginBottom": "28px"}),
        html.Div([
            html.Div([html.Span(ic + "  ", style={"color": bc}),
                      html.Span(tx, style={"fontFamily": MONO, "fontSize": "11px",
                                           "color": C["text"]})],
                className="stepin",
                style={"background": C["surf2"], "border": f"1px solid {bc}33",
                       "borderRadius": "8px", "padding": "10px 16px",
                       "marginBottom": "9px", "textAlign": "center"})
            for ic, bc, tx in steps
        ], style={"maxWidth": "340px", "margin": "0 auto"}),
    ], id="loading-screen", style={"display": "none", "paddingTop": "80px"})


# ─────────────────────────────────────────────
# FULL LAYOUT
# ─────────────────────────────────────────────

def build_layout(theme: str = "dark"):
    set_theme(theme)
    btn_label = "☀ LIGHT" if theme == "dark" else "🌙 DARK"
    btn_style = {
        "background": "rgba(108,99,255,0.12)",
        "border": "1px solid rgba(108,99,255,0.3)",
        "borderRadius": "6px", "padding": "4px 10px",
        "color": C["accent"], "fontFamily": MONO,
        "fontSize": "9px", "letterSpacing": "0.14em", "cursor": "pointer",
    }

    return html.Div([
        dcc.Store(id="results-store"),
        dcc.Store(id="chat-history", data=[]),
        dcc.Store(id="chat-pending", data=None),
        dcc.Store(id="theme-store", data=theme),

        # HEADER
        html.Div([html.Div([
            html.Div([
                html.Span("NOVA", style={"fontFamily": BEBAS, "fontSize": "24px",
                    "color": C["accent"], "letterSpacing": "0.06em"}),
                html.Span("DD", style={"fontFamily": BEBAS, "fontSize": "24px",
                    "color": C["cyan"], "letterSpacing": "0.06em"}),
                html.Div("M&A DUE DILIGENCE ORCHESTRATOR · AMAZON NOVA 2",
                    style={"fontFamily": MONO, "fontSize": "8px",
                           "letterSpacing": "0.22em", "color": C["muted"]}),
            ]),
            html.Div([
                html.Span("Amazon Hackathon 2026", style={"fontFamily": MONO,
                    "fontSize": "10px", "color": C["muted"]}),
                html.Span(" · ", style={"color": C["border"], "margin": "0 6px"}),
                html.Span("Nova 2 Extended Thinking", style={"fontFamily": MONO,
                    "fontSize": "10px", "color": C["cyan"]}),
                html.Span(" · ", style={"color": C["border"], "margin": "0 6px"}),
                html.Button(btn_label, id="theme-toggle", n_clicks=0, style=btn_style),
            ]),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "center", "maxWidth": "1700px",
                  "margin": "0 auto", "padding": "0 24px"})],
        style={"background": C["surf"], "borderBottom": f"1px solid {C['border']}",
               "padding": "13px 0", "position": "sticky", "top": "0", "zIndex": "100"}),

        # BODY
        html.Div([
            sidebar(),
            html.Div([
                empty_state(),
                loading_screen(),
                html.Div(id="results-panel", style={"display": "none"}),
            ], style={"flex": "1", "minWidth": "0"}),
        ], style={"display": "flex", "gap": "18px", "padding": "18px 24px",
                  "maxWidth": "1700px", "margin": "0 auto", "alignItems": "flex-start"}),

    ], id="theme-root", style={"background": C["bg"], "minHeight": "100vh"})