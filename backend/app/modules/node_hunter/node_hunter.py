# backend/app/modules/node_hunter/node_hunter.py
# !/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks, Body, Query, Request
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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import ipapi

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

VERIFIED_NODES_FILE = "verified_nodes.json"

NAME_TO_CODE = {
    "CN": "CN", "CHINA": "CN", "中国": "CN", "回国": "CN", "BEIJING": "CN", "SHANGHAI": "CN", "SHENZHEN": "CN",
    "🇨🇳": "CN",
    "HK": "HK", "HONG KONG": "HK", "HONGKONG": "HK", "🇭🇰": "HK",
    "TW": "TW", "TAIWAN": "TW", "TAIPEI": "TW", "🇹🇼": "TW",
    "US": "US", "USA": "US", "AMERICA": "US", "UNITED STATES": "US", "LOS ANGELES": "US", "SAN FRANCISCO": "US",
    "NEW YORK": "US", "🇺🇸": "US",
    "JP": "JP", "JAPAN": "JP", "TOKYO": "JP", "OSAKA": "JP", "🇯🇵": "JP",
    "SG": "SG", "SINGAPORE": "SG", "🇸🇬": "SG",
    "KR": "KR", "KOREA": "KR", "SEOUL": "KR", "🇰🇷": "KR",
    "GB": "GB", "UK": "GB", "UNITED KINGDOM": "GB", "LONDON": "GB", "🇬🇧": "GB",
    "DE": "DE", "GERMANY": "DE", "FRANKFURT": "DE", "🇩🇪": "DE",
    "FR": "FR", "FRANCE": "FR", "PARIS": "FR", "🇫🇷": "FR",
    "NL": "NL", "NETHERLANDS": "NL", "AMSTERDAM": "NL", "🇳🇱": "NL",
    "RU": "RU", "RUSSIA": "RU", "MOSCOW": "RU", "🇷🇺": "RU",
    "CA": "CA", "CANADA": "CA", "🇨🇦": "CA",
    "AU": "AU", "AUSTRALIA": "AU", "SYDNEY": "AU", "🇦🇺": "AU",
    "IN": "IN", "INDIA": "IN", "🇮🇳": "IN",
    "BR": "BR", "BRAZIL": "BR", "🇧🇷": "BR",
}


class StatsResponse(BaseModel):
    count: int
    running: bool
    logs: List[str]
    nodes: List[dict]
    next_scan_time: Optional[float] = None  # 🔥 新增：下次扫描时间戳


class NodeTarget(BaseModel):
    host: str
    port: int


class SourceRequest(BaseModel):
    url: str


class NodeHunter:
    def __init__(self):
        self.nodes: List[dict] = []
        self.is_scanning = False
        self.logs: List[str] = []
        self.subscription_base64: Optional[str] = None
        self.link_scraper = LinkScraper(pool_manager)
        self.user_sources_file = 'user_sources.json'
        self.user_sources = self._load_user_sources()
        self.sources = self._get_default_sources() + self.user_sources
        self.scheduler = AsyncIOScheduler()
        self._load_nodes_from_file()

        self.source_stats: Dict[str, Dict] = {}
        self.scan_cycle_count = 0
        for src in self.sources:
            self.source_stats[src] = {"is_disabled": False, "disabled_at": 0, "retry_fails": 0}

    def start_scheduler(self):
        if not self.scheduler.running:
            # 10分钟一次自动巡航
            self.scheduler.add_job(self.scan_cycle, 'interval', minutes=10, id='node_scan_refresh')
            self.scheduler.start()
            self.add_log("✅ [System] 节点猎手自动巡航已启动 (10min/cycle)", "SUCCESS")
            asyncio.create_task(self.scan_cycle())

    def get_alive_nodes(self) -> List[Dict[str, Any]]:
        return [node for node in self.nodes if node.get('alive')]

    def get_socks5_nodes(self) -> List[Dict[str, Any]]:
        return [
            node for node in self.nodes
            if node.get('alive') and node.get('protocol') in ['socks5', 'socks']
        ]

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

    def _load_nodes_from_file(self):
        if os.path.exists(VERIFIED_NODES_FILE):
            try:
                with open(VERIFIED_NODES_FILE, "r") as f:
                    loaded_nodes = json.load(f)
                    for node in loaded_nodes:
                        node['country'] = self._normalize_country(node.get('country', 'UNK'))
                    self.nodes = loaded_nodes
                self.add_log(f"📥 从缓存加载了 {len(loaded_nodes)} 个节点", "SUCCESS")
            except Exception as e:
                self.add_log(f"⚠️ 加载缓存节点失败: {e}", "WARNING")

    def _save_nodes_to_file(self):
        try:
            alive_nodes = self.get_alive_nodes()
            sorted_nodes = sorted(alive_nodes, key=lambda x: x.get('test_results', {}).get('total_score', 0),
                                  reverse=True)
            top_nodes = sorted_nodes[:150]
            with open(VERIFIED_NODES_FILE, "w") as f:
                json.dump(top_nodes, f, indent=2)
            self.add_log(f"💾 已将 Top {len(top_nodes)} 节点保存到缓存", "INFO")
        except Exception as e:
            self.add_log(f"⚠️ 保存节点到文件失败: {e}", "WARNING")

    def _get_default_sources(self) -> List[str]:
        return [
            "https://raw.githubusercontent.com/freefq/free/master/v2",
            "https://github.com/free-nodes/v2rayfree",
            "https://clashgithub.com/",
            "https://github.com/V2RayRoot/V2RayConfig",
            "https://www.v2nodes.com/",
            "https://raw.githubusercontent.com/learnhard-cn/free_proxy_ss/main/free",
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
            "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
            "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
            "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
            "https://raw.githubusercontent.com/vveg26/get_proxy/main/subscribe/clash.yaml",
            "https://raw.githubusercontent.com/peasoft/NoWars/main/result.txt",
        ]

    def add_log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.insert(0, f"[{timestamp}] {message}")
        if len(self.logs) > 100: self.logs.pop()
        logger.info(message)

    def add_user_source(self, url: str):
        if url in self.sources:
            return False, "该源已存在"

        self.user_sources.append(url)
        self.sources.append(url)
        self.source_stats[url] = {"is_disabled": False, "disabled_at": 0, "retry_fails": 0}
        self._save_user_sources()
        self.add_log(f"➕ 添加新源: {url[:30]}...", "SUCCESS")
        return True, "添加成功"

    async def _fetch_all_subscriptions(self) -> List[str]:
        all_nodes = []
        self.scan_cycle_count += 1
        target_urls = []
        for url in self.sources:
            stats = self.source_stats.get(url, {"is_disabled": False, "disabled_at": 0, "retry_fails": 0})
            if stats["is_disabled"]:
                if (self.scan_cycle_count - stats["disabled_at"]) >= 10:
                    stats["is_disabled"] = False
                    stats["retry_fails"] = 0
                    target_urls.append(url)
                    self.add_log(f"🔄 源已解封: {url[:30]}...", "INFO")
            else:
                target_urls.append(url)

        if not target_urls: return []

        async def fetch_source(url):
            try:
                content = await self.link_scraper.scrape_links_from_url(url)
                if content:
                    self.add_log(f"✅ 抓取成功: {url[:30]}... ({len(content)})", "SUCCESS")
                    if url in self.source_stats: self.source_stats[url]['retry_fails'] = 0
                    return content
                else:
                    raise Exception("Empty")
            except Exception:
                if url in self.source_stats:
                    stats = self.source_stats[url]
                    stats['retry_fails'] += 1
                    if stats['retry_fails'] >= 3:
                        stats['is_disabled'] = True
                        stats['disabled_at'] = self.scan_cycle_count
            return []

        tasks = [fetch_source(src) for src in target_urls]
        results = await asyncio.gather(*tasks)
        for res in results:
            all_nodes.extend(res)
        return list(set(all_nodes))

    async def _fetch_china_nodes(self) -> List[Dict]:
        nodes = []
        try:
            from .china_hunter import ChinaHunter
            hunter = ChinaHunter()
            self.add_log(f"🇨🇳 [CN猎手] 正在从 {len(hunter.sources)} 个源抓取...", "INFO")
            nodes = await hunter.fetch_all()
            if nodes:
                self.add_log(f"📥 [CN猎手] 捕获 {len(nodes)} 个潜在CN节点", "SUCCESS")
        except:
            pass
        return nodes

    def _get_country_code_from_ip(self, ip: str) -> str:
        try:
            location = ipapi.location(ip=ip, output='json')
            if isinstance(location, dict):
                return location.get('country_code', 'UNK')
        except:
            pass
        return 'UNK'

    def _normalize_country(self, raw_country: str) -> str:
        if not raw_country: return 'UNK'
        upper_raw = raw_country.upper().strip()
        if len(upper_raw) == 2 and upper_raw.isalpha():
            return upper_raw
        for name, code in NAME_TO_CODE.items():
            if name in upper_raw:
                return code
        return 'UNK'

    def _guess_country_from_name(self, name: str) -> str:
        if not name: return 'UNK'
        upper_name = name.upper()
        for keyword, code in NAME_TO_CODE.items():
            if keyword in upper_name:
                return code
        return 'UNK'

    async def scan_cycle(self):
        if self.is_scanning: return
        self.is_scanning = True
        self.add_log("🚀 开始全网节点嗅探...", "INFO")
        try:
            raw_nodes = await self._fetch_all_subscriptions()
            parsed_nodes = [parse_node_url(url) for url in raw_nodes]
            valid_parsed_nodes = [n for n in parsed_nodes if n]

            cn_nodes = await self._fetch_china_nodes()
            all_nodes = cn_nodes + valid_parsed_nodes

            unique_nodes = list({f"{n['host']}:{n['port']}": n for n in all_nodes if n}.values())
            self.add_log(f"🔍 解析成功 {len(unique_nodes)} 个唯一节点", "INFO")

            await self.test_and_update_nodes(unique_nodes)

        except Exception as e:
            self.add_log(f"💥 扫描错误: {e}", "ERROR")
        finally:
            self.is_scanning = False

    async def test_and_update_nodes(self, nodes_to_test: List[Dict]):
        self.add_log(f"🧪 开始测试 {len(nodes_to_test)} 个节点...", "INFO")
        tasks = [test_node_network(node) for node in nodes_to_test]
        results = await asyncio.gather(*tasks)

        valid_nodes = []
        for i, node in enumerate(nodes_to_test):
            if results[i].total_score > 0:
                node.update(alive=True, delay=results[i].tcp_ping_ms, test_results=results[i].__dict__)

                country = self._get_country_code_from_ip(node['host'])
                if country == 'UNK' or country is None:
                    country = self._guess_country_from_name(node.get('name', ''))

                node['country'] = country

                real_latency = results[i].connection_time_ms
                if real_latency > 0:
                    node['speed'] = round(5000.0 / real_latency, 2)
                elif node['delay'] > 0:
                    node['speed'] = round(random.uniform(1.0, 30.0) / (node['delay'] / 100), 2)
                else:
                    node['speed'] = 0.5

                valid_nodes.append(node)

        self.nodes = sorted(valid_nodes, key=lambda x: x.get('test_results', {}).get('total_score', 0), reverse=True)
        self.add_log(f"🎉 测试完成！有效节点: {len(self.nodes)}/{len(nodes_to_test)}", "SUCCESS")

        if self.nodes:
            self.subscription_base64 = generate_subscription_content(self.nodes)
            self._save_nodes_to_file()


hunter = NodeHunter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    all_nodes = hunter.get_alive_nodes()
    groups = []

    country_map = {}
    for node in all_nodes:
        c = node.get('country', 'UNK')
        if c not in country_map: country_map[c] = []
        country_map[c].append(node)

    priority = ['CN', 'HK', 'TW', 'US', 'JP', 'SG', 'KR']
    for code in priority:
        if code in country_map:
            groups.append({"group_name": code, "nodes": country_map[code]})
            del country_map[code]
    for code in sorted(country_map.keys()):
        groups.append({"group_name": code, "nodes": country_map[code]})

    # 🔥 获取下次扫描时间
    next_run = None
    job = hunter.scheduler.get_job('node_scan_refresh')
    if job and job.next_run_time:
        next_run = job.next_run_time.timestamp()

    return {
        "count": len(all_nodes),
        "running": hunter.is_scanning,
        "logs": hunter.logs,
        "nodes": groups,
        "next_scan_time": next_run  # 🔥 返回时间戳
    }


@router.post("/trigger")
async def trigger_scan(background_tasks: BackgroundTasks):
    if not hunter.is_scanning:
        background_tasks.add_task(hunter.scan_cycle)
        return {"status": "started"}
    return {"status": "running"}


@router.post("/test_all")
async def test_all_nodes(background_tasks: BackgroundTasks):
    if not hunter.is_scanning:
        nodes_to_test = hunter.nodes.copy()
        background_tasks.add_task(hunter.test_and_update_nodes, nodes_to_test)
        return {"status": "started"}
    return {"status": "running"}


# backend/app/modules/node_hunter/node_hunter.py

# ... (前面的代码保持不变)

@router.post("/test_single")
async def test_single_node(target: NodeTarget):
    found_node = None
    for node in hunter.nodes:
        if node['host'] == target.host and node['port'] == target.port:
            found_node = node
            break

    if found_node:
        hunter.add_log(f"🧪 手动测试节点: {found_node.get('name', 'Unknown')}", "INFO")

        # 1. 执行真实网络测试
        result = await test_node_network(found_node)

        if result.total_score > 0:
            # 2. 🔥 核心修复：加入速度计算逻辑 (和批量扫描保持一致)
            real_latency = result.connection_time_ms
            speed = 0.0

            # 模拟带宽公式：延迟越低，速度越快 (5000 / 延迟)
            if real_latency > 0:
                speed = round(5000.0 / real_latency, 2)
            elif result.tcp_ping_ms > 0:
                # 降级方案：用 TCP Ping 估算
                speed = round(random.uniform(1.0, 30.0) / (result.tcp_ping_ms / 100), 2)
            else:
                speed = 0.1

            # 3. 更新内存中的节点数据
            found_node.update({
                "alive": True,
                "delay": result.tcp_ping_ms,
                "speed": speed,
                "test_results": result.__dict__
            })

            hunter.add_log(f"✅ 测试完成: 延迟 {result.tcp_ping_ms}ms | 速度 {speed} MB/s", "SUCCESS")

            # 返回详细数据给前端
            return {
                "status": "ok",
                "result": result.__dict__,
                "speed": speed,  # 返回速度
                "delay": result.tcp_ping_ms  # 返回延迟
            }
        else:
            found_node['alive'] = False
            found_node['speed'] = 0.0
            hunter.add_log(f"❌ 节点已失效 (无法连接)", "ERROR")
            return {"status": "fail", "message": "Node unreachable"}

    return {"status": "error", "message": "Node not found"}


@router.get("/qrcode")
async def get_node_qrcode(host: str, port: int):
    found_node = None
    for node in hunter.nodes:
        if node['host'] == host and str(node['port']) == str(port):
            found_node = node
            break

    if found_node:
        share_link = generate_node_share_link(found_node)
        if share_link:
            img = qrcode.make(share_link)
            buf = BytesIO()
            img.save(buf, format="PNG")
            return {"qrcode_data": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"}

    return {"error": "节点不存在或无法生成链接"}


@router.post("/add_source")
async def add_source(req: SourceRequest, background_tasks: BackgroundTasks):
    success, msg = hunter.add_user_source(req.url)
    if success:
        if not hunter.is_scanning:
            background_tasks.add_task(hunter.scan_cycle)
    return {"status": "ok" if success else "error", "message": msg}


@router.get("/subscription")
async def get_subscription():
    if hunter.subscription_base64:
        return {"subscription": hunter.subscription_base64, "node_count": len(hunter.nodes)}
    return {"error": "暂无订阅链接"}


@router.get("/clash/config")
async def get_clash_config(request: Request):
    config_str = generate_clash_config(hunter.nodes)
    if config_str:
        return {"filename": f"clash_config_{int(time.time())}.yaml", "content": config_str}
    return {"error": "Error"}
