# backend/app/main.py
import asyncio
import uvicorn
from typing import Optional
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
from fastapi import Query
from .modules.system.monitor import router as system_router
from .modules.visitor_tracker.tracker import visitor_tracker_middleware, create_db_and_tables, router as visitor_router
from .modules.system.monitor import router as monitor_router
from .modules.visitor_tracker.tracker import router as tracker_router

load_dotenv()

# 设置全局 Pool Manager (core/ai_hub 用)
set_pool_manager(pool_manager)

# 🔥 新增：应用访客追踪中间件
app = FastAPI(title="SpiderFlow API")
app.middleware("http")(visitor_tracker_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    🔥 优化：快速启动，所有重型操作都异步进行
    前端可以立即连接，无需等待初始化完成
    """
    # 🔥 同步操作只做最少必要的：
    print("🚀 [System] FastAPI 服务启动完成，已准备好响应请求")
    
    # 异步启动所有重型服务，不阻塞
    async def init_services():
        try:
            # 创建访客数据库表（快速操作）
            create_db_and_tables()
            print("✅ [System] 数据库初始化完成")
            
            # 启动代理池管理器（后台服务）
            if pool_manager:
                pool_manager.start()
                print(f"✅ [System] 代理池引擎已加载 (ID: {id(pool_manager)})")
            
            # 启动节点扫描调度器
            if node_hunter:
                node_hunter.start_scheduler()
                print("✅ [System] 节点猎手调度器已启动")
            
            # 连接 NodeHunter 和 ProxyManager
            if pool_manager and node_hunter:
                print("🔗 [System] 连接 NodeHunter -> ProxyManager...")
                pool_manager.set_node_provider(node_hunter.get_alive_nodes)
                if pool_manager.node_provider:
                    print("✅ [System] 连接成功！ProxyManager 已就绪")
        except Exception as e:
            print(f"⚠️ [System] 初始化过程中出错: {e}")
    
    # 使用 asyncio.create_task 在后台执行所有初始化，不阻塞启动
    asyncio.create_task(init_services())


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


# ==========================================
# 🔥 诊断端点：检查 Supabase 环境变量配置
# ==========================================
@app.get("/api/debug/supabase")
async def debug_supabase_config():
    """
    诊断 Supabase 配置状态（不暴露敏感信息）
    用于排查线上环境变量问题
    """
    import os
    
    url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    anon_key = os.getenv("SUPABASE_KEY", "")
    
    # Azure 特有环境变量
    is_azure = bool(os.getenv("WEBSITE_SITE_NAME"))
    azure_env = os.getenv("WEBSITE_SITE_NAME", "N/A")
    
    return {
        "environment": "Azure" if is_azure else "Local",
        "azure_site_name": azure_env,
        "supabase_url": {
            "configured": bool(url),
            "preview": url[:40] + "..." if url else None
        },
        "supabase_service_role_key": {
            "configured": bool(service_key),
            "length": len(service_key) if service_key else 0
        },
        "supabase_key": {
            "configured": bool(anon_key),
            "length": len(anon_key) if anon_key else 0
        },
        "all_env_with_supa": [k for k in os.environ.keys() if 'SUPA' in k.upper()],
        "recommendation": "OK" if (url and (service_key or anon_key)) else "请在 Azure App Service > 配置 > 应用程序设置中添加 SUPABASE_URL 和 SUPABASE_KEY"
    }


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
# 🔥 新增：注册访客追踪路由
app.include_router(visitor_router)
app.include_router(monitor_router, prefix="/api/system", tags=["System"])
app.include_router(tracker_router, prefix="/api/visitor", tags=["Visitor"])

# ==========================================
# 🔥 新增：直接暴露 /api/nodes 端点给前端使用
# ==========================================
@app.get("/api/nodes")
async def api_get_nodes(
    limit: int = Query(50, ge=1, le=500),
    show_socks_http: Optional[bool] = Query(None),
    show_china_nodes: Optional[bool] = Query(None)
):
    """
    供前端直接调用的节点数据接口
    返回格式包含 mainland_score/overseas_score 等字段
    支持 socks/http 和中国节点显示开关
    """
    alive_nodes = node_hunter.get_alive_nodes()
    # 🔥 新增: 默认使用服务端状态
    if show_socks_http is None:
        show_socks_http = node_hunter.show_socks_http
    if show_china_nodes is None:
        show_china_nodes = node_hunter.show_china_nodes

    # 🔥 新增: 根据开关过滤 socks/http 节点
    if not show_socks_http:
        # 过滤掉 socks 和 http 协议的节点
        alive_nodes = [
            node for node in alive_nodes 
            if node.get('protocol', '').lower() not in ['socks5', 'socks', 'http', 'https']
        ]

    if not show_china_nodes:
        alive_nodes = [
            node for node in alive_nodes 
            if node.get('country', '').upper() != 'CN'
        ]
    
    # 按分数排序（优先大陆分数，其次海外分数）
    sorted_nodes = sorted(
        alive_nodes,
        key=lambda x: (
            -(x.get('mainland_score', 0) or 0),
            -(x.get('overseas_score', 0) or 0)
        )
    )
    
    # 🔥 新增: 如果显示 socks/http，将它们放在最前面
    if show_socks_http:
        socks_http_nodes = [
            node for node in sorted_nodes 
            if node.get('protocol', '').lower() in ['socks5', 'socks', 'http', 'https']
        ]
        other_nodes = [
            node for node in sorted_nodes 
            if node.get('protocol', '').lower() not in ['socks5', 'socks', 'http', 'https']
        ]
        sorted_nodes = socks_http_nodes + other_nodes
    
    # 限制返回数量
    limited_nodes = sorted_nodes[:limit]
    
    # 构造返回数据（兼容前端期望的格式：content 字段包含节点原始数据）
    import json
    from .modules.node_hunter.config_generator import generate_node_share_link
    
    result = []
    for node in limited_nodes:
        # 生成节点分享链接
        share_link = generate_node_share_link(node)
        
        # 构造节点内容（原始格式）
        node_content = {
            "protocol": node.get('protocol', 'unknown'),
            "host": node.get('host'),
            "port": node.get('port'),
            "country": node.get('country', 'UNK'),
            "name": node.get('name', f"{node.get('host')}:{node.get('port')}"),
            "ps": node.get('ps', node.get('name', f"{node.get('host')}:{node.get('port')}")),
            "server": node.get('server'),  # 如果有的话
            "method": node.get('method'),
            "password": node.get('password'),
            "obfs": node.get('obfs'),
            "obfs_param": node.get('obfs_param'),
            "protocol_param": node.get('protocol_param'),
            "remarks": node.get('remarks'),
            "group": node.get('group')
        }
        
        result.append({
            "id": node.get('id', f"{node.get('host')}:{node.get('port')}"),
            "protocol": node.get('protocol', 'unknown'),
            "host": node.get('host'),
            "port": node.get('port'),
            "country": node.get('country', 'UNK'),
            "name": node.get('name', f"{node.get('host')}:{node.get('port')}"),
            "link": share_link,  # 分享链接
            # 关键：content 字段用于前端解析
            "content": json.dumps(node_content, ensure_ascii=False),
            # 测试数据字段
            "speed": node.get('speed', 0),
            "delay": node.get('delay', 0),
            "latency": node.get('latency', node.get('delay', 0)),
            "is_free": node.get('is_free', False),
            # 双区域测速字段
            "mainland_score": node.get('mainland_score', 0),
            "mainland_latency": node.get('mainland_latency', 0),
            "overseas_score": node.get('overseas_score', 0),
            "overseas_latency": node.get('overseas_latency', 0),
            "alive": node.get('alive', False)
        })
    
    return result


# ==========================================
# 🔥 数据同步端点 - 直接调用 Supabase 上传
# ==========================================
@app.post("/api/sync")
async def sync_data_to_supabase():
    """
    触发数据同步到 Supabase 的端点
    用于前端 [同步数据] 按钮
    
    🔥 修复：不再依赖本地脚本，直接调用 supabase_helper
    这样在任何环境（本地/Azure/Vercel）都能正常工作
    """
    import os
    from datetime import datetime
    from .modules.node_hunter.supabase_helper import upload_to_supabase, get_supabase_credentials
    
    try:
        print("\n" + "="*70)
        print("📤 收到前端同步请求，开始同步数据到 Supabase...")
        print("="*70)
        
        # 1. 检查 Supabase 凭证
        url, key = get_supabase_credentials()
        if not url or not key:
            error_msg = "Supabase 凭证未配置！请检查环境变量 SUPABASE_URL 和 SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY"
            print(f"❌ {error_msg}")
            print(f"   SUPABASE_URL: {'已设置' if url else '❌ 未设置'}")
            print(f"   SUPABASE_KEY: {'已设置' if key else '❌ 未设置'}")
            return {
                "success": False,
                "message": error_msg,
                "timestamp": datetime.now().isoformat()
            }
        
        # 2. 获取活跃节点
        alive_nodes = node_hunter.get_alive_nodes() if node_hunter else []
        
        if not alive_nodes:
            msg = "没有活跃节点可同步，请先执行节点检测"
            print(f"⚠️ {msg}")
            return {
                "success": False,
                "message": msg,
                "node_count": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        # 3. 去重处理
        seen = {}
        for node in alive_nodes:
            key_id = f"{node.get('host')}:{node.get('port')}"
            if key_id not in seen:
                seen[key_id] = node
        
        unique_nodes = list(seen.values())
        print(f"📊 准备同步: {len(unique_nodes)} 个节点 (去重后)")
        
        # 4. 执行上传 (返回 tuple: (success, detail))
        result = await upload_to_supabase(unique_nodes)
        
        # 兼容旧版返回值
        if isinstance(result, tuple):
            success, detail = result
        else:
            success, detail = result, ""
        
        print("="*70)
        
        if success:
            msg = f"同步成功！已上传 {detail} 个节点到 Supabase"
            print(f"✅ {msg}")
            return {
                "success": True,
                "message": msg,
                "node_count": detail if isinstance(detail, int) else len(unique_nodes),
                "timestamp": datetime.now().isoformat()
            }
        else:
            msg = f"同步失败: {detail}"
            print(f"❌ {msg}")
            return {
                "success": False,
                "message": msg,
                "node_count": len(unique_nodes),
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        import traceback
        error_msg = f"同步异常: {type(e).__name__}: {str(e)}"
        print(f"❌ {error_msg}")
        print(traceback.format_exc())
        return {
            "success": False,
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }
