# frontend/callbacks/pipeline.py
"""
Pipeline callbacks:
- show file list on upload
- show loading screen on run
- call FastAPI and store results
- render full results panel
"""

from __future__ import annotations

import base64
import json
import math

import logging
logger = logging.getLogger(__name__)

import os
import hashlib
from dash import Input, Output, State, no_update, html, dcc, ctx
import dash_daq as daq
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from frontend.theme import C, MONO, BEBAS, DM, score_color, level_color, score_label, card_shadow, set_theme, DARK_C, LIGHT_C
from frontend.charts import (
    deal_score_gauge, score_breakdown_chart, risk_heatmap,
    coverage_chart, financial_subscores_chart, flag_breakdown_chart,
)
from frontend.layout import sec, badge, deal_banner, stat_card

def card(children, extra: dict = None):
    s = {
        "background": C["surf"], "border": f"1px solid {C['border']}",
        "borderRadius": "14px", "padding": "18px 20px", "boxShadow": card_shadow(),
    }
    if extra:
        s.update(extra)
    return html.Div(children, style=s)

# Copied exactly from original app.py — do not use layout.py version
SCORE_DESCRIPTIONS = {
    ("FINANCIAL","excellent"): "Revenue is compounding strongly, EBITDA margins are healthy, debt levels are conservative, and cash generation is robust. The balance sheet presents no material concerns and supports the proposed valuation.",
    ("FINANCIAL","strong"): "Solid top-line growth with adequate margins and a manageable debt profile. Minor inefficiencies exist but do not threaten deal economics. Cash flow coverage is sufficient to service obligations post-acquisition.",
    ("FINANCIAL","moderate"): "Performance is acceptable but uneven — margins show compression or inconsistency, cash flow coverage is thin, or revenue quality contains a high proportion of one-time items. Warrants a purchase price adjustment discussion.",
    ("FINANCIAL","elevated risk"): "Multiple financial warning signs detected: declining margins, elevated debt-to-EBITDA, weak cash generation, or earnings quality concerns. A quality-of-earnings review is strongly recommended before proceeding.",
    ("FINANCIAL","high risk"): "Significant financial distress indicators present. The company may be burning cash, carrying unsustainable leverage, or reporting inflated earnings. Deal economics are materially at risk without substantial price renegotiation.",
    ("FINANCIAL","critical risk"): "Severe financial instability. Evidence of near-term liquidity crisis, potential insolvency risk, or material misstatement. Acquisition at current terms would likely destroy acquirer value. Do not proceed without forensic audit.",
    ("LEGAL","excellent"): "All reviewed contracts are well-structured with balanced terms, clear IP ownership, and no material liability exposure. Indemnification provisions are reasonable and termination clauses are standard. No legal impediments to close.",
    ("LEGAL","strong"): "Contracts are generally clean with only minor clauses requiring negotiation. IP ownership is clear, and no significant indemnification or change-of-control risks have been identified. Standard legal due diligence is sufficient.",
    ("LEGAL","moderate"): "Several clauses flagged as above-market or one-sided — including indemnification caps, IP assignment ambiguity, or customer concentration in key contracts. Targeted renegotiation before signing is advisable.",
    ("LEGAL","elevated risk"): "Multiple high-risk provisions identified: uncapped liability exposure, unfavourable IP terms, problematic change-of-control triggers, or key customer agreements at risk of termination post-close. Legal restructuring required.",
    ("LEGAL","high risk"): "Significant legal exposure across several contract types. Liability could materially exceed deal value in adverse scenarios. Pending or threatened litigation, unclear IP chain of title, or locked-in unfavourable terms with major counterparties.",
    ("LEGAL","critical risk"): "Deal-threatening legal exposure. Evidence of undisclosed litigation, fundamental IP ownership disputes, or contractual obligations that make the acquisition structurally unworkable. Immediate specialist legal counsel required before proceeding.",
    ("COMPLIANCE","excellent"): "The target is fully compliant across all applicable jurisdictions with no open regulatory actions, no antitrust concerns, and all required licences and permits in good standing. Regulatory close timeline is expected to be straightforward.",
    ("COMPLIANCE","strong"): "Minor regulatory items noted but no blocking issues. Required approvals are routine and precedent exists for timely clearance. GDPR and data privacy obligations are substantially met with only minor remediation needed.",
    ("COMPLIANCE","moderate"): "Several regulatory approvals are required that may extend the deal timeline by 3–6 months. Antitrust pre-notification likely needed in at least one jurisdiction. Data privacy compliance requires attention but is not deal-blocking.",
    ("COMPLIANCE","elevated risk"): "Multiple regulatory approvals required across jurisdictions with material antitrust risk. One or more blocking issues identified that must be resolved prior to close. Regulatory timeline uncertainty could affect deal certainty.",
    ("COMPLIANCE","high risk"): "Blocking compliance issues present — including potential HSR or EC antitrust intervention, unresolved GDPR enforcement exposure, or sector-specific regulatory violations. Deal close is uncertain without active regulatory engagement.",
    ("COMPLIANCE","critical risk"): "Severe regulatory exposure that may render the transaction impermissible. Active regulatory investigations, major data privacy breaches, or antitrust concerns significant enough to require structural remedies or outright prohibition.",
    ("OVERALL","excellent"): "Highly attractive acquisition opportunity. Strong performance across all diligence dimensions with no material blockers. Recommend proceeding to definitive agreement with standard conditions.",
    ("OVERALL","strong"): "Solid deal with manageable risks across financial, legal, and compliance dimensions. Minor conditions recommended. Value creation thesis is intact and execution risk is within acceptable bounds.",
    ("OVERALL","moderate"): "Proceed with conditions. Multiple areas require targeted remediation — price adjustment, legal renegotiation, or regulatory timeline planning. The deal is viable but requires active risk management through to close.",
    ("OVERALL","elevated risk"): "Significant risks across two or more diligence dimensions create meaningful deal uncertainty. Substantial conditions, escrow arrangements, or price renegotiation are needed before proceeding. Recommend extended due diligence.",
    ("OVERALL","high risk"): "High probability of value erosion or deal failure post-close. The combination of financial, legal, and compliance issues creates compounding risk that is difficult to mitigate through standard deal structures. Reconsider deal economics.",
    ("OVERALL","critical risk"): "Do not proceed under current terms. Critical issues across multiple dimensions make this acquisition highly likely to destroy value. A fundamental restructuring of deal terms, scope, or structure is required before any further commitment.",
}

def _score_label(s):
    if s >= 80: return "EXCELLENT"
    if s >= 65: return "STRONG"
    if s >= 50: return "MODERATE"
    if s >= 35: return "ELEVATED RISK"
    if s >= 20: return "HIGH RISK"
    return "CRITICAL RISK"

def _score_desc(area, score):
    tier = _score_label(score).lower()
    return SCORE_DESCRIPTIONS.get((area.upper(), tier), f"{_score_label(score)} — score {score}/100")

def led_score_card(area, level, score, tid, tip):
    sc = score_color(score)
    desc = _score_desc(area, score)
    return html.Div([
        html.Div([
            daq.Indicator(value=True, color=sc, size=14, style={"display": "inline-block"}),
            html.Span(" ⓘ", id=tid, style={"color": "rgba(108,99,255,0.6)", "fontSize": "9px",
                "cursor": "help", "marginLeft": "5px"}),
            dbc.Tooltip(tip, target=tid, placement="top",
                style={"fontFamily": MONO, "fontSize": "10px", "lineHeight": "1.6", "maxWidth": "200px",
                       "background": C["surf2"], "border": f"1px solid {C['border']}",
                       "borderRadius": "8px", "padding": "8px 10px", "color": C["text"]}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
        html.Div(str(score), style={"fontFamily": BEBAS, "fontSize": "40px", "color": sc,
            "lineHeight": "1", "letterSpacing": "0.02em"}),
        html.Div(_score_label(score), style={"fontFamily": MONO, "fontSize": "8px", "color": sc,
            "letterSpacing": "0.12em", "marginTop": "2px", "fontWeight": "700", "opacity": "0.9"}),
        html.Div(desc, style={"fontFamily": DM, "fontSize": "11px", "color": C["muted"],
            "lineHeight": "1.55", "marginTop": "8px", "flexGrow": "1"}),
        html.Div(style={"height": "1px", "background": C["border"], "margin": "10px 0 8px"}),
        html.Div(area, style={"fontFamily": MONO, "fontSize": "8px", "color": C["muted"],
            "letterSpacing": "0.18em"}),
    ], style={"flex": "1", "background": C["surf"], "border": f"1px solid {sc}33",
              "borderRadius": "12px", "padding": "14px 12px", "display": "flex",
              "flexDirection": "column", "boxShadow": card_shadow()})
from frontend.api_client import run_diligence, upload_files, extract_from_folder


def register(app):

    # ── File list display ────────────────────────────────────────
    @app.callback(Output("file-list", "children"), Input("upload-docs", "filename"))
    def show_files(fns):
        if not fns:
            return html.Div()
        icons = {"pdf": "📄", "docx": "📝", "xlsx": "📊", "xls": "📊"}
        return html.Div([html.Div([
            html.Span(icons.get(f.split(".")[-1].lower(), "📁") + "  "),
            html.Span(f, style={"fontFamily": MONO, "fontSize": "10px", "color": C["text"]}),
        ], style={"background": C["bg"], "border": f"1px solid {C['border']}",
                  "borderRadius": "6px", "padding": "5px 10px", "marginBottom": "4px"})
        for f in fns])

    # ── Show loading screen immediately on run ───────────────────
    @app.callback(
        Output("loading-screen", "style"),
        Output("empty-state", "style", allow_duplicate=True),
        Input("run-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def show_loading(n):
        if not n:
            return no_update, no_update
        return {"display": "block", "paddingTop": "80px"}, {"display": "none"}

    # ── Update URL on new pipeline run ───────────────────────────
    @app.callback(
        Output("url", "search"),
        Input("results-store", "data"),
        prevent_initial_call=True
    )
    def update_url(data):
        if not data or "doc_id" not in data:
            return no_update
        return f"?doc_id={data['doc_id']}"


    # ── Load pipeline on start from URL ──────────────────────────
    @app.callback(
        Output("results-store", "data", allow_duplicate=True),
        Output("pipeline-progress", "children", allow_duplicate=True),
        Input("url", "search"),
        Input("auth-token", "data"),
        prevent_initial_call=True
    )
    def load_from_url(search, token):
        if not token:
            return no_update, no_update
        if not search or "doc_id=" not in search:
            return no_update, no_update
        
        try:
            # Parse ?doc_id=XYZ
            params = dict(p.split("=") for p in search.strip("?").split("&") if "=" in p)
            doc_id = params.get("doc_id")
            
            if not doc_id:
                return no_update, no_update

            from frontend.api_client import get_diligence
            result = get_diligence(doc_id, token)
            result["doc_id"] = doc_id
            
            return result, html.Div("✓ Loaded shared project",
                style={"fontFamily": MONO, "fontSize": "11px", "color": C["low"]})
        except:
            return no_update, no_update


    # ── Project Result Sync Poller ──────────────────────────────
    @app.callback(
        Output("results-store", "data", allow_duplicate=True),
        Input("sync-interval", "n_intervals"),
        State("auth-token", "data"),
        State("url", "search"),
        State("results-store", "data"),
        prevent_initial_call=True
    )
    def sync_project(n, token, search, current_data):
        if not token or not search or "doc_id=" not in search:
            return no_update
        
        try:
            params = dict(p.split("=") for p in search.strip("?").split("&") if "=" in p)
            doc_id = params.get("doc_id")
            if not doc_id:
                return no_update

            # Only sync if results-store is empty OR we want to poll for completion
            # In a real app, we might check a 'status' field.
            # Here, if current_data is None or missing synthesis_report, we poll.
            if current_data and current_data.get("synthesis_report"):
                return no_update

            from frontend.api_client import get_diligence
            result = get_diligence(doc_id, token)
            result["doc_id"] = doc_id
            return result
        except Exception as e:
            logger.error(f"Sync project error: {e}")
            return no_update


    # ── Run pipeline → store results ─────────────────────────────
    @app.callback(
        Output("results-store", "data"),
        Output("pipeline-progress", "children"),
        Input("run-btn", "n_clicks"),
        State("upload-docs", "contents"),
        State("upload-docs", "filename"),
        State("folder-path", "value"),
        State("auth-token", "data"),
        prevent_initial_call=True,
    )
    def run_pipeline(n, contents, filenames, folder_path, token):
        if not n:
            return no_update, no_update
        try:
            if folder_path and os.path.isdir(folder_path):
                result = extract_from_folder(folder_path, token)
                if result and "doc_id" not in result:
                    # Fallback doc_id generation
                    result["doc_id"] = result.get("doc_id") or hashlib.sha256(folder_path.encode()).hexdigest()[:16]

            elif contents and filenames:
                file_tuples = [
                    (filename, base64.b64decode(content.split(",", 1)[1]))
                    for content, filename in zip(contents, filenames)
                ]
                upload_resp = upload_files(file_tuples, token)
                result = run_diligence(upload_resp["extracted_text"], "uploaded_vdr", token)
                result["doc_id"] = upload_resp["doc_id"]

            else:
                return None, html.Div("⚠ Upload files or enter a folder path.",
                    style={"fontFamily": MONO, "fontSize": "11px", "color": C["high"]})

            return result, html.Div("✓  Pipeline complete",
                style={"fontFamily": MONO, "fontSize": "11px", "color": C["low"]})

        except Exception as e:
            return None, html.Div(f"✕  {e}",
                style={"fontFamily": MONO, "fontSize": "11px", "color": C["critical"]})

    # ── Render results panel ─────────────────────────────────────
    @app.callback(
        Output("results-panel", "children"),
        Output("results-panel", "style"),
        Output("empty-state", "style"),
        Output("loading-screen", "style", allow_duplicate=True),
        Input("results-store", "data"),
        State("theme-store", "data"),
        prevent_initial_call=True,
    )
    def render(data, theme):
        set_theme(theme or "dark")
        hidden = {"display": "none"}
        if not data or not isinstance(data, dict):
            return html.Div(), hidden, {"paddingTop": "130px"}, hidden

        def _get_dict(obj):
            return obj if isinstance(obj, dict) else {}

        syn  = _get_dict(data.get("synthesis_report"))
        fin  = _get_dict(data.get("financial_analysis"))
        con  = _get_dict(data.get("contract_red_flags"))
        comp = _get_dict(data.get("compliance_issues"))
        
        score_breakdown = _get_dict(syn.get("score_breakdown"))
        if not score_breakdown:
            score_breakdown = {"financial": 50, "legal": 50, "compliance": 50, "overall": 50}
            
        rm = _get_dict(syn.get("risk_matrix"))
        
        deal_score      = syn.get("deal_score", 50)
        diligence_cov   = _get_dict(syn.get("diligence_coverage"))
        deal_risks      = syn.get("deal_risks_summary", [])
        fin_scores      = _get_dict(fin.get("scores"))

        n_flags     = len(con.get("red_flags", []))
        n_blocking  = len(comp.get("blocking_issues", []))
        n_approvals = len(comp.get("regulatory_approvals_needed", []))
        fin_score   = fin.get("financial_score", score_breakdown.get("financial", 50))

        results = html.Div([
            # ROW 1: gauge + LED cards + stat cards
            html.Div([
                card([
                    sec("Deal Score", "Weighted: Financial×0.4 + Legal×0.35 + Compliance×0.25"),
                    dcc.Graph(figure=deal_score_gauge(deal_score, syn.get("deal_recommendation", "unknown")),
                              config={"displayModeBar": False}, style={"height": "190px"}),
                    deal_banner(syn.get("deal_recommendation", "unknown")),
                    html.Div(style={"height": "12px"}),
                    html.Div(_render_narrative(deal_score, score_breakdown, syn.get("deal_recommendation", "")),
                        style={"fontFamily": DM, "fontSize": "11px", "color": C["muted"], "lineHeight": "1.7"}),
                ], extra={"width": "280px", "flexShrink": "0", "marginBottom": "0",
                          "display": "flex", "flexDirection": "column"}),

                html.Div([
                    html.Div([
                        led_score_card("FINANCIAL",  rm.get("financial",  "unknown"), score_breakdown.get("financial",  50), "r-tt-fin", "Financial health score. Drives 40% of deal score."),
                        led_score_card("LEGAL",      rm.get("legal",      "unknown"), score_breakdown.get("legal",      50), "r-tt-leg", "Legal/contract risk score. Drives 35% of deal score."),
                    ], style={"display": "flex", "gap": "12px", "flex": "1"}),
                    html.Div([
                        led_score_card("COMPLIANCE", rm.get("compliance", "unknown"), score_breakdown.get("compliance", 50), "r-tt-cmp", "Compliance score. Drives 25% of deal score."),
                        led_score_card("OVERALL",    rm.get("overall",    "unknown"), deal_score,                            "r-tt-ovr", "Weighted composite deal score."),
                    ], style={"display": "flex", "gap": "12px", "flex": "1"}),
                ], style={"flex": "1", "display": "flex", "flexDirection": "column", "gap": "12px"}),

                html.Div([
                    stat_card("CONTRACT FLAGS",  n_flags,    C["high"],     "identified",  "r-tt-1", "High-risk clauses flagged by AI legal agent."),
                    stat_card("BLOCKING ISSUES", n_blocking, C["critical"], "must resolve","r-tt-2", "Issues that could prevent deal close."),
                    stat_card("APPROVALS",       n_approvals,C["medium"],   "regulatory",  "r-tt-3", "Regulatory bodies requiring approval."),
                    stat_card("FIN. SCORE",      fin_score,  score_color(fin_score), "/ 100","r-tt-4", "AI financial health score 0-100."),
                ], style={"display": "flex", "flexDirection": "column", "gap": "12px",
                          "width": "160px", "flexShrink": "0"}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "14px", "alignItems": "stretch"}),

            # ROW 2: score breakdown + risk heatmap + coverage
            html.Div([
                card([
                    sec("Area Score Breakdown"),
                    dcc.Graph(figure=score_breakdown_chart(score_breakdown),
                              config={"displayModeBar": False}, style={"height": "160px"}),
                ], extra={"flex": "1", "marginBottom": "0"}),
                card([
                    sec("Risk Heatmap"),
                    dcc.Graph(figure=risk_heatmap(deal_risks),
                              config={"displayModeBar": False}, style={"height": "260px"}),
                ], extra={"flex": "1.3", "marginBottom": "0"}),
                card([
                    sec("Diligence Coverage"),
                    dcc.Graph(figure=coverage_chart(diligence_cov) if diligence_cov else go.Figure(),
                              config={"displayModeBar": False}, style={"height": "180px"}),
                ], extra={"flex": "1", "marginBottom": "0"}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "14px", "alignItems": "stretch"}),

            # ROW 3: exec summary + top red flags
            html.Div([
                card([
                    sec("Executive Summary"),
                    html.Div(syn.get("executive_summary", ""), style={"fontFamily": MONO,
                        "fontSize": "11px", "color": C["muted"], "lineHeight": "2"}),
                ], extra={"flex": "1", "marginBottom": "0"}),
                card([
                    sec("Top Red Flags"),
                    html.Div([_flag_card(f) for f in syn.get("top_3_red_flags", [])]),
                ], extra={"flex": "1", "marginBottom": "0"}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "14px"}),

            # ROW 4: financial subscores + contract flag breakdown
            html.Div([
                card([
                    sec("Financial Sub-Scores"),
                    dcc.Graph(figure=financial_subscores_chart(fin_scores) if fin_scores else go.Figure(),
                              config={"displayModeBar": False}, style={"height": "175px"}),
                ], extra={"flex": "1", "marginBottom": "0"}),
                card([
                    sec("Contract Flag Breakdown"),
                    dcc.Graph(figure=flag_breakdown_chart(con),
                              config={"displayModeBar": False}, style={"height": "80px", "marginBottom": "8px"}),
                    html.Div(con.get("summary", "") if con else "", style={"fontFamily": MONO,
                        "fontSize": "11px", "color": C["muted"], "lineHeight": "1.8",
                        "borderLeft": f"2px solid {C['accent']}", "paddingLeft": "12px"}),
                ], extra={"flex": "1", "marginBottom": "0"}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "14px"}),

            # ROW 5: next steps + compliance
            html.Div([
                card([_next_steps_panel(syn)], extra={"flex": "1", "marginBottom": "0"}),
                card([_compliance_panel(comp)], extra={"flex": "1.4", "marginBottom": "0"}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "14px"}),

            # ROW 6: financial detail + contracts
            html.Div([
                card([_financial_panel(fin)], extra={"flex": "1", "marginBottom": "0"}),
                card([_contract_panel(con)],  extra={"flex": "1", "marginBottom": "0"}),
            ], style={"display": "flex", "gap": "14px", "marginBottom": "0"}),
        ])

        return results, {"display": "block"}, hidden, hidden


# ─────────────────────────────────────────────
# PANEL HELPERS
# ─────────────────────────────────────────────

def _deal_score_narrative(score: int, breakdown: dict, recommendation: str) -> str:
    fin = breakdown.get("financial", 50)
    leg = breakdown.get("legal", 50)
    cmp = breakdown.get("compliance", 50)

    areas = {"Financial": fin, "Legal": leg, "Compliance": cmp}
    weakest = min(areas.keys(), key=lambda k: areas.get(k, 50) or 50)
    weakest_score = areas.get(weakest, 50) or 50

    if score >= 75:
        opener = f"This deal scores **{score}/100** — a strong result indicating well-managed risks across all diligence dimensions."
    elif score >= 55:
        opener = f"This deal scores **{score}/100** — moderate overall health with targeted risks that can be mitigated through deal structuring."
    elif score >= 35:
        opener = f"This deal scores **{score}/100** — significant concerns identified across multiple areas. Proceeding requires substantial conditions."
    else:
        opener = f"This deal scores **{score}/100** — critical risk profile. The weight of issues identified makes this transaction high-risk at current terms."

    if weakest_score < 35:
        drag = f"**{weakest}** is the primary drag at {weakest_score}/100, representing the most immediate threat to deal value."
    elif weakest_score < 55:
        drag = f"**{weakest}** ({weakest_score}/100) requires the most attention and should be the focus of pre-close remediation efforts."
    else:
        drag = f"All areas are in acceptable range. **{weakest}** ({weakest_score}/100) has the most room for improvement."

    rec_map = {
        "proceed":                 "The AI synthesis agent recommends proceeding to definitive agreement.",
        "proceed_with_conditions": "The AI synthesis agent recommends proceeding only with specific conditions attached.",
        "do_not_proceed":          "The AI synthesis agent recommends against proceeding under current terms.",
    }
    rec_line = rec_map.get(recommendation, "")
    return f"{opener} {drag} {rec_line}"


def _render_narrative(score: int, breakdown: dict, recommendation: str):
    """Render deal score narrative with **bold** as cyan spans."""
    import re
    text = _deal_score_narrative(score, breakdown, recommendation)
    parts = []
    last = 0
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        if m.start() > last:
            parts.append(html.Span(text[last:m.start()], style={"color": C["muted"]}))
        parts.append(html.Span(m.group(1), style={"color": C["cyan"], "fontWeight": "700"}))
        last = m.end()
    if last < len(text):
        parts.append(html.Span(text[last:], style={"color": C["muted"]}))
    return parts


def _flag_card(f):
    sev = f.get("severity", "medium")
    col = level_color(sev)
    return html.Div([
        html.Div([badge(sev, col), html.Span("  "), badge(f.get("area", ""), C["accent"])],
                 style={"marginBottom": "7px"}),
        html.Div(f.get("flag", ""), style={"fontFamily": DM, "fontWeight": "500",
            "fontSize": "13px", "color": C["text"], "lineHeight": "1.5"}),
    ], style={"background": C["surf2"], "borderLeft": f"3px solid {col}",
              "borderRadius": "10px", "padding": "12px 14px", "marginBottom": "8px"})


def _next_steps_panel(syn):
    steps = syn.get("next_steps", [])
    conds = syn.get("recommended_conditions", [])
    return html.Div([
        sec("Next Steps & Conditions"),
        *[html.Div([html.Span("◆ ", style={"color": C["cond"]}),
                    html.Span(c, style={"fontFamily": MONO, "fontSize": "11px", "color": C["text"]})],
                   style={"marginBottom": "8px"}) for c in conds],
        html.Div(style={"height": "10px"}) if conds else html.Div(),
        *[html.Div([
            html.Span(f"{i+1:02d}", style={"fontFamily": BEBAS, "fontSize": "22px",
                "color": C["accent"], "marginRight": "12px", "minWidth": "26px", "lineHeight": "1.1"}),
            html.Span(s, style={"fontFamily": DM, "fontSize": "13px",
                "color": C["text"], "lineHeight": "1.5"}),
        ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "11px"})
        for i, s in enumerate(steps)],
    ])


def _compliance_panel(comp):
    if not comp or "error" in comp:
        return html.Div()
    overall = comp.get("overall_compliance_risk", "unknown")
    col     = level_color(overall)
    gdpr    = comp.get("gdpr_data_privacy_issues", False)
    blocking  = comp.get("blocking_issues", [])
    approvals = comp.get("regulatory_approvals_needed", [])
    antitrust = comp.get("antitrust_concerns", [])

    def lst(title, items, ic):
        if not items:
            return html.Div()
        return html.Div([
            html.Div(title, style={"fontFamily": MONO, "fontSize": "9px",
                "color": ic, "letterSpacing": "0.15em", "marginBottom": "8px"}),
            *[html.Div(f"• {item}", style={"fontFamily": MONO, "fontSize": "11px",
                "color": C["text"], "marginBottom": "4px", "lineHeight": "1.5"})
              for item in items],
        ], style={"marginBottom": "12px"})

    return html.Div([
        sec("Regulatory & Compliance"),
        html.Div([badge(f"Risk: {overall}", col), html.Span("  "),
                  badge("GDPR Issues" if gdpr else "GDPR OK", C["high"] if gdpr else C["low"])],
                 style={"marginBottom": "12px"}),
        html.Div(comp.get("summary", ""), style={"fontFamily": MONO, "fontSize": "11px",
            "color": C["muted"], "lineHeight": "1.9",
            "borderLeft": f"2px solid {col}", "paddingLeft": "12px", "marginBottom": "14px"}),
        html.Div([
            html.Div([lst("🚫 BLOCKING", blocking, C["critical"]),
                      lst("📋 APPROVALS", approvals, C["high"])],
                     style={"flex": "1", "paddingRight": "12px"}),
            html.Div([lst("⚖ ANTITRUST", antitrust, C["medium"])], style={"flex": "1"}),
        ], style={"display": "flex"}),
    ])


def _financial_panel(fin):
    if not fin or "error" in fin:
        return html.Div()
    risks = fin.get("key_financial_risks", [])
    pos   = fin.get("key_financial_positives", [])
    return html.Div([
        sec("Financial Deep Dive"),
        html.Div([
            html.Div([
                html.Div(str(v), style={"fontFamily": BEBAS, "fontSize": "22px",
                    "color": C["cyan"], "lineHeight": "1"}),
                html.Div(k, style={"fontFamily": MONO, "fontSize": "8px",
                    "color": C["muted"], "letterSpacing": "0.12em", "marginTop": "2px"}),
            ], style={"background": C["surf2"], "border": f"1px solid {C['border']}",
                      "borderRadius": "8px", "padding": "12px 10px", "flex": "1", "textAlign": "center"})
            for k, v in [
                ("REVENUE CAGR",  f"{fin.get('revenue_cagr_pct')}%" if fin.get('revenue_cagr_pct') else "—"),
                ("EBITDA MARGIN", f"{fin.get('ebitda_margin_pct') or fin.get('ebitda_margin')}%" if (fin.get('ebitda_margin_pct') or fin.get('ebitda_margin')) else "—"),
                ("DEBT/EBITDA",   "Debt-Free" if fin.get('debt_to_ebitda') == 0.0 else (f"{fin.get('debt_to_ebitda')}x" if fin.get('debt_to_ebitda') else fin.get('debt_to_equity') or "—")),
                ("CASH",          fin.get("cash_position", "—").title()),
            ]
        ], style={"display": "flex", "gap": "8px", "marginBottom": "14px"}),
        html.Div(fin.get("summary", ""), style={"fontFamily": MONO, "fontSize": "11px",
            "color": C["muted"], "lineHeight": "1.9",
            "borderLeft": f"2px solid {C['accent']}", "paddingLeft": "12px", "marginBottom": "14px"}),
        *([html.Div([
            html.Div("⚠ RISKS", style={"fontFamily": MONO, "fontSize": "9px",
                "color": C["high"], "letterSpacing": "0.15em", "marginBottom": "8px"}),
            *[html.Div([html.Span("• ", style={"color": C["high"]}),
                        html.Span(r, style={"color": C["text"]})],
                       style={"fontFamily": MONO, "fontSize": "11px",
                              "marginBottom": "5px", "lineHeight": "1.5"}) for r in risks],
        ], style={"marginBottom": "14px", "borderLeft": f"2px solid {C['high']}44", "paddingLeft": "12px"})] if risks else []),
        *([html.Div([
            html.Div("✓ POSITIVES", style={"fontFamily": MONO, "fontSize": "9px",
                "color": C["low"], "letterSpacing": "0.15em", "marginBottom": "8px"}),
            *[html.Div([html.Span("• ", style={"color": C["low"]}),
                        html.Span(p, style={"color": C["text"]})],
                       style={"fontFamily": MONO, "fontSize": "11px",
                              "marginBottom": "5px", "lineHeight": "1.5"}) for p in pos],
        ], style={"marginBottom": "14px", "borderLeft": f"2px solid {C['low']}44", "paddingLeft": "12px"})] if pos else []),
    ])


def _contract_panel(con):
    if not con or "error" in con:
        return html.Div()
    flags   = con.get("red_flags", [])
    overall = con.get("overall_contract_risk", "unknown")
    col     = level_color(overall)
    items   = []
    for f in flags:
        rc     = level_color(f.get("risk_level", "medium"))
        prob   = f.get("probability", "—")
        impact = f.get("impact", "—")
        items.append(html.Div([
            html.Div([
                badge(f.get("risk_level", ""), rc),
                html.Span(f"  {f.get('clause', '')}", style={"fontFamily": DM,
                    "fontWeight": "600", "fontSize": "13px", "color": C["text"]}),
                html.Span(f"  P:{prob}% I:{impact}%", style={"fontFamily": MONO,
                    "fontSize": "9px", "color": C["muted"], "marginLeft": "8px"}),
            ], style={"marginBottom": "6px"}),
            html.Div(f.get("explanation", ""), style={"fontFamily": MONO, "fontSize": "11px",
                "color": C["muted"], "lineHeight": "1.6", "marginBottom": "5px"}),
            html.Div([html.Span("→ ", style={"color": C["cyan"]}),
                      html.Span(f.get("recommendation", ""), style={"fontFamily": MONO,
                          "fontSize": "11px", "color": C["cyan"]})]),
        ], style={"background": C["surf2"], "borderLeft": f"3px solid {rc}",
                  "borderRadius": "10px", "padding": "12px 14px", "marginBottom": "9px"}))

    return html.Div([
        sec("Contract Red Flags"),
        html.Div([badge(f"Overall: {overall}", col), html.Span("  "),
                  badge(f"Liability: {con.get('liability_exposure', '—')}",
                        level_color(con.get("liability_exposure", "medium")))],
                 style={"marginBottom": "14px"}),
        html.Div(items),
    ])