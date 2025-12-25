# backend/app/modules/crawler/crawlers/text_crawler.py
import asyncio
import json
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Route
from urllib.parse import urlparse
from abc import ABC, abstractmethod
import re
from typing import List, Dict

# 引入代理池管理器 (相对导入)
try:
    from ...proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

GLOBAL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"


class BaseCrawler(ABC):
    def __init__(self, pool_manager=None):
        self.pool_manager = pool_manager

    @abstractmethod
    async def crawl(self, url: str, network_type: str = "proxy", force_browser: bool = False):
        pass

    async def get_playwright_proxy(self, network_type="auto"):
        if network_type == "direct":
            return None, "Direct"

        proxy_config = None
        proxy_name = "Direct (Fallback)"

        if self.pool_manager and network_type in ["proxy", "auto", "node"]:
            # 每次获取都随机取一个高质量节点，确保重试时能换 IP
            alive_nodes = [p for p in self.pool_manager.proxies if p.score > 0]
            if alive_nodes:
                # 随机性更大一点，防止一直随到同一个
                p = random.choice(alive_nodes[:20] if len(alive_nodes) > 20 else alive_nodes)
                proxy_config = {"server": p.to_url()}
                proxy_name = f"🌐 Proxy-{p.ip}"
                return proxy_config, proxy_name

        return None, "Direct (Fallback)"


async def async_request(method, url, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))


async def request_with_chain_async(url, headers=None, stream=False, timeout=15, method="GET", network_type="proxy",
                                   pool_manager=None):
    if headers is None: headers = {}
    domain = urlparse(url).netloc
    referer = "https://juejin.cn/" if "juejin" in domain else "https://www.google.com/"

    base_headers = {
        "User-Agent": GLOBAL_USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer, "Upgrade-Insecure-Requests": "1"
    }
    base_headers.update(headers)

    chain = []
    if network_type == "direct":
        chain.append((None, "Direct", 10))
    else:
        if pool_manager:
            alive_nodes = [p for p in pool_manager.proxies if p.score > 0]
            if alive_nodes:
                selected = sorted(alive_nodes, key=lambda p: p.score, reverse=True)[:5]
                for p in selected:
                    chain.append((p.to_url(), f"🌐 Proxy-{p.ip}", 10))
        chain.append((None, "Direct (Fallback)", 10))

    if not chain:
        chain.append((None, "Direct (Emergency)", 10))

    last_error = None
    for proxy_url, name, time_limit in chain:
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            resp = await async_request(
                method, url, headers=base_headers, proxies=proxies,
                timeout=time_limit, verify=False, stream=stream
            )
            if resp.status_code in [200, 304]:
                resp.network_name = name
                return resp
            last_error = f"{name} Error ({resp.status_code})"
        except Exception as e:
            last_error = f"{name} Exception: {str(e)}"

    class DummyResponse:
        status_code = 500;
        text = "";
        content = b"";
        network_name = f"Failed. Last: {last_error}"

        def json(self): return {}

    return DummyResponse()


async def block_aggressive(route):
    if route.request.resource_type in ["image", "font", "media"]:
        await route.abort()
    else:
        await route.continue_()


class GeneralTextCrawler(BaseCrawler):
    def extract_text_from_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        data_list = []

        if soup.title: data_list.append({"类型": "标题", "内容": soup.title.string.strip(), "备注": "Meta-Title"})

        art = soup.select_one(".article-content") or soup.select_one(".markdown-body")
        if art: data_list.append({"类型": "ARTICLE", "内容": art.get_text("\n", strip=True), "备注": "Juejin Article"})

        # 增强的选择器 (针对掘金多变的结构)
        selectors = [
            ".comment-list-wrapper .comment-item",
            "div[class*='comment-item']",
            ".comment-list .item",
            "div[data-test-id='comment-item']",
            ".comments-container .comment"
        ]

        juejin_comments = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                juejin_comments = found
                break

        for item in juejin_comments:
            content = item.select_one(".comment-content") or item.select_one("div[class*='content']")
            if content:
                user = item.select_one(".user-name") or item.select_one(".name")
                u_text = user.get_text(strip=True) if user else "User"
                data_list.append({"类型": "评论", "内容": content.get_text(strip=True), "备注": f"User: {u_text}"})

        if data_list: return data_list

        gen_art = soup.find("article") or soup.find("div", class_=re.compile(r'post|article|content', re.I))
        if gen_art:
            t = gen_art.get_text("\n", strip=True)
            if len(t) > 20: data_list.append({"类型": "ARTICLE", "内容": t, "备注": "General Article"})

        for c in soup.select("div[class*='comment'], div[class*='reply']")[:50]:
            t = c.get_text(strip=True)
            if 10 < len(t) < 500: data_list.append({"类型": "评论", "内容": t, "备注": "General Comment"})

        return data_list

    async def extract_text_async(self, html):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.extract_text_from_html, html)

    async def crawl(self, url: str, network_type: str = "proxy", force_browser: bool = False):
        # 1. 静态抓取 (Request Phase)
        if not force_browser:
            yield json.dumps(
                {"step": "process", "message": f"🚀 启动极速文本解析 (Requests) [{network_type}]..."}) + "\n"
            resp = await request_with_chain_async(url, network_type=network_type, pool_manager=self.pool_manager)

            if resp.status_code == 599:
                yield json.dumps({"step": "error", "message": f"❌ {resp.network_name}"}) + "\n"
                return

            net_name = getattr(resp, "network_name", "未知")
            data_list = []
            if resp.status_code in [200, 304] and len(resp.text) > 100:
                resp.encoding = 'utf-8'
                data_list = await self.extract_text_async(resp.text)

            is_juejin = "juejin.cn" in url
            has_comments = any(d['类型'] == '评论' for d in data_list)

            if data_list and (not is_juejin or has_comments):
                yield json.dumps({"step": "process",
                                  "message": f"🌐 静态提取成功 ({net_name}) - 发现 {len(data_list)} 条数据"}) + "\n"
                yield pd.DataFrame(data_list)
                return

            yield json.dumps({"step": "process", "message": f"⚠️ 静态抓取不满足 ({net_name})，启动浏览器渲染..."}) + "\n"
        else:
            yield json.dumps({"step": "process", "message": f"🖥️ 用户强制使用浏览器渲染..."}) + "\n"

        # ==================== 🔥 核心增强：Playwright 自动重试机制 (3条命) 🔥 ====================
        max_retries = 3
        # 如果是直连，只试一次，因为网络环境不变重试没意义
        if network_type == "direct": max_retries = 1

        for attempt in range(1, max_retries + 1):
            try:
                # 每次尝试都重新获取一个新代理
                proxy_conf, proxy_name = await self.get_playwright_proxy(network_type)
                yield json.dumps({"step": "process",
                                  "message": f"🌐 [第 {attempt}/{max_retries} 次尝试] 启动浏览器: {proxy_name}..."}) + "\n"

                async with async_playwright() as p:
                    browser = None
                    try:
                        # 增加防检测参数
                        browser = await p.chromium.launch(
                            headless=True,
                            args=["--mute-audio", "--disable-blink-features=AutomationControlled"],
                            proxy=proxy_conf
                        )
                        context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                        page = await context.new_page()
                        await page.route("**/*", block_aggressive)

                        # 增加超时容错
                        await page.goto(url, timeout=45000, wait_until="networkidle")

                        # 掘金专用逻辑
                        if "juejin.cn" in url:
                            yield json.dumps({"step": "process", "message": "🖱️ 检测到掘金，正在贪婪抓取..."}) + "\n"

                            try:
                                await page.click(".fetch-comment-btn", timeout=3000)
                                await asyncio.sleep(2)
                            except:
                                pass

                            # 增加滚动等待时间，应对慢节点
                            prev_height = 0
                            for i in range(10):  # 滚10次
                                await page.keyboard.press("End")
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                # 慢网速下，给 3 秒加载时间
                                await asyncio.sleep(3)

                                new_height = await page.evaluate("document.body.scrollHeight")
                                if new_height == prev_height:
                                    # 尝试晃动
                                    await page.evaluate("window.scrollBy(0, -300)")
                                    await asyncio.sleep(1)
                                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                    await asyncio.sleep(2)
                                    if await page.evaluate("document.body.scrollHeight") == new_height:
                                        break
                                prev_height = new_height
                                if i % 2 == 0:
                                    yield json.dumps(
                                        {"step": "process", "message": f"🖱️ 滚动加载中 ({i + 1})..."}) + "\n"

                        else:
                            # 通用滚动
                            for _ in range(5):
                                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                                await asyncio.sleep(1)

                        content = await page.content()
                        data_list = await self.extract_text_async(content)

                        # 判断是否成功
                        if data_list:
                            c_count = len([d for d in data_list if d['类型'] == '评论'])
                            yield json.dumps({"step": "process",
                                              "message": f"✅ 深度渲染提取成功 - 发现 {len(data_list)} 条数据 ({c_count} 条评论)"}) + "\n"
                            yield pd.DataFrame(data_list)
                            await browser.close()
                            return  # 🔥 成功就退出函数，不再重试

                        # 如果没抓到数据，抛出异常触发重试
                        raise Exception("页面加载成功但未提取到有效数据 (可能是白屏或被拦截)")

                    except Exception as e:
                        err_msg = str(e)
                        # 如果是最后一次尝试，才报 Error
                        if attempt == max_retries:
                            yield json.dumps({"step": "error", "message": f"❌ 最终失败: {err_msg}"}) + "\n"
                        else:
                            # 否则只报 Warning，并继续循环
                            yield json.dumps({"step": "process",
                                              "message": f"⚠️ 当前节点 ({proxy_name}) 不稳定: {err_msg}，准备切换节点重试..."}) + "\n"
                    finally:
                        if browser: await browser.close()

            except Exception as outer_e:
                # 捕获获取代理等外部错误
                if attempt == max_retries:
                    yield json.dumps({"step": "error", "message": f"❌ 启动失败: {str(outer_e)}"}) + "\n"