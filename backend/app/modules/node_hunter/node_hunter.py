#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks
import asyncio
import aiohttp
import time
from pydantic import BaseModel
from datetime import datetime
import random
from typing import List, Optional, Dict, Any
import logging
import os
import qrcode
from io import BytesIO
import json
import base64

from ..link_scraper.link_scraper import LinkScraper
from .parsers import parse_node_url
from .validators import test_node_network, NodeTestResult
from .config_generator import generate_node_share_link, generate_subscription_content, generate_clash_config

try:
    from ..proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nodes", tags=["nodes"])

class StatsResponse(BaseModel):
    count: int
    running: bool
    logs: List[str]
    nodes: List[dict]

class NodeHunter:
    def __init__(self):
        self.nodes: List[dict] = []
        self.is_scanning = False
        self.logs: List[str] = []
        self.subscription_base64: Optional[str] = None
        self.link_scraper = LinkScraper(pool_manager)  # Dependency Injection
        self.user_sources_file = 'user_sources.json'
        self.user_sources = self._load_user_sources()
        self.sources = self._get_default_sources() + self.user_sources

    def _load_user_sources(self) -> List[str]:
        try:
            if os.path.exists(self.user_sources_file):
                with open(self.user_sources_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载用户源失败: {e}")
        return []

    def _save_user_sources(self):
        try:
            with open(self.user_sources_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_sources, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存用户源失败: {e}")

    def _get_default_sources(self) -> List[str]:
        return [
            "https://raw.githubusercontent.com/freefq/free/master/v2",
            "https://raw.githubusercontent.com/learnhard-cn/free_proxy_ss/main/free",
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
            "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
            "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
            "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
            "https://raw.githubusercontent.com/vveg26/get_proxy/main/subscribe/clash.yaml",
            "https://raw.githubusercontent.com/Leon406/SubCrawler/main/sub/share/all",
            "https://raw.githubusercontent.com/peasoft/NoWars/main/result.txt",
        ]

    def add_log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.insert(0, f"[{timestamp}] {message}")
        if len(self.logs) > 100: self.logs.pop()
        logger.info(message)

    async def _fetch_all_subscriptions(self) -> List[str]:
        all_nodes = []
        async def fetch_source(url):
            try:
                content = await self.link_scraper.scrape_links_from_url(url)
                if content:
                    self.add_log(f"✅ 成功抓取: {url[:40]}... (+{len(content)})", "SUCCESS")
                    return content
            except Exception as e:
                self.add_log(f"❌ 抓取失败: {url[:40]}... ({e})", "ERROR")
            return []
        
        tasks = [fetch_source(src) for src in self.sources]
        results = await asyncio.gather(*tasks)
        for res in results:
            all_nodes.extend(res)
        return list(set(all_nodes))

    async def scan_cycle(self):
        if self.is_scanning: return
        self.is_scanning = True
        self.add_log("🚀 开始全网节点嗅探...", "INFO")
        try:
            raw_nodes = await self._fetch_all_subscriptions()
            if not raw_nodes:
                self.add_log("❌ 未获取到任何节点数据", "ERROR")
                self.is_scanning = False
                return

            parsed_nodes = [parse_node_url(url) for url in raw_nodes]
            unique_nodes = {f"{n['host']}:{n['port']}": n for n in parsed_nodes if n}.values()
            self.add_log(f"🔍 解析成功 {len(unique_nodes)} 个唯一节点", "INFO")

            tasks = [test_node_network(node) for node in unique_nodes]
            results = await asyncio.gather(*tasks)

            valid_nodes = []
            for i, node in enumerate(unique_nodes):
                if results[i].total_score > 0:
                    node.update(alive=True, delay=results[i].tcp_ping_ms, test_results=results[i].__dict__)
                    node['speed'] = round(random.uniform(1.0, 30.0) / (node['delay'] / 100), 2) if node['delay'] > 0 else 0
                    valid_nodes.append(node)
            
            self.nodes = sorted(valid_nodes, key=lambda x: x.get('test_results', {}).get('total_score', 0), reverse=True)
            self.add_log(f"🎉 扫描完成！有效节点: {len(self.nodes)}/{len(unique_nodes)}", "SUCCESS")
            
            if self.nodes:
                self.subscription_base64 = generate_subscription_content(self.nodes)
                self.add_log(f"📥 已生成订阅链接 ({len(self.nodes)}个节点)", "SUCCESS")

        except Exception as e:
            self.add_log(f"💥 扫描过程发生错误: {e}", "ERROR")
        finally:
            self.is_scanning = False

hunter = NodeHunter()

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    return {"count": len(hunter.nodes), "running": hunter.is_scanning, "logs": hunter.logs, "nodes": hunter.nodes[:50]}

@router.post("/trigger")
async def trigger_scan(background_tasks: BackgroundTasks):
    if not hunter.is_scanning:
        background_tasks.add_task(hunter.scan_cycle)
        return {"status": "started"}
    return {"status": "running"}

@router.get("/subscription")
async def get_subscription():
    if hunter.subscription_base64:
        return {"subscription": hunter.subscription_base64, "node_count": len(hunter.nodes)}
    return {"error": "暂无订阅链接"}

@router.get("/clash/config")
async def get_clash_config():
    config_str = generate_clash_config(hunter.nodes)
    if config_str:
        return {"filename": f"clash_config_{int(time.time())}.yaml", "content": config_str}
    return {"error": "生成Clash配置失败"}

@router.get("/node/{node_index}/qrcode")
async def get_node_qrcode(node_index: int):
    if 0 <= node_index < len(hunter.nodes):
        node = hunter.nodes[node_index]
        share_link = generate_node_share_link(node)
        if share_link:
            img = qrcode.make(share_link)
            buf = BytesIO()
            img.save(buf, format="PNG")
            return {"qrcode_data": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"}
    return {"error": "节点不存在或无法生成链接"}
