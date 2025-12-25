# backend/app/modules/proxy/proxy_engine.py
import asyncio
import aiohttp
import re
import time
import json
import os
import random
import logging
from fastapi import APIRouter, BackgroundTasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ==================== 配置区域 ====================
PROXY_STORE_FILE = "valid_proxies.json"
UPSTREAM_PROXY = os.getenv("UPSTREAM_PROXY")

# 验证目标
TEST_URL_GLOBAL = "https://www.google.com/generate_204"
TEST_URL_CN = "https://www.bilibili.com"
TIMEOUT = 4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProxyEngine")

router = APIRouter(prefix="/api/proxy_pool", tags=["proxy_pool"])


class ProxyRecord(BaseModel):
    ip: str
    port: int
    protocol: str
    speed: float = 0.0
    country: str = "UNK"
    last_check: str = ""
    source: str = "public"
    score: int = 100

    def to_url(self):
        if self.protocol == "https":
            return f"http://{self.ip}:{self.port}"
        return f"{self.protocol}://{self.ip}:{self.port}"


class ProxyManager:
    def __init__(self):
        self.proxies: list[ProxyRecord] = []
        self.is_running = False
        self.logs = []
        self.scheduler = AsyncIOScheduler()
        self.load_from_file()
        self.node_provider = None 

    def set_node_provider(self, provider_func):
        """注入 NodeHunter 的节点提供函数"""
        self.log("🔗 Node Hunter provider has been connected to the proxy pool.")
        self.node_provider = provider_func

    def start(self):
        if not self.scheduler.running:
            # 🔥 核心修复：添加定时任务，每 5 分钟自动刷新一次
            self.scheduler.add_job(self.run_cycle, 'interval', minutes=5, id='proxy_refresh')
            self.scheduler.start()
            self.log("✅ [System] 代理池自动巡检已启动 (5min/cycle)")
            # 启动时立即运行一次
            asyncio.create_task(self.run_cycle())

    def get_standard_chain(self):
        chain = []
        
        # 🔥 恢复：从 NodeHunter 获取节点
        if self.node_provider:
            try:
                nodes = self.node_provider()
                for node in nodes[:5]: # 取前5个
                    chain.append((f"socks5://{node['host']}:{node['port']}", f"🛰️ NodeHunter ({node['name'][:10]})", 10))
            except Exception as e:
                self.log(f"⚠️ Failed to get nodes from provider: {e}")

        alive_nodes = [p for p in self.proxies if p.score > 0]
        if alive_nodes:
            top_limit = min(len(alive_nodes), 20)
            top_nodes = alive_nodes[:top_limit]
            selected = random.sample(top_nodes, min(len(top_nodes), 3))
            for p in selected:
                chain.append((p.to_url(), f"Hunter Node ({p.country})", 5))

        paid_url = os.getenv("PAID_PROXY_URL")
        if paid_url:
            chain.append((paid_url, "👑 Paid Proxy", 5))

        if os.getenv("USE_TOR_BACKUP", "True") == "True":
            tor_host = os.getenv("TOR_HOST", "127.0.0.1")
            tor_port = os.getenv("TOR_PORT", "9050")
            chain.append((f"socks5h://{tor_host}:{tor_port}", "🧅 Tor Network", 10))

        return chain

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {msg}"
        print(log_entry)
        self.logs.insert(0, log_entry)
        if len(self.logs) > 200: self.logs.pop()

    def load_from_file(self):
        if os.path.exists(PROXY_STORE_FILE):
            try:
                with open(PROXY_STORE_FILE, "r") as f:
                    data = json.load(f)
                    self.proxies = [ProxyRecord(**item) for item in data]
                self.log(f"📥 加载缓存: {len(self.proxies)} 个")
            except:
                pass

    def save_to_file(self):
        try:
            # 去重并排序
            unique_proxies = {f"{p.ip}:{p.port}": p for p in self.proxies}.values()
            self.proxies = sorted(list(unique_proxies), key=lambda x: x.speed)
            
            with open(PROXY_STORE_FILE, "w") as f:
                json.dump([p.dict() for p in self.proxies], f)
        except:
            pass

    async def fetch_public_sources(self):
        candidates = []
        sources = [
            ("https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt", "socks5"),
            ("https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt", "socks5"),
            ("https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=5000&country=all", "socks5"),
            ("https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt", "http"),
            ("https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all", "http"),
        ]
        self.log(f"🌍 开始抓取 (Sources: {len(sources)})...")
        async with aiohttp.ClientSession() as session:
            for url, default_proto in sources:
                try:
                    content = None
                    try:
                        async with session.get(url, timeout=8, ssl=False) as resp:
                            if resp.status == 200: content = await resp.text()
                    except:
                        if UPSTREAM_PROXY:
                            try:
                                async with session.get(url, proxy=UPSTREAM_PROXY, timeout=10, ssl=False) as resp:
                                    if resp.status == 200: content = await resp.text()
                            except:
                                pass

                    if content:
                        found = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[:\s](\d+)', content)
                        if found:
                            for ip, port in found:
                                candidates.append({"ip": ip, "port": int(port), "protocol": default_proto})
                except:
                    pass
        return candidates

    async def validate_one(self, proxy_dict, session):
        proto = proxy_dict['protocol']
        proxy_url = f"{proto}://{proxy_dict['ip']}:{proxy_dict['port']}"
        start = time.time()
        is_valid = False
        try:
            async with session.get(TEST_URL_GLOBAL, proxy=proxy_url, timeout=TIMEOUT, ssl=False) as resp:
                if resp.status in [200, 204]: is_valid = True
        except:
            try:
                async with session.get(TEST_URL_CN, proxy=proxy_url, timeout=TIMEOUT, ssl=False) as resp:
                    if resp.status == 200: is_valid = True
            except:
                pass

        if is_valid:
            speed = int((time.time() - start) * 1000)
            if proto == "http": proto = "https"
            return ProxyRecord(ip=proxy_dict['ip'], port=proxy_dict['port'], protocol=proto, speed=speed,
                               last_check=datetime.now().strftime("%H:%M:%S"), source="public_scan", score=100)
        return None

    async def run_cycle(self):
        if self.is_running: return
        self.is_running = True
        try:
            self.log("🚀 ==== 启动 IP 净化 (5min 轮换) ====")
            candidates = await self.fetch_public_sources()
            
            # 保留现有存活的代理
            for p in self.proxies:
                if p.score > 0: # 只保留分数高的
                    proto = "http" if p.protocol == "https" else p.protocol
                    candidates.append({"ip": p.ip, "port": p.port, "protocol": proto})

            unique = {f"{c['ip']}:{c['port']}": c for c in candidates}.values()
            total = len(unique)
            if total == 0: return

            self.log(f"⚡ 验证 {total} 个节点...")
            valid_list = []
            batch_size = 150
            candidate_list = list(unique)

            async with aiohttp.ClientSession() as session:
                for i in range(0, total, batch_size):
                    # if not self.is_running: break # 移除此检查，确保任务完成
                    batch = candidate_list[i:i + batch_size]
                    tasks = [self.validate_one(p, session) for p in batch]
                    results = await asyncio.gather(*tasks)
                    new_valid = [r for r in results if r]
                    valid_list.extend(new_valid)
                    
                    # 实时更新，避免等待太久
                    if new_valid:
                        # 简单的合并去重
                        current_map = {f"{p.ip}:{p.port}": p for p in self.proxies}
                        for p in new_valid:
                            current_map[f"{p.ip}:{p.port}"] = p
                        self.proxies = list(current_map.values())
                        self.save_to_file()

            self.log(f"✅ 净化完成！当前可用: {len(self.proxies)} 个")
        except Exception as e:
            self.log(f"❌ 异常: {e}")
        finally:
            self.is_running = False

    def clear_all(self):
        self.proxies = []
        self.save_to_file()
        self.is_running = False
        self.log("🗑️ 已清空")


manager = ProxyManager()


@router.get("/stats")
async def get_stats():
    return {"count": len(manager.proxies), "running": manager.is_running, "logs": manager.logs,
            "best": [p.dict() for p in manager.proxies[:20]]}


@router.get("/list")
async def get_list(): return manager.proxies


@router.get("/pop")
async def get_random_proxy():
    if not manager.proxies: return {"proxy": None}
    choice = random.choice(manager.proxies[:20])
    return {"proxy": choice.to_url()}


@router.post("/trigger")
async def trigger_task(background_tasks: BackgroundTasks):
    if manager.is_running: return {"message": "Busy"}
    background_tasks.add_task(manager.run_cycle)
    return {"message": "Started"}


@router.delete("/clean")
async def clean_pool():
    manager.clear_all()
    return {"message": "Cleared"}
