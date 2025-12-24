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

# 引入代理池管理器 (相对导入)
try:
    from ...proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

GLOBAL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
GLOBAL_COOKIE_JAR = {}

class BaseCrawler(ABC):
    @abstractmethod
    async def crawl(self, url: str, network_type: str = "proxy"):
        pass

    async def get_playwright_proxy(self, network_type="proxy"):
        if network_type == "direct": return None
        
        if pool_manager and network_type == "proxy":
            alive_nodes = [p for p in pool_manager.proxies if p.score > 0]
            if alive_nodes:
                p = random.choice(alive_nodes[:10])
                return {"server": p.to_url()}
        
        return None

async def async_request(method, url, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))

async def request_with_chain_async(url, headers=None, stream=False, timeout=10, method="GET", network_type="proxy"):
    if headers is None: headers = {}

    base_headers = {
        "User-Agent": GLOBAL_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }
    base_headers.update(headers)

    chain = []
    
    if network_type == "direct":
        chain.append((None, "Direct", 10))
    
    else: 
        if pool_manager:
            alive_nodes = [p for p in pool_manager.proxies if p.score > 0]
            if alive_nodes:
                selected = sorted(alive_nodes, key=lambda p: p.speed)[:5]
                for p in selected:
                    chain.append((p.to_url(), f"Proxy-{p.ip}:{p.port}", 5))
        
        chain.append((None, "Direct", 5))

    last_error = None
    for proxy_url, name, time_limit in chain:
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            resp = await async_request(
                method, url, headers=base_headers, proxies=proxies,
                timeout=time_limit, verify=False, stream=stream
            )
            if resp.status_code == 200:
                resp.network_name = name
                return resp
            last_error = f"{name} Error ({resp.status_code})"
        except Exception as e:
            last_error = f"{name} Exception: {str(e)}"
    
    class DummyResponse:
        status_code = 500; text = ""; content = b""; network_name = f"Failed. Last: {last_error}"
        def json(self): return {}
    return DummyResponse()

def parse_playwright_proxy(p_url):
    if not p_url: return None
    try:
        u = urlparse(p_url)
        return {"server": f"{u.scheme}://{u.hostname}:{u.port}", "username": u.username, "password": u.password}
    except:
        return None

async def block_aggressive(route):
    if route.request.resource_type in ["image", "font", "media", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

class GeneralTextCrawler(BaseCrawler):
    def extract_text_from_html(self, html):
        soup = BeautifulSoup(html, "html.parser")
        data_list = []
        title = soup.title.string.strip() if soup.title else ""
        if title: data_list.append({"类型": "标题", "内容": title, "备注": "Meta-Title"})
        article = soup.find("article") or soup.find("div", class_=re.compile(r'(article|content|post|entry|main)', re.I)) or soup.find("main") or soup.body
        if article:
            for tag in article(["script", "style", "noscript", "svg", "button", "input", "form", "nav", "footer", "iframe", "header"]):
                tag.decompose()
            for tag in article.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
                txt = tag.get_text(strip=True)
                if len(txt) > 10:
                    if not any(d['内容'] == txt for d in data_list):
                        data_list.append({"类型": tag.name.upper(), "内容": txt, "备注": "Text"})
        return data_list

    async def extract_text_async(self, html):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.extract_text_from_html, html)

    async def crawl(self, url: str, network_type: str = "proxy"):
        yield json.dumps({"step": "process", "message": f"🚀 启动极速文本解析 (Requests) [{network_type}]..."}) + "\n"
        
        resp = await request_with_chain_async(url, network_type=network_type)
        net_name = getattr(resp, "network_name", "未知")
        
        data_list = []
        if resp.status_code == 200 and len(resp.text) > 100:
            resp.encoding = 'utf-8'
            data_list = await self.extract_text_async(resp.text)
        
        if data_list and len(data_list) > 1:
            yield json.dumps({"step": "process", "message": f"🌐 静态提取成功 ({net_name}) - 发现 {len(data_list)} 条数据"}) + "\n"
            yield pd.DataFrame(data_list)
            return
            
        yield json.dumps({"step": "process", "message": f"⚠️ 静态抓取失败 ({net_name})，启动浏览器渲染..."}) + "\n"
        
        proxy_conf = await self.get_playwright_proxy(network_type)
        proxy_display = "Direct"
        if proxy_conf and proxy_conf['server']:
             try:
                 u = urlparse(proxy_conf['server'])
                 proxy_display = f"Proxy-{u.hostname}:{u.port}"
             except:
                 proxy_display = "Proxy-Unknown"

        yield json.dumps({"step": "process", "message": f"🌐 渲染节点: {proxy_display}..."}) + "\n"
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True, args=["--mute-audio"], proxy=proxy_conf)
                context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                page = await context.new_page()
                await page.route("**/*", block_aggressive)
                await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                content = await page.content()
                data_list = await self.extract_text_async(content)
                if data_list:
                    yield json.dumps({"step": "process", "message": f"✅ 深度渲染提取成功 - 发现 {len(data_list)} 条数据"}) + "\n"
                    yield pd.DataFrame(data_list)
                    await browser.close()
                    return
                await browser.close()
            except Exception as e:
                yield json.dumps({"step": "process", "message": f"❌ 浏览器渲染错误: {str(e)}"}) + "\n"

        yield json.dumps({"step": "error", "message": "❌ 最终失败：无法提取有效文本"}) + "\n"
