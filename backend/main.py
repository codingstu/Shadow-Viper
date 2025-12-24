# backend/main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 引入各个模块的路由
from alchemy_engine import router as alchemy_router
from proxy_engine import router as proxy_router
from node_hunter import router as node_router
from cyber_range import router as cyber_router
from eagle_eye import router as eagle_router
from crawler_engine import router as crawler_router  # 🔥 新增模块
from proxy_engine import manager as pool_manager  # 🔥 引入管理器
from data_refinery import router as refinery_router
from generator_engine import router as generator_router
from game_engine import router as game_router # 🔥 新增

load_dotenv()

app = FastAPI(title="Cyber Range API")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔥🔥🔥 关键：启动时激活代理池自动巡检 🔥🔥🔥
@app.on_event("startup")
# async def startup_event():
    # pool_manager.start()
    # print("🚀 [System] 代理池引擎已独立启动 (自动维护模式)")

@app.get("/")
def read_root():
    return {"message": "Cyber Range API", "status": "running"}

# ==================== 路由注册 ====================

# 1. 代理池管理
app.include_router(proxy_router)

# 2. 节点猎手 (V2Ray/Clash)
app.include_router(node_router)

# 3. 爬虫引擎 (极速/深度/视频流)
app.include_router(crawler_router)

# 4. 炼金工坊 (数据清洗)
app.include_router(alchemy_router)

# 5. 网络靶场 (模拟训练)
app.include_router(cyber_router)

# 6. Eagle Eye (资产审计)
app.include_router(eagle_router)

# 7. DataRefinery (数据炼油厂)
app.include_router(refinery_router)

app.include_router(generator_router)

app.include_router(game_router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)