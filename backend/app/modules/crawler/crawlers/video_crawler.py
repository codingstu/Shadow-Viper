# backend/app/modules/crawler/crawlers/video_crawler.py
import asyncio
import json
import re
import requests
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Route
from abc import ABC, abstractmethod
import pandas as pd

# 引入代理池管理器 (相对导入)
try:
    from ...proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

GLOBAL_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
GLOBAL_COOKIE_JAR = {}

class BaseCrawler(ABC):
    @abstractmethod
    async def crawl(self, url: str, network_type: str = "auto"):
        pass

    async def get_proxy_chain(self, network_type: str = "auto"):
        chain = []
        if network_type == "direct":
            chain.append((None, "Direct", 10))
            return chain

        if pool_manager:
            if network_type in ["node", "auto"] and pool_manager.node_provider:
                try:
                    nodes = pool_manager.node_provider()
                    for node in nodes[:3]:
                        chain.append((f"socks5://{node['host']}:{node['port']}", f"🛰️ Shadow Matrix ({node['name'][:10]})", 10))
                except: pass
            
            if network_type in ["proxy", "auto"]:
                alive_nodes = [p for p in pool_manager.proxies if p.score > 0]
                if alive_nodes:
                    selected = sorted(alive_nodes, key=lambda p: p.speed)[:3]
                    for p in selected:
                        chain.append((p.to_url(), f"🌐 Hunter Pool ({p.country})", 5))
        
        if not chain: # Fallback
            chain.append((None, "Direct", 10))
        return chain

async def async_request(method, url, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))

async def request_with_chain_async(url, headers=None, stream=False, timeout=10, method="GET", network_type="auto"):
    if headers is None: headers = {}
    base_headers = {
        "User-Agent": GLOBAL_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    base_headers.update(headers)
    
    chain = []
    if network_type == "direct":
        chain.append((None, "Direct", 10))
    elif network_type == "node":
        if pool_manager and pool_manager.node_provider:
            nodes = pool_manager.node_provider()
            for node in nodes[:3]: chain.append((f"socks5://{node['host']}:{node['port']}", f"🛰️ {node['name']}", 15))
        if not chain: chain.append((None, "Direct (Fallback)", 10))
    elif network_type == "proxy":
        if pool_manager:
            proxies = [p for p in pool_manager.proxies if p.score > 0]
            if proxies:
                for p in sorted(proxies, key=lambda p: p.speed)[:3]: chain.append((p.to_url(), "🌐 Hunter Pool", 10))
        if not chain: chain.append((None, "Direct (Fallback)", 10))
    else: # auto
        if pool_manager and pool_manager.node_provider:
            nodes = pool_manager.node_provider()
            if nodes: chain.append((f"socks5://{nodes[0]['host']}:{nodes[0]['port']}", f"🛰️ {nodes[0]['name']}", 15))
        if pool_manager:
            proxies = [p for p in pool_manager.proxies if p.score > 0]
            if proxies: chain.append((random.choice(proxies).to_url(), "🌐 Hunter Pool", 10))
        chain.append((None, "Direct", 10))

    for proxy_url, name, time_limit in chain:
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            resp = await async_request(method, url, headers=base_headers, proxies=proxies, timeout=time_limit, verify=False, stream=stream)
            if resp.status_code in [200, 206, 302]:
                return resp
        except:
            continue
    class DummyResponse:
        status_code = 500; text = ""; content=b"";
        def json(self): return {}
    return DummyResponse()

def parse_playwright_proxy(p_url):
    if not p_url: return None
    try:
        u = urlparse(p_url)
        return {"server": f"{u.scheme}://{u.hostname}:{u.port}", "username": u.username, "password": u.password}
    except:
        return None

async def block_media_and_images(route):
    if route.request.resource_type in ["image", "font"]:
        await route.abort()
    else:
        await route.continue_()

class BilibiliCrawler(BaseCrawler):
    async def fetch_api_metadata_async(self, url, network_type):
        try:
            bvid_match = re.search(r"(BV\w+)", url)
            if not bvid_match: return None
            bvid = bvid_match.group(1)
            headers = {"Referer": f"https://www.bilibili.com/video/{bvid}", "User-Agent": GLOBAL_USER_AGENT}
            
            # 🔥 核心修复：B站API优先尝试直连
            api_chain = [(None, "Direct", 5)]
            if network_type != 'direct': # 如果不是强制直连，则把其他代理作为备选
                proxies = await self.get_proxy_chain(network_type)
                api_chain.extend(proxies)

            info_resp = None
            for proxy, name, timeout in api_chain:
                try:
                    proxies = {"http": proxy, "https": proxy} if proxy else None
                    info_resp = await async_request("get", f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=headers, proxies=proxies, timeout=timeout)
                    if info_resp.status_code == 200 and info_resp.json().get('code') == 0:
                        break # 成功获取，跳出循环
                except:
                    continue
            
            if not info_resp or info_resp.status_code != 200: return None
            
            data = info_resp.json().get('data')
            if not data: return None
            cid = data['cid']
            meta = {"title": data['title'], "cover": data['pic']}
            play_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&fnval=1&platform=html5&high_quality=1"
            play_resp = await request_with_chain_async(play_api, headers=headers, network_type=network_type)
            video_url = ""
            if play_resp.status_code == 200 and play_resp.json().get('code') == 0:
                video_url = play_resp.json()['data']['durl'][0]['url']
            
            if video_url:
                return {**meta, "video_url": video_url, "verified": True}
            return {**meta, "video_url": "", "verified": False}
        except Exception:
            return None

    async def crawl(self, url: str, network_type: str = "auto"):
        yield json.dumps({"step": "process", "message": "📺 启动 B站 专用爬虫..."}) + "\n"
        api_data = await self.fetch_api_metadata_async(url, network_type)
        if api_data and api_data.get('verified'):
            yield json.dumps({"step": "process", "message": f"✅ API 解析成功: {api_data['title'][:15]}..."}) + "\n"
            results = [{"类型": "标题", "内容": api_data['title'], "备注": "API-Title"}, {"类型": "图片", "内容": api_data['cover'], "备注": "Cover"}, {"类型": "视频", "内容": api_data['video_url'], "备注": "Direct-Stream"}]
            yield pd.DataFrame(results)
            return
        yield json.dumps({"step": "process", "message": "⚠️ API 受限，启动 Playwright 嗅探..."}) + "\n"
        chain = await self.get_proxy_chain(network_type)
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 启动浏览器: [{name}]..."}) + "\n"
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=False, args=["--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                    page = await context.new_page()
                    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,otf}", lambda route: route.abort())
                    captured = []
                    page.on("request", lambda r: captured.append(r.url) if any(x in r.url for x in [".m4s", ".flv", ".mp4"]) else None)
                    await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    try: await page.click(".bilibili-player-video-wrap", timeout=2000)
                    except: pass
                    await asyncio.sleep(4)
                    cookies = await context.cookies()
                    GLOBAL_COOKIE_JAR[urlparse(url).netloc] = {c['name']: c['value'] for c in cookies}
                    final_video = max(captured, key=len) if captured else ""
                    if final_video:
                        title = await page.title()
                        yield json.dumps({"step": "process", "message": f"✅ 嗅探成功..."}) + "\n"
                        yield pd.DataFrame([{"类型": "标题", "内容": title.strip(), "备注": "Sniff-Title"}, {"类型": "视频", "内容": final_video, "备注": "Stream"}])
                        await browser.close(); return
                    await browser.close()
                except: continue
        yield json.dumps({"step": "error", "message": "❌ B站 任务失败"}) + "\n"

class YouTubeCrawler(BaseCrawler):
    async def crawl(self, url: str, network_type: str = "auto"):
        yield json.dumps({"step": "process", "message": "🟥 启动 YouTube 爬虫..."}) + "\n"
        MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        chain = await self.get_proxy_chain(network_type)
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 尝试节点: {name}..."}) + "\n"
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled", "--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=MOBILE_UA, viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
                    page = await context.new_page()
                    await page.route("**/*.{woff,woff2,ttf,otf}", lambda route: route.abort())
                    captured = []
                    page.on("request", lambda r: captured.append(r.url) if any(k in r.url for k in ["videoplayback", ".m3u8"]) else None)
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    try:
                        if await page.is_visible("button[aria-label='Reject all']"): await page.click("button[aria-label='Reject all']")
                        await page.tap("#player-container-id"); await page.tap(".html5-main-video")
                    except: pass
                    await asyncio.sleep(5)
                    final_video = ""
                    m3u8_list = [u for u in captured if "m3u8" in u]
                    if m3u8_list: final_video = m3u8_list[0]
                    elif captured:
                        candidates = [u for u in captured if "mime=audio" not in u]
                        final_video = max(candidates, key=len) if candidates else captured[0]
                    if final_video:
                        title = await page.title()
                        clean_title = title.replace(" - YouTube", "").strip()
                        yield json.dumps({"step": "process", "message": f"✅ 捕获成功..."}) + "\n"
                        yield pd.DataFrame([{"类型": "标题", "内容": clean_title, "备注": "Title"}, {"类型": "视频", "内容": final_video, "备注": "Stream"}])
                        await browser.close(); return
                    await browser.close()
                except: continue
        yield json.dumps({"step": "error", "message": "❌ YouTube 任务失败"}) + "\n"

class UniversalVideoCrawler(BaseCrawler):
    async def crawl(self, url: str, network_type: str = "auto"):
        yield json.dumps({"step": "process", "message": "🎬 启动通用视频嗅探..."}) + "\n"
        chain = await self.get_proxy_chain(network_type)
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 启动浏览器: [{name}]..."}) + "\n"
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=False, args=["--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                    page = await context.new_page()
                    await page.route("**/*", block_media_and_images)
                    captured = []
                    page.on("request", lambda r: captured.append(r.url) if any(x in r.url for x in [".m3u8", ".mp4"]) and not r.url.startswith("blob:") else None)
                    await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    try: await page.click("video, .player", timeout=2000)
                    except: pass
                    await asyncio.sleep(3)
                    cookies = await context.cookies()
                    domain = urlparse(url).netloc
                    GLOBAL_COOKIE_JAR[domain] = {c['name']: c['value'] for c in cookies}
                    if "missav" in domain: GLOBAL_COOKIE_JAR["missav.ws"] = GLOBAL_COOKIE_JAR[domain]
                    priority = [u for u in captured if ".m3u8" in u]
                    final_video = priority[0] if priority else (captured[0] if captured else "")
                    if not final_video:
                        if v := await page.query_selector("video"):
                            src = await v.get_attribute("src")
                            if src and src.startswith("http"): final_video = src
                    if final_video:
                        title = await page.title()
                        yield json.dumps({"step": "process", "message": f"✅ 嗅探成功..."}) + "\n"
                        yield pd.DataFrame([{"类型": "标题", "内容": title.strip(), "备注": "Title"}, {"类型": "视频", "内容": final_video, "备注": "Stream"}])
                        await browser.close(); return
                    await browser.close()
                except: continue
        yield json.dumps({"step": "error", "message": "❌ 未嗅探到视频流"}) + "\n"
