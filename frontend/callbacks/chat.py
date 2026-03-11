# frontend/callbacks/chat.py
"""
Chat callbacks — two-stage pattern:
  Stage 1: instantly show user message + typing indicator, clear input
  Stage 2: call FastAPI /chat, replace typing indicator with Nova's reply
"""

from __future__ import annotations

from dash import Input, Output, State, no_update, html, dcc, ctx, ALL
from dash.exceptions import PreventUpdate

from frontend.theme import C, MONO, DM, set_theme

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
        # Turn can be {'user': '...', 'bot': '...'} (old format) or ChatMessage dict (role, content)
        if "role" in turn:
            if turn["role"] == "user":
                bubbles.append(_bubble_user(turn["content"]))
            else:
                bubbles.append(_bubble_nova(turn["content"]))
        else:
            bubbles.append(_bubble_user(turn.get("user", "")))
            bubbles.append(_bubble_nova(turn.get("bot", "")))
    return bubbles


def register(app):

    # ── Quick question → fill input ──────────────────────────────
    @app.callback(
        Output("chat-input", "value", allow_duplicate=True),
        Input({"type": "quick-q", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def quick_question(n_clicks):
        if not any(n_clicks):
            return no_update
        triggered = ctx.triggered_id
        if triggered is None:
            return no_update
        return QUICK_QUESTIONS[triggered["index"]]

    # ── Chat Sync Poller ─────────────────────────────────────────
    @app.callback(
        Output("chat-history", "data"),
        Input("sync-interval", "n_intervals"),
        State("auth-token", "data"),
        State("results-store", "data"),
        State("chat-history", "data"),
        prevent_initial_call=False,
    )
    def sync_chat(n, token, pipeline_data, current_history):
        if not token or not pipeline_data or "doc_id" not in pipeline_data:
            return no_update
        
        doc_id = pipeline_data["doc_id"]
        try:
            from frontend.api_client import get_chat_history
            new_history = get_chat_history(token, doc_id)
            
            # Simple check to avoid circular updates/no-ops
            if len(new_history) != len(current_history):
                return new_history
        except:
            pass
        return no_update

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

    # ── Stage 2: call FastAPI, then clear pending ────────────────
    @app.callback(
        Output("chat-pending", "data", allow_duplicate=True),
        Input("chat-pending", "data"),
        State("chat-history", "data"),
        State("results-store", "data"),
        State("auth-token", "data"),
        prevent_initial_call=True,
    )
    def chat_stage2(msg, history, pipeline_data, token):
        if not msg or not pipeline_data or not token:
            return no_update

        try:
            doc_id  = pipeline_data.get("doc_id") or ""
            if doc_id:
                history_payload = []
                for t in history[-6:]:
                    if "role" in t:
                        history_payload.append({"role": t["role"], "content": t["content"]})
                    else:
                        history_payload.append({"role": "user", "content": t.get("user", "")})
                        history_payload.append({"role": "assistant", "content": t.get("bot", "")})
                
                # Import here to avoid circular dependencies if any
                from frontend.api_client import BASE_URL
                import requests
                
                requests.post(
                    f"{BASE_URL}/diligence/{doc_id}/chat", 
                    json={"message": msg, "history": history_payload},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60
                )
        except Exception as e:
            print(f"Chat error: {e}")
            
        return None # Clear pending, poller will pick up the results

    # ── Final Render Callback ────────────────────────────────────
    @app.callback(
        Output("chat-messages", "children"),
        Input("chat-history", "data"),
        State("chat-pending", "data"),
        State("theme-store", "data"),
        prevent_initial_call=False
    )
    def render_chat(history, pending, theme):
        set_theme(theme or "dark")
        bubbles = _build_bubbles(history)
        if pending:
            bubbles.append(_bubble_user(pending))
            bubbles.append(_typing_indicator())
        return bubbles

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