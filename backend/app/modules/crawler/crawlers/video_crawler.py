# backend/app/modules/crawler/crawlers/video_crawler.py
import asyncio
import json
import re
import requests
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Route
from abc import ABC, abstractmethod
import pandas as pd
import random

GLOBAL_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
GLOBAL_COOKIE_JAR = {}

class BaseCrawler(ABC):
    def __init__(self, pool_manager=None):
        self.pool_manager = pool_manager

    @abstractmethod
    async def crawl(self, url: str, network_type: str = "auto"):
        pass

    async def get_proxy_chain(self, network_type: str = "auto"):
        chain = []
        
        if network_type == "direct":
            chain.append((None, "Direct", 10))
            return chain

        if self.pool_manager:
            # 🔥 核心修复：获取所有节点，但在内部过滤
            if network_type in ["node", "auto"] and self.pool_manager.node_provider:
                try:
                    all_nodes = self.pool_manager.node_provider()
                    socks_nodes = [n for n in all_nodes if n.get('protocol') in ['socks5', 'socks']]
                    if socks_nodes:
                        selected_nodes = random.sample(socks_nodes, min(len(socks_nodes), 3))
                        for node in selected_nodes:
                            chain.append((f"socks5://{node['host']}:{node['port']}", f"🛰️ Node-{node['host']}", 15))
                except Exception as e:
                    print(f"Error getting nodes: {e}")
            
            if network_type in ["proxy", "auto"]:
                alive_nodes = [p for p in self.pool_manager.proxies if p.score > 0]
                if alive_nodes:
                    selected = random.sample(alive_nodes, min(len(alive_nodes), 3))
                    for p in selected:
                        chain.append((p.to_url(), f"🌐 Proxy-{p.ip}", 10))
        
        if network_type == "auto" or not chain:
            chain.append((None, "Direct (Fallback)", 10))
            
        return chain

    async def get_playwright_proxy(self, network_type="auto"):
        if network_type == "direct":
            return None, "Direct"

        proxy_config = None
        proxy_name = None
        
        if self.pool_manager:
            # 🔥 核心修复：获取所有节点，但在内部过滤
            if network_type in ["node", "auto"]:
                if self.pool_manager.node_provider:
                    try:
                        all_nodes = self.pool_manager.node_provider()
                        socks_nodes = [n for n in all_nodes if n.get('protocol') in ['socks5', 'socks']]
                        if socks_nodes:
                            node = random.choice(socks_nodes[:5])
                            proxy_config = {"server": f"socks5://{node['host']}:{node['port']}"}
                            proxy_name = f"🛰️ Node-{node['host']}"
                            return proxy_config, proxy_name
                    except: pass
            
            if network_type in ["proxy", "auto"]:
                alive_nodes = [p for p in self.pool_manager.proxies if p.score > 0]
                if alive_nodes:
                    p = random.choice(sorted(alive_nodes, key=lambda p: p.score, reverse=True)[:10])
                    proxy_config = {"server": p.to_url()}
                    proxy_name = f"🌐 Proxy-{p.ip}"
                    return proxy_config, proxy_name

        if network_type == "node" and not proxy_config:
             return None, "No SOCKS5 Nodes"

        return None, "Direct (Fallback)"

async def async_request(method, url, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))

async def request_with_chain_async(url, chain, headers=None, stream=False, timeout=10, method="GET"):
    if headers is None: headers = {}
    base_headers = {
        "User-Agent": GLOBAL_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    base_headers.update(headers)

    if not chain:
        return None

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
            
            api_chain = await self.get_proxy_chain(network_type)
            
            info_resp = await request_with_chain_async(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", api_chain, headers=headers)
            
            if not info_resp or info_resp.status_code != 200: return None
            
            data = info_resp.json().get('data')
            if not data: return None
            cid = data['cid']
            meta = {"title": data['title'], "cover": data['pic']}
            play_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&fnval=1&platform=html5&high_quality=1"
            
            play_resp = await request_with_chain_async(play_api, api_chain, headers=headers)

            video_url = ""
            if play_resp and play_resp.status_code == 200 and play_resp.json().get('code') == 0:
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
            yield json.dumps({"step": "process", "message": f"✅ API 解析成功..."}) + "\n"
            results = [{"类型": "标题", "内容": api_data['title'], "备注": "API-Title"}, {"类型": "图片", "内容": api_data['cover'], "备注": "Cover"}, {"类型": "视频", "内容": api_data['video_url'], "备注": "Direct-Stream"}]
            yield pd.DataFrame(results)
            return
        yield json.dumps({"step": "process", "message": "⚠️ API 受限，启动 Playwright 嗅探..."}) + "\n"
        
        proxy_conf, proxy_name = await self.get_playwright_proxy(network_type)
        
        yield json.dumps({"step": "process", "message": f"🌐 启动浏览器: [{proxy_name}]..."}) + "\n"
        
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
            except: pass
        yield json.dumps({"step": "error", "message": "❌ B站 任务失败"}) + "\n"

class YouTubeCrawler(BaseCrawler):
    async def crawl(self, url: str, network_type: str = "auto"):
        yield json.dumps({"step": "process", "message": "🟥 启动 YouTube 爬虫..."}) + "\n"
        MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        
        proxy_conf, proxy_name = await self.get_playwright_proxy(network_type)
        
        yield json.dumps({"step": "process", "message": f"🌐 尝试节点: {proxy_name}..."}) + "\n"
        
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
            except: pass
        yield json.dumps({"step": "error", "message": "❌ YouTube 任务失败"}) + "\n"

class UniversalVideoCrawler(BaseCrawler):
    async def crawl(self, url: str, network_type: str = "auto"):
        yield json.dumps({"step": "process", "message": "🎬 启动通用视频嗅探..."}) + "\n"
        
        chain = await self.get_proxy_chain(network_type)
        
        for proxy_url, name, _ in chain:
            yield json.dumps({"step": "process", "message": f"🌐 启动浏览器: [{name}]..."}) + "\n"
            proxy_conf = parse_playwright_proxy(proxy_url)
            
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=False, args=["--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                    page = await context.new_page()
                    await page.route("**/*", block_media_and_images)
                    
                    captured = []
                    page.on("request", lambda r: captured.append(r.url) if any(x in r.url for x in [".m3u8", ".mp4"]) and not r.url.startswith("blob:") else None)
                    
                    try:
                        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    except Exception as e:
                        yield json.dumps({"step": "process", "message": f"⚠️ 页面加载失败 ({name}): {str(e)[:50]}..."}) + "\n"
                        await browser.close()
                        continue 

                    await asyncio.sleep(3)
                    
                    try:
                        await page.click(".plyr__poster", timeout=2000)
                        await page.click("button[class*='play']", timeout=1000)
                    except: pass
                    
                    await asyncio.sleep(3)
                    
                    for frame in page.frames:
                        try:
                            if await frame.query_selector("video"):
                                src = await frame.eval_on_selector("video", "el => el.src")
                                if src: captured.append(src)
                        except: pass

                    content = await page.content()
                    m3u8_matches = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', content)
                    if m3u8_matches:
                        captured.extend(m3u8_matches)

                    priority = [u for u in captured if ".m3u8" in u]
                    final_video = priority[0] if priority else (captured[0] if captured else "")

                    if not final_video:
                        if v := await page.query_selector("video"):
                            src = await v.get_attribute("src")
                            if src and src.startswith("http"): final_video = src
                    
                    if final_video:
                        # 🔥 核心修复：增强标题提取逻辑
                        title = "Unknown Title"
                        try:
                            # 1. 尝试 og:title
                            title = await page.eval_on_selector("meta[property='og:title']", "el => el.content")
                        except:
                            try:
                                # 2. 尝试 h1
                                title = await page.inner_text("h1")
                            except:
                                try:
                                    # 3. 回退到 page.title()
                                    title = await page.title()
                                except: pass

                        cover = "No Cover"
                        try:
                            cover = await page.eval_on_selector("meta[property='og:image']", "el => el.content")
                        except:
                            try:
                                cover = await page.eval_on_selector("video", "el => el.poster")
                            except: pass

                        yield json.dumps({"step": "process", "message": f"✅ 嗅探成功..."}) + "\n"
                        yield pd.DataFrame([
                            {"类型": "标题", "内容": title.strip(), "备注": "Title"}, 
                            {"类型": "图片", "内容": cover, "备注": "Cover"},
                            {"类型": "视频", "内容": final_video, "备注": url}
                        ])
                        await browser.close()
                        return 
                    
                    await browser.close()
            except Exception as e:
                yield json.dumps({"step": "process", "message": f"⚠️ 浏览器异常 ({name}): {str(e)[:50]}..."}) + "\n"
                continue

        yield json.dumps({"step": "error", "message": "❌ 未嗅探到视频流 (所有尝试均失败)"}) + "\n"
