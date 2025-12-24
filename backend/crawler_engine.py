# backend/crawler_engine.py
import asyncio
import json
import re
import pandas as pd
import time
import random
import os
import requests  # 🔥 坚定回归 Requests
from urllib.parse import quote, unquote, urlparse, urljoin
from fastapi import APIRouter, Response, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Route
from dotenv import load_dotenv
from abc import ABC, abstractmethod

# 引入代理池管理器
try:
    from proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

load_dotenv()

router = APIRouter(tags=["crawler"])

# ==================== 全局配置 ====================
# 🔥 升级：更真实的浏览器指纹，对抗 403
GLOBAL_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
GLOBAL_COOKIE_JAR = {}

VIDEO_SITES = [
    "missav", "missav.ws", "jable", "pornhub", "xvideos",
    "youtube", "youtu.be", "bilibili", "spankbang", "ddh", "jav", "hqporner"
]


class CrawlRequest(BaseModel):
    url: str
    mode: str = "auto"


def random_delay():
    time.sleep(random.uniform(0.5, 1.5))


def is_video_site(url: str) -> bool:
    return any(site in url.lower() for site in VIDEO_SITES)


# ==================== 🚀 核心修复：异步线程包裹 Requests ====================
async def async_request(method, url, **kwargs):
    """
    🔥 魔法函数：在异步环境中使用 requests 而不卡死服务器
    原理：将同步的 requests 操作扔到线程池中运行
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))


async def request_with_chain_async(url, headers=None, stream=False, timeout=10, method="GET"):
    """
    基于 requests 的异步代理链请求
    """
    if headers is None: headers = {}

    # 🔥 关键：补全高仿浏览器 Headers (解决 linux.do 403 问题)
    base_headers = {
        "User-Agent": GLOBAL_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }
    base_headers.update(headers)

    domain = urlparse(url).netloc
    cookies = GLOBAL_COOKIE_JAR.get(domain)

    # 获取标准链路 (Hunter -> Paid -> Tor -> Direct)
    chain = []
    if pool_manager:
        chain = pool_manager.get_standard_chain()

    # 最后才加 Direct (直连)
    chain.append((None, "Direct", 5))

    last_error = None
    failed_count = 0

    for proxy_url, name, time_limit in chain:
        try:
            current_timeout = timeout if not proxy_url else time_limit + 5

            # 构造 requests 格式代理字典
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

            # 🔥 放在线程池跑，不阻塞
            resp = await async_request(
                method,
                url,
                headers=base_headers,
                cookies=cookies,
                proxies=proxies,
                timeout=current_timeout,
                verify=False,  # 忽略 SSL 报错
                stream=stream
            )

            # 成功判定的状态码
            if resp.status_code in [200, 206, 302]:
                resp.network_name = name
                return resp
            elif resp.status_code in [403, 412, 429]:
                # 遇到风控，记录错误，继续尝试下一个
                last_error = f"{name} Blocked ({resp.status_code})"
                failed_count += 1
                continue
            else:
                last_error = f"{name} Error ({resp.status_code})"
                failed_count += 1
                continue

        except Exception as e:
            last_error = f"{name} Exception: {str(e)}"
            failed_count += 1
            continue

    # 构造失败响应
    class DummyResponse:
        status_code = 500
        text = ""
        content = b""
        network_name = f"Failed ({failed_count} paths tried). Last: {last_error}"

        def json(self): return {}

    return DummyResponse()


def parse_playwright_proxy(p_url):
    if not p_url: return None
    try:
        u = urlparse(p_url)
        return {"server": f"{u.scheme}://{u.hostname}:{u.port}", "username": u.username, "password": u.password}
    except:
        return None


# ==================== 辅助函数：资源拦截 ====================
async def block_media_and_images(route: Route):
    """拦截图片和字体，加速页面加载"""
    if route.request.resource_type in ["image", "font"]:
        await route.abort()
    else:
        await route.continue_()

async def block_aggressive(route: Route):
    """激进拦截：拦截图片、字体、媒体和样式表（用于纯文本提取）"""
    if route.request.resource_type in ["image", "font", "media", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()


# ==================== 爬虫基类 ====================
class BaseCrawler(ABC):
    @abstractmethod
    async def crawl(self, url: str):
        pass

    async def get_proxy_chain(self):
        chain = []
        if pool_manager: chain = pool_manager.get_standard_chain()
        chain.append((None, "Direct", 10))
        return chain


# ==================== 1. B站 专用爬虫 ====================
class BilibiliCrawler(BaseCrawler):
    async def fetch_api_metadata_async(self, url):
        try:
            bvid_match = re.search(r"(BV\w+)", url)
            if not bvid_match: return None
            bvid = bvid_match.group(1)

            # 🔥 修复 1: 使用具体的视频页作为 Referer
            headers = {"Referer": f"https://www.bilibili.com/video/{bvid}"}

            # 🔥 修复 2: 先访问一次主页获取 Cookie (这一步至关重要)
            # B站 API 需要 buvid3 等 cookie 才能正常返回数据
            await request_with_chain_async(url, headers=headers, method="HEAD")

            # 1. 元数据
            info_resp = await request_with_chain_async(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
                                                       headers=headers)
            if info_resp.status_code != 200: return None

            data = info_resp.json().get('data')
            if not data: return None

            cid = data['cid']
            meta = {"title": data['title'], "cover": data['pic']}

            # 2. 视频流
            play_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&fnval=1&platform=html5&high_quality=1"
            play_resp = await request_with_chain_async(play_api, headers=headers)

            video_url = ""
            if play_resp.status_code == 200:
                p_data = play_resp.json()
                if p_data['code'] == 0 and 'durl' in p_data['data']:
                    video_url = p_data['data']['durl'][0]['url']

            # 3. 严格核验
            if video_url:
                v_headers = headers.copy()
                v_headers['Range'] = 'bytes=0-100'
                check = await request_with_chain_async(video_url, headers=v_headers, timeout=8)
                if check.status_code in [200, 206]:
                    return {**meta, "video_url": video_url, "verified": True}

            return {**meta, "video_url": "", "verified": False}
        except Exception as e:
            return None

    async def crawl(self, url: str):
        yield json.dumps({"step": "process", "message": "📺 启动 B站 专用爬虫..."}) + "\n"

        api_data = await self.fetch_api_metadata_async(url)
        if api_data and api_data.get('verified'):
            yield json.dumps({"step": "process", "message": f"✅ API 解析成功: {api_data['title'][:15]}..."}) + "\n"
            results = [
                {"类型": "标题", "内容": api_data['title'], "备注": "API-Title"},
                {"类型": "图片", "内容": api_data['cover'], "备注": "Cover"},
                {"类型": "视频", "内容": api_data['video_url'], "备注": "Direct-Stream"}
            ]
            yield pd.DataFrame(results)
            return

        yield json.dumps({"step": "process", "message": "⚠️ API 受限，启动 Playwright 嗅探..."}) + "\n"

        chain = await self.get_proxy_chain()
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 启动浏览器: [{name}]..."}) + "\n"

            async with async_playwright() as p:
                try:
                    # B站可能需要 headful 模式来通过某些检查
                    browser = await p.chromium.launch(headless=False, args=["--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                    page = await context.new_page()

                    # 🔥 修复：B站视频流嗅探不能拦截 media，否则无法捕获 .m4s/.flv
                    # 仅拦截图片和字体
                    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,otf}", lambda route: route.abort())

                    captured = []
                    page.on("request", lambda r: captured.append(r.url) if any(
                        x in r.url for x in [".m4s", ".flv", ".mp4"]) else None)

                    try:
                        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    except:
                        await browser.close(); continue

                    await asyncio.sleep(3)
                    try:
                        await page.click(".bilibili-player-video-wrap", timeout=2000)
                    except:
                        pass
                    await asyncio.sleep(4)

                    cookies = await context.cookies()
                    GLOBAL_COOKIE_JAR[urlparse(url).netloc] = {c['name']: c['value'] for c in cookies}

                    final_video = max(captured, key=len) if captured else ""

                    if final_video:
                        title = await page.title()
                        yield json.dumps({"step": "process", "message": f"✅ 嗅探成功..."}) + "\n"
                        yield pd.DataFrame([
                            {"类型": "标题", "内容": title.strip(), "备注": "Sniff-Title"},
                            {"类型": "视频", "内容": final_video, "备注": "Stream"}
                        ])
                        await browser.close();
                        return
                    await browser.close()
                except:
                    continue

        yield json.dumps({"step": "error", "message": "❌ B站 任务失败"}) + "\n"


# ==================== 2. YouTube 专用爬虫 ====================
class YouTubeCrawler(BaseCrawler):
    async def crawl(self, url: str):
        yield json.dumps({"step": "process", "message": "🟥 启动 YouTube 爬虫..."}) + "\n"
        MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        chain = await self.get_proxy_chain()
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 尝试节点: {name}..."}) + "\n"
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=False,
                                                      args=["--disable-blink-features=AutomationControlled",
                                                            "--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=MOBILE_UA, viewport={"width": 375, "height": 812},
                                                        is_mobile=True, has_touch=True)
                    page = await context.new_page()

                    # YouTube 比较敏感，只拦截字体，保留图片可能有助于加载
                    await page.route("**/*.{woff,woff2,ttf,otf}", lambda route: route.abort())

                    captured = []
                    page.on("request", lambda r: captured.append(r.url) if any(
                        k in r.url for k in ["videoplayback", ".m3u8"]) else None)
                    try:
                        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    except:
                        await browser.close(); continue
                    await asyncio.sleep(2)
                    try:
                        if await page.is_visible("button[aria-label='Reject all']"): await page.click(
                            "button[aria-label='Reject all']")
                        await page.tap("#player-container-id");
                        await page.tap(".html5-main-video")
                    except:
                        pass
                    await asyncio.sleep(5)
                    final_video = ""
                    m3u8_list = [u for u in captured if "m3u8" in u]
                    if m3u8_list:
                        final_video = m3u8_list[0]
                    elif captured:
                        candidates = [u for u in captured if "mime=audio" not in u]
                        final_video = max(candidates, key=len) if candidates else captured[0]
                    if final_video:
                        title = await page.title()
                        clean_title = title.replace(" - YouTube", "").strip()
                        yield json.dumps({"step": "process", "message": f"✅ 捕获成功..."}) + "\n"
                        yield pd.DataFrame([{"类型": "标题", "内容": clean_title, "备注": "Title"},
                                            {"类型": "视频", "内容": final_video, "备注": "Stream"}])
                        await browser.close();
                        return
                    await browser.close()
                except:
                    continue
        yield json.dumps({"step": "error", "message": "❌ YouTube 任务失败"}) + "\n"


# ==================== 3. 通用视频爬虫 ====================
class UniversalVideoCrawler(BaseCrawler):
    async def crawl(self, url: str):
        yield json.dumps({"step": "process", "message": "🎬 启动通用视频嗅探..."}) + "\n"
        chain = await self.get_proxy_chain()
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 启动浏览器: [{name}]..."}) + "\n"
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=False, args=["--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                    page = await context.new_page()

                    # 拦截图片和字体
                    await page.route("**/*", block_media_and_images)

                    captured = []
                    page.on("request", lambda r: captured.append(r.url) if any(
                        x in r.url for x in [".m3u8", ".mp4"]) and not r.url.startswith("blob:") else None)
                    try:
                        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    except:
                        await browser.close(); continue
                    await asyncio.sleep(3)
                    try:
                        await page.click("video, .player", timeout=2000)
                    except:
                        pass
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
                        yield pd.DataFrame([{"类型": "标题", "内容": title.strip(), "备注": "Title"},
                                            {"类型": "视频", "内容": final_video, "备注": "Stream"}])
                        await browser.close();
                        return
                    await browser.close()
                except:
                    continue
        yield json.dumps({"step": "error", "message": "❌ 未嗅探到视频流"}) + "\n"


# ==================== 4. 极速文本爬虫 (Requests 版本) ====================
class GeneralTextCrawler(BaseCrawler):
    def extract_text_from_html(self, html):
        """还原旧版逻辑"""
        soup = BeautifulSoup(html, "html.parser")
        data_list = []

        title = soup.title.string.strip() if soup.title else ""
        if title: data_list.append({"类型": "标题", "内容": title, "备注": "Meta-Title"})

        article = soup.find("div", class_="RichText") or \
                  soup.find("div", class_="markdown-body") or \
                  soup.find("article") or \
                  soup.body

        if article:
            for tag in article(
                    ["script", "style", "noscript", "svg", "button", "input", "form", "nav", "footer", "iframe"]):
                tag.decompose()

            for tag in article.find_all(['p', 'h1', 'h2', 'h3', 'li']):
                txt = tag.get_text(strip=True)
                if len(txt) > 5:  # 还原阈值
                    data_list.append({"类型": tag.name.upper(), "内容": txt, "备注": "Text"})
        return data_list

    async def extract_text_async(self, html):
        """🔥 优化：将 CPU 密集的 BeautifulSoup 解析放入线程池，避免阻塞事件循环"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.extract_text_from_html, html)

    async def crawl(self, url: str):
        yield json.dumps({"step": "process", "message": "🚀 启动极速文本解析 (Requests)..."}) + "\n"
        await asyncio.sleep(random.uniform(0.5, 1.5))

        # 1. 尝试 requests (线程池执行)
        resp = await request_with_chain_async(url)
        net_name = getattr(resp, "network_name", "未知")

        data_list = []
        if resp.status_code == 200:
            resp.encoding = 'utf-8'
            if len(resp.text) > 500:
                # 使用异步包装的解析函数
                data_list = await self.extract_text_async(resp.text)

        # 成功则直接返回
        if data_list:
            yield json.dumps({"step": "process", "message": f"🌐 静态提取成功 ({net_name})"}) + "\n"
            yield pd.DataFrame(data_list)
            return

        # 2. 如果 requests 失败，启动浏览器兜底
        yield json.dumps({"step": "process", "message": f"⚠️ 静态抓取失败 ({net_name})，启动浏览器渲染..."}) + "\n"

        chain = await self.get_proxy_chain()
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 渲染节点: {name}..."}) + "\n"

            async with async_playwright() as p:
                try:
                    # 文本爬取可以使用 headless=True，速度更快
                    browser = await p.chromium.launch(headless=True, args=["--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                    page = await context.new_page()

                    # 🔥 优化：激进拦截图片、字体、媒体和CSS，极大提升加载速度
                    await page.route("**/*", block_aggressive)

                    try:
                        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                        await asyncio.sleep(3)
                    except:
                        await browser.close(); continue

                    content = await page.content()
                    # 同样使用异步解析
                    data_list = await self.extract_text_async(content)

                    if data_list:
                        yield json.dumps({"step": "process", "message": "✅ 深度渲染提取成功"}) + "\n"
                        yield pd.DataFrame(data_list)
                        await browser.close();
                        return
                    await browser.close()
                except:
                    continue

        yield json.dumps({"step": "error", "message": "❌ 最终失败：无法提取有效文本"}) + "\n"


# ==================== 工厂类 & 路由 ====================
class CrawlerFactory:
    @staticmethod
    def get_crawler(url: str, mode: str) -> BaseCrawler:
        if "bilibili.com" in url:
            return BilibiliCrawler()
        elif "youtube.com" in url or "youtu.be" in url:
            return YouTubeCrawler()
        elif is_video_site(url) or mode == "media":
            return UniversalVideoCrawler()
        return GeneralTextCrawler()


async def smart_router(url: str, mode: str):
    yield json.dumps({"step": "init", "message": f"任务启动: {url} [Mode: {mode}]"}) + "\n"
    await asyncio.sleep(0.5)

    crawler = CrawlerFactory.get_crawler(url, mode)

    try:
        df = pd.DataFrame()
        async for chunk in crawler.crawl(url):
            if isinstance(chunk, pd.DataFrame):
                df = pd.concat([df, chunk], ignore_index=True)
            else:
                yield chunk

        if not df.empty:
            filename = f"data_{int(time.time())}.csv"
            filepath = os.path.abspath(filename)
            df.to_csv(filepath, index=False, encoding="utf-8-sig")
            download_url = f"http://127.0.0.1:8000/download/{filename}"
            yield json.dumps({"step": "done", "download_url": download_url}) + "\n"
        else:
            yield json.dumps({"step": "error", "message": "结果为空"}) + "\n"

    except Exception as e:
        yield json.dumps({"step": "error", "message": f"系统错误: {str(e)}"}) + "\n"


# ==================== 视频流代理 ====================
@router.get("/api/proxy")
async def proxy_stream(url: str, request: Request):
    target_url = unquote(url)
    parsed = urlparse(target_url)
    domain = parsed.netloc.lower()
    current_ua = GLOBAL_USER_AGENT
    referer = f"{parsed.scheme}://{domain}/"
    origin = f"{parsed.scheme}://{domain}"

    if "youtube" in domain:
        current_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

    # 🍪 修复 Cookie 跨域问题：bilivideo.com 需要使用 bilibili.com 的 Cookie
    req_cookies = GLOBAL_COOKIE_JAR.get(domain)
    if not req_cookies and ("bilivideo.com" in domain or "bilibili" in domain):
        # 尝试从主站域名获取 Cookie
        req_cookies = GLOBAL_COOKIE_JAR.get("www.bilibili.com") or GLOBAL_COOKIE_JAR.get("bilibili.com")

    # 🔥 紧急修复：B站视频流防盗链处理
    if "bilivideo.com" in domain or "bilibili" in domain:
        referer = "https://www.bilibili.com/"
        origin = "https://www.bilibili.com"

    headers = {"User-Agent": current_ua, "Referer": referer, "Origin": origin,
               "Range": request.headers.get("range", "bytes=0-")}

    # 🛡️ 增强：添加浏览器 Fetch 头，伪装成真实的视频播放请求
    headers.update({
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "Accept-Encoding": "identity",  # 视频流不需要 gzip
        "Connection": "keep-alive"
    })

    chain = []
    if pool_manager: chain = pool_manager.get_standard_chain()
    chain.append((None, "Direct", 10))

    for proxy_url, name, timeout_sec in chain:
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            loop = asyncio.get_running_loop()

            # 使用 requests 获取流，不读取内容，只获取 headers 和 iterator
            resp = await loop.run_in_executor(None, lambda: requests.get(
                target_url, headers=headers, cookies=req_cookies,
                stream=True, timeout=(5, timeout_sec), verify=False, proxies=proxies
            ))

            if resp.status_code >= 400: continue

            content_type = resp.headers.get("content-type", "application/octet-stream")

            # 如果是 m3u8 播放列表，需要重写内部的 TS 链接
            if "mpegurl" in content_type or ".m3u8" in target_url:
                text = resp.text # 这里会读取内容，但 m3u8 通常很小
                new_lines = []
                for line in text.splitlines():
                    if line and not line.startswith("#"):
                        full_ts = urljoin(target_url, line.strip())
                        line = f"http://127.0.0.1:8000/api/proxy?url={quote(full_ts)}"
                    new_lines.append(line)
                return Response(content="\n".join(new_lines), media_type=content_type)

            # 流式传输内容
            def iter_content():
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    yield chunk

            return StreamingResponse(
                iter_content(),
                status_code=resp.status_code,
                headers={
                    "Content-Type": content_type,
                    "Content-Range": resp.headers.get("Content-Range"),
                    "Content-Length": resp.headers.get("Content-Length"),
                    "Accept-Ranges": "bytes"
                },
                media_type=content_type
            )
        except:
            continue

    return Response(status_code=502, content="Stream Failed")


@router.post("/api/crawl")
async def start_crawl(request: CrawlRequest):
    return StreamingResponse(smart_router(request.url, request.mode), media_type="application/x-ndjson")


@router.get("/download/{filename}")
async def download_file(filename: str):
    filepath = os.path.abspath(filename)
    if os.path.exists(filepath): return FileResponse(filepath, filename=filename)
    return Response("File not found", status_code=404)
