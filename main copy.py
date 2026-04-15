import flet as ft
import asyncio, httpx, subprocess, sys, time
from components import AIStudioApp

API_BASE = "http://127.0.0.1:8000"
backend_proc = None

def start_backend():
    global backend_proc
    try:
        backend_proc = subprocess.Popen([sys.executable, "backend.py"])
        time.sleep(1.5)
    except: pass

async def main(page: ft.Page):
    # --- 1. Initialize the App Object (UI & Config) ---
    app = AIStudioApp(
        page=page, 
        on_send_click=lambda e: asyncio.create_task(on_send(e)),
        on_save_click=lambda e: asyncio.create_task(save_settings(e))
    )

    # --- 2. Logic Definitions ---
    async def on_send(e):
        prompt = app.chat_input.value
        if not prompt: return
        app.chat_input.value = ""
        app.chat_container.controls.clear()
        app.chat_container.controls.append(ft.Markdown("", selectable=True))
        cur_md = app.chat_container.controls[-1]
        header = f"**You:** {prompt}\n\n**AI:** "
        cur_md.value = header + "_Thinking..._"
        page.update()
        
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                payload = {"prompt": prompt, "model": app.model_dd.value, "temperature": float(app.temp_slider.value), "stream": app.stream_cb.value}
                if app.stream_cb.value:
                    async with client.stream("POST", f"{API_BASE}/chat", json=payload) as resp:
                        full_res, first = "", True
                        async for chunk in resp.aiter_text():
                            if first: cur_md.value = header; first = False
                            full_res += chunk
                            cur_md.value = header + full_res
                            page.update()
                else:
                    resp = await client.post(f"{API_BASE}/chat", json=payload)
                    cur_md.value = header + resp.json()["content"]
                    page.update()
            await refresh_history()
        except Exception as ex:
            cur_md.value = header + f"\n\n*Error: {ex}*"
            page.update()

    async def save_settings(e):
        async with httpx.AsyncClient() as client:
            await client.post(f"{API_BASE}/settings", json={
                "base_url": app.base_url_input.value, 
                "system_prompt": app.system_prompt_input.value, 
                "temperature": float(app.temp_slider.value)
            })
        page.snack_bar = ft.SnackBar(ft.Text("Settings Saved!"), open=True)
        page.update()

    async def refresh_history():
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                sessions = (await client.get(f"{API_BASE}/sessions")).json()
                app.history_list.controls = [
                    ft.ListTile(title=ft.Text(s["title"], size=11), on_click=lambda e, s=s: asyncio.create_task(load_ui_chat(s)))
                    for sid, s in sorted(sessions.items(), reverse=True)
                ]
                page.update()
        except: pass

    async def load_ui_chat(sess):
        app.chat_container.controls.clear()
        if "model" in sess: app.model_dd.value = sess["model"]
        if "stream" in sess: app.stream_cb.value = sess["stream"]
        msgs = sess.get("messages", [])
        new_text = "".join([f"**You:** {m['content']}\n\n" if m['role'] == 'user' else f"{m['content']}\n\n---\n\n" for m in msgs if m['role'] != 'system'])
        app.chat_container.controls.append(ft.Markdown(new_text, selectable=True, code_theme="atom-one-dark"))
        page.update()

    def handle_nav(e):
        idx = e.control.selected_index
        if idx == 0:
            app.main_content.content, app.chat_view.visible, app.settings_view.visible = app.chat_view, True, False
        elif idx == 1:
            app.main_content.content, app.chat_view.visible, app.settings_view.visible = app.settings_view, False, True
            asyncio.create_task(load_initial_data())
        elif idx == 2:
            app.sidebar.visible = not app.sidebar.visible
        page.update()

    # --- 3. Build and Display ---
    page.add(app.build_layout(on_nav_change=handle_nav))

    # --- Data Sync Tasks ---
    async def load_initial_data():
        try:
            async with httpx.AsyncClient() as c:
                d = (await c.get(f"{API_BASE}/settings")).json()
                app.base_url_input.value, app.system_prompt_input.value = d.get("base_url", ""), d.get("system_prompt", "")
                val = d.get("temperature", 0.7)
                app.temp_slider.value, app.temp_display.value = val, f"{val:.1f}"
                page.update()
        except: pass

    async def check_status():
        while True:
            try:
                async with httpx.AsyncClient(timeout=1.0) as c:
                    data = (await c.get(f"{API_BASE}/ping")).json()
                    if data.get("lm_studio") == "online":
                        app.status_dot.color, app.status_text.value = ft.Colors.GREEN, "LM Studio Online"
                        if not app.model_dd.options:
                            models = (await c.get(f"{API_BASE}/models")).json()
                            app.model_dd.options = [ft.dropdown.Option(m) for m in models]
                            if models: app.model_dd.value = models[0]
                    else: app.status_dot.color, app.status_text.value = ft.Colors.ORANGE, "LM Studio Offline"
            except: app.status_dot.color, app.status_text.value = ft.Colors.RED, "Backend Offline"
            page.update()
            await asyncio.sleep(5)

    asyncio.create_task(load_initial_data()); asyncio.create_task(refresh_history()); asyncio.create_task(check_status())

if __name__ == "__main__":
    if "--dev" not in sys.argv: start_backend()
    try: ft.run(main, assets_dir="assets")
    finally:
        if backend_proc: backend_proc.terminate()