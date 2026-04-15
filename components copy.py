import flet as ft

class ChatView(ft.Column):
    def __init__(self, app):
        super().__init__(expand=True)
        self.controls = [
            ft.Row([app.model_dd, app.stream_cb, app.status_dot, app.status_text]),
            ft.Container(content=app.chat_container, expand=True, bgcolor="black", padding=20, border_radius=10),
            ft.Row([app.chat_input, ft.IconButton(icon=ft.Icons.SEND, on_click=app.on_send_click)])
        ]

class SettingsView(ft.Column):
    def __init__(self, app):
        super().__init__(spacing=20, visible=False)
        self.controls = [
            ft.Text("Settings", size=25, weight="bold"),
            app.base_url_input, app.system_prompt_input,
            ft.Row([ft.Text("Temperature:"), app.temp_display]),
            app.temp_slider,
            ft.FilledButton("Save Settings", icon=ft.Icons.SAVE, on_click=app.on_save_click)
        ]

class AIStudioApp:
    def __init__(self, page: ft.Page, on_send_click, on_save_click):
        # --- Page Configuration ---
        self.page = page
        self.page.window_icon = "/icon.png"
        self.page.title = "AI Studio Pro"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width, self.page.window_height = 1100, 800

        # --- Callbacks (The Logic hooks) ---
        self.on_send_click = on_send_click
        self.on_save_click = on_save_click

        # --- UI State Objects (The "Data") ---
        self.status_dot = ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.RED, size=12)
        self.status_text = ft.Text("Offline", size=11)
        self.chat_container = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE)
        self.history_list = ft.Column(spacing=0)
        self.model_dd = ft.Dropdown(label="Model", expand=True)
        self.stream_cb = ft.Checkbox(label="Stream", value=True)
        self.chat_input = ft.TextField(label="Message...", expand=True, on_submit=self.on_send_click)
        self.base_url_input = ft.TextField(label="LM Studio Base URL")
        self.system_prompt_input = ft.TextField(label="System Prompt", multiline=True, min_lines=3)
        self.temp_display = ft.Text("0.7", weight="bold", size=16)
        self.temp_slider = ft.Slider(
            min=0, max=2, value=0.7, divisions=20, 
            on_change=lambda e: (setattr(self.temp_display, "value", f"{e.control.value:.1f}"), self.page.update())
        )

        # --- Internal Views ---
        self.chat_view = ChatView(self)
        self.settings_view = SettingsView(self)
        self.sidebar = ft.Container(
            content=ft.Column([ft.Text("HISTORY", weight="bold"), ft.Divider(), self.history_list]), 
            width=280, bgcolor="#1A1B1E", padding=10
        )
        self.main_content = ft.Container(content=self.chat_view, expand=True)

    def build_layout(self, on_nav_change):
        self.nav_rail = ft.NavigationRail(
            selected_index=0, label_type="all", 
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.CHAT, label="Chat"),
                ft.NavigationRailDestination(icon=ft.Icons.SETTINGS, label="Settings"),
                ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label="History"),
            ], 
            on_change=on_nav_change
        )
        return ft.Row([self.nav_rail, self.sidebar, self.main_content], expand=True)