# backend/app/modules/crawler/crawler_engine.py
import asyncio
import json
import os
import time
import pandas as pd
from fastapi import APIRouter, Response, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List

# 引入独立的爬虫实现
from .crawlers.text_crawler import GeneralTextCrawler
from .crawlers.video_crawler import BilibiliCrawler, YouTubeCrawler, UniversalVideoCrawler
from .proxy import router as proxy_router
# 🔥 恢复：使用普通版分析器
from .battle_analyzer import analyze_comments_for_battle 

router = APIRouter(tags=["crawler"])
router.include_router(proxy_router)

pool_manager = None
try:
    from ..proxy.proxy_engine import manager as pm
    pool_manager = pm
except ImportError:
    pass

node_hunter = None
try:
    from ..node_hunter.node_hunter import hunter as nh
    node_hunter = nh
except ImportError:
    pass

class CrawlRequest(BaseModel):
    url: str
    mode: str = "auto"
    network_type: str = "auto"

class AnalyzeCommentsRequest(BaseModel):
    post_title: str
    comments: List[dict]

VIDEO_SITES = [
    "missav", "missav.ws", "jable", "pornhub", "xvideos",
    "youtube", "youtu.be", "bilibili", "spankbang", "ddh", "jav", "hqporner"
]

def is_video_site(url: str) -> bool:
    return any(site in url.lower() for site in VIDEO_SITES)

class CrawlerFactory:
    @staticmethod
    def get_crawler(url: str, mode: str, manager=None):
        if "bilibili.com" in url:
            return BilibiliCrawler(pool_manager=manager)
        elif "youtube.com" in url or "youtu.be" in url:
            return YouTubeCrawler(pool_manager=manager)
        elif is_video_site(url) or mode == "media":
            return UniversalVideoCrawler(pool_manager=manager)
        return GeneralTextCrawler(pool_manager=manager)

async def smart_router(url: str, mode: str, network_type: str):
    if pool_manager and pool_manager.node_provider is None:
        if node_hunter:
            pool_manager.set_node_provider(node_hunter.get_alive_nodes)
    
    is_linked = pool_manager and pool_manager.node_provider is not None
    pm_status = "✅" if is_linked else "❌"
    node_count = 0
    if is_linked:
        try:
            nodes = pool_manager.node_provider()
            node_count = len(nodes) if nodes else 0
        except: pass
    
    status_msg = f"[Pool:{pm_status}(Nodes:{node_count})]"
    yield json.dumps({"step": "init", "message": f"任务启动: {url} [Mode: {mode}] [Net: {network_type}] {status_msg}"}) + "\n"
    
    crawler = CrawlerFactory.get_crawler(url, mode, manager=pool_manager)

    try:
        df = pd.DataFrame()
        async for chunk in crawler.crawl(url, network_type=network_type):
            if isinstance(chunk, pd.DataFrame):
                df = pd.concat([df, chunk], ignore_index=True)
            else:
                yield chunk

        if not df.empty:
            json_data = df.to_json(orient='records', force_ascii=False)
            yield json.dumps({
                "step": "done", 
                "data": json.loads(json_data),
                "columns": df.columns.tolist()
            }) + "\n"
        else:
            yield json.dumps({"step": "error", "message": "未能提取到有效数据"}) + "\n"

    except Exception as e:
        yield json.dumps({"step": "error", "message": f"系统错误: {str(e)}"}) + "\n"

@router.post("/api/crawl")
async def start_crawl(request: CrawlRequest):
    return StreamingResponse(smart_router(request.url, request.mode, request.network_type), media_type="application/x-ndjson")

# 🔥 恢复：使用普通、一次性返回的端点
@router.post("/api/crawl/analyze_comments")
async def analyze_comments_endpoint(request: AnalyzeCommentsRequest):
    try:
        battle_data = await analyze_comments_for_battle(request.post_title, request.comments)
        return battle_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/download/{filename}")
async def download_file(filename: str):
    filepath = os.path.abspath(filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, filename=filename)
    return Response("File not found", status_code=404)
