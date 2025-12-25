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
from typing import List, Dict, Optional, Tuple
import re

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

    def _sync_validate(self, proxy_conf: Dict) -> bool:
        """
        🔥 升级版工兵：不仅要通，还要有一点带宽
        请求掘金的 robots.txt (小文件但真实)，确保代理能访问目标站
        """
        # 目标改为掘金的 robots.txt，既轻量又能验证对目标站的连通性
        test_url = "https://juejin.cn/robots.txt"

        proxies = None
        if proxy_conf and "server" in proxy_conf:
            srv = proxy_conf["server"]
            proxies = {"http": srv, "https": srv}

        try:
            # 5秒超时，确保有一点速度
            resp = requests.get(test_url, proxies=proxies, timeout=5, verify=False,
                                headers={"User-Agent": GLOBAL_USER_AGENT})
            return resp.status_code == 200
        except:
            return False

    async def select_session_proxy(self, network_type="auto") -> Tuple[Optional[Dict], str]:
        if network_type == "direct":
            return None, "Direct"

        candidates = []
        if self.pool_manager and network_type in ["node", "auto"]:
            if self.pool_manager.node_provider:
                try:
                    nodes = self.pool_manager.node_provider()
                    if nodes:
                        native_nodes = [n for n in nodes if n.get('protocol') in ['socks5', 'socks4', 'http', 'https']]
                        random.shuffle(native_nodes)
                        for node in native_nodes[:30]:
                            protocol = node.get('protocol')
                            schema = "socks5" if "socks" in protocol else "http"
                            conf = {"server": f"{schema}://{node['host']}:{node['port']}"}
                            if node.get('username') and node.get('password'):
                                conf['username'] = node.get('username')
                                conf['password'] = node.get('password')
                            candidates.append((conf, f"🛰️ Native-{node['host']}"))
                except Exception as e:
                    print(f"[ProxySelector] Error: {e}")

        if self.pool_manager and (network_type in ["proxy", "auto"] or network_type == "node"):
            alive_nodes = [p for p in self.pool_manager.proxies if p.score > 0]
            if alive_nodes:
                random.shuffle(alive_nodes)
                for p in alive_nodes[:15]:
                    conf = {"server": p.to_url()}
                    candidates.append((conf, f"🌐 ProxyPool-{p.ip}"))

        if candidates:
            print(f"🔎 [ProxySelector] Testing {len(candidates)} candidates (Target: Juejin)...")
            loop = asyncio.get_running_loop()
            for conf, name in candidates:
                is_valid = await loop.run_in_executor(None, self._sync_validate, conf)
                if is_valid:
                    print(f"✅ [ProxySelector] Selected: {name}")
                    return conf, name
            print("⚠️ [ProxySelector] No valid proxy found, fallback to Direct.")

        return None, "Direct (Fallback)"

    async def async_request(self, method, url, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))

    async def request_with_fixed_proxy(self, url, proxy_conf, proxy_name, headers=None, stream=False, timeout=15):
        if headers is None: headers = {}
        domain = urlparse(url).netloc
        referer = "https://juejin.cn/" if "juejin" in domain else "https://www.google.com/"
        base_headers = {"User-Agent": GLOBAL_USER_AGENT, "Referer": referer}
        base_headers.update(headers)

        proxies = None
        if proxy_conf and "server" in proxy_conf:
            srv = proxy_conf["server"]
            proxies = {"http": srv, "https": srv}

        try:
            resp = await self.async_request("GET", url, headers=base_headers, proxies=proxies, timeout=timeout,
                                            verify=False, stream=stream)
            resp.network_name = proxy_name
            return resp
        except Exception as e:
            class DummyResponse:
                status_code = 500;
                text = "";
                content = b"";
                network_name = f"{proxy_name} Failed: {str(e)}";

                def json(self): return {}

            return DummyResponse()

    async def extract_text_async(self, html):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.extract_text_from_html, html)

    def extract_text_from_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        data_list = []
        if soup.title: data_list.append({"类型": "标题", "内容": soup.title.string.strip(), "备注": "Meta-Title"})
        art = soup.select_one(".article-content") or soup.select_one(".markdown-body")
        if art: data_list.append({"类型": "ARTICLE", "内容": art.get_text("\n", strip=True), "备注": "Juejin Article"})

        selectors = [".comment-list-wrapper .comment-item", "div[class*='comment-item']", ".comment-list .item",
                     "div[data-test-id='comment-item']"]
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
        if gen_art: data_list.append(
            {"类型": "ARTICLE", "内容": gen_art.get_text("\n", strip=True), "备注": "General Article"})
        return data_list


class GeneralTextCrawler(BaseCrawler):
    async def crawl(self, url: str, network_type: str = "proxy", force_browser: bool = False):
        yield json.dumps({"step": "process", "message": "🔎 正在实时筛选最佳节点..."}) + "\n"
        session_proxy_conf, session_proxy_name = await self.select_session_proxy(network_type)
        yield json.dumps({"step": "process", "message": f"🔒 锁定优质线路: {session_proxy_name}"}) + "\n"

        if not force_browser:
            yield json.dumps({"step": "process", "message": f"🚀 启动极速文本解析..."}) + "\n"
            resp = await self.request_with_fixed_proxy(url, session_proxy_conf, session_proxy_name)
            data_list = []
            if resp.status_code in [200, 304] and len(resp.text) > 100:
                resp.encoding = 'utf-8'
                data_list = await self.extract_text_async(resp.text)

            is_juejin = "juejin.cn" in url
            has_comments = any(d['类型'] == '评论' for d in data_list)
            if data_list and (not is_juejin or has_comments):
                yield json.dumps({"step": "process", "message": f"🌐 静态提取成功 - {len(data_list)} 条数据"}) + "\n"
                yield pd.DataFrame(data_list)
                return
            yield json.dumps({"step": "process", "message": f"⚠️ 静态抓取不满足，启动浏览器..."}) + "\n"

        max_retries = 3 if network_type != "direct" else 1

        async def block_aggressive(route):
            if route.request.resource_type in ["image", "font", "media"]:
                await route.abort()
            else:
                await route.continue_()

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                yield json.dumps({"step": "process", "message": "🔄 节点失效，重新筛选..."}) + "\n"
                session_proxy_conf, session_proxy_name = await self.select_session_proxy(network_type)

            try:
                yield json.dumps({"step": "process",
                                  "message": f"🌐 [第 {attempt}/{max_retries} 次] 启动浏览器: {session_proxy_name}..."}) + "\n"
                async with async_playwright() as p:
                    browser = None
                    try:
                        browser = await p.chromium.launch(headless=True, args=["--mute-audio",
                                                                               "--disable-blink-features=AutomationControlled"],
                                                          proxy=session_proxy_conf)
                        context = await browser.new_context(user_agent=GLOBAL_USER_AGENT)
                        page = await context.new_page()
                        await page.route("**/*", block_aggressive)

                        # 🔥 核心优化：放宽等待条件，只要 DOM 出来就行，不等资源完全加载
                        await page.goto(url, timeout=60000, wait_until="domcontentloaded")

                        # 手动等待核心内容出现，作为双保险
                        try:
                            await page.wait_for_selector("article, .markdown-body, .article-content", timeout=15000)
                        except:
                            pass  # 如果等不到也不要紧，继续往下走

                        if "juejin.cn" in url:
                            yield json.dumps({"step": "process", "message": "🖱️ 掘金贪婪滚动中..."}) + "\n"
                            try:
                                await page.click(".fetch-comment-btn", timeout=3000); await asyncio.sleep(2)
                            except:
                                pass
                            prev_height = 0
                            for i in range(10):
                                await page.keyboard.press("End")
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                await asyncio.sleep(2.5)
                                new_height = await page.evaluate("document.body.scrollHeight")
                                if new_height == prev_height: break
                                prev_height = new_height
                                if i % 2 == 0: yield json.dumps(
                                    {"step": "process", "message": f"🖱️ 加载更多评论 ({i + 1})..."}) + "\n"
                        else:
                            for _ in range(5): await page.evaluate(
                                "window.scrollBy(0, window.innerHeight)"); await asyncio.sleep(1)

                        content = await page.content()
                        data_list = await self.extract_text_async(content)
                        if data_list:
                            c_count = len([d for d in data_list if d['类型'] == '评论'])
                            yield json.dumps({"step": "process",
                                              "message": f"✅ 深度渲染成功 - {len(data_list)} 条数据 ({c_count} 评论)"}) + "\n"
                            yield pd.DataFrame(data_list)
                            await browser.close();
                            return

                        # 如果是 domcontentloaded 模式，可能有时候页面确实还没渲染完，抛出异常重试
                        raise Exception("页面结构不完整 (可能是加载太慢)")

                    except Exception as e:
                        if attempt == max_retries:
                            yield json.dumps({"step": "error", "message": f"❌ 最终失败: {str(e)}"}) + "\n"
                        else:
                            yield json.dumps({"step": "process", "message": f"⚠️ 节点不稳: {str(e)}"}) + "\n"
                    finally:
                        if browser: await browser.close()
            except Exception as outer_e:
                if attempt == max_retries: yield json.dumps(
                    {"step": "error", "message": f"❌ 启动失败: {str(outer_e)}"}) + "\n"