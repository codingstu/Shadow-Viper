import asyncio
import aiohttp
import re
import time
import json
import os
import random
from fastapi import APIRouter, BackgroundTasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ==================== 配置区域 ====================
PROXY_STORE_FILE = "valid_proxies.json"

# 备用代理 (用于辅助抓取)
UPSTREAM_PROXY = os.getenv("UPSTREAM_PROXY")

# 🔥【绝对核心】必须是 HTTPS，否则无法用于 MissAV
TEST_URL = "https://www.google.com"
TIMEOUT = 8

router = APIRouter(prefix="/api/proxy_pool", tags=["proxy_pool"])


class ProxyRecord(BaseModel):
    ip: str
    port: str
    protocol: str
    speed: float
    last_check: str
    source: str
    score: int = 100


class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.is_running = False
        self.logs = []
        self.scheduler = AsyncIOScheduler()
        self.load_from_file()

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {msg}"
        print(log_entry)
        self.logs.insert(0, log_entry)
        if len(self.logs) > 100: self.logs.pop()

    def load_from_file(self):
        if os.path.exists(PROXY_STORE_FILE):
            try:
                with open(PROXY_STORE_FILE, "r") as f:
                    data = json.load(f)
                    self.proxies = [ProxyRecord(**item) for item in data]
                self.log(f"📥 已加载 {len(self.proxies)} 个历史代理")
            except:
                pass

    def save_to_file(self):
        try:
            self.proxies.sort(key=lambda x: x.speed)
            with open(PROXY_STORE_FILE, "w") as f:
                json.dump([p.dict() for p in self.proxies], f)
        except:
            pass

    # --- 1. 抓取模块 ---
    async def fetch_public_sources(self):
        candidates = []
        sources = [
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
            "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt",
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
        ]

        self.log(f"🌍 开始抓取 {len(sources)} 个源...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

        async with aiohttp.ClientSession(headers=headers) as session:
            for url in sources:
                content = None
                try:
                    async with session.get(url, timeout=10, ssl=False) as resp:
                        if resp.status == 200: content = await resp.text()
                except:
                    # 备用：走付费代理抓取
                    try:
                        async with session.get(url, proxy=UPSTREAM_PROXY, timeout=15, ssl=False) as resp:
                            if resp.status == 200: content = await resp.text()
                    except:
                        pass

                if content:
                    found = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[:\s](\d+)', content)
                    if found:
                        self.log(f"      └─ 提取到 {len(found)} 个 IP")
                        for ip, port in found:
                            candidates.append({
                                "ip": ip, "port": port, "protocol": "http",
                                "source": "Public", "score": 50
                            })
        return candidates

    # --- 2. 验证模块 ---
    async def validate_one(self, proxy_dict, session):
        proxy_url = f"http://{proxy_dict['ip']}:{proxy_dict['port']}"
        start = time.time()
        try:
            # 🔥 强制 HTTPS 握手
            async with session.get(TEST_URL, proxy=proxy_url, timeout=TIMEOUT, ssl=False) as resp:
                if resp.status == 200:
                    speed = int((time.time() - start) * 1000)
                    return {
                        **proxy_dict,
                        "speed": speed,
                        "last_check": datetime.now().strftime("%H:%M:%S"),
                        "protocol": "HTTPS",  # 🔥【新增这一行】验证通过后，强制改名为 HTTPS
                        "score": 100
                    }
        except:
            return None

    async def run_cycle(self):
        if self.is_running: return
        self.is_running = True
        self.log("🚀 ==== 开始 IP 狩猎 (严格HTTPS模式) ====")

        # 1. 抓取
        candidates = await self.fetch_public_sources()

        # 2. 复活赛：只给现存代理一次机会，如果这次不行直接剔除
        for p in self.proxies:
            candidates.append(p.dict())

        # 清空当前列表，重新洗牌
        self.proxies = []
        self.save_to_file()

        # 3. 去重
        unique_map = {f"{p['ip']}:{p['port']}": p for p in candidates}
        unique_candidates = list(unique_map.values())
        total = len(unique_candidates)
        self.log(f"⚡ 待验证: {total} 个 (正在清洗非HTTPS代理...)")

        if total == 0:
            self.is_running = False
            return

        # 4. 验证
        batch_size = 200
        async with aiohttp.ClientSession() as session:
            for i in range(0, total, batch_size):
                if not self.is_running: break
                batch = unique_candidates[i:i + batch_size]
                tasks = [self.validate_one(p, session) for p in batch]
                results = await asyncio.gather(*tasks)

                new_valid = [r for r in results if r]
                if len(new_valid) > 0:
                    self.proxies.extend([ProxyRecord(**p) for p in new_valid])
                    self.save_to_file()
                    self.log(f"   ✨ 捕获 {len(new_valid)} 个 HTTPS 代理")
                await asyncio.sleep(0.2)

        self.is_running = False
        self.log(f"✅ 扫描结束。最终有效: {len(self.proxies)} 个")

    # 🔥 新增：清空功能
    def clear_all(self):
        self.proxies = []
        self.save_to_file()
        self.log("🗑️ IP 池已清空")


manager = ProxyManager()


@router.get("/stats")
async def get_stats():
    return {"count": len(manager.proxies), "running": manager.is_running, "logs": manager.logs}


@router.get("/list")
async def get_list():
    return manager.proxies[:100]


@router.get("/pop")
async def get_random_proxy():
    if not manager.proxies: return {"proxy": None}
    choice = random.choice(manager.proxies[:20])
    return {"proxy": f"http://{choice.ip}:{choice.port}"}


@router.post("/trigger")
async def trigger_task(background_tasks: BackgroundTasks):
    if manager.is_running: return {"message": "Busy"}
    background_tasks.add_task(manager.run_cycle)
    return {"message": "Started"}


# 🔥 新增接口
@router.delete("/clean")
async def clean_pool():
    manager.clear_all()
    return {"message": "Cleared"}