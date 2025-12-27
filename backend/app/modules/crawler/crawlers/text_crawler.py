# backend/app/modules/crawler/crawlers/text_crawler.py
import asyncio
import json
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Route
from urllib.parse import urlparse, urljoin
from abc import ABC, abstractmethod
import re
from typing import List, Dict

GLOBAL_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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
        proxy_name = None
        
        if self.pool_manager:
            if network_type in ["node", "auto"]:
                if self.pool_manager.node_provider:
                    try:
                        all_nodes = self.pool_manager.node_provider()
                        # 🔥 核心修复：允许 http 和 socks5
                        compatible_nodes = [n for n in all_nodes if n.get('protocol') in ['socks5', 'socks', 'http']]
                        if compatible_nodes:
                            node = random.choice(compatible_nodes[:5])
                            # Playwright 的 proxy server 需要完整的 URL
                            if node['protocol'] == 'http':
                                proxy_config = {"server": f"http://{node['host']}:{node['port']}"}
                            else: # socks5
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

        if network_type != "auto":
            return None, "Direct (Fallback - No Nodes)"

        return None, "Direct (Fallback)"

async def async_request(method, url, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))

async def request_with_chain_async(url, headers=None, stream=False, timeout=15, method="GET", network_type="proxy", pool_manager=None):
    if headers is None: headers = {}
    domain = urlparse(url).netloc
    referer = "https://juejin.cn/" if "juejin" in domain else "https://www.google.com/"
    
    base_headers = {
        "User-Agent": GLOBAL_USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer, "Upgrade-Insecure-Requests": "1"
    }
    base_headers.update(headers)

    chain = []
    if network_type == "direct": chain.append((None, "Direct", 10))
    else:
        if pool_manager:
            if network_type in ["node", "auto"] and pool_manager.node_provider:
                try:
                    all_nodes = pool_manager.node_provider()
                    compatible_nodes = [n for n in all_nodes if n.get('protocol') in ['socks5', 'socks', 'http']]
                    for node in compatible_nodes[:5]:
                        if node['protocol'] == 'http':
                             chain.append((f"http://{node['host']}:{node['port']}", f"🛰️ Node-{node['host']}", 10))
                        else:
                             chain.append((f"socks5://{node['host']}:{node['port']}", f"🛰️ Node-{node['host']}", 10))
                except: pass
            if network_type in ["proxy", "auto"]:
                alive_nodes = [p for p in pool_manager.proxies if p.score > 0]
                if alive_nodes:
                    selected = sorted(alive_nodes, key=lambda p: p.score, reverse=True)[:5]
                    for p in selected: chain.append((p.to_url(), f"🌐 Proxy-{p.ip}", 10))
        if network_type == "auto" or not chain: chain.append((None, "Direct (Fallback)", 10))

    if not chain:
        class NoProxyResponse: status_code = 599; network_name = f"Strict Mode: No Proxy for '{network_type}'"; text=""
        return NoProxyResponse()

    for proxy_url, name, time_limit in chain:
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            resp = await async_request(method, url, headers=base_headers, proxies=proxies, timeout=time_limit, verify=False, stream=stream)
            if resp.status_code in [200, 304]:
                resp.network_name = name
                return resp
        except: continue
    
    class DummyResponse: status_code = 500; text = ""; network_name = "Failed"
    return DummyResponse()

async def block_aggressive(route):
    if route.request.resource_type in ["image", "font", "media"]: await route.abort()
    else: await route.continue_()

class GeneralTextCrawler(BaseCrawler):
    def extract_text_from_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        data_list = []
        
        if soup.title: data_list.append({"类型": "标题", "内容": soup.title.string.strip(), "备注": "Meta-Title"})

        art = soup.select_one(".article-content") or soup.select_one(".markdown-body")
        if art: data_list.append({"类型": "ARTICLE", "内容": art.get_text("\n", strip=True), "备注": "Juejin Article"})

        selectors = [".comment-list-wrapper .comment-item", "div[class*='comment-item']", ".comment-list .item"]
        juejin_comments = []
        for sel in selectors:
            found = soup.select(sel)
            if found: juejin_comments = found; break

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
        
        for c in soup.select("div[class*='comment'], div[class*='reply']")[:500]:
            t = c.get_text(strip=True)
            if 5 < len(t) < 1000:
                data_list.append({"类型": "评论", "内容": t, "备注": "General Comment"})

        return data_list

    async def extract_text_async(self, html):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.extract_text_from_html, html)

    def _is_list_page(self, url: str) -> bool:
        if "juejin.cn" in url and ("/backend" in url or "/frontend" in url or "/android" in url or "/ios" in url or "/ai" in url):
            return True
        if "/tag/" in url or "/category/" in url or "/list/" in url:
            return True
        return False

    def _extract_links_from_list(self, html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.select("a.title[href*='/post/']"):
            href = a.get('href')
            if href:
                full_url = urljoin(base_url, href)
                if full_url not in links:
                    links.append(full_url)

        if not links:
             for a in soup.find_all('a', href=True):
                 href = a['href']
                 if len(href) > 10 and ('/article/' in href or '/p/' in href or '.html' in href):
                     full_url = urljoin(base_url, href)
                     if full_url not in links:
                         links.append(full_url)
        return links

    async def crawl(self, url: str, network_type: str = "proxy", force_browser: bool = False):
        # 🔥 核心修复：列表页批量抓取逻辑
        if self._is_list_page(url) and not force_browser:
            yield json.dumps({"step": "process", "message": f"📂 检测到列表页，启动浏览器解析文章列表..."}) + "\n"

            proxy_conf, proxy_name = await self.get_playwright_proxy(network_type)

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, proxy=proxy_conf)
                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=30000, wait_until="networkidle")
                    content = await page.content()
                    links = self._extract_links_from_list(content, url)
                except Exception as e:
                    yield json.dumps({"step": "error", "message": f"❌ 列表页加载失败: {e}"}) + "\n"
                    await browser.close()
                    return
                finally:
                    await browser.close()

            target_links = links[:5]
            if not target_links:
                yield json.dumps({"step": "error", "message": "⚠️ 未在列表页找到有效文章链接"}) + "\n"
                return

            yield json.dumps({"step": "process", "message": f"✅ 发现 {len(links)} 篇文章，准备抓取前 {len(target_links)} 篇..."}) + "\n"

            # 🔥 核心修复：递归调用 self.crawl，确保每篇文章都走完整流程（含评论抓取）
            for i, link in enumerate(target_links):
                yield json.dumps({"step": "process", "message": f"📄 [{i+1}/{len(target_links)}] 正在抓取: {link}"}) + "\n"

                # 递归调用，允许它在需要时自动切换到浏览器
                async for chunk in self.crawl(link, network_type=network_type, force_browser=force_browser):
                    # 过滤掉递归调用中的 init 消息，避免前端日志混乱
                    try:
                        data = json.loads(chunk)
                        if data.get("step") == "init": continue
                    except: pass
                    yield chunk

                await asyncio.sleep(random.uniform(1, 3))

            yield json.dumps({"step": "done", "message": "🎉 批量抓取完成"}) + "\n"
            return

        # ==================== 原有单页抓取逻辑 (保持不变) ====================
        if not force_browser:
            yield json.dumps({"step": "process", "message": f"🚀 启动极速文本解析 (Requests) [{network_type}]..."}) + "\n"
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
                yield json.dumps({"step": "process", "message": f"🌐 静态提取成功 ({net_name}) - 发现 {len(data_list)} 条数据"}) + "\n"
                yield pd.DataFrame(data_list)
                return
            
            yield json.dumps({"step": "process", "message": f"⚠️ 静态抓取不满足 ({net_name})，启动浏览器渲染..."}) + "\n"
        else:
            yield json.dumps({"step": "process", "message": f"🖥️ 用户强制使用浏览器渲染..."}) + "\n"
        
        try:
            proxy_conf, proxy_name = await self.get_playwright_proxy(network_type)
        except Exception as e:
            yield json.dumps({"step": "error", "message": f"❌ {str(e)}"}) + "\n"
            return

        yield json.dumps({"step": "process", "message": f"🌐 渲染节点: {proxy_name}..."}) + "\n"

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True, args=["--mute-audio"], proxy=proxy_conf)
                context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                page = await context.new_page()
                await page.route("**/*", block_aggressive)

                await page.goto(url, timeout=60000, wait_until="networkidle")
                
                if "juejin.cn" in url:
                    yield json.dumps({"step": "process", "message": "🖱️ 检测到掘金，正在深度滚动..."}) + "\n"
                    try:
                        for _ in range(10):
                            await page.keyboard.press("End")
                            await asyncio.sleep(1)
                            try: await page.click("button.fetch-comment-btn", timeout=500)
                            except: pass
                            try: await page.click(".load-more", timeout=500)
                            except: pass
                    except: pass
                else:
                    for _ in range(5):
                        await page.evaluate("window.scrollBy(0, window.innerHeight)")
                        await asyncio.sleep(1)

                content = await page.content()
                data_list = await self.extract_text_async(content)
                
                if data_list:
                    c_count = len([d for d in data_list if d['类型'] == '评论'])
                    yield json.dumps({"step": "process", "message": f"✅ 深度渲染提取成功 - 发现 {len(data_list)} 条数据 ({c_count} 条评论)"}) + "\n"
                    yield pd.DataFrame(data_list)
                else:
                    yield json.dumps({"step": "error", "message": "❌ 渲染后仍未发现有效数据"}) + "\n"

            except Exception as e:
                yield json.dumps({"step": "error", "message": f"❌ 浏览器异常: {str(e)}"}) + "\n"
            finally:
                if browser: await browser.close()
