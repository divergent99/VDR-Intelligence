# frontend/charts.py
"""
All Plotly figure builders for the VDR Intelligence dashboard.
Every function takes data, returns a go.Figure — no Dash, no layout, no callbacks.
"""

from __future__ import annotations

import math

import plotly.graph_objects as go

from frontend.theme import C, MONO, BEBAS, DM


def score_color(s: int) -> str:
    if s >= 75: return C["low"]
    if s >= 50: return C["medium"]
    if s >= 25: return C["high"]
    return C["critical"]


def level_color(lvl: str) -> str:
    return {
        "critical": C["critical"],
        "high":     C["high"],
        "medium":   C["medium"],
        "low":      C["low"],
    }.get(str(lvl).lower(), C["muted"])


# ─────────────────────────────────────────────
# DEAL SCORE GAUGE
# ─────────────────────────────────────────────

def deal_score_gauge(score: int, recommendation: str) -> go.Figure:
    col   = score_color(score)
    R_OUT = 1.0
    R_IN  = 0.55
    N_PTS = 60

    def arc_xy(r, a_start, a_end):
        pts = [a_start + (a_end - a_start) * i / (N_PTS - 1) for i in range(N_PTS)]
        return [r * math.cos(a) for a in pts], [r * math.sin(a) for a in pts]

    segments = [
        (math.pi,       3*math.pi/4, "rgba(255,59,92,0.75)"),
        (3*math.pi/4,   math.pi/2,   "rgba(255,140,66,0.75)"),
        (math.pi/2,     math.pi/4,   "rgba(255,209,102,0.75)"),
        (math.pi/4,     0,           "rgba(6,214,160,0.75)"),
    ]

    fig = go.Figure()

    for a_start, a_end, seg_col in segments:
        ox, oy = arc_xy(R_OUT, a_start, a_end)
        ix, iy = arc_xy(R_IN,  a_end,   a_start)
        fig.add_trace(go.Scatter(
            x=ox + ix + [ox[0]], y=oy + iy + [oy[0]],
            fill="toself", fillcolor=seg_col,
            line=dict(color="rgba(0,0,0,0)", width=0),
            hoverinfo="skip", showlegend=False, mode="lines",
        ))

    angle  = math.pi * (1.0 - score / 100.0)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    NEEDLE_L = R_IN * 0.88
    BASE_W   = 0.04
    tip_x = NEEDLE_L * cos_a;  tip_y = NEEDLE_L * sin_a
    b1x   =  BASE_W * (-sin_a); b1y =  BASE_W * cos_a
    b2x   = -BASE_W * (-sin_a); b2y = -BASE_W * cos_a

    fig.add_trace(go.Scatter(
        x=[b1x, tip_x, b2x, b1x], y=[b1y, tip_y, b2y, b1y],
        fill="toself", fillcolor=col, line=dict(color=col, width=1),
        hoverinfo="skip", showlegend=False, mode="lines",
    ))

    hub_r  = 0.065
    hub_pts = 40
    hx = [hub_r * math.cos(2*math.pi*i/hub_pts) for i in range(hub_pts+1)]
    hy = [hub_r * math.sin(2*math.pi*i/hub_pts) for i in range(hub_pts+1)]
    fig.add_trace(go.Scatter(
        x=hx, y=hy, fill="toself", fillcolor=C["surf"],
        line=dict(color=col, width=2),
        hoverinfo="skip", showlegend=False, mode="lines",
    ))

    R_TICK = R_OUT + 0.12
    annotations = [
        dict(
            text=label,
            x=R_TICK * math.cos(math.pi * (1.0 - val / 100.0)),
            y=R_TICK * math.sin(math.pi * (1.0 - val / 100.0)),
            xref="x", yref="y", showarrow=False,
            font=dict(family=MONO, size=9, color=C["muted"]),
            xanchor="center", yanchor="middle",
        )
        for val, label in [(0,"0"),(25,"25"),(50,"50"),(75,"75"),(100,"100")]
    ]
    annotations.append(dict(
        text=str(score), x=0, y=-0.32, xref="x", yref="y",
        showarrow=False,
        font=dict(family=BEBAS, size=46, color=col),
        xanchor="center", yanchor="middle",
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=0), height=190,
        showlegend=False, annotations=annotations,
        xaxis=dict(visible=False, range=[-1.25, 1.25], fixedrange=True, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False, range=[-0.45, 1.18], fixedrange=True),
    )
    return fig


# ─────────────────────────────────────────────
# SCORE BREAKDOWN BARS
# ─────────────────────────────────────────────

def score_breakdown_chart(score_breakdown: dict) -> go.Figure:
    areas  = list(score_breakdown.keys())
    scores = [score_breakdown[a] for a in areas]
    colors = [score_color(s) for s in scores]

    fig = go.Figure()
    for area, score, col in zip(areas, scores, colors):
        fig.add_trace(go.Bar(
            name=area.upper(), x=[score], y=[area], orientation="h",
            marker=dict(color=col, line=dict(width=0)),
            text=f"  {score}", textposition="inside",
            textfont=dict(family=BEBAS, size=14, color=C["bg"]),
            hovertemplate=f"<b>{area.upper()}</b>: {score}/100<extra></extra>",
            showlegend=False,
        ))
        fig.add_trace(go.Bar(
            x=[100-score], y=[area], orientation="h",
            marker=dict(color=C["border"], line=dict(width=0)),
            hoverinfo="skip", showlegend=False,
        ))

    fig.update_layout(
        barmode="stack", paper_bgcolor=C["surf"], plot_bgcolor=C["surf"],
        margin=dict(l=0, r=10, t=4, b=4), height=160,
        xaxis=dict(visible=False, range=[0, 102]),
        yaxis=dict(
            tickfont=dict(family=MONO, size=10, color=C["muted"]),
            gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)",
            categoryorder="array",
            categoryarray=["overall", "compliance", "legal", "financial"],
        ),
        bargap=0.35,
    )
    return fig


# ─────────────────────────────────────────────
# RISK HEATMAP
# ─────────────────────────────────────────────

def risk_heatmap(deal_risks: list[dict]) -> go.Figure:
    if not deal_risks:
        return go.Figure()

    area_colors = {"financial": C["cyan"], "legal": C["accent"], "compliance": C["high"]}
    fig = go.Figure()

    for r in deal_risks:
        prob   = r.get("probability", 50)
        impact = r.get("impact", 50)
        area   = r.get("area", "financial").lower()
        col    = area_colors.get(area, C["muted"])
        name   = r.get("risk", "")[:30]

        fig.add_trace(go.Scatter(
            x=[prob], y=[impact],
            mode="markers+text",
            marker=dict(size=14, color=col, line=dict(color=C["bg"], width=2), opacity=0.85),
            text=[name], textposition="top center",
            textfont=dict(family=MONO, size=8, color=C["muted"]),
            name=area.upper(),
            hovertemplate=f"<b>{name}</b><br>Probability: {prob}%<br>Impact: {impact}%<br>Area: {area.upper()}<extra></extra>",
            showlegend=False,
        ))

    for x0,x1,y0,y1,fc in [
        (0,50,0,50,"rgba(6,214,160,0.03)"),   (50,100,0,50,"rgba(255,209,102,0.06)"),
        (0,50,50,100,"rgba(255,209,102,0.06)"),(50,100,50,100,"rgba(255,59,92,0.08)"),
    ]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
            fillcolor=fc, line=dict(width=0), layer="below")

    for text, x, y in [
        ("LOW RISK", 25, 25), ("CRITICAL ZONE", 75, 75),
        ("HIGH IMPACT", 75, 25), ("LIKELY", 25, 75),
    ]:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False,
            font=dict(family=MONO, size=8, color="rgba(200,200,200,0.4)"))

    fig.update_layout(
        paper_bgcolor=C["surf"], plot_bgcolor=C["surf"],
        margin=dict(l=40, r=10, t=10, b=40), height=260,
        xaxis=dict(title=dict(text="PROBABILITY →", font=dict(family=MONO, size=9, color=C["muted"])),
                   range=[0,100], gridcolor=C["border"], linecolor=C["border"],
                   tickfont=dict(family=MONO, size=8, color=C["muted"])),
        yaxis=dict(title=dict(text="IMPACT →", font=dict(family=MONO, size=9, color=C["muted"])),
                   range=[0,100], gridcolor=C["border"], linecolor=C["border"],
                   tickfont=dict(family=MONO, size=8, color=C["muted"])),
        showlegend=False,
    )
    return fig


# ─────────────────────────────────────────────
# DILIGENCE COVERAGE
# ─────────────────────────────────────────────

def coverage_chart(diligence_coverage: dict) -> go.Figure:
    labels = {
        "financial_documents": "Financial Docs",
        "legal_contracts":     "Legal Contracts",
        "compliance_docs":     "Compliance Docs",
        "ip_documents":        "IP Documents",
        "hr_documents":        "HR Documents",
    }
    items = sorted(
        [(labels.get(k, k), v) for k, v in diligence_coverage.items()],
        key=lambda x: x[1], reverse=True,
    )

    fig = go.Figure()
    for label, pct in items:
        col = C["low"] if pct >= 70 else C["medium"] if pct >= 40 else C["high"]
        fig.add_trace(go.Bar(
            x=[pct], y=[label], orientation="h",
            marker=dict(color=col, line=dict(width=0)),
            text=f"  {pct}%", textposition="inside",
            textfont=dict(family=BEBAS, size=13, color=C["bg"]),
            hovertemplate=f"<b>{label}</b>: {pct}% covered<extra></extra>",
            showlegend=False,
        ))
        fig.add_trace(go.Bar(
            x=[100-pct], y=[label], orientation="h",
            marker=dict(color=C["border"], line=dict(width=0)),
            hoverinfo="skip", showlegend=False,
        ))

    fig.update_layout(
        barmode="stack", paper_bgcolor=C["surf"], plot_bgcolor=C["surf"],
        margin=dict(l=0, r=10, t=4, b=4), height=180,
        xaxis=dict(visible=False, range=[0, 102]),
        yaxis=dict(tickfont=dict(family=MONO, size=9, color=C["muted"]),
                   gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)"),
        bargap=0.3,
    )
    return fig


# ─────────────────────────────────────────────
# FINANCIAL SUB-SCORES
# ─────────────────────────────────────────────

def financial_subscores_chart(scores: dict) -> go.Figure:
    labels = {
        "revenue_quality":     "Revenue Quality",
        "margin_health":       "Margin Health",
        "debt_sustainability": "Debt Sustainability",
        "cash_adequacy":       "Cash Adequacy",
        "earnings_quality":    "Earnings Quality",
    }
    ks = list(scores.keys())
    vs = [scores[k] for k in ks]
    ls = [labels.get(k, k) for k in ks]
    cs = [score_color(v) for v in vs]

    fig = go.Figure(go.Bar(
        x=vs, y=ls, orientation="h",
        marker=dict(color=cs, line=dict(width=0)),
        text=[f"  {v}" for v in vs], textposition="inside",
        textfont=dict(family=BEBAS, size=13, color=C["bg"]),
        hovertemplate="<b>%{y}</b>: %{x}/100<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=C["surf"], plot_bgcolor=C["surf"],
        margin=dict(l=0, r=10, t=4, b=4), height=175,
        xaxis=dict(range=[0, 105], gridcolor=C["border"], linecolor=C["border"],
                   tickfont=dict(family=MONO, size=8, color=C["muted"])),
        yaxis=dict(tickfont=dict(family=MONO, size=9, color=C["muted"]),
                   gridcolor="rgba(0,0,0,0)", linecolor="rgba(0,0,0,0)"),
        showlegend=False,
    )
    return fig


# ─────────────────────────────────────────────
# FLAG BREAKDOWN
# ─────────────────────────────────────────────

def flag_breakdown_chart(contract: dict) -> go.Figure:
    flags  = contract.get("red_flags", []) if contract else []
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in flags:
        k = f.get("risk_level", "medium").upper()
        if k in counts:
            counts[k] += 1

    fig = go.Figure()
    for lvl, col in [("CRITICAL", C["critical"]), ("HIGH", C["high"]),
                     ("MEDIUM", C["medium"]), ("LOW", C["low"])]:
        if counts[lvl]:
            fig.add_trace(go.Bar(
                name=lvl, x=[counts[lvl]], y=["FLAGS"], orientation="h",
                marker=dict(color=col, line=dict(width=0)),
                text=str(counts[lvl]), textposition="inside",
                textfont=dict(family=BEBAS, size=14, color=C["bg"]),
                hovertemplate=f"<b>{lvl}</b>: {counts[lvl]} flags<extra></extra>",
            ))

    fig.update_layout(
        barmode="stack", paper_bgcolor=C["surf"], plot_bgcolor=C["surf"],
        margin=dict(l=0, r=0, t=0, b=0), height=48,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=True, bargap=0,
        legend=dict(orientation="h", font=dict(family=MONO, size=9, color=C["muted"]),
                    bgcolor="rgba(0,0,0,0)", x=0, y=-2.5),
    )
    return fig