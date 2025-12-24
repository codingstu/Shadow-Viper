# backend/app/main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 引入各个模块的路由 (使用相对导入)
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

load_dotenv()

# 🔥 核心修复：移除 NodeHunter 和 ProxyManager 的直接连接
# pool_manager.set_node_provider(node_hunter.get_alive_nodes)
set_pool_manager(pool_manager)

app = FastAPI(title="SpiderFlow API")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lifespan 事件处理
@app.on_event("startup")
async def startup_event():
    # 启动代理池管理器
    if pool_manager:
        # pool_manager.start()  # 禁用自动启动
        print("🚀 [System] 代理池引擎已加载 (手动模式)")
    else:
        print("⚠️ [System] 代理池管理器未加载")

@app.get("/")
def read_root():
    return {"message": "SpiderFlow API", "status": "running"}

# ==================== 路由注册 ====================
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
