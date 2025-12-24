# backend/app/modules/game/game_engine.py
import re
import json
import sqlite3
import time
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

try:
    # 引入新的异步流式函数 (相对导入)
    from ...core.ai_hub import call_ai_stream_async
except ImportError:
    call_ai_stream_async = None

router = APIRouter(prefix="/api/game", tags=["game"])


class GameRequest(BaseModel):
    requirement: str


DB_FILE = "apps_storage.db"


def clean_code_block(text):
    if not text: return ""
    pattern = r"```html(.*?)```"
    match = re.search(pattern, text, flags=re.DOTALL)
    if match: return match.group(1).strip()
    return text.replace("```", "").strip()


# 🔥 核心升级：Prompt 7.0 (模板填空 + 防语法错误版)
def build_game_architect_prompt(requirement):
    return (
        f"You are a Senior Game Architect. Build a SINGLE FILE HTML game using Phaser 3: '{requirement}'.\n"
        "Technical Stack:\n"
        "1. Library: <script src='https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js'></script>\n"
        "2. Architecture: Class-based `GameScene extends Phaser.Scene`.\n"
        "\n"
        "🔥🔥🔥 MANDATORY CODE PATTERNS (COPY THESE) 🔥🔥🔥\n"
        "To prevent crashes, you MUST use these patterns:\n"
        "\n"
        "1. **SAFE OBJECT CREATION** (Do NOT use physics.add.text):\n"
        "   ```javascript\n"
        "   createEmoji(x, y, emoji, isStatic = false) {\n"
        "       const txt = this.add.text(x, y, emoji, { fontSize: '32px' });\n"
        "       txt.setOrigin(0.5);\n"
        "       this.physics.add.existing(txt, isStatic);\n"
        "       if (!isStatic) txt.body.setCollideWorldBounds(true);\n"
        "       return txt;\n"
        "   }\n"
        "   ```\n"
        "\n"
        "2. **SAFE SHOOTING** (Groups are safer):\n"
        "   - Create group: `this.bullets = this.physics.add.group();`\n"
        "   - Fire: \n"
        "     `const b = this.createEmoji(this.player.x, this.player.y, '🔥');`\n"
        "     `this.bullets.add(b);`\n"
        "     `b.body.setVelocity(vx, vy);`\n"
        "\n"
        "3. **SAFE COLLISION** (Check active status):\n"
        "   ```javascript\n"
        "   this.physics.add.collider(this.bullets, this.enemies, (bullet, enemy) => {\n"
        "       if (bullet.active && enemy.active) {\n"
        "           bullet.destroy();\n"
        "           enemy.destroy();\n"
        "           // Add score here\n"
        "       }\n"
        "   });\n"
        "   ```\n"
        "\n"
        "4. **SAFE UPDATE**:\n"
        "   - `update()` {\n"
        "       if (!this.player || !this.player.active) return;\n"
        "       // ... controls ...\n"
        "   }\n"
        "\n"
        "Requirements:\n"
        "- Use **Arrow Functions** `() =>` for all callbacks to fix scope.\n"
        "- NO external images. Use Emojis.\n"
        "- If making a Tank game: Player=🚜, Enemy=😈, Wall=🧱, Bullet=💥.\n"
        "- Implement basic AI for enemies (move towards player or random).\n"
        "Output ONLY the valid HTML code."
    )


@router.post("/generate")
async def generate_game_stream(req: GameRequest):
    if not call_ai_stream_async:
        return StreamingResponse(iter(["Error: AI Hub missing"]), status_code=500)

    prompt = build_game_architect_prompt(req.requirement)

    async def event_stream():
        full_raw_code = ""
        # 温度 0.1，让它严格照抄模板
        async for chunk in call_ai_stream_async("Output valid HTML only.", prompt, model="deepseek-ai/DeepSeek-V3",
                                    temperature=0.1):
            full_raw_code += chunk
            yield json.dumps({"type": "chunk", "content": chunk}) + "\n"

        clean_html = clean_code_block(full_raw_code)

        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            save_req = f"[GAME] {req.requirement}"
            c.execute("INSERT INTO apps (requirement, html, created_at) VALUES (?, ?, ?)",
                      (save_req, clean_html, time.time()))
            new_id = c.lastrowid
            conn.commit()
            conn.close()
            yield json.dumps({"type": "done", "id": new_id, "html": clean_html}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
