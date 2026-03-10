# frontend/theme.py
"""
Theme constants and style helpers shared across layout, charts, and callbacks.
Import C, MONO, BEBAS, DM everywhere instead of redefining them.
"""

from __future__ import annotations

DARK_C = {
    "bg": "#07070f", "surf": "#0d0d1a", "surf2": "#13132a", "border": "#1c1c3a",
    "accent": "#6c63ff", "cyan": "#00e5cc", "text": "#e8e8f8", "muted": "#5a5a7a",
    "critical": "#ff3b5c", "high": "#ff8c42", "medium": "#ffd166", "low": "#06d6a0",
    "cond": "#ff8c42", "stop": "#ff3b5c", "proceed": "#06d6a0",
}
LIGHT_C = {
    "bg": "#f0f2f8", "surf": "#ffffff", "surf2": "#e8eaf4", "border": "#d0d4e8",
    "accent": "#5046e5", "cyan": "#0099aa", "text": "#0d0d2b", "muted": "#4a4a6a",
    "critical": "#cc1133", "high": "#c05800", "medium": "#a07000", "low": "#007a55",
    "cond": "#c05800", "stop": "#cc1133", "proceed": "#007a55",
}

# Active theme — mutated by theme toggle callback
C = DARK_C.copy()

MONO  = "'JetBrains Mono',monospace"
BEBAS = "'Bebas Neue',sans-serif"
DM    = "'DM Sans',sans-serif"


def set_theme(theme: str) -> None:
    """Switch the active theme. Call from the theme toggle callback."""
    global C
    C.update(DARK_C if theme == "dark" else LIGHT_C)


def score_label(s: int) -> str:
    if s >= 80: return "EXCELLENT"
    if s >= 65: return "STRONG"
    if s >= 50: return "MODERATE"
    if s >= 35: return "ELEVATED RISK"
    if s >= 20: return "HIGH RISK"
    return "CRITICAL RISK"


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


def card_shadow() -> str:
    return (
        "0 2px 12px rgba(0,0,0,0.35),0 1px 3px rgba(0,0,0,0.25)"
        if C == DARK_C else
        "0 2px 12px rgba(0,0,0,0.10),0 1px 4px rgba(0,0,0,0.07)"
    )