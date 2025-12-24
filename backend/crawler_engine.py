# backend/crawler_engine.py
import asyncio
import json
import requests
import re
import pandas as pd
import time
import random
import os
from urllib.parse import quote, unquote, urlparse, urljoin
from fastapi import APIRouter, Response, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
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
GLOBAL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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


# ==================== 核心网络工具 ====================
def request_with_chain(url, headers=None, stream=False, timeout=10, method="GET"):
    """通用请求内核：自动轮询 Hunter > Paid > Tor > Direct"""
    if headers is None: headers = {}
    headers.setdefault("User-Agent", GLOBAL_USER_AGENT)

    domain = urlparse(url).netloc
    cookies = GLOBAL_COOKIE_JAR.get(domain)

    # 获取标准链路
    chain = []
    if pool_manager:
        chain = pool_manager.get_standard_chain()
    chain.append((None, "Direct", 5))

    last_error = None

    for proxy_url, name, time_limit in chain:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        try:
            current_timeout = timeout if not proxy_url else time_limit + 5
            resp = requests.request(
                method, url, headers=headers, cookies=cookies, stream=stream,
                timeout=current_timeout, proxies=proxies, verify=False
            )
            # 412 是 B站风控，视为失败继续换 IP
            if resp.status_code in [200, 206, 302]:
                resp.network_name = name
                return resp
            elif resp.status_code in [403, 412, 429]:
                last_error = f"{name} Blocked ({resp.status_code})"
                continue
        except Exception as e:
            last_error = str(e)
            continue

    dummy = requests.Response()
    dummy.status_code = 500
    dummy.network_name = f"All Failed: {last_error}"
    return dummy


def parse_playwright_proxy(p_url):
    """Playwright 代理格式转换"""
    if not p_url: return None
    try:
        u = urlparse(p_url)
        return {"server": f"{u.scheme}://{u.hostname}:{u.port}", "username": u.username, "password": u.password}
    except:
        return None


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


# ==================== 1. B站 专用爬虫 (修复 412 风控) ====================
class BilibiliCrawler(BaseCrawler):
    def fetch_api_metadata(self, url):
        """B站 API 核心逻辑 (带风控检测)"""
        try:
            bvid_match = re.search(r"(BV\w+)", url)
            if not bvid_match: return None
            bvid = bvid_match.group(1)

            headers = {"User-Agent": GLOBAL_USER_AGENT, "Referer": "https://www.bilibili.com/"}

            # 1. 元数据 (如果返回 412，request_with_chain 会尝试换代理，如果都失败则返回 500)
            info_resp = request_with_chain(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
                                           headers=headers)
            if info_resp.status_code != 200: return None  # 可能是 412 风控

            data = info_resp.json().get('data')
            if not data: return None

            cid = data['cid']
            meta = {"title": data['title'], "cover": data['pic']}

            # 2. 视频流 (优先 MP4)
            play_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&fnval=1&platform=html5&high_quality=1"
            play_resp = request_with_chain(play_api, headers=headers)

            video_url = ""
            if play_resp.status_code == 200:
                p_data = play_resp.json()
                if p_data['code'] == 0 and 'durl' in p_data['data']:
                    video_url = p_data['data']['durl'][0]['url']

            # 3. 严格核验 (确保代理能拉动流)
            if video_url:
                v_headers = headers.copy()
                v_headers['Range'] = 'bytes=0-100'  # 只读前100字节
                check = request_with_chain(video_url, headers=v_headers, timeout=8)

                # 200 或 206 均表示连接成功
                if check.status_code in [200, 206]:
                    return {**meta, "video_url": video_url, "verified": True}

            return {**meta, "video_url": "", "verified": False}
        except Exception as e:
            print(f"Bili API Error: {e}")
            return None

    async def crawl(self, url: str):
        yield json.dumps({"step": "process", "message": "📺 启动 B站 专用爬虫..."}) + "\n"

        # 策略 A: API 秒开 (尝试获取直链)
        api_data = self.fetch_api_metadata(url)
        if api_data and api_data.get('verified'):
            yield json.dumps({"step": "process", "message": f"✅ API 解析成功: {api_data['title'][:15]}..."}) + "\n"
            results = [
                {"类型": "标题", "内容": api_data['title'], "备注": "API-Title"},
                {"类型": "图片", "内容": api_data['cover'], "备注": "Cover"},
                {"类型": "视频", "内容": api_data['video_url'], "备注": "Direct-Stream"}
            ]
            yield pd.DataFrame(results)
            return

        yield json.dumps(
            {"step": "process", "message": "⚠️ API 均被风控 (412) 或无效，降级到 Playwright 模拟真人..."}) + "\n"

        # 策略 B: 浏览器嗅探 (强力对抗 412)
        chain = await self.get_proxy_chain()
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 启动嗅探: [{name}]..."}) + "\n"

            async with async_playwright() as p:
                try:
                    # B站需要有头模式来加载播放器
                    browser = await p.chromium.launch(headless=False, args=["--mute-audio"], proxy=proxy_conf)
                    context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                    page = await context.new_page()

                    captured = []
                    # 监听所有可能的流媒体格式
                    page.on("request", lambda r: captured.append(r.url) if any(
                        x in r.url for x in [".m4s", ".flv", ".mp4"]) else None)

                    try:
                        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    except:
                        await browser.close(); continue

                    # 自动点击播放 (对抗懒加载)
                    await asyncio.sleep(3)
                    try:
                        await page.click(".bilibili-player-video-wrap", timeout=2000)
                    except:
                        pass

                    # 再等一会确保流开始传输
                    await asyncio.sleep(4)

                    # 提取 Cookie 供后续代理播放使用
                    cookies = await context.cookies()
                    GLOBAL_COOKIE_JAR[urlparse(url).netloc] = {c['name']: c['value'] for c in cookies}

                    # 优先取最长的 URL (通常是高画质)
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

        yield json.dumps({"step": "error", "message": "❌ B站 所有通道尝试失败，请检查网络或更新代理池"}) + "\n"


# ==================== 2. YouTube 专用爬虫 (模拟 iOS) ====================
class YouTubeCrawler(BaseCrawler):
    async def crawl(self, url: str):
        yield json.dumps({"step": "process", "message": "🟥 启动 YouTube 专用爬虫 (iOS 伪装)..."}) + "\n"

        # 定义 iOS UA
        MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

        chain = await self.get_proxy_chain()
        for proxy_url, name, _ in chain:
            proxy_conf = parse_playwright_proxy(proxy_url)
            yield json.dumps({"step": "process", "message": f"🌐 尝试节点: {name}..."}) + "\n"

            async with async_playwright() as p:
                try:
                    # 启动模拟手机的浏览器
                    browser = await p.chromium.launch(
                        headless=False,
                        args=["--disable-blink-features=AutomationControlled", "--mute-audio"],
                        proxy=proxy_conf
                    )
                    context = await browser.new_context(
                        user_agent=MOBILE_UA,  # 关键：爬虫也是这个 UA
                        viewport={"width": 375, "height": 812},
                        is_mobile=True,
                        has_touch=True,
                        ignore_https_errors=True
                    )
                    page = await context.new_page()

                    captured = []
                    # 监听 m3u8 和 videoplayback
                    page.on("request", lambda r: captured.append(r.url) if any(
                        k in r.url for k in ["videoplayback", ".m3u8"]) else None)

                    try:
                        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    except:
                        await browser.close(); continue

                    # 自动点击移动端弹窗
                    await asyncio.sleep(2)
                    try:
                        if await page.is_visible("button[aria-label='Reject all']"):
                            await page.click("button[aria-label='Reject all']")
                        # 移动端通常需要点击一下屏幕中间来播放
                        await page.tap("#player-container-id")
                        await page.tap(".html5-main-video")
                    except:
                        pass

                    await asyncio.sleep(5)

                    final_video = ""
                    # 优先 m3u8 (HLS)，其次 videoplayback
                    m3u8_list = [u for u in captured if "m3u8" in u]
                    if m3u8_list:
                        final_video = m3u8_list[0]
                    elif captured:
                        # 过滤掉仅音频流
                        candidates = [u for u in captured if "mime=audio" not in u]
                        final_video = max(candidates, key=len) if candidates else captured[0]

                    if final_video:
                        title = await page.title()
                        clean_title = title.replace(" - YouTube", "").strip()
                        yield json.dumps({"step": "process", "message": f"✅ YouTube 捕获成功 (HLS/MP4)..."}) + "\n"
                        yield pd.DataFrame([
                            {"类型": "标题", "内容": clean_title, "备注": "Title"},
                            {"类型": "视频", "内容": final_video, "备注": "Stream"}
                        ])
                        await browser.close();
                        return

                    await browser.close()
                except:
                    continue

        yield json.dumps({"step": "error", "message": "❌ YouTube 任务失败"}) + "\n"


# ==================== 3. 通用视频爬虫 (MissAV 等) ====================
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

                    captured = []
                    # 通用嗅探规则：m3u8, mp4
                    page.on("request", lambda r: captured.append(r.url) if any(
                        x in r.url for x in [".m3u8", ".mp4"]) and not r.url.startswith("blob:") else None)

                    try:
                        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    except:
                        await browser.close(); continue

                    await asyncio.sleep(3)
                    # 尝试点击播放 (通用选择器)
                    try:
                        await page.click("video, .player", timeout=2000)
                    except:
                        pass
                    await asyncio.sleep(3)

                    # 捕获 Cookie (MissAV 必须)
                    cookies = await context.cookies()
                    domain = urlparse(url).netloc
                    GLOBAL_COOKIE_JAR[domain] = {c['name']: c['value'] for c in cookies}
                    if "missav" in domain: GLOBAL_COOKIE_JAR["missav.ws"] = GLOBAL_COOKIE_JAR[domain]

                    # 优选 m3u8
                    priority = [u for u in captured if ".m3u8" in u]
                    final_video = priority[0] if priority else (captured[0] if captured else "")

                    if not final_video:
                        if v := await page.query_selector("video"):
                            src = await v.get_attribute("src")
                            if src and src.startswith("http"): final_video = src

                    if final_video:
                        title = await page.title()
                        yield json.dumps({"step": "process", "message": f"✅ 嗅探成功..."}) + "\n"
                        yield pd.DataFrame([
                            {"类型": "标题", "内容": title.strip(), "备注": "Title"},
                            {"类型": "视频", "内容": final_video, "备注": "Stream"}
                        ])
                        await browser.close();
                        return

                    await browser.close()
                except:
                    continue

        yield json.dumps({"step": "error", "message": "❌ 未嗅探到视频流"}) + "\n"


# ==================== 4. 极速文本爬虫 ====================
class GeneralTextCrawler(BaseCrawler):
    async def crawl(self, url: str):
        yield json.dumps({"step": "process", "message": "🚀 启动极速文本解析..."}) + "\n"
        random_delay()

        resp = request_with_chain(url)
        net_name = getattr(resp, "network_name", "未知")

        if resp.status_code != 200:
            yield json.dumps({"step": "error", "message": f"❌ 请求失败: {net_name} ({resp.status_code})"}) + "\n"
            return

        yield json.dumps({"step": "process", "message": f"🌐 通道: {net_name}"}) + "\n"

        if len(resp.text) < 500:
            yield json.dumps({"step": "process", "message": "⚠️ 页面内容过短"}) + "\n"

        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        data_list = []

        title = soup.title.string.strip() if soup.title else ""
        if title: data_list.append({"类型": "标题", "内容": title, "备注": "Meta-Title"})

        article = soup.find("div", class_="RichText") or soup.find("div", class_="markdown-body") or soup.find(
            "article") or soup.body
        if article:
            for tag in article(
                    ["script", "style", "noscript", "svg", "button", "input", "form", "nav", "footer", "iframe"]):
                tag.decompose()

            for tag in article.find_all(['p', 'h1', 'h2', 'h3', 'li']):
                txt = tag.get_text(strip=True)
                if len(txt) > 5:
                    data_list.append({"类型": tag.name.upper(), "内容": txt, "备注": "Text"})

        if data_list:
            yield pd.DataFrame(data_list)
        else:
            yield json.dumps({"step": "error", "message": "❌ 未提取到有效文本"}) + "\n"


# ==================== 工厂类 & 路由 ====================
class CrawlerFactory:
    @staticmethod
    def get_crawler(url: str, mode: str) -> BaseCrawler:
        is_video = is_video_site(url)

        if "bilibili.com" in url:
            return BilibiliCrawler()
        elif "youtube.com" in url or "youtu.be" in url:
            return YouTubeCrawler()
        elif is_video or mode == "media":
            return UniversalVideoCrawler()
        else:
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


# ==================== 视频流代理 (Referer 增强版) ====================
@router.get("/api/proxy")
# ==================== 视频流代理 (YouTube 专用优化) ====================

# ==================== 视频流代理 (修复 YouTube 播放) ====================
@router.get("/api/proxy")
async def proxy_stream(url: str, request: Request):
    target_url = unquote(url)
    parsed = urlparse(target_url)
    domain = parsed.netloc.lower()

    # 默认 PC UA
    current_ua = GLOBAL_USER_AGENT

    # 策略配置
    referer = f"{parsed.scheme}://{domain}/"
    origin = f"{parsed.scheme}://{domain}"

    if "bili" in domain:
        referer = "https://www.bilibili.com/"
    elif "missav" in domain or "surrit" in domain:
        referer = "https://missav.ws/"
        origin = "https://missav.ws"
    # 🔥🔥🔥 YouTube 专用修复 🔥🔥🔥
    elif "googlevideo" in domain or "youtube" in domain:
        referer = "https://www.youtube.com/"
        origin = "https://www.youtube.com"
        # 关键：必须和爬虫一样使用 iOS UA，否则 Google 会拒绝连接
        current_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

    headers = {
        "User-Agent": current_ua,
        "Referer": referer,
        "Origin": origin,
        "Range": request.headers.get("range", "bytes=0-")
    }

    # 代理链策略
    proxy_chain = []

    # YouTube 视频流通常绑定 IP，直连成功率反而最高（如果服务器在海外）
    # 或者必须使用极其稳定的梯子。这里尝试 直连 -> 代理池
    if "googlevideo" in domain:
        proxy_chain.append((None, "Direct Priority", 5))
        if pool_manager: proxy_chain.extend(pool_manager.get_standard_chain())
    else:
        if pool_manager: proxy_chain = pool_manager.get_standard_chain()
        proxy_chain.append((None, "Direct", 10))

    for proxy_url, name, timeout_sec in proxy_chain:
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            session = requests.Session()
            resp = session.get(
                target_url, headers=headers, cookies=GLOBAL_COOKIE_JAR.get(domain),
                stream=True, timeout=(5, timeout_sec), verify=False, proxies=proxies
            )

            # 过滤错误，特别是 403 (Google 常返回 403 代表链接失效或 IP 不对)
            if resp.status_code >= 400:
                continue

            # 过滤 HTML (有时候代理会返回登录页)
            content_type = resp.headers.get("content-type", "application/octet-stream")
            if "text/html" in content_type:
                continue

            # M3U8 代理重写 (关键：让分片也走这个代理接口)
            if "mpegurl" in content_type or ".m3u8" in target_url:
                new_lines = []
                for line in resp.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        new_lines.append(line)
                    else:
                        # 将 m3u8 里的相对/绝对路径都转回我们的代理接口
                        full_ts_url = urljoin(target_url, line)
                        proxy_ts_url = f"http://127.0.0.1:8000/api/proxy?url={quote(full_ts_url)}"
                        new_lines.append(proxy_ts_url)

                return Response(content="\n".join(new_lines), media_type=content_type)

            # 普通流媒体透传
            return StreamingResponse(
                resp.iter_content(chunk_size=64 * 1024),
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