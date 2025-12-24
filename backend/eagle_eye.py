# backend/eagle_eye.py
import asyncio
import aiohttp
import random
import time
import ipaddress
import os
import re
from datetime import datetime
from typing import List, Tuple
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from aiohttp_socks import ProxyConnector
from playwright.async_api import async_playwright

# 强制清理环境变量
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

try:
    from proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

router = APIRouter(prefix="/api/eagle-eye", tags=["eagle_eye"])

# ==================== 配置 ====================
TARGET_PORTS = [80, 8080, 81, 8000, 554, 443]


def get_virtual_identity():
    mac = "00:%02x:%02x:%02x:%02x:%02x" % (
        random.randint(0, 255), random.randint(0, 255),
        random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
    )
    return {
        "mac": mac.upper(),
        "ua": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(100, 128)}.0.0.0 Safari/537.36"
    }


def parse_ip_targets(raw_text: str) -> List[str]:
    targets = []
    parts = re.split(r'[,\s\n]+', raw_text)
    for part in parts:
        part = part.strip()
        if not part: continue
        try:
            if '/' in part:
                net = ipaddress.ip_network(part, strict=False)
                targets.extend([str(ip) for ip in list(net.hosts())[:100]])
            elif '-' in part:
                s, e = part.split('-')
                start, end = int(ipaddress.IPv4Address(s)), int(ipaddress.IPv4Address(e))
                if end - start > 100: end = start + 100
                targets.extend([str(ipaddress.IPv4Address(ip)) for ip in range(start, end + 1)])
            else:
                ipaddress.IPv4Address(part)
                targets.append(part)
        except:
            pass
    return list(set(targets))


class EagleScanner:
    def __init__(self):
        self.is_running = False
        self.should_stop = False  # 🔥 新增停止标志
        self.results = []
        self.logs = []
        self.stats = {"total": 0, "scanned": 0, "found": 0, "percent": 0}
        self.identity = get_virtual_identity()

    def add_log(self, msg, level="INFO"):
        icon = "🔴" if level == "CRITICAL" else ("🟠" if level == "WARN" else "🔵")
        self.logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {icon} {msg}")
        if len(self.logs) > 200: self.logs.pop()

    def update_progress(self):
        if self.stats["total"] > 0:
            self.stats["percent"] = int((self.stats["scanned"] / self.stats["total"]) * 100)

    def stop(self):
        """🔥 触发停止"""
        self.should_stop = True
        self.add_log("🛑 收到停止指令，正在终止任务...", "WARN")

    # 🔥 Playwright 爬虫引擎
    async def fetch_shodan_via_browser(self, query):
        if self.should_stop: return []  # 停止检测

        self.add_log(f"🌍 [Browser] 启动隐形浏览器抓取: {query}", "INFO")
        extracted_targets = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.identity["ua"])
            page = await context.new_page()

            try:
                if self.should_stop: raise Exception("User Stopped")  # 停止检测

                search_url = f"https://www.shodan.io/search?query={query}"
                self.add_log(f"🔗 正在访问: {search_url} ...")

                await page.goto(search_url, timeout=30000)
                try:
                    await page.wait_for_selector('div.search-result', timeout=5000)
                except:
                    pass

                content = await page.content()

                ips = re.findall(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', content)
                unique_ips = set()
                for ip in ips:
                    if not ip.startswith("192.168") and not ip.startswith("127.") and not ip.startswith("10."):
                        try:
                            ipaddress.ip_address(ip)
                            unique_ips.add(ip)
                        except:
                            pass

                if not unique_ips:
                    self.add_log("⚠️ 页面已加载但未提取到 IP", "WARN")
                else:
                    self.add_log(f"✅ 成功提取 {len(unique_ips)} 个 IP，准备全链路验证...", "INFO")
                    for ip in unique_ips:
                        extracted_targets.append({"ip": ip})

            except Exception as e:
                if "User Stopped" not in str(e):
                    self.add_log(f"❌ 浏览器异常: {str(e)}", "WARN")
            finally:
                await browser.close()

        return extracted_targets

    # 🔥 核心：验证漏斗
    async def verify_and_grab(self, ip: str, port: int):
        if self.should_stop: return  # 停止检测

        target_url = f"http://{ip}:{port}"
        # === 变动开始 ===
        # 直接从中央管理器获取链路
        if pool_manager:
            chain = pool_manager.get_standard_chain()
        else:
            chain = []  # 防止模块未加载报错

        # 增加直连兜底 (可选)
        chain.append((None, "Direct", 3))
        # === 变动结束 ===
        is_accessible = False
        final_brand = "Unknown"
        final_proxy = "None"
        final_status = "DEAD"
        final_risk = "INFO"

        for proxy_url, proxy_name, timeout in chain:
            if self.should_stop: return  # 停止检测
            try:
                connector = ProxyConnector.from_url(proxy_url) if proxy_url else aiohttp.TCPConnector()
                headers = {"User-Agent": self.identity["ua"], "Connection": "close"}
                async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                    async with session.get(target_url, timeout=timeout, ssl=False) as resp:

                        # 🚫 过滤：403 和 500 直接扔掉
                        if resp.status == 403 or resp.status == 401 or resp.status >= 500:
                            return

                        # ✅ 存活！
                        is_accessible = True
                        final_proxy = proxy_name

                        server = resp.headers.get("Server", "")
                        body = (await resp.text())[:1000].lower()

                        if "hikvision" in server or "app-webs" in server:
                            final_brand = "Hikvision"
                        elif "dahua" in server:
                            final_brand = "Dahua"

                        # 🔐 认证识别
                        if resp.status == 401:
                            final_status = "Auth (401)"
                            final_risk = "HIGH"
                        elif "login" in body or "password" in body:
                            final_status = "Login Page"
                            final_risk = "HIGH"
                        else:
                            final_status = f"Open ({resp.status})"

                        self.add_log(f"✅ [有效] {ip}:{port} | {final_brand} | via {final_proxy}", "INFO")
                        break
            except Exception:
                continue

        if is_accessible:
            self.results.insert(0, {
                "ip": ip, "port": port, "brand": final_brand,
                "status": final_status, "proxy": final_proxy,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "risk": final_risk
            })
            self.stats["found"] += 1

    async def search_and_audit(self, query: str):
        # 1. 爬虫获取
        targets = await self.fetch_shodan_via_browser(query)
        if not targets or self.should_stop: return

        self.stats["total"] = len(targets) * len(TARGET_PORTS)

        # 2. 验证漏斗
        sem = asyncio.Semaphore(50)

        async def worker(item):
            if self.should_stop: return
            ip = item['ip']
            for port in [80, 8080, 81, 554]:
                if self.should_stop: break
                async with sem:
                    await self.verify_and_grab(ip, port)
                    self.stats["scanned"] += 1
                    self.update_progress()

        await asyncio.gather(*[worker(t) for t in targets])

    async def execute(self, target_input: str, mode: str):
        if self.is_running: return
        self.is_running = True
        self.should_stop = False  # 重置标志位
        self.results = []
        self.stats = {"total": 0, "scanned": 0, "found": 0, "percent": 0}
        self.identity = get_virtual_identity()

        try:
            if mode == "shodan":
                if re.search(r'[a-zA-Z]', target_input):
                    await self.search_and_audit(target_input)
                else:
                    ips = parse_ip_targets(target_input)
                    if ips:
                        self.add_log(f"🚀 验证输入 IP...", "INFO")
                        self.stats["total"] = len(ips) * len(TARGET_PORTS)
                        sem = asyncio.Semaphore(50)

                        async def worker(ip, port):
                            if self.should_stop: return
                            async with sem:
                                await self.verify_and_grab(ip, port)
                                self.stats["scanned"] += 1
                                self.update_progress()

                        await asyncio.gather(*[worker(ip, p) for ip in ips for p in TARGET_PORTS])
            else:
                ips = parse_ip_targets(target_input)
                if ips:
                    self.add_log(f"🚀 实战扫描: {len(ips)} 主机", "INFO")
                    self.stats["total"] = len(ips) * len(TARGET_PORTS)
                    sem = asyncio.Semaphore(50)

                    async def worker(ip, port):
                        if self.should_stop: return
                        async with sem:
                            await self.verify_and_grab(ip, port)
                            self.stats["scanned"] += 1
                            self.update_progress()

                    tasks = [worker(ip, p) for ip in ips for p in TARGET_PORTS]
                    await asyncio.gather(*tasks)
                else:
                    self.add_log("⚠️ 请输入有效 IP", "WARN")

        except Exception as e:
            self.add_log(f"❌ 任务中断: {e}", "WARN")
        finally:
            self.is_running = False
            self.add_log("🏁 任务已结束", "INFO")


eagle = EagleScanner()


class ScanReq(BaseModel):
    target: str
    mode: str = "active"


@router.post("/scan")
async def start_scan(req: ScanReq, bg: BackgroundTasks):
    if eagle.is_running: return {"status": "error", "msg": "Running"}
    bg.add_task(eagle.execute, req.target, req.mode)
    return {"status": "started"}


# 🔥 新增停止接口
@router.post("/stop")
async def stop_scan():
    if eagle.is_running:
        eagle.stop()
        return {"status": "stopping"}
    return {"status": "not_running"}


@router.get("/status")
async def get_status():
    return {
        "running": eagle.is_running,
        "progress": f"{eagle.stats['scanned']} / {eagle.stats['total']}",
        "percent": eagle.stats['percent'],
        "logs": eagle.logs[:100],
        "results": eagle.results,
        "identity": eagle.identity,
        "active_chain": [f"{item[1]}" for item in pool_manager.get_standard_chain()]
    }


@router.post("/crack")
async def crack(ip: str):
    eagle.add_log(f"ℹ️ 目标 {ip} 已标记，请进行人工审计", "INFO")
    return {"status": "queued"}