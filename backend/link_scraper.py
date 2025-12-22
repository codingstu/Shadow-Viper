#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
链接抓取器 - 自动从网页抓取节点订阅链接
"""

import re
import json
import base64
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urlparse, urljoin
import aiohttp
import asyncio
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LinkScraper:
    """智能链接抓取器"""

    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        ]

        # 节点链接正则模式
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

        # 常见的节点关键词
        self.node_keywords = [
            '订阅', 'subscribe', 'sub', '节点', 'node', 'proxy',
            'v2ray', 'vmess', 'vless', 'trojan', 'shadowsocks',
            'clash', 'yaml', '配置', 'config', '机场', 'free',
            '免费', '分享', 'share', 'link', '链接', 'url'
        ]

        # GitHub特定的模式
        self.github_patterns = [
            r'github\.com/([^/]+)/([^/]+)/raw/',
            r'github\.com/([^/]+)/([^/]+)/blob/',
            r'raw\.githubusercontent\.com/([^/]+)/([^/]+)/',
            r'gist\.githubusercontent\.com/([^/]+)/',
        ]

    async def scrape_links_from_url(self, url: str) -> List[str]:
        """从URL抓取节点链接"""
        try:
            headers = {
                'User-Agent': self.user_agents[0],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            timeout = aiohttp.ClientTimeout(total=15)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers, allow_redirects=True) as response:
                    if response.status != 200:
                        logger.error(f"请求失败: {response.status}")
                        return []

                    content_type = response.headers.get('Content-Type', '').lower()

                    # 如果是文本文件，直接解析
                    if any(ct in content_type for ct in ['text/plain', 'application/json']):
                        text = await response.text()
                        return self.extract_links_from_text(text)

                    # 如果是HTML，使用BeautifulSoup解析
                    elif 'text/html' in content_type:
                        html = await response.text()
                        return await self.extract_links_from_html(html, url)

                    # 其他类型
                    else:
                        # 尝试读取为文本
                        try:
                            text = await response.text()
                            return self.extract_links_from_text(text)
                        except:
                            return []

        except Exception as e:
            logger.error(f"抓取链接失败 {url}: {str(e)}")
            return []

    async def extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """从HTML中提取节点链接"""
        links = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # 查找所有链接
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                full_url = urljoin(base_url, href)

                # 检查是否是节点链接
                if self.is_node_link(full_url) or self.is_subscription_link(full_url):
                    links.append(full_url)

            # 查找文本内容中的链接
            text = soup.get_text()
            links.extend(self.extract_links_from_text(text))

            # 查找code/pre标签中的内容
            for code_tag in soup.find_all(['code', 'pre', 'textarea']):
                code_text = code_tag.get_text()
                links.extend(self.extract_links_from_text(code_text))

            # 查找所有可能的订阅链接
            for pattern_name, pattern in self.patterns.items():
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    full_url = urljoin(base_url, match)
                    links.append(full_url)

        except Exception as e:
            logger.error(f"解析HTML失败: {str(e)}")

        # 去重
        unique_links = []
        for link in links:
            if link not in unique_links:
                unique_links.append(link)

        return unique_links

    def extract_links_from_text(self, text: str) -> List[str]:
        """从文本中提取节点链接"""
        links = []

        # 查找所有协议链接
        for pattern_name, pattern in self.patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                links.append(match)

        return links

    def is_node_link(self, url: str) -> bool:
        """判断是否为节点链接"""
        url_lower = url.lower()
        return any(
            url_lower.startswith(protocol)
            for protocol in ['vmess://', 'vless://', 'trojan://', 'ss://', 'ssr://']
        )

    def is_subscription_link(self, url: str) -> bool:
        """判断是否为订阅链接"""
        url_lower = url.lower()
        parsed = urlparse(url_lower)

        # 检查文件扩展名
        path = parsed.path
        if any(path.endswith(ext) for ext in ['.yaml', '.yml', '.txt', '.conf', '.json', '.list']):
            return True

        # 检查路径中的关键词
        path_lower = path.lower()
        if any(keyword in path_lower for keyword in ['subscribe', 'sub', 'clash', 'v2ray', 'proxy']):
            return True

        # 检查域名中的关键词
        domain = parsed.netloc.lower()
        if any(keyword in domain for keyword in ['sub', 'subscribe', 'node', 'proxy']):
            return True

        return False

    async def test_link_validity(self, url: str) -> Dict[str, Any]:
        """测试链接有效性"""
        try:
            headers = {
                'User-Agent': self.user_agents[0],
                'Accept': '*/*',
            }

            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers, allow_redirects=True) as response:
                    if response.status == 200:
                        content = await response.text()

                        # 检查内容是否是有效的节点数据
                        is_valid = self.validate_node_content(content)

                        return {
                            'valid': is_valid,
                            'status': response.status,
                            'content_type': response.headers.get('Content-Type'),
                            'size': len(content),
                            'nodes_found': len(self.extract_links_from_text(content)),
                            'is_github': 'github' in url.lower(),
                        }
                    else:
                        return {
                            'valid': False,
                            'status': response.status,
                            'error': f"HTTP {response.status}",
                        }

        except Exception as e:
            return {
                'valid': False,
                'status': 0,
                'error': str(e),
            }

    def validate_node_content(self, content: str) -> bool:
        """验证节点内容有效性"""
        if not content.strip():
            return False

        # 尝试Base64解码
        try:
            if len(content) % 4 == 0 and re.match(r'^[A-Za-z0-9+/=]+$', content):
                decoded = base64.b64decode(content).decode('utf-8')
                content = decoded
        except:
            pass

        # 检查是否包含节点链接
        links = self.extract_links_from_text(content)
        if len(links) > 0:
            return True

        # 检查是否是有效的JSON（可能是Clash配置）
        try:
            data = json.loads(content)
            if isinstance(data, dict) and ('proxies' in data or 'Proxy' in data):
                return True
        except:
            pass

        # 检查是否是YAML格式（可能是Clash配置）
        if any(keyword in content.lower() for keyword in self.node_keywords):
            return True

        return False

    def is_github_url(self, url: str) -> bool:
        """判断是否为GitHub URL"""
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.github_patterns)

    def convert_github_url(self, url: str) -> str:
        """将GitHub URL转换为RAW URL"""
        url_lower = url.lower()

        # 如果是GitHub blob链接，转换为raw
        if 'github.com' in url_lower and '/blob/' in url_lower:
            url_lower = url_lower.replace('/blob/', '/raw/')

        # 确保是raw.githubusercontent.com
        if 'github.com' in url_lower and '/raw/' not in url_lower:
            url_lower = url_lower.replace('github.com', 'raw.githubusercontent.com')
            url_lower = url_lower.replace('/blob/', '/')

        return url_lower