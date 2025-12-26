# backend/app/modules/game/game_engine.py
import re
import json
import sqlite3
import time
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

try:
    from ...core.ai_hub import call_ai_stream_async
except ImportError:
    call_ai_stream_async = None

router = APIRouter(prefix="/api/game", tags=["game"])


class GameRequest(BaseModel):
    requirement: str
    game_type: str = "2d"  # 🔥 新增：游戏类型参数


DB_FILE = "apps_storage.db"


def clean_code_block(text):
    if not text:
        return ""
    # 匹配 HTML 代码块
    pattern = r"```html(.*?)```"
    match = re.search(pattern, text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()

    # 匹配 JavaScript 代码块（针对 Three.js）
    pattern_js = r"```javascript(.*?)```"
    match_js = re.search(pattern_js, text, flags=re.DOTALL)
    if match_js:
        js_code = match_js.group(1).strip()
        # 将 JS 包装成完整的 HTML
        return wrap_js_to_html(js_code)

    return text.replace("```", "").strip()


def wrap_js_to_html(js_code):
    """将纯 JavaScript 代码包装成完整的 HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D Game</title>
    <style>
        body {{ 
            margin: 0; 
            padding: 0; 
            overflow: hidden; 
            background: #0a0a0a;
            color: white;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        #game-container {{
            width: 100vw;
            height: 100vh;
        }}
        #ui {{
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 100;
            background: rgba(0,0,0,0.5);
            padding: 10px;
            border-radius: 5px;
            font-size: 14px;
        }}
        #controls {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.5);
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
        }}
        .key {{ 
            display: inline-block; 
            background: rgba(255,255,255,0.1); 
            padding: 2px 6px; 
            margin: 0 2px; 
            border-radius: 3px; 
            border: 1px solid rgba(255,255,255,0.2);
        }}
    </style>
</head>
<body>
    <div id="game-container"></div>
    <div id="ui">
        <div>🎮 <span id="score">Score: 0</span></div>
        <div>❤️ <span id="health">Health: 100</span></div>
    </div>
    <div id="controls">
        <div>WASD: 移动 | 空格: 跳跃/射击 | 鼠标: 视角</div>
        <div>R: 重新开始 | ESC: 暂停</div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // Three.js 游戏主逻辑
        {js_code}

        // 性能优化：限制帧率
        let lastTime = 0;
        const targetFPS = 60;
        const frameInterval = 1000 / targetFPS;

        function optimizedAnimate(time) {{
            requestAnimationFrame(optimizedAnimate);

            const deltaTime = time - lastTime;
            if (deltaTime < frameInterval) return;

            lastTime = time - (deltaTime % frameInterval);
            // 更新游戏逻辑
            if (window.updateGame) {{
                window.updateGame(deltaTime / 1000);
            }}
            // 渲染场景
            if (window.renderScene) {{
                window.renderScene();
            }}
        }}
        requestAnimationFrame(optimizedAnimate);
    </script>
</body>
</html>'''


# 🔥 2D 游戏提示词（优化版）
def build_2d_game_prompt(requirement):
    return (
        f"你是一个高级 2D 游戏架构师。使用 Phaser 3 创建一个单文件 HTML 游戏：'{requirement}'。\n\n"
        "技术要求：\n"
        "1. 使用 Phaser 3.60.0 CDN：<script src='https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js'></script>\n"
        "2. 使用类继承结构：class GameScene extends Phaser.Scene\n\n"
        "安全编码规范（必须遵守）：\n"
        "1. 使用箭头函数避免作用域问题\n"
        "2. 使用 physics.add.existing() 而不是 physics.add.text()\n"
        "3. 所有碰撞检测都要检查 active 状态\n"
        "4. 更新函数中检查对象是否存在和激活\n"
        "5. 使用 emoji 而不是外部图片资源\n\n"
        "性能优化：\n"
        "1. 使用 this.time.addEvent 替代 setInterval\n"
        "2. 批量处理敌人和子弹\n"
        "3. 及时销毁不需要的对象\n\n"
        "游戏设计：\n"
        "1. 玩家控制：WASD 或方向键移动，空格键交互\n"
        "2. 计分系统：显示分数\n"
        "3. 生命值：显示生命条或数值\n"
        "4. 游戏状态：暂停、重新开始功能\n"
        "5. 敌人 AI：简单的追踪或巡逻逻辑\n\n"
        "输出要求：\n"
        "只输出完整的 HTML 代码，包含所有必要的样式和 JavaScript。\n"
        "确保代码可以在低配置服务器（1GB RAM）上流畅运行。"
    )


# 🔥 3D 游戏提示词（Three.js 轻量版）
# 更新 Three.js 版本到 r152（支持 mergeBufferGeometries）
def build_3d_game_prompt(requirement):
    return (
        f"你是一个高级 3D 游戏架构师。使用 Three.js 创建一个轻量级单文件 HTML 游戏：'{requirement}'。\n\n"
        "⚠️ 重要注意事项：\n"
        "1. 确保所有 JavaScript 语法正确，避免使用 'negative' 这样的词代替负号，使用 '-' 表示负数\n"
        "2. 所有代码必须语法正确，没有拼写错误\n"
        "3. 使用正确的 Three.js API 调用\n"
        "4. 确保所有括号、引号正确匹配\n\n"
        "技术栈：\n"
        "1. 使用 Three.js 最新版 CDN\n"
        "2. 使用简单的几何体减少性能消耗\n"
        "3. 实现基本的游戏循环和交互\n\n"
        "输出要求：\n"
        "输出完整的 HTML 文件，包含所有必要的 CSS 和 JavaScript。\n"
        "确保代码语法 100% 正确，可以直接运行。"
    )

def wrap_js_to_html(js_code):
    """将纯 JavaScript 代码包装成完整的 HTML（修复版本）"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D Game</title>
    <style>
        body {{ 
            margin: 0; 
            padding: 0; 
            overflow: hidden; 
            background: #0a0a0a;
            color: white;
        }}
        #game-container {{
            width: 100vw;
            height: 100vh;
        }}
        #ui {{
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 100;
            background: rgba(0,0,0,0.5);
            padding: 10px;
            border-radius: 5px;
            font-family: Arial, sans-serif;
        }}
        #controls {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.5);
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div id="game-container"></div>
    <div id="ui">
        <div>🎮 <span id="score">Score: 0</span></div>
        <div>❤️ <span id="health">Health: 100</span></div>
    </div>
    <div id="controls">
        <div>WASD: Move | Space: Jump/Shoot | Mouse: Look</div>
    </div>

    <!-- 使用新版本的 Three.js 并包含 BufferGeometryUtils -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.152.2/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.152.2/examples/jsm/utils/BufferGeometryUtils.js"></script>
    <script>
        // 简单的游戏初始化检查
        function checkThreeJS() {{
            if (!window.THREE) {{
                document.getElementById('game-container').innerHTML = 
                    '<div style="color:white;padding:20px;">Failed to load Three.js</div>';
                return false;
            }}
            return true;
        }}

        // 游戏主逻辑
        if (checkThreeJS()) {{
            {js_code}
        }}
    </script>
</body>
</html>'''


@router.post("/generate")
async def generate_game_stream(req: GameRequest):
    if not call_ai_stream_async:
        return StreamingResponse(iter(["Error: AI Hub missing"]), status_code=500)

    # 🔥 根据游戏类型选择不同的提示词
    if req.game_type == "3d":
        prompt = build_3d_game_prompt(req.requirement)
    else:
        prompt = build_2d_game_prompt(req.requirement)

    def validate_and_fix_threejs_code(html_code):
        """验证并修复 Three.js 代码中的常见错误"""
        if not html_code:
            return html_code

        # 修复 "negative" 语法错误
        html_code = re.sub(r'negative\s+(\d+)', r'-\1', html_code)

        # 修复常见的语法错误
        common_fixes = [
            (r'new THREE\.Vector3\(([^)]+)\)', lambda m: f'new THREE.Vector3({m.group(1)})'),
            # 确保数字前面是运算符或括号
            (r'(?<![+\-*/(\[])\s*(-?\d+\.?\d*)', lambda m: f' {m.group(1)}'),  # 保留负数的正确格式
        ]

        for pattern, replacement in common_fixes:
            html_code = re.sub(pattern, replacement, html_code)

        # 检查是否有明显的语法错误
        error_check_lines = html_code.split('\n')
        for i, line in enumerate(error_check_lines):
            # 检查未闭合的括号
            open_paren = line.count('(')
            close_paren = line.count(')')
            if open_paren != close_paren:
                print(f"警告：第{i + 1}行括号不匹配：{line}")

            # 检查未闭合的引号
            if line.count("'") % 2 != 0 or line.count('"') % 2 != 0:
                print(f"警告：第{i + 1}行引号不匹配：{line}")

        return html_code

    async def event_stream():
        full_raw_code = ""
        # 🔥 根据游戏类型调整温度参数
        temperature = 0.1 if req.game_type == "2d" else 0.2  # 3D 游戏需要更多创造性
        clean_code = clean_code_block(full_raw_code)

        # 🔥 验证并修复代码
        if req.game_type == "3d":
            clean_code = validate_and_fix_threejs_code(clean_code)

        async for chunk in call_ai_stream_async(
                f"Output {'valid HTML' if req.game_type == '2d' else 'JavaScript'} code only.",
                prompt,
                model="deepseek-ai/DeepSeek-V3",
                temperature=temperature
        ):
            full_raw_code += chunk
            yield json.dumps({"type": "chunk", "content": chunk}) + "\n"

        # 🔥 处理生成的代码
        clean_code = clean_code_block(full_raw_code)

        # 如果是 3D 游戏且返回的是纯 JS，包装成 HTML
        if req.game_type == "3d" and not clean_code.strip().startswith("<!DOCTYPE"):
            clean_code = wrap_js_to_html(clean_code)

        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()

            # 🔥 检查是否需要创建 game_type 字段
            try:
                c.execute("SELECT game_type FROM apps LIMIT 1")
            except sqlite3.OperationalError:
                # 如果 game_type 字段不存在，添加它
                c.execute("ALTER TABLE apps ADD COLUMN game_type TEXT DEFAULT '2d'")

            save_req = f"[GAME] {req.requirement}"
            c.execute(
                "INSERT INTO apps (requirement, html, game_type, created_at) VALUES (?, ?, ?, ?)",
                (save_req, clean_code, req.game_type, time.time())
            )
            new_id = c.lastrowid
            conn.commit()
            conn.close()

            yield json.dumps({
                "type": "done",
                "id": new_id,
                "html": clean_code,
                "game_type": req.game_type  # 🔥 返回游戏类型
            }) + "\n"

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


# 🔥 新增：3D 游戏特定 API（可选）
@router.get("/threejs/template")
async def get_threejs_template():
    """获取一个基础的 Three.js 游戏模板"""
    basic_template = """
// 基础 Three.js 游戏模板
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // 性能优化
document.getElementById('game-container').appendChild(renderer.domElement);

// 光源
const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
scene.add(ambientLight);
const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
directionalLight.position.set(10, 20, 5);
scene.add(directionalLight);

// 地面
const groundGeometry = new THREE.PlaneGeometry(100, 100);
const groundMaterial = new THREE.MeshStandardMaterial({ color: 0x3a7c3a });
const ground = new THREE.Mesh(groundGeometry, groundMaterial);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// 玩家（立方体）
const playerGeometry = new THREE.BoxGeometry(1, 2, 1);
const playerMaterial = new THREE.MeshStandardMaterial({ color: 0x4169e1 });
const player = new THREE.Mesh(playerGeometry, playerMaterial);
player.position.y = 1;
scene.add(player);

// 敌人数组
const enemies = [];

// 创建敌人
function createEnemy(x, z) {
    const geometry = new THREE.SphereGeometry(0.8, 16, 16);
    const material = new THREE.MeshStandardMaterial({ color: 0xff4444 });
    const enemy = new THREE.Mesh(geometry, material);
    enemy.position.set(x, 1, z);
    scene.add(enemy);
    enemies.push(enemy);
    return enemy;
}

// 创建一些敌人
createEnemy(5, 5);
createEnemy(-5, 5);
createEnemy(5, -5);

// 相机跟随玩家
camera.position.set(0, 5, 10);
camera.lookAt(player.position);

// 玩家移动速度
const playerSpeed = 5;
const keys = {};

// 键盘控制
window.addEventListener('keydown', (e) => keys[e.code] = true);
window.addEventListener('keyup', (e) => keys[e.code] = false);

// 游戏状态
let score = 0;
let gameRunning = true;

// 更新游戏逻辑
window.updateGame = function(deltaTime) {
    if (!gameRunning) return;

    // 玩家移动
    if (keys['KeyW'] || keys['ArrowUp']) player.position.z -= playerSpeed * deltaTime;
    if (keys['KeyS'] || keys['ArrowDown']) player.position.z += playerSpeed * deltaTime;
    if (keys['KeyA'] || keys['ArrowLeft']) player.position.x -= playerSpeed * deltaTime;
    if (keys['KeyD'] || keys['ArrowRight']) player.position.x += playerSpeed * deltaTime;

    // 敌人 AI：简单追踪
    enemies.forEach(enemy => {
        const dx = player.position.x - enemy.position.x;
        const dz = player.position.z - enemy.position.z;
        const distance = Math.sqrt(dx * dx + dz * dz);

        if (distance > 0.5) {
            enemy.position.x += (dx / distance) * 2 * deltaTime;
            enemy.position.z += (dz / distance) * 2 * deltaTime;
        }

        // 碰撞检测
        if (distance < 1.5) {
            // 处理碰撞
        }
    });

    // 更新 UI
    document.getElementById('score').textContent = `Score: ${score}`;
};

// 渲染场景
window.renderScene = function() {
    renderer.render(scene, camera);
};

// 窗口大小调整
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
"""

    return {
        "template": wrap_js_to_html(basic_template),
        "note": "轻量级 Three.js 游戏模板，适合低配置服务器"
    }