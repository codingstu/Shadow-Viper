# backend/app/main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 引入各个模块的路由
from .modules.alchemy.alchemy_engine import router as alchemy_router
from .modules.proxy.proxy_engine import router as proxy_router, manager as pool_manager
from .modules.node_hunter.node_hunter import router as node_router, hunter as node_hunter
from .modules.cyber_range.cyber_range import router as cyber_router
from .modules.eagle_eye.eagle_eye import router as eagle_router
from .modules.crawler.crawler_engine import router as crawler_router
from .modules.data_refinery.data_refinery import router as refinery_router
from .modules.generator.generator_engine import router as generator_router
from .modules.game.game_engine import router as game_router
from .modules.shodan.shodan_engine import router as shodan_router
from .core.ai_hub import set_pool_manager
from fastapi.responses import HTMLResponse
from .modules.system.monitor import router as system_router

load_dotenv()

# 设置全局 Pool Manager (core/ai_hub 用)
set_pool_manager(pool_manager)

app = FastAPI(title="SpiderFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    # 1. 启动代理池管理器
    if pool_manager:
        pool_manager.start()
        print(f"🚀 [System] 代理池引擎已加载 (ID: {id(pool_manager)})")
    else:
        print("⚠️ [System] 代理池管理器未加载")

    # 2. 启动 Shadow Matrix 扫描
    if node_hunter:
        node_hunter.start_scheduler()
    else:
        print("⚠️ [System] Shadow Matrix 未加载")

    # 🔥 核心修复：在启动时强制连接 NodeHunter 和 ProxyManager 🔥🔥🔥
    if pool_manager and node_hunter:
        print("🔗 [System] 正在连接 NodeHunter -> ProxyManager...")
        # 🔥 恢复：传递所有节点，让爬虫自己去过滤
        pool_manager.set_node_provider(node_hunter.get_alive_nodes)

        # 验证连接是否成功
        if pool_manager.node_provider:
            print("✅ [System] 连接成功！ProxyManager 现在可以获取所有猎手节点。")
        else:
            print("❌ [System] 连接失败！NodeProvider 仍为 None。")


# 伪装根目录
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
        <head><title>Site Maintenance</title></head>
        <body>
            <h1>System Update</h1>
            <p>The service is currently undergoing maintenance.</p>
        </body>
    </html>
    """


@app.get("/api/status")
async def read_status():
    return {"message": "SpiderFlow API", "status": "running"}


app.include_router(proxy_router)
app.include_router(node_router)
app.include_router(crawler_router)
app.include_router(alchemy_router)
app.include_router(cyber_router)
app.include_router(eagle_router)
app.include_router(refinery_router)
app.include_router(generator_router)
app.include_router(game_router)
app.include_router(shodan_router)
app.include_router(system_router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
