import asyncio
import json
import requests
import re
import pandas as pd
import time
import random
import os
from urllib.parse import quote, unquote, urlparse, urljoin
from fastapi import FastAPI, Response, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from alchemy_engine import router as alchemy_router
from fake_useragent import UserAgent
from proxy_engine import router as proxy_router
from proxy_engine import manager as pool_manager  # <--- 新增这行
from node_hunter import router as node_router
from dotenv import load_dotenv

load_dotenv()  # 加载.env

# ==================== 配置区域 ====================

# 🔥【已配置】你的付费代理地址 (全站优先)
PAID_PROXY_URL = os.getenv("PAID_PROXY_URL")

# 🔥【已配置】Tor 备用
USE_TOR_BACKUP = True
TOR_PROXIES = {
    "http": f"socks5h://{os.getenv('TOR_HOST', '127.0.0.1')}:{os.getenv('TOR_PORT', '9050')}",
    "https": f"socks5h://{os.getenv('TOR_HOST', '127.0.0.1')}:{os.getenv('TOR_PORT', '9050')}"
}

# 全局统一 User-Agent (模拟 Chrome 120)
GLOBAL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 国内直连白名单
DOMESTIC_KEYWORDS = [
    "juejin.cn", "cn-bj.ufileos.com", "csdn.net", "zhihu.com",
    "weibo.com", "baidu.com", "taobao.com", "qq.com", "cnblogs.com", "douban.com"
]

VIDEO_SITES = [
    "missav", "missav.ws", "jable", "pornhub", "xvideos",
    "youtube", "bilibili", "spankbang", "ddh", "jav"
]

# 🔥 全局 Cookie 缓存 (关键：用于将 Playwright 的 Cookie 传给视频流)
GLOBAL_COOKIE_JAR = {}


# ==================== 辅助函数 ====================

def is_domestic(url: str) -> bool:
    return any(keyword in url for keyword in DOMESTIC_KEYWORDS)


def is_video_site(url: str) -> bool:
    return any(site in url.lower() for site in VIDEO_SITES)


def random_delay(min_sec=0.5, max_sec=1.5):
    time.sleep(random.uniform(min_sec, max_sec))

# ... (random_delay 函数结束)

# 🔥 新增以下两个函数：
def get_pool_config():
    """从 IP 池获取 requests 用的配置"""
    if not pool_manager.proxies: return None
    # 负载均衡：从速度最快的 Top 20 里随机选一个
    top_n = min(len(pool_manager.proxies), 20)
    choice = random.choice(pool_manager.proxies[:top_n])
    p_str = f"http://{choice.ip}:{choice.port}"
    return {"http": p_str, "https": p_str}

def get_pool_config_browser():
    """从 IP 池获取 Playwright 用的配置"""
    if not pool_manager.proxies: return None
    top_n = min(len(pool_manager.proxies), 20)
    choice = random.choice(pool_manager.proxies[:top_n])
    return {"server": f"http://{choice.ip}:{choice.port}"}

# ==================== 智能网络请求 ====================
def fetch_smart(url, headers=None, stream=False, timeout=15):
    if headers is None:
        headers = {"User-Agent": GLOBAL_USER_AGENT}
    else:
        headers["User-Agent"] = GLOBAL_USER_AGENT

    # 尝试注入 Cookie
    domain = urlparse(url).netloc
    cookies = None
    # 模糊匹配 Cookie
    for d, c in GLOBAL_COOKIE_JAR.items():
        if d in domain or domain in d:
            cookies = c
            break

    # 1. 国内直连
    if is_domestic(url):
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, stream=stream, timeout=timeout, proxies=None,
                                verify=False)
            resp.network_name = "直连 (国内)"
            return resp
        except:
            pass

    # 策略列表
    strategies = []
    # 1. 付费代理 (第一顺位)
    if PAID_PROXY_URL:
        strategies.append(({"http": PAID_PROXY_URL, "https": PAID_PROXY_URL}, "付费代理"))

    # 🔥 2. 猎手 IP 池 (新增：第二顺位)
    pool_proxy = get_pool_config()
    if pool_proxy:
        strategies.append((pool_proxy, "猎手IP池"))

    # 3. Tor (第三顺位)
    if USE_TOR_BACKUP:
        strategies.append((TOR_PROXIES, "Tor网络"))

    # 4. 直连 (兜底)
    strategies.append((None, "直连 (兜底)"))

    last_err = None
    for proxies, name in strategies:
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, stream=stream, timeout=timeout, proxies=proxies,
                                verify=False)
            if resp.status_code != 403:
                resp.network_name = name
                return resp
        except Exception as e:
            last_err = e
            pass

    dummy = requests.Response()
    dummy.status_code = 500
    dummy.network_name = "全部失败"
    return dummy


# ==================== B站专用 API ====================
def parse_bilibili_api(url):
    try:
        bvid_match = re.search(r"(BV\w+)", url)
        if not bvid_match: return None
        bvid = bvid_match.group(1)

        headers = {
            "User-Agent": GLOBAL_USER_AGENT,
            "Referer": "https://www.bilibili.com/"
        }

        info_resp = fetch_smart(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=headers).json()
        if info_resp.get('code') != 0: return None

        data = info_resp['data']
        cid = data['cid']
        title = data['title']
        cover = data['pic']

        play_url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&fnval=1&platform=html5&high_quality=1"
        play_resp = fetch_smart(play_url, headers=headers).json()
        if play_resp.get('code') != 0: return None

        video_url = play_resp['data']['durl'][0]['url']
        return {"title": title, "cover": cover, "video_url": video_url}
    except Exception as e:
        print(f"API Error: {e}")
        return None


# ==================== FastAPI 应用 ====================
app = FastAPI()

app.include_router(proxy_router)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.include_router(alchemy_router)

app.include_router(node_router)


class CrawlRequest(BaseModel):
    url: str
    mode: str = "auto"


# ==========================================
# 🔥 核心：完美伪装视频流代理
# ==========================================
@app.get("/api/proxy")
async def proxy_stream(url: str, request: Request):
    target_url = unquote(url)
    method = request.method
    parsed = urlparse(target_url)
    domain = parsed.netloc.lower()
    full_url = target_url.lower()

    # 1. 智能 Referer
    referer = f"{parsed.scheme}://{domain}/"
    if any(k in full_url for k in ["bilibili", "bilivideo", "akamaized", "upos", "hdslb"]):
        referer = "https://www.bilibili.com/"
    elif "jable" in domain:
        referer = "https://jable.tv/"
    elif any(k in domain for k in
             ["missav", "surrit", "tsyndicate", "svacdn", "saawsedge", "sixy", "ahcdn", "growcdn", "fourhoi"]):
        referer = "https://missav.ws/"

    # 2. 🔥 浏览器级 Headers (欺骗 CDN)
    headers = {
        "User-Agent": GLOBAL_USER_AGENT,
        "Referer": referer,
        "Origin": f"{parsed.scheme}://{domain}",
        "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "video",  # 明确告诉服务器我是来拉视频的
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Accept-Encoding": "identity"  # 禁止压缩
    }

    if request.headers.get("range"):
        headers["Range"] = request.headers.get("range")

    # 3. Cookie 注入 (至关重要)
    cookies = GLOBAL_COOKIE_JAR.get(domain)
    # 如果没找到具体域名的 cookie，试试主站的
    if not cookies and "missav" in referer:
        cookies = GLOBAL_COOKIE_JAR.get("missav.ws")

    # 4. 代理策略
    proxy_chain = []
    # 1. 付费代理
    if PAID_PROXY_URL:
        proxy_chain.append(({"http": PAID_PROXY_URL, "https": PAID_PROXY_URL}, "PaidProxy", 30))

    # 🔥 2. 猎手 IP 池 (新增)
    pool_proxy = get_pool_config()
    if pool_proxy:
        proxy_chain.append((pool_proxy, "HunterPool", 30))

    # 3. Tor
    if USE_TOR_BACKUP:
        proxy_chain.append((TOR_PROXIES, "TorNetwork", 40))

    # 4. 直连
    proxy_chain.append((None, "DirectConnect", 20))

    last_error = None

    for proxies, name, timeout_sec in proxy_chain:
        try:
            print(f"🌊 [Stream] {name} -> {domain} ...")
            session = requests.Session()
            resp = session.request(
                method=method,
                url=target_url,
                headers=headers,
                cookies=cookies,  # 带上通行证
                stream=True,
                timeout=(5, timeout_sec),
                verify=False,
                proxies=proxies
            )

            # 状态码检查
            if resp.status_code >= 400:
                print(f"⚠️ [Stream] {name} 失败: {resp.status_code}")
                last_error = f"Status {resp.status_code}"
                continue

            # 🔥 内容类型检查 (防止把 Cloudflare 的 HTML 错误页当视频发给前端)
            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                print(f"⚠️ [Stream] {name} 返回了 HTML (可能是 Cloudflare 拦截)，视为失败。")
                last_error = "Blocked by Cloudflare (HTML response)"
                continue

            # 成功！开始传输
            print(f"✅ [Stream] {name} 连接成功! Content-Type: {content_type}")

            # M3U8 重写
            if method == "GET" and (".m3u8" in target_url or "mpegurl" in content_type):
                content = resp.text
                base_url = target_url.rsplit('/', 1)[0] + "/"
                new_lines = []
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        new_lines.append(line)
                    else:
                        abs_url = urljoin(base_url, line)
                        proxy_url = f"http://127.0.0.1:8000/api/proxy?url={quote(abs_url)}"
                        new_lines.append(proxy_url)
                return Response(content="\n".join(new_lines), media_type="application/vnd.apple.mpegurl")

            response_headers = {
                "Access-Control-Allow-Origin": "*",
                "Accept-Ranges": "bytes",
                "Content-Type": content_type
            }
            if "Content-Range" in resp.headers: response_headers["Content-Range"] = resp.headers["Content-Range"]
            if "Content-Length" in resp.headers: response_headers["Content-Length"] = resp.headers["Content-Length"]

            return StreamingResponse(
                resp.iter_content(chunk_size=32 * 1024),
                status_code=resp.status_code,
                headers=response_headers,
                media_type=content_type
            )

        except Exception as e:
            last_error = str(e)
            continue

    print(f"🔥 [Stream] Fail: {target_url} | {last_error}")
    return Response(status_code=502, content=f"Stream Error: {last_error}")


# ==========================================
# 引擎 A: 极速引擎
# ==========================================
async def engine_lightweight(url: str):
    if is_video_site(url):
        yield json.dumps({"step": "error", "message": "⚠️ 视频网站请切换到 [深度媒体] 模式。"}) + "\n"
        return

    yield json.dumps({"step": "process", "message": f"🚀 启动极速引擎..."}) + "\n"
    random_delay()

    if "reddit.com" in url:
        clean_url = url.split('?')[0].rstrip('/') + ".json"
        try:
            resp = fetch_smart(clean_url)
            net_name = getattr(resp, "network_name", "未知")
            yield json.dumps({"step": "process", "message": f"🌐 通道: {net_name}"}) + "\n"

            if resp.status_code == 200:
                data = resp.json()
                post = data[0]['data']['children'][0]['data']
                comments = data[1]['data']['children']
                data_list = []
                data_list.append({"类型": "标题", "内容": post.get('title', 'No Title'), "备注": "Reddit-JSON"})
                data_list.append({"类型": "正文", "内容": post.get('selftext', ''), "备注": "Reddit-Post"})

                count = 0
                for child in comments:
                    if count >= 50: break
                    body = child.get('data', {}).get('body', '')
                    if body:
                        data_list.append({"类型": "评论", "内容": body, "备注": f"Comment-{count + 1}"})
                        count += 1
                yield pd.DataFrame(data_list)
                return
        except:
            pass

    try:
        resp = fetch_smart(url)
        net_name = getattr(resp, "network_name", "未知")
        yield json.dumps({"step": "process", "message": f"🌐 通道: {net_name}"}) + "\n"

        if len(resp.text) < 500:
            yield json.dumps({"step": "process", "message": "⚠️ 警告：页面内容过短。"}) + "\n"

        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        data_list = []
        title = soup.title.string.strip() if soup.title else ""
        if title: data_list.append({"类型": "标题", "内容": title, "备注": "Meta-Title"})

        article = soup.find("div", class_="RichText") or soup.find("div", class_="markdown-body") or soup.find(
            "article") or soup.body
        if article:
            for tag in article(["script", "style", "noscript", "svg", "button", "input", "form", "nav", "footer"]):
                tag.decompose()
            for tag in article.find_all(['p', 'h1', 'h2', 'h3', 'li', 'code', 'pre']):
                txt = tag.get_text(strip=True)
                if len(txt) > 5:
                    data_list.append({"类型": tag.name.upper(), "内容": txt, "备注": "Text"})

        yield pd.DataFrame(data_list)
    except Exception as e:
        yield json.dumps({"step": "error", "message": f"引擎错误: {str(e)}"}) + "\n"


# ==========================================
# 引擎 B: 深度引擎 (Playwright)
# ==========================================
async def engine_heavyweight(url: str):
    url = url.strip()
    is_video = is_video_site(url)
    is_bilibili = "bilibili.com" in url

    mode_msg = "B站API/桌面模式" if is_bilibili else ("视频流嗅探模式" if is_video else "全站渲染模式")
    yield json.dumps({"step": "process", "message": f"🚜 启动 Playwright [{mode_msg}]..."}) + "\n"

    if is_bilibili:
        yield json.dumps({"step": "process", "message": "尝试调用 B站官方 API..."}) + "\n"
        api_data = parse_bilibili_api(url)
        if api_data:
            yield json.dumps({"step": "process", "message": f"✅ API 解析成功: {api_data['title'][:20]}..."}) + "\n"
            results = [
                {"类型": "标题", "内容": api_data['title'], "备注": "API-Title"},
                {"类型": "视频", "内容": api_data['video_url'], "备注": api_data['cover']},
                {"类型": "图片", "内容": api_data['cover'], "备注": "Cover"}
            ]
            yield pd.DataFrame(results)
            return

    launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--ignore-certificate-errors",
                   "--disable-infobars", "--window-size=1920,1080"]

    def get_proxy_config(proxy_url):
        try:
            parsed = urlparse(proxy_url)
            return {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}", "username": parsed.username,
                    "password": parsed.password}
        except:
            return None

    attempts = []
    # 1. 付费代理
    if PAID_PROXY_URL:
        attempts.append((get_proxy_config(PAID_PROXY_URL), "付费代理"))

    # 🔥 2. 猎手 IP 池 (新增)
    pool_conf = get_pool_config_browser()
    if pool_conf:
        attempts.append((pool_conf, "猎手IP池"))

    # 3. Tor
    if USE_TOR_BACKUP:
        attempts.append(({"server": "socks5://127.0.0.1:9050"}, "Tor网络"))

    # 4. 直连
    attempts.append((None, "本机直连"))

    for proxy_conf, proxy_name in attempts:
        yield json.dumps({"step": "process", "message": f"🌐 启动浏览器: [{proxy_name}]..."}) + "\n"

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=False, args=launch_args, proxy=proxy_conf)
                context = await browser.new_context(user_agent=GLOBAL_USER_AGENT,
                                                    viewport={'width': 1920, 'height': 1080}, locale="en-US")
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")

                page = await context.new_page()
                captured_videos = []
                page.on("request", lambda r: captured_videos.append(r.url) if any(
                    x in r.url for x in [".m3u8", ".mp4", ".flv"]) else None)

                try:
                    await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                except Exception as e:
                    print(f"{proxy_name} timeout: {e}")
                    await browser.close()
                    continue

                # Cloudflare check
                title = await page.title()
                if "Just a moment" in title or "Verify" in await page.content():
                    yield json.dumps({"step": "process", "message": f"⚠️ [{proxy_name}] 遭遇 Cloudflare..."}) + "\n"
                    await asyncio.sleep(5)
                    try:
                        for frame in page.frames:
                            if box := await frame.query_selector("input[type='checkbox']"): await box.click()
                    except:
                        pass
                    await asyncio.sleep(5)
                    if "Just a moment" in await page.title():
                        await browser.close()
                        continue

                await asyncio.sleep(2)

                # 🔥【关键】保存 Cookie，供视频流代理使用
                cookies = await context.cookies()
                domain_key = urlparse(url).netloc
                cookie_dict = {c['name']: c['value'] for c in cookies}
                GLOBAL_COOKIE_JAR[domain_key] = cookie_dict
                # MissAV 特殊处理
                if "missav" in domain_key:
                    GLOBAL_COOKIE_JAR["missav.ws"] = cookie_dict

                yield json.dumps({"step": "process", "message": f"🍪 Cookie 捕获成功: {len(cookies)} 个"}) + "\n"

                try:
                    await page.click("video, .bilibili-player-video")
                except:
                    pass

                if is_video:
                    await asyncio.sleep(4)

                results = []
                title = await page.title()
                results.append({"类型": "标题", "内容": title.strip(), "备注": "Title"})

                cover = ""
                if og := await page.query_selector('meta[property="og:image"]'): cover = await og.get_attribute(
                    "content")

                v_url = ""
                if captured_videos:
                    valid = [u for u in captured_videos if "http" in u and "google" not in u]
                    if valid: v_url = max(valid, key=len)

                if not v_url:
                    if v_tag := await page.query_selector("video"): v_url = await v_tag.get_attribute("src")

                if v_url:
                    if v_url.startswith("//"): v_url = "https:" + v_url
                    results.append({"类型": "视频", "内容": v_url, "备注": cover or "No Cover"})
                    yield json.dumps({"step": "process", "message": f"✅ 抓取成功: {v_url[:30]}..."}) + "\n"
                else:
                    if cover:
                        results.append({"类型": "图片", "内容": cover, "备注": "Cover-Only"})
                        yield json.dumps({"step": "process", "message": "⚠️ 仅获取到封面。"}) + "\n"
                    else:
                        await browser.close()
                        continue

                if not is_video:
                    body = await page.inner_text("body")
                    if "Verify" not in body[:200]:
                        main = await page.query_selector('article') or await page.query_selector('body')
                        if main:
                            for t in await main.query_selector_all('h1, h2, p'):
                                txt = await t.inner_text()
                                if len(txt) > 5: results.append({"类型": "文本", "内容": txt[:500], "备注": "Text"})

                yield pd.DataFrame(results)
                break

            except Exception as e:
                yield json.dumps({"step": "error", "message": f"[{proxy_name}] 异常: {str(e)}"}) + "\n"
                continue
            finally:
                await browser.close()


async def smart_router(url: str, mode: str):
    yield json.dumps({"step": "init", "message": f"任务启动: {url} [模式: {mode}]"}) + "\n"
    await asyncio.sleep(0.5)
    df = pd.DataFrame()
    use_heavy = False
    if is_video_site(url) or mode == 'media': use_heavy = True
    try:
        if use_heavy:
            async for chunk in engine_heavyweight(url):
                if isinstance(chunk, pd.DataFrame):
                    df = chunk
                else:
                    yield chunk
        else:
            async for chunk in engine_lightweight(url):
                if isinstance(chunk, pd.DataFrame):
                    df = chunk
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


@app.post("/api/crawl")
async def start_crawl(request: CrawlRequest):
    return StreamingResponse(smart_router(request.url, request.mode), media_type="application/x-ndjson")


@app.get("/download/{filename}")
async def download_file(filename: str):
    filepath = os.path.abspath(filename)
    if os.path.exists(filepath): return FileResponse(filepath, filename=filename)
    return Response("File not found", status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
