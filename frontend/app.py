# frontend/app.py
"""
VDR Intelligence — Dash frontend
Run: python -m frontend.app  →  http://localhost:8050

Requires FastAPI backend running on port 8000:
    uvicorn api.main:app --port 8000
"""

import dash
import dash_bootstrap_components as dbc

from frontend.layout import build_layout
from frontend.callbacks import pipeline, chat, toggle, auth

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700"
        "&family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600;700&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="VDR Intelligence",
)

app.index_string = """<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#07070f;color:#e8e8f8;font-family:'DM Sans',sans-serif;overflow-x:hidden;transition:background-color .25s,color .25s}
body.light-mode{background:#f0f2f8 !important;color:#0d0d2b !important}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:#0d0d1a}
::-webkit-scrollbar-thumb{background:#6c63ff55;border-radius:2px}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}
@keyframes fadein{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes stepin{from{opacity:0;transform:translateX(-16px)}to{opacity:1;transform:translateX(0)}}
.spinner{width:50px;height:50px;border:2px solid #1c1c3a;border-top:2px solid #6c63ff;border-right:2px solid #00e5cc;border-radius:50%;animation:spin .75s linear infinite;margin:0 auto 18px}
.pulse{animation:pulse 2s ease infinite}
.stepin{animation:stepin .4s ease forwards;opacity:0}
.stepin:nth-child(1){animation-delay:.1s}.stepin:nth-child(2){animation-delay:.5s}
.stepin:nth-child(3){animation-delay:.9s}.stepin:nth-child(4){animation-delay:1.3s}
.run-btn:hover{filter:brightness(1.1);transform:translateY(-1px);transition:all .15s}
.quick-q-btn:hover{background:rgba(108,99,255,0.12) !important;color:#6c63ff !important;border-color:rgba(108,99,255,0.3) !important;}
input::placeholder{color:#2a2a4a!important}input:focus{outline:none!important}
.typing-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#00e5cc;margin:0 2px;animation:typing-bounce .9s infinite ease-in-out}
.typing-dot:nth-child(2){animation-delay:.2s}.typing-dot:nth-child(3){animation-delay:.4s}
@keyframes typing-bounce{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-5px);opacity:1}}
/* ── Markdown inside Nova bubbles — dark (default) ── */
.nova-md{font-family:'JetBrains Mono',monospace;font-size:11px;line-height:1.65;color:#8888aa;overflow-wrap:break-word}
.nova-md p{margin:0 0 6px}
.nova-md h1,.nova-md h2,.nova-md h3,.nova-md h4{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#00e5cc;letter-spacing:0.1em;text-transform:uppercase;margin:8px 0 4px}
.nova-md strong,.nova-md b{color:#e8e8f8;font-weight:700}
.nova-md ul,.nova-md ol{padding-left:16px;margin:4px 0 6px}
.nova-md li{margin-bottom:3px}
.nova-md blockquote{border-left:2px solid #ff4d4d;padding-left:10px;margin:6px 0;color:#ff4d4d}
.nova-md table{width:100%;border-collapse:collapse;font-size:10px;margin:8px 0;display:block;overflow-x:auto}
.nova-md th{background:#1c1c3a;color:#00e5cc;padding:5px 8px;text-align:left;border:1px solid #2a2a4a;font-weight:700;white-space:nowrap}
.nova-md td{padding:4px 8px;border:1px solid #2a2a4a;color:#c8c8e8;vertical-align:top}
.nova-md tr:nth-child(even) td{background:#0d0d1a}
.nova-md code{background:#1c1c3a;color:#6c63ff;padding:1px 5px;border-radius:3px;font-size:10px}
/* ── Light mode overrides ── */
body.light-mode .nova-md{color:#2a2a4a}
body.light-mode .nova-md strong,body.light-mode .nova-md b{color:#0d0d2b}
body.light-mode .nova-md h1,body.light-mode .nova-md h2,body.light-mode .nova-md h3,body.light-mode .nova-md h4{color:#0077aa}
body.light-mode .nova-md blockquote{border-left-color:#cc0000;color:#cc0000}
body.light-mode .nova-md th{background:#dde3f0;color:#0077aa;border-color:#b0bcd8}
body.light-mode .nova-md td{color:#2a2a4a;border-color:#b0bcd8}
body.light-mode .nova-md tr:nth-child(even) td{background:#eef1f8}
body.light-mode .nova-md code{background:#e0e4f0;color:#5500cc}
/* ── Chat bubble light mode ── */
body.light-mode .chat-bubble-nova{background:#e8ecf8 !important;border-color:#b0bcd8 !important}
body.light-mode .chat-bubble-user{background:rgba(108,99,255,0.08) !important;border-color:rgba(108,99,255,0.25) !important}
body.light-mode .chat-bubble-user .chat-label{color:#5500cc !important}
body.light-mode .chat-bubble-user .chat-text{color:#0d0d2b !important}
/* ── Risk table light mode ── */
body.light-mode .risk-table-dark{background:#dde3f0 !important;color:#0d0d2b !important;border-color:#b0bcd8 !important}
</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

# Layout
app.layout = build_layout("dark")

# Register all callbacks
pipeline.register(app)
chat.register(app)
auth.register_auth(app)
toggle.register(app)

if __name__ == "__main__":
    app.run(debug=False, port=8050)