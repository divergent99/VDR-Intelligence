# frontend/callbacks/auth.py
from dash import Input, Output, State, no_update, html, ctx, dcc, ALL
from frontend.api_client import login, register, share_project, get_my_projects
from frontend.theme import MONO, DM, BEBAS, C

def register_auth(app):
    # Login Modal Logic
    @app.callback(
        Output("auth-token", "data"),
        Output("user-email", "data"),
        Output("login-modal", "is_open"),
        Output("login-error", "children"),
        Input("login-btn", "n_clicks"),
        Input("register-btn", "n_clicks"),
        State("login-email", "value"),
        State("login-password", "value"),
        State("auth-token", "data"),
        prevent_initial_call=False
    )
    def handle_login(n_login, n_register, email, password, current_token):
        if current_token:
            return no_update, no_update, False, ""
            
        triggered = ctx.triggered_id
        if not triggered:
            return no_update, no_update, True, ""
            
        if not email or not password:
            return no_update, no_update, True, "Please enter email and password"
            
        try:
            if triggered == "login-btn":
                res = login(email, password)
            else:
                res = register(email, password)
            return res["access_token"], res["email"], False, ""
        except Exception as e:
            return no_update, no_update, True, f"Error: {e}"

    # Share Modal Logic
    @app.callback(
        Output("share-modal", "is_open"),
        Output("share-link-read", "value"),
        Output("share-status", "children"),
        Input("open-share-btn", "n_clicks"),
        Input("do-share-btn", "n_clicks"),
        State("share-email", "value"),
        State("results-store", "data"),
        State("auth-token", "data"),
        State("url", "href"),
        prevent_initial_call=True
    )
    def handle_share(n_open, n_do, email, result_data, token, href):
        triggered = ctx.triggered_id
        if not result_data or "doc_id" not in result_data:
            return False, "", ""
            
        doc_id = result_data["doc_id"]
        
        if "?" in href:
            base_url = href.split("?")[0]
        else:
            base_url = href
        share_link = f"{base_url}?doc_id={doc_id}"
            
        if triggered == "open-share-btn":
            return True, share_link, ""
            
        if triggered == "do-share-btn":
            if not email:
                return True, share_link, "Please enter an email"
            try:
                msg = share_project(token, doc_id, email)
                return True, share_link, msg.get("msg", "Shared!")
            except Exception as e:
                return True, share_link, f"Error: {e}"
                
        return no_update, no_update, no_update

    @app.callback(
        Output("user-display", "children"),
        Output("auth-token", "data", allow_duplicate=True),
        Output("login-modal", "is_open", allow_duplicate=True),
        Input("user-email", "data"),
        Input("logout-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def handle_user_display(email, n_logout):
        triggered = ctx.triggered_id
        if triggered == "logout-btn":
            return "", None, True
        return email or "", no_update, no_update

    # My Projects Modal & Sync
    @app.callback(
        Output("projects-modal", "is_open"),
        Input("open-projects-btn", "n_clicks"),
        Input("close-projects-btn", "n_clicks"),
        State("projects-modal", "is_open"),
        prevent_initial_call=True
    )
    def toggle_projects(n1, n2, is_open):
        return not is_open

    @app.callback(
        Output("my-projects-store", "data"),
        Input("auth-token", "data"),
        Input("sync-interval", "n_intervals"),
        State("my-projects-store", "data"),
        prevent_initial_call=False
    )
    def sync_projects(token, n, current_data):
        if not token:
            return []
        try:
            return get_my_projects(token)
        except Exception:
            return current_data or []

    @app.callback(
        Output("projects-list-container", "children"),
        Input("my-projects-store", "data")
    )
    def render_projects_list(projects):
        if not projects:
            return html.Div("No projects found.", style={"textAlign": "center", "padding": "20px", "color": C["muted"]})
        
        cards = []
        for p in projects:
            doc_id = p.get("doc_id")
            name = p.get("name", "Untitled")
            role = p.get("role", "collaborator")
            cards.append(html.Div([
                html.Div([
                    html.Div(name, style={"fontFamily": DM, "fontSize": "13px", "fontWeight": "600", "color": C["text"]}),
                    html.Div(f"{doc_id[:12]}…", style={"fontFamily": MONO, "fontSize": "10px", "color": C["accent"]}),
                    html.Div(role.upper(), style={"fontFamily": MONO, "fontSize": "9px", "color": C["muted"]}),
                ], style={"flex": "1"}),
                html.Button("LOAD", id={"type": "load-project", "id": doc_id}, className="action-btn-small",
                            style={"fontSize": "10px", "padding": "4px 12px"})
            ], style={
                "display": "flex", "alignItems": "center", "padding": "12px", 
                "borderBottom": f"1px solid {C['border']}", "gap": "15px"
            }))
        return cards

    @app.callback(
        Output("url", "search", allow_duplicate=True),
        Output("projects-modal", "is_open", allow_duplicate=True),
        Input({"type": "load-project", "id": ALL}, "n_clicks"),
        prevent_initial_call=True
    )
    def load_project_from_list(n_clicks):
        if not any(n_clicks):
            return no_update, no_update
        
        # Determine which button was clicked
        if not ctx.triggered:
            return no_update, no_update
            
        triggered_id = ctx.triggered_id
        doc_id = triggered_id.get("id")
        return f"?doc_id={doc_id}", False
