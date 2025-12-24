# backend/generator_engine.py
import re
import json
import sqlite3
import time
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

try:
    # 引入新的异步流式函数
    from ai_hub import call_ai_stream_async
except ImportError:
    call_ai_stream_async = None

router = APIRouter(prefix="/api/generator", tags=["generator"])


class AppRequest(BaseModel):
    requirement: str


DB_FILE = "apps_storage.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS apps
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  requirement TEXT, 
                  html TEXT, 
                  created_at REAL)''')
    conn.commit()
    conn.close()


init_db()


def clean_code_block(text):
    if not text: return ""
    pattern = r"```html(.*?)```"
    match = re.search(pattern, text, flags=re.DOTALL)
    if match: return match.group(1).strip()
    return text.replace("```", "").strip()


def build_architect_prompt(requirement):
    return (
        f"You are a Senior Frontend Architect. Create a Single Page Application (SPA) based on: '{requirement}'.\n"
        "Technical Constraints:\n"
        "1. Output ONE single HTML file containing CSS (Bootstrap 5) and JS (Vue 3).\n"
        # 🔥 修正点：必须是纯净的 HTML 属性，不能有 Markdown 标记
"2. Use <script src='https://unpkg.com/vue@3/dist/vue.global.js'></script>\n"
"3. Use <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>\n"        "4. No backend calls. Mock all data in `data()`.\n"
        "5. Persistence: Use `localStorage` in `mounted()` and `watch`.\n"
        "6. PREVENT RELOAD: Use `@submit.prevent` on forms.\n"
        "Output ONLY the raw HTML code."
    )


@router.post("/generate_app")
async def generate_app_stream(req: AppRequest):
    if not call_ai_stream:
        return StreamingResponse(iter(["Error: AI Hub missing"]), status_code=500)

    prompt = build_architect_prompt(req.requirement)

    async def event_stream():
        full_raw_code = ""

        # 流式生成
        for chunk in call_ai_stream("Output valid HTML only.", prompt, model="deepseek-ai/DeepSeek-V3",
                                    temperature=0.1):
            full_raw_code += chunk
            # 发送代码片段
            yield json.dumps({"type": "chunk", "content": chunk}) + "\n"

        # 生成结束处理
        clean_html = clean_code_block(full_raw_code)

        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO apps (requirement, html, created_at) VALUES (?, ?, ?)",
                      (req.requirement, clean_html, time.time()))
            new_id = c.lastrowid
            conn.commit()
            conn.close()

            # 发送完成信号
            yield json.dumps({"type": "done", "id": new_id, "html": clean_html}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


# ... (Get History, Load, Delete 接口保持不变，省略以节省篇幅，请保留原文件下半部分) ...
# 为了确保代码完整，建议你保留下面原有的 GET/DELETE 接口
@router.get("/history")
async def get_history():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, requirement, created_at FROM apps ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [{"id": r["id"], "title": r["requirement"][:20] + "...", "full_req": r["requirement"]} for r in rows]


@router.get("/load/{app_id}")
async def load_app(app_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT html FROM apps WHERE id=?", (app_id,))
    row = c.fetchone()
    conn.close()
    return {"html": row[0]} if row else {}


@router.delete("/delete/{app_id}")
async def delete_app(app_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM apps WHERE id=?", (app_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}