# backend/app/modules/crawler/crawler_engine.py
import asyncio
import json
import os
import time
import pandas as pd
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

# 引入独立的爬虫实现和代理流
from .crawlers.text_crawler import GeneralTextCrawler
from .crawlers.video_crawler import BilibiliCrawler, YouTubeCrawler, UniversalVideoCrawler
from .proxy import router as proxy_router

router = APIRouter(tags=["crawler"])

# 将代理流路由包含进来
router.include_router(proxy_router)

class CrawlRequest(BaseModel):
    url: str
    mode: str = "auto"
    network_type: str = "proxy" # 🔥 新增：proxy(自动/代理池), node(仅节点), direct(仅直连)

VIDEO_SITES = [
    "missav", "missav.ws", "jable", "pornhub", "xvideos",
    "youtube", "youtu.be", "bilibili", "spankbang", "ddh", "jav", "hqporner"
]

def is_video_site(url: str) -> bool:
    return any(site in url.lower() for site in VIDEO_SITES)

class CrawlerFactory:
    @staticmethod
    def get_crawler(url: str, mode: str):
        if "bilibili.com" in url:
            return BilibiliCrawler()
        elif "youtube.com" in url or "youtu.be" in url:
            return YouTubeCrawler()
        elif is_video_site(url) or mode == "media":
            return UniversalVideoCrawler()
        return GeneralTextCrawler()

async def smart_router(url: str, mode: str, network_type: str):
    yield json.dumps({"step": "init", "message": f"任务启动: {url} [Mode: {mode}] [Net: {network_type}]"}) + "\n"
    await asyncio.sleep(0.5)

    crawler = CrawlerFactory.get_crawler(url, mode)

    try:
        df = pd.DataFrame()
        # 🔥 将 network_type 传递给 crawl 方法
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
    # 🔥 传递 network_type
    return StreamingResponse(smart_router(request.url, request.mode, request.network_type), media_type="application/x-ndjson")

@router.get("/download/{filename}")
async def download_file(filename: str):
    filepath = os.path.abspath(filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, filename=filename)
    return Response("File not found", status_code=404)
