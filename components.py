import flet as ft
import os
import json
from dotenv import load_dotenv

load_dotenv()

# --- STRICT CONFIGURATION LOADING ---
REQUIRED_KEYS = [
    "APP_TITLE", "CHAT_TAB", "SETTINGS_TAB", "HISTORY_TAB", 
    "HISTORY_HEADER", "MODEL_LABEL", "STREAM_LABEL", 
    "INPUT_PLACEHOLDER", "SETTINGS_TITLE", "URL_LABEL", 
    "PERSONA_LABEL", "TEMP_LABEL", "SAVE_BTN", "DELETE_TOOLTIP", 
    "OFFLINE", "LM_ONLINE", "LM_OFFLINE", "BACKEND_OFFLINE", 
    "THINKING", "ERROR_PREFIX", "SAVE_SUCCESS",
    "USER_PREFIX", "ASSISTANT_PREFIX"
]

def load_labels():
    config_path = "labels.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"CRITICAL: Configuration file '{config_path}' not found.")
    
    with open(config_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"CRITICAL: Failed to parse '{config_path}'. {e}")
    
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise KeyError(f"CRITICAL: Missing keys in labels.json: {', '.join(missing)}")
    return data

UI_LABELS = load_labels()

class AppState:
    def __init__(self):
        self.api_base = os.getenv("API_BASE", "http://127.0.0.1:8000")
        self.is_loading = False

class ChatView(ft.Column):
    def __init__(self, app):
        super().__init__(expand=True)
        self.loader = ft.ProgressBar(visible=False, color=ft.Colors.BLUE_400)
        self.send_button = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED, 
            icon_color=ft.Colors.BLUE_400, 
            on_click=app.on_send_click
        )
        self.controls = [
            ft.Row([app.model_dd, app.stream_cb, app.status_dot, app.status_text]),
            self.loader,
            ft.Container(
                content=app.chat_container, expand=True, 
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE), 
                padding=20, border_radius=10, border=ft.border.all(1, ft.Colors.WHITE10)
            ),
            ft.Row([app.chat_input, self.send_button])
        ]

class SettingsView(ft.Column):
    def __init__(self, app):
        super().__init__(spacing=20)
        self.controls = [
            ft.Text(UI_LABELS["SETTINGS_TITLE"], size=25, weight="bold"),
            app.base_url_input, app.system_prompt_input,
            ft.Row([ft.Text(UI_LABELS["TEMP_LABEL"]), app.temp_display]),
            app.temp_slider,
            ft.FilledButton(UI_LABELS["SAVE_BTN"], icon=ft.Icons.SAVE, on_click=app.on_save_click)
        ]

class AIStudioApp:
    def __init__(self, page: ft.Page, on_send_click, on_save_click):
        self.page, self.state = page, AppState()
        self.page.title = UI_LABELS["APP_TITLE"]
        
        try:
            self.page.window_width = int(os.getenv("WINDOW_WIDTH", "1100").split('#')[0].strip())
            self.page.window_height = int(os.getenv("WINDOW_HEIGHT", "800").split('#')[0].strip())
        except:
            self.page.window_width, self.page.window_height = 1100, 800

        self.on_send_click, self.on_save_click = on_send_click, on_save_click
        self.status_dot = ft.Icon(ft.Icons.LENS, color=ft.Colors.RED, size=12)
        self.status_text = ft.Text(UI_LABELS["OFFLINE"], size=11)
        self.chat_container = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE)
        self.history_list = ft.Column(spacing=0)
        self.model_dd = ft.Dropdown(label=UI_LABELS["MODEL_LABEL"], expand=True)
        self.stream_cb = ft.Checkbox(label=UI_LABELS["STREAM_LABEL"], value=True)
        self.chat_input = ft.TextField(label=UI_LABELS["INPUT_PLACEHOLDER"], expand=True, on_submit=self.on_send_click, shift_enter=True)
        self.base_url_input = ft.TextField(label=UI_LABELS["URL_LABEL"])
        self.system_prompt_input = ft.TextField(label=UI_LABELS["PERSONA_LABEL"], multiline=True, min_lines=3)
        self.temp_display = ft.Text("0.7", weight="bold", size=16)
        self.temp_slider = ft.Slider(min=0, max=2, value=0.7, divisions=20, on_change=self._update_temp)

        self.chat_view, self.settings_view = ChatView(self), SettingsView(self)
        self.sidebar = ft.Container(content=ft.Column([ft.Text(UI_LABELS["HISTORY_HEADER"], weight="bold", size=12), ft.Divider(height=1), self.history_list]), width=280, bgcolor="#1A1B1E", padding=15)
        self.main_content = ft.Container(content=self.chat_view, expand=True)

    def _update_temp(self, e):
        self.temp_display.value = f"{e.control.value:.1f}"
        self.page.update()

    def update_send_status(self, available: bool):
        self.chat_view.send_button.disabled = self.chat_input.disabled = not available
        self.chat_view.send_button.icon_color = ft.Colors.BLUE_400 if available else ft.Colors.GREY_600
        self.page.update()

    def set_loading(self, loading: bool):
        self.state.is_loading = self.chat_view.loader.visible = self.chat_input.disabled = self.chat_view.send_button.disabled = loading
        self.page.update()

    def build_history_item(self, sid, title, on_click, on_delete):
        return ft.ListTile(
            title=ft.Text(title, size=11, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            on_click=on_click, content_padding=ft.padding.only(left=10, right=0),
            trailing=ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=ft.Colors.RED_400, on_click=on_delete, tooltip=UI_LABELS["DELETE_TOOLTIP"])
        )

    def build_layout(self, on_nav_change):
        self.nav_rail = ft.NavigationRail(selected_index=0, label_type="all", destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.CHAT_OUTLINED, label=UI_LABELS["CHAT_TAB"]),
            ft.NavigationRailDestination(icon=ft.Icons.SETTINGS_OUTLINED, label=UI_LABELS["SETTINGS_TAB"]),
            ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label=UI_LABELS["HISTORY_TAB"]),
        ], on_change=on_nav_change)
        return ft.Row([self.nav_rail, self.sidebar, self.main_content], expand=True)