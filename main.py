import flet as ft
import asyncio, httpx, subprocess, sys, time
from components import AIStudioApp, UI_LABELS

backend_proc = None

def start_backend():
    global backend_proc
    try:
        backend_proc = subprocess.Popen([sys.executable, "backend.py"])
        time.sleep(1.5)
    except Exception as e: print(f"Backend Start Error: {e}")

async def main(page: ft.Page):
    app = AIStudioApp(page=page, on_send_click=lambda e: asyncio.create_task(on_send(e)), on_save_click=lambda e: asyncio.create_task(save_settings(e)))

    async def safe_focus():
        """Safely attempts to focus the input field with a small delay to avoid UI thread timeouts."""
        await asyncio.sleep(0.1)
        try:
            await app.chat_input.focus()
        except:
            pass # Focus failed, but app won't crash

    async def on_send(e):
        prompt = app.chat_input.value.strip()
        if not prompt or app.state.is_loading: return
        
        app.chat_container.controls.clear()
        app.set_loading(True)
        
        app.chat_container.controls.append(
            ft.Markdown(UI_LABELS["USER_PREFIX"].format(content=prompt), selectable=True)
        )
        app.chat_container.controls.append(
            ft.Markdown(UI_LABELS["THINKING"], selectable=True, opacity=0.5)
        )
        
        cur_md, app.chat_input.value = app.chat_container.controls[-1], ""
        page.update() 
        
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                payload = {
                    "prompt": prompt, "model": app.model_dd.value, 
                    "temperature": float(app.temp_slider.value), "stream": app.stream_cb.value
                }
                if app.stream_cb.value:
                    async with client.stream("POST", f"{app.state.api_base}/chat", json=payload) as resp:
                        full_res, first_chunk = "", True
                        async for chunk in resp.aiter_text():
                            if first_chunk: cur_md.value, cur_md.opacity, first_chunk = "", 1.0, False
                            full_res += chunk
                            cur_md.value = full_res
                            page.update()
                else:
                    resp = await client.post(f"{app.state.api_base}/chat", json=payload)
                    cur_md.value, cur_md.opacity = resp.json().get("content", ""), 1.0
            await refresh_history()
        except Exception as ex: 
            cur_md.value = f"{UI_LABELS['ERROR_PREFIX']}{ex}"
        finally:
            app.set_loading(False)
            await safe_focus()
            page.update()

    async def refresh_history():
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                sessions = (await client.get(f"{app.state.api_base}/sessions")).json()
                app.history_list.controls = [
                    app.build_history_item(
                        sid=sid, title=s["title"], 
                        on_click=lambda e, sess=s: asyncio.create_task(load_ui_chat(sess)), 
                        on_delete=lambda e, sid=sid: asyncio.create_task(delete_session(sid))
                    ) for sid, s in sorted(sessions.items(), reverse=True)
                ]
                page.update()
        except: pass

    async def load_ui_chat(sess):
        """Restores session state and prompt safely."""
        app.chat_container.controls.clear()
        
        if sess.get("model"): app.model_dd.value = sess.get("model")
        app.stream_cb.value = sess.get("stream", True)
        
        msgs = sess.get("messages", [])
        content = ""
        for m in msgs:
            template = UI_LABELS["USER_PREFIX"] if m['role'] == 'user' else UI_LABELS["ASSISTANT_PREFIX"]
            content += template.format(content=m['content'])
        
        app.chat_container.controls.append(ft.Markdown(content, selectable=True))

        user_msgs = [m["content"] for m in msgs if m["role"] == "user"]
        app.chat_input.value = user_msgs[0] if user_msgs else ""
        
        page.update() # Render the new view first
        await safe_focus() # Then attempt focus safely
        page.update()

    async def save_settings(e):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{app.state.api_base}/settings", json={
                    "base_url": app.base_url_input.value, 
                    "system_prompt": app.system_prompt_input.value, 
                    "temperature": float(app.temp_slider.value)
                })
            app.page.snack_bar = ft.SnackBar(ft.Text(UI_LABELS["SAVE_SUCCESS"]))
            app.page.snack_bar.open = True
            page.update()
        except: pass

    def handle_nav(e):
        idx = int(e.data)
        if idx == 0:
            app.main_content.content = app.chat_view
        elif idx == 1:
            app.main_content.content = app.settings_view
            asyncio.create_task(load_initial_data())
        elif idx == 2:
            app.sidebar.visible = not app.sidebar.visible
            e.control.selected_index = 0 if app.main_content.content == app.chat_view else 1
        page.update()

    async def check_status():
        while True:
            try:
                async with httpx.AsyncClient(timeout=1.0) as c:
                    data = (await c.get(f"{app.state.api_base}/ping")).json()
                    if data.get("lm_studio") == "online":
                        app.status_dot.color, app.status_text.value = ft.Colors.GREEN, UI_LABELS["LM_ONLINE"]
                        app.update_send_status(True)
                        if not app.model_dd.options:
                            models = (await c.get(f"{app.state.api_base}/models")).json()
                            app.model_dd.options = [ft.dropdown.Option(m) for m in models]
                            if models: app.model_dd.value = models[0]
                    else: 
                        app.status_dot.color, app.status_text.value = ft.Colors.ORANGE, UI_LABELS["LM_OFFLINE"]
                        app.update_send_status(False)
            except: 
                app.status_dot.color, app.status_text.value = ft.Colors.RED, UI_LABELS["BACKEND_OFFLINE"]
                app.update_send_status(False)
            page.update()
            await asyncio.sleep(5)

    async def load_initial_data():
        try:
            async with httpx.AsyncClient() as c:
                d = (await c.get(f"{app.state.api_base}/settings")).json()
                app.base_url_input.value, app.system_prompt_input.value = d.get("base_url"), d.get("system_prompt")
                val = d.get("temperature", 0.7)
                app.temp_slider.value, app.temp_display.value = val, f"{val:.1f}"
                page.update()
        except: pass

    page.add(app.build_layout(on_nav_change=handle_nav))
    await asyncio.gather(refresh_history(), check_status())

if __name__ == "__main__":
    if "--dev" not in sys.argv: start_backend()
    try: ft.run(main, assets_dir="assets")
    finally:
        if backend_proc: backend_proc.terminate()