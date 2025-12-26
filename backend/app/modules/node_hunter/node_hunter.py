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
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..link_scraper.link_scraper import LinkScraper
from .parsers import parse_node_url
from .validators import test_node_network, NodeTestResult
from .config_generator import generate_node_share_link, generate_subscription_content, generate_clash_config

try:
    from ..proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

CHINA_PROXY_SOURCE = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CN/data.txt"

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nodes", tags=["nodes"])

VERIFIED_NODES_FILE = "verified_nodes.json"


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
        self.link_scraper = LinkScraper(pool_manager)
        self.user_sources_file = 'user_sources.json'
        self.user_sources = self._load_user_sources()
        self.sources = self._get_default_sources() + self.user_sources
        self.scheduler = AsyncIOScheduler()
        self._load_nodes_from_file()

    def start_scheduler(self):
        if not self.scheduler.running:
            # ==================== 👇 修改：注释掉旧的健康检查 👇 ====================
            # 逻辑已移入 ChinaHunter.fetch_all 内部，随主循环自动执行，不再需要独立任务
            # self.scheduler.add_job(self.china_hunter.check_sources_health, 'interval', minutes=5, id='source_health_check')
            # ==================== 👆 修改结束 👆 ====================

            self.scheduler.start()
            self.add_log("✅ [System] 节点猎手自动巡航已启动 (10min/cycle)", "SUCCESS")
            asyncio.create_task(self.scan_cycle())

    def get_alive_nodes(self) -> List[Dict[str, Any]]:
        return [node for node in self.nodes if node.get('alive')]

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
                    existing_node_ids = {f"{n['host']}:{n['port']}" for n in self.nodes}
                    for node in loaded_nodes:
                        node_id = f"{node['host']}:{node['port']}"
                        if node_id not in existing_node_ids:
                            self.nodes.append(node)
                self.add_log(f"📥 从缓存加载了 {len(loaded_nodes)} 个已验证节点", "SUCCESS")
            except Exception as e:
                self.add_log(f"⚠️ 加载缓存节点失败: {e}", "WARNING")

    def _save_nodes_to_file(self):
        try:
            nodes_to_save = sorted(self.get_alive_nodes(),
                                   key=lambda x: x.get('test_results', {}).get('total_score', 0), reverse=True)[:20]
            with open(VERIFIED_NODES_FILE, "w") as f:
                json.dump(nodes_to_save, f, indent=2)
            self.add_log(f"💾 已将 Top {len(nodes_to_save)} 节点保存到缓存", "INFO")
        except Exception as e:
            self.add_log(f"⚠️ 保存节点到文件失败: {e}", "WARNING")

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

    async def _fetch_china_nodes(self) -> List[Dict]:
        """专门抓取 GitHub 上的回国节点"""
        nodes = []

        # ==================== 👇 新增逻辑 (调用 china_hunter) 👇 ====================
        try:
            # 延迟导入，防止循环引用
            from .china_hunter import ChinaHunter

            # 实例化新猎手
            hunter = ChinaHunter()
            self.add_log(f"🇨🇳 [新版] 正在启动回国节点猎手 (源数量: {len(hunter.sources)})...", "INFO")

            # 执行抓取
            nodes = await hunter.fetch_all()

            if nodes:
                self.add_log(f"📥 [新版] 回国猎手捕获成功: {len(nodes)} 个节点", "SUCCESS")
            else:
                self.add_log(f"⚠️ [新版] 回国猎手本次未捕获到节点", "WARNING")

        except ImportError:
            self.add_log("❌ 未找到 china_hunter 模块，请检查文件是否存在", "ERROR")
        except Exception as e:
            self.add_log(f"⚠️ [新版] 回国节点抓取异常: {e}", "WARNING")
        # ==================== 👆 新增逻辑结束 👆 ====================

        # ==================== 👇 旧逻辑 (已注释保留) 👇 ====================
        # self.add_log(f"🇨🇳 正在抓取回国专用节点...", "INFO")
        # try:
        #     async with aiohttp.ClientSession() as session:
        #         async with session.get(CHINA_PROXY_SOURCE, timeout=10) as resp:
        #             if resp.status == 200:
        #                 text = await resp.text()
        #                 lines = text.strip().split('\n')
        #                 for line in lines:
        #                     line = line.strip()
        #                     if ":" in line and not line.startswith("#"):
        #                         try:
        #                             # data.txt 格式通常是 ip:port
        #                             parts = line.split(":")
        #                             ip = parts[0]
        #                             port = int(parts[1])
        #
        #                             # 手动构造节点对象
        #                             nodes.append({
        #                                 "id": f"cn_http_{ip}_{port}",
        #                                 "name": f"🇨🇳 回国专线 | {ip}",  # 强制加上国旗
        #                                 "protocol": "http",  # GitHub 免费列表多为 HTTP
        #                                 "host": ip,
        #                                 "port": port,
        #                                 "country": "CN",  # 关键标记
        #                                 "type": "back_to_china"
        #                             })
        #                         except:
        #                             continue
        #                 self.add_log(f"📥 抓取到 {len(nodes)} 个潜在回国节点", "SUCCESS")
        # except Exception as e:
        #     self.add_log(f"⚠️ 回国节点抓取失败: {e}", "WARNING")
        # ==================== 👆 旧逻辑结束 👆 ====================

        return nodes


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

            # 过滤掉解析失败的
            valid_parsed_nodes = [n for n in parsed_nodes if n]

            # === 新增逻辑：抓取回国节点 ===
            cn_nodes = await self._fetch_china_nodes()

            # === 合并列表 (回国节点放前面) ===
            all_nodes = cn_nodes + valid_parsed_nodes

            unique_nodes = list({f"{n['host']}:{n['port']}": n for n in parsed_nodes if n}.values())
            self.add_log(f"🔍 解析成功 {len(unique_nodes)} 个唯一节点", "INFO")

            await self.test_and_update_nodes(unique_nodes)

        except Exception as e:
            self.add_log(f"💥 扫描过程发生错误: {e}", "ERROR")
        finally:
            self.is_scanning = False

    async def test_and_update_nodes(self, nodes_to_test: List[Dict]):
        self.add_log(f"🧪 开始对 {len(nodes_to_test)} 个节点进行真实网络测试...", "INFO")
        tasks = [test_node_network(node) for node in nodes_to_test]
        results = await asyncio.gather(*tasks)

        valid_nodes = []
        for i, node in enumerate(nodes_to_test):
            if results[i].total_score > 0:
                node.update(alive=True, delay=results[i].tcp_ping_ms, test_results=results[i].__dict__)
                # ==================== 👇 修改开始：更科学的速度计算 👇 ====================
                # 优先使用真实的 HTTP 连接耗时
                real_latency = results[i].connection_time_ms

                if real_latency > 0:
                    # 延迟越低，模拟的带宽速度越大
                    # 比如 500ms 延迟 -> 约 10 MB/s
                    # 2000ms 延迟 -> 约 2.5 MB/s
                    node['speed'] = round(5000.0 / real_latency, 2)
                elif node['delay'] > 0:
                    # 降级方案：用 TCP Ping 估算
                    node['speed'] = round(random.uniform(1.0, 30.0) / (node['delay'] / 100), 2)
                else:
                    node['speed'] = 0.5  # 保底
                # ==================== 👆 修改结束 👆 ====================
                valid_nodes.append(node)

        self.nodes = sorted(valid_nodes, key=lambda x: x.get('test_results', {}).get('total_score', 0), reverse=True)
        self.add_log(f"🎉 测试完成！有效节点: {len(self.nodes)}/{len(nodes_to_test)}", "SUCCESS")

        if self.nodes:
            self.subscription_base64 = generate_subscription_content(self.nodes)
            self.add_log(f"📥 已生成订阅链接 ({len(self.nodes)}个节点)", "SUCCESS")
            self._save_nodes_to_file()


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


@router.post("/test_all")
async def test_all_nodes(background_tasks: BackgroundTasks):
    if not hunter.is_scanning:
        nodes_to_test = hunter.nodes.copy()
        background_tasks.add_task(hunter.test_and_update_nodes, nodes_to_test)
        return {"status": "started", "message": f"开始测试 {len(nodes_to_test)} 个节点"}
    return {"status": "running", "message": "扫描正在进行中"}


@router.post("/test_node/{node_index}")
async def test_single_node(node_index: int):
    if 0 <= node_index < len(hunter.nodes):
        node = hunter.nodes[node_index]
        hunter.add_log(f"🧪 手动测试节点: {node.get('name', 'Unknown')}", "INFO")
        result = await test_node_network(node)
        if result.total_score > 0:
            node.update(alive=True, delay=result.tcp_ping_ms, test_results=result.__dict__)
            hunter.add_log(f"✅ 节点可用 (得分: {result.total_score})", "SUCCESS")
        else:
            node['alive'] = False
            hunter.add_log(f"❌ 节点不可用", "ERROR")
        return {"status": "ok", "result": result.__dict__}
    return {"status": "error", "message": "Node index out of range"}


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