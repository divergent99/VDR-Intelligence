# frontend/callbacks/chat.py
"""
Chat callbacks — two-stage pattern:
  Stage 1: instantly show user message + typing indicator, clear input
  Stage 2: call FastAPI /chat, replace typing indicator with Nova's reply
"""

from __future__ import annotations

from dash import Input, Output, State, no_update, html, dcc, ctx
from dash.exceptions import PreventUpdate

from frontend.theme import C, MONO, DM, set_theme
from frontend.api_client import chat as nova_chat

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


def _bubble_user(msg: str) -> html.Div:
    return html.Div([
        html.Div("YOU", className="chat-label", style={"fontFamily": MONO, "fontSize": "9px",
            "color": C["accent"], "letterSpacing": "0.15em", "marginBottom": "3px"}),
        html.Div(msg, className="chat-text", style={"fontFamily": MONO, "fontSize": "11px",
            "color": C["text"], "lineHeight": "1.5"}),
    ], className="chat-bubble-user",
    style={"background": C["accent"] + "12", "border": f"1px solid {C['accent']}33",
              "borderRadius": "10px", "padding": "9px 12px",
              "alignSelf": "flex-end", "maxWidth": "94%"})


def _bubble_nova(reply: str) -> html.Div:
    return html.Div([
        html.Div("NOVA", style={"fontFamily": MONO, "fontSize": "9px",
            "color": C["cyan"], "letterSpacing": "0.15em", "marginBottom": "3px"}),
        dcc.Markdown(reply, className="nova-md",
            style={"fontSize": "11px"},
            dangerously_allow_html=False),
    ], className="chat-bubble-nova",
    style={"background": C["surf2"], "border": f"1px solid {C['border']}",
              "borderRadius": "10px", "padding": "10px 13px",
              "alignSelf": "flex-start", "maxWidth": "96%"})


def _typing_indicator() -> html.Div:
    return html.Div([
        html.Div("NOVA", style={"fontFamily": MONO, "fontSize": "9px",
            "color": C["cyan"], "letterSpacing": "0.15em", "marginBottom": "6px"}),
        html.Div([
            html.Span(className="typing-dot"),
            html.Span(className="typing-dot"),
            html.Span(className="typing-dot"),
        ], style={"display": "flex", "alignItems": "center", "height": "20px"}),
    ], id="typing-indicator", className="chat-bubble-nova",
    style={"background": C["surf2"], "border": f"1px solid {C['border']}",
           "borderRadius": "10px", "padding": "10px 13px",
           "alignSelf": "flex-start", "maxWidth": "96%"})


def _build_bubbles(history: list[dict]) -> list:
    bubbles = []
    for turn in history:
        bubbles.append(_bubble_user(turn["user"]))
        bubbles.append(_bubble_nova(turn["bot"]))
    return bubbles


def register(app):

    # ── Quick question → fill input ──────────────────────────────
    @app.callback(
        Output("chat-input", "value", allow_duplicate=True),
        Input({"type": "quick-q", "index": __import__("dash").ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def quick_question(n_clicks):
        if not any(n_clicks):
            return no_update
        triggered = ctx.triggered_id
        if triggered is None:
            return no_update
        return QUICK_QUESTIONS[triggered["index"]]

    # ── Stage 1: show message + typing indicator instantly ───────
    @app.callback(
        Output("chat-messages", "children", allow_duplicate=True),
        Output("chat-pending", "data"),
        Output("chat-input", "value"),
        Input("chat-send", "n_clicks"),
        Input("chat-input", "n_submit"),
        State("chat-input", "value"),
        State("chat-history", "data"),
        State("theme-store", "data"),
        prevent_initial_call=True,
    )
    def chat_stage1(_, __, msg, history, theme):
        set_theme(theme or "dark")
        if not msg or not msg.strip():
            return no_update, no_update, no_update
        bubbles = _build_bubbles(history)
        bubbles.append(_bubble_user(msg.strip()))
        bubbles.append(_typing_indicator())
        return bubbles, msg.strip(), ""

    # ── Auto-scroll chat ─────────────────────────────────────────
    app.clientside_callback(
        "function(c){setTimeout(function(){"
        "var e=document.getElementById('chat-messages');"
        "if(e)e.scrollTop=e.scrollHeight;},60);"
        "return window.dash_clientside.no_update;}",
        Output("chat-messages", "id"),
        Input("chat-messages", "children"),
        prevent_initial_call=True,
    )

    # ── Stage 2: call FastAPI, replace typing indicator ──────────
    @app.callback(
        Output("chat-messages", "children"),
        Output("chat-history", "data"),
        Input("chat-pending", "data"),
        State("chat-history", "data"),
        State("results-store", "data"),
        State("theme-store", "data"),
        prevent_initial_call=True,
    )
    def chat_stage2(msg, history, pipeline_data, theme):
        set_theme(theme or "dark")
        if not msg:
            return no_update, no_update

        if not pipeline_data:
            bot = "Run the diligence pipeline first, then ask me anything about this deal."
        else:
            try:
                doc_id  = pipeline_data.get("doc_id") or ""
                if not doc_id:
                    bot = "No document ID found — please re-run the pipeline before chatting."
                    new_history = history + [{"user": msg, "bot": bot}]
                    return _build_bubbles(new_history), new_history
                history_payload = [
                    {"role": "user",      "content": t["user"]}
                    for t in history[-6:]
                ] + [
                    {"role": "assistant", "content": t["bot"]}
                    for t in history[-6:]
                ]
                bot = nova_chat(doc_id, msg, history_payload)
            except Exception as e:
                bot = f"Error contacting API: {e}"

        new_history = history + [{"user": msg, "bot": bot}]
        return _build_bubbles(new_history), new_history