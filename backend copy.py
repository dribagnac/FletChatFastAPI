import json, httpx, uvicorn, anyio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()
CONFIG_FILE = "model_persistence.json"

class ChatRequest(BaseModel):
    prompt: str
    model: str
    temperature: float
    stream: bool

async def load_state():
    path = anyio.Path(CONFIG_FILE)
    if await path.exists():
        try:
            return json.loads(await path.read_bytes())
        except: pass
    return {"sessions": {}, "base_url": "http://localhost:1234", "system_prompt": "You are a helpful assistant.", "temperature": 0.7}

async def save_state(state):
    await anyio.Path(CONFIG_FILE).write_bytes(json.dumps(state).encode())

@app.get("/ping")
async def ping():
    state = await load_state()
    url = state.get("base_url", "http://localhost:1234")
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            res = await client.get(f"{url}/v1/models")
            if res.status_code == 200: return {"status": "ok", "lm_studio": "online"}
    except: pass
    return {"status": "ok", "lm_studio": "offline"}

@app.get("/settings")
async def get_settings(): return await load_state()

@app.post("/settings")
async def update_settings(upd: dict):
    state = await load_state()
    state.update(upd)
    await save_state(state)
    return {"status": "ok"}

@app.get("/sessions")
async def list_sessions():
    state = await load_state()
    return state.get("sessions", {})

@app.delete("/sessions/{sid}")
async def delete_session(sid: str):
    state = await load_state()
    if sid in state["sessions"]:
        del state["sessions"][sid]
        await save_state(state)
        return {"status": "deleted"}
    raise HTTPException(status_code=404)

@app.get("/models")
async def get_models():
    state = await load_state()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{state['base_url']}/v1/models")
            return [m["id"] for m in r.json().get("data", [])]
    except: return []

@app.post("/chat")
async def chat(req: ChatRequest):
    state = await load_state()
    sid = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # NEW: Save model and stream state into the session metadata
    state["sessions"][sid] = {
        "title": req.prompt[:30] + ("..." if len(req.prompt) > 30 else ""), 
        "model": req.model,
        "stream": req.stream,
        "messages": [
            {"role": "system", "content": state["system_prompt"]}, 
            {"role": "user", "content": req.prompt}
        ]
    }
    
    payload = {"model": req.model, "messages": state["sessions"][sid]["messages"], "temperature": req.temperature, "stream": req.stream}

    if not req.stream:
        async with httpx.AsyncClient(timeout=None) as c:
            r = await c.post(f"{state['base_url']}/v1/chat/completions", json=payload)
            txt = r.json()["choices"][0]["message"]["content"]
            state["sessions"][sid]["messages"].append({"role": "assistant", "content": txt})
            await save_state(state)
            return JSONResponse({"content": txt})

    async def gen():
        full = ""
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream("POST", f"{state['base_url']}/v1/chat/completions", json=payload) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            content = json.loads(line[6:])["choices"][0]["delta"].get("content", "")
                            if content:
                                full += content
                                yield content
                        except: continue
        state["sessions"][sid]["messages"].append({"role": "assistant", "content": full})
        await save_state(state)
    return StreamingResponse(gen())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)