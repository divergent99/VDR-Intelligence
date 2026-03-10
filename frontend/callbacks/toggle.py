# frontend/callbacks/theme.py
"""
Theme toggle callback — switches between dark and light mode.
"""

from __future__ import annotations

from dash import Input, Output, State

from frontend.theme import DARK_C, LIGHT_C, set_theme, C
from frontend.layout import build_layout


def register(app):

    @app.callback(
        Output("theme-root", "children"),
        Output("theme-root", "style"),
        Output("theme-store", "data"),
        Input("theme-toggle", "n_clicks"),
        State("theme-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_theme(n, current):
        new_theme = "light" if current == "dark" else "dark"
        set_theme(new_theme)
        new_layout = build_layout(new_theme)
        root_style = {"background": C["bg"], "minHeight": "100vh"}
        return new_layout.children, root_style, new_theme

    # Sync body class with theme
    app.clientside_callback(
        """
        function(theme) {
            if (theme === 'light') {
                document.body.classList.add('light-mode');
            } else {
                document.body.classList.remove('light-mode');
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("theme-store", "id"),
        Input("theme-store", "data"),
        prevent_initial_call=False,
    )