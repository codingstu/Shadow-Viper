# backend/link_scraper.py
import re
import json
import base64
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urlparse, urljoin
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from aiohttp_socks import ProxyConnector

# 1. 引入中央代理管理器
try:
    from proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

logger = logging.getLogger(__name__)


class LinkScraper:
    """智能链接抓取器 (接入全球代理池)"""

    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        ]

        # 正则模式
        self.patterns = {
            'vmess': r'(vmess://[A-Za-z0-9+/=\-]+)',
            'vless': r'(vless://[^\s"\']+)',
            'trojan': r'(trojan://[^\s"\']+)',
            'ss': r'(ss://[A-Za-z0-9+/=\-]+)',
            'ssr': r'(ssr://[A-Za-z0-9+/=\-]+)',
            'hy2': r'(hysteria2://[^\s"\']+)',
            'tuic': r'(tuic://[^\s"\']+)',
            'subscription': r'(https?://[^\s"\']+\.(?:yaml|yml|txt|conf|json|list))',
            'base64': r'(https?://[^\s"\']+\.(?:b64|base64|sub))',
        }
        self.node_keywords = ['订阅', 'subscribe', 'sub', '节点', 'node', 'proxy', 'v2ray', 'clash', 'free', 'share']
        self.github_patterns = [r'github\.com', r'raw\.githubusercontent\.com']

    # 🔥🔥🔥 核心升级：使用代理链抓取 🔥🔥🔥
    async def scrape_links_from_url(self, url: str) -> List[str]:
        # 获取标准链路 (Hunter > Paid > Tor > Direct)
        chain = []
        if pool_manager:
            chain = pool_manager.get_standard_chain()
        chain.append((None, "Direct", 5))

        for proxy_url, name, timeout_sec in chain:
            try:
                # logger.info(f"🔍 [Scraper] 尝试抓取 {url} via {name}...")
                connector = ProxyConnector.from_url(proxy_url) if proxy_url else aiohttp.TCPConnector(ssl=False)

                async with aiohttp.ClientSession(connector=connector,
                                                 timeout=aiohttp.ClientTimeout(total=timeout_sec + 5)) as session:
                    headers = {'User-Agent': self.user_agents[0]}
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            # 成功获取！
                            content_type = response.headers.get('Content-Type', '').lower()
                            if 'text/html' in content_type:
                                html = await response.text()
                                return await self.extract_links_from_html(html, url)
                            else:
                                text = await response.text()
                                return self.extract_links_from_text(text)
            except:
                continue  # 失败则尝试下一个代理

        logger.error(f"❌ [Scraper] 所有通道均无法抓取: {url}")
        return []

    # 🔥🔥🔥 核心升级：使用代理链测试有效性 🔥🔥🔥
    async def test_link_validity(self, url: str) -> Dict[str, Any]:
        # 同样使用链路
        chain = []
        if pool_manager:
            chain = pool_manager.get_standard_chain()
        chain.append((None, "Direct", 5))

        for proxy_url, name, timeout_sec in chain:
            try:
                connector = ProxyConnector.from_url(proxy_url) if proxy_url else aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector,
                                                 timeout=aiohttp.ClientTimeout(total=timeout_sec + 5)) as session:
                    async with session.get(url, headers={'User-Agent': self.user_agents[0]}) as response:
                        if response.status == 200:
                            content = await response.text()
                            is_valid = self.validate_node_content(content)
                            return {
                                'valid': is_valid,
                                'status': 200,
                                'content': content if is_valid else None,  # 返回内容供后续提取
                                'size': len(content),
                                'nodes_found': len(self.extract_links_from_text(content))
                            }
            except:
                continue

        return {'valid': False, 'error': "All connections failed"}

    async def extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        links = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                full_url = urljoin(base_url, a_tag['href'])
                if self.is_node_link(full_url) or self.is_subscription_link(full_url):
                    links.append(full_url)

            text = soup.get_text()
            links.extend(self.extract_links_from_text(text))

            # 正则补漏
            for pattern in self.patterns.values():
                matches = re.findall(pattern, html)
                for m in matches:
                    links.append(urljoin(base_url, m if isinstance(m, str) else m[0]))
        except:
            pass
        return list(set(links))

    def extract_links_from_text(self, text: str) -> List[str]:
        links = []
        for pattern in self.patterns.values():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                links.append(m if isinstance(m, str) else m[0])
        return links

    def validate_node_content(self, content: str) -> bool:
        if not content.strip(): return False
        try:
            # Try base64
            if re.match(r'^[A-Za-z0-9+/=]+$', content.strip()): return True
        except:
            pass

        if len(self.extract_links_from_text(content)) > 0: return True

        try:  # Try JSON/YAML
            if "proxies" in content or "Proxy" in content: return True
        except:
            pass

        return False

    def is_node_link(self, url: str) -> bool:
        return any(url.lower().startswith(p) for p in ['vmess://', 'vless://', 'trojan://', 'ss://', 'ssr://'])

    def is_subscription_link(self, url: str) -> bool:
        return any(k in url.lower() for k in ['sub', 'subscribe', 'node', 'yaml', 'txt'])

    def is_github_url(self, url: str) -> bool:
        return 'github' in url.lower()

    def convert_github_url(self, url: str) -> str:
        # 简单转换 logic
        if 'github.com' in url and '/blob/' in url:
            return url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
        return url
