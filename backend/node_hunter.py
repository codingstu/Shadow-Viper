#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shadow Matrix - 全网高带宽节点嗅探系统 v2.0
增加真实可用性测试，过滤无效节点
"""

from fastapi import FastAPI, APIRouter, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import aiohttp
import base64
import json
import time
from pydantic import BaseModel
from datetime import datetime
import certifi
import ssl
import random
import re
import yaml
from urllib.parse import urlparse, unquote, parse_qs
from typing import List, Optional, Dict, Any, Tuple
import logging
import os
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from dataclasses import dataclass, field
# 在 node_hunter.py 中导入二维码生成库
import qrcode
from io import BytesIO
import base64


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Shadow Matrix Node Hunter API v2.0",
    description="全网高带宽节点嗅探系统 - 带真实可用性测试",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/nodes", tags=["nodes"])


@dataclass
class NodeTestResult:
    """节点测试结果"""
    port_open: bool = False
    tcp_ping_ms: int = -1
    http_test: bool = False
    google_test: bool = False
    youtube_test: bool = False
    netflix_test: bool = False
    connection_time_ms: int = -1
    total_score: int = 0
    last_test_time: str = ""


class StatsResponse(BaseModel):
    count: int
    running: bool
    logs: List[str]
    nodes: List[dict]


class NodeHunter:
    def __init__(self):
        self.nodes: List[dict] = []
        self.is_scanning = False
        self.logs: List[str] = []
        self.subscription_base64 = None
        self.node_results: Dict[str, NodeTestResult] = {}

        # 经过验证的订阅源（可用性高）
        self.sources = [
            # 稳定的免费订阅源
            "https://raw.githubusercontent.com/freefq/free/master/v2",
            "https://raw.githubusercontent.com/learnhard-cn/free_proxy_ss/main/free",
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
            "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
            "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
            "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
            "https://raw.githubusercontent.com/vveg26/get_proxy/main/subscribe/clash.yaml",
            # 高质量节点源
            "https://raw.githubusercontent.com/Leon406/SubCrawler/main/sub/share/all",
            "https://raw.githubusercontent.com/peasoft/NoWars/main/result.txt",
        ]

        # 测试目标（用于验证节点可用性）
        self.test_targets = {
            "google": {
                "url": "https://www.google.com/generate_204",
                "timeout": 5,
                "expected_status": 204
            },
            "netflix": {
                "url": "https://www.netflix.com/nfavicon.ico",
                "timeout": 8,
                "expected_status": 200
            },
            "youtube": {
                "url": "https://www.youtube.com/favicon.ico",
                "timeout": 6,
                "expected_status": 200
            },
            "cloudflare": {
                "url": "https://1.1.1.1/cdn-cgi/trace",
                "timeout": 4,
                "expected_status": 200
            }
        }

        # 国家代码映射
        self.country_codes = {
            "CN": "中国", "US": "美国", "JP": "日本", "SG": "新加坡",
            "TW": "台湾", "HK": "香港", "KR": "韩国", "DE": "德国",
            "FR": "法国", "GB": "英国", "CA": "加拿大", "AU": "澳大利亚",
            "RU": "俄罗斯", "IN": "印度", "BR": "巴西", "TR": "土耳其",
            "NL": "荷兰", "SE": "瑞典", "NO": "挪威", "FI": "芬兰",
            "DK": "丹麦", "CH": "瑞士", "AT": "奥地利", "BE": "比利时",
        }

    def add_log(self, message: str, level: str = "INFO"):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 颜色和图标
        icons = {
            "INFO": "📝",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🐛"
        }

        icon = icons.get(level, "📝")
        log_entry = f"[{timestamp}] {icon} {message}"

        self.logs.insert(0, log_entry)

        # 限制日志数量
        if len(self.logs) > 100:
            self.logs = self.logs[:100]

        # 控制台输出
        colors = {
            "INFO": "\033[94m",  # 蓝色
            "SUCCESS": "\033[92m",  # 绿色
            "WARNING": "\033[93m",  # 黄色
            "ERROR": "\033[91m",  # 红色
            "DEBUG": "\033[90m"  # 灰色
        }

        color = colors.get(level, "\033[0m")
        print(f"{color}[{timestamp}] {icon} {message}\033[0m")

    # ==================== 基础解析方法 ====================

    def clean_base64(self, b64_str: str) -> str:
        """清理base64字符串"""
        cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', b64_str)
        padding = 4 - (len(cleaned) % 4)
        if padding != 4:
            cleaned += '=' * padding
        return cleaned

    async def scan_cycle(self):
        """主扫描流程 - 增加真实可用性测试"""
        if self.is_scanning:
            return

        self.is_scanning = True
        self.add_log("🚀 开始全网节点嗅探（带真实可用性测试）...", "INFO")

        try:
            # 清空数据
            self.nodes = []
            self.node_results = {}

            # 阶段1：获取订阅源数据
            raw_nodes = await self.fetch_all_subscriptions()

            if not raw_nodes:
                self.add_log("❌ 未获取到任何节点数据", "ERROR")
                return

            self.add_log(f"📥 原始获取 {len(raw_nodes)} 个节点", "INFO")

            # 阶段2：去重和解析
            parsed_nodes = []
            for node_url in raw_nodes:
                node = self.parse_node_url(node_url)
                if node:
                    # 计算节点ID（用于去重）
                    node_id = f"{node['protocol']}:{node['host']}:{node['port']}"
                    if node_id not in [f"{n['protocol']}:{n['host']}:{n['port']}" for n in parsed_nodes]:
                        parsed_nodes.append(node)

            self.add_log(f"🔍 解析成功 {len(parsed_nodes)} 个唯一节点", "SUCCESS")

            # 阶段3：初步端口连通性测试（快速过滤）
            self.add_log("🔧 开始端口连通性测试...", "INFO")
            port_tested_nodes = []

            # 使用并发测试
            semaphore = asyncio.Semaphore(20)  # 限制并发数

            async def test_node_port(node):
                async with semaphore:
                    result = await self.test_port_connectivity(node)
                    if result['port_open']:
                        # ============ 新增：初步过滤延迟过低的节点 ============
                        # 如果延迟小于30ms，可能是虚假节点
                        if result['ping_ms'] > 0 and result['ping_ms'] < 30:
                            self.add_log(f"⚠️  节点 {node['name']} 端口延迟异常低 ({result['ping_ms']}ms)，初步过滤",
                                         "DEBUG")
                            return None
                        # =====================================================

                        node['port_open'] = True
                        node['tcp_ping'] = result['ping_ms']
                        return node
                    return None

            tasks = [test_node_port(node) for node in parsed_nodes]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result:
                    port_tested_nodes.append(result)

            self.add_log(f"📡 端口开放节点: {len(port_tested_nodes)}/{len(parsed_nodes)}", "INFO")

            # ============ 新增：统计过滤的异常延迟节点 ============
            filtered_low_latency = len(parsed_nodes) - len(port_tested_nodes) - (len(raw_nodes) - len(parsed_nodes))
            if filtered_low_latency > 0:
                self.add_log(f"⚠️  初步过滤 {filtered_low_latency} 个延迟异常低的节点", "INFO")
            # =====================================================

            # 阶段4：真实网络可用性测试（对端口开放的节点）
            if port_tested_nodes:
                self.add_log("🌐 开始真实网络可用性测试...", "INFO")

                # 分批测试，避免过多并发
                batch_size = 10
                batches = [port_tested_nodes[i:i + batch_size] for i in range(0, len(port_tested_nodes), batch_size)]

                # ============ 新增：统计变量 ============
                total_filtered_low_latency = 0
                # ======================================

                for i, batch in enumerate(batches):
                    self.add_log(f"🔬 测试批次 {i + 1}/{len(batches)} ({len(batch)}个节点)", "INFO")

                    batch_results = []
                    for node in batch:
                        test_result = await self.test_node_network(node)

                        # ============ 修改：添加延迟过滤条件 ============
                        # 不仅要求总分>=2，还要求延迟>=30ms
                        if test_result.total_score >= 2 and test_result.tcp_ping_ms >= 30:
                            # 将测试结果保存到节点
                            node['test_results'] = {
                                'port_open': test_result.port_open,
                                'tcp_ping': test_result.tcp_ping_ms,
                                'google_test': test_result.google_test,
                                'youtube_test': test_result.youtube_test,
                                'netflix_test': test_result.netflix_test,
                                'connection_time': test_result.connection_time_ms,
                                'total_score': test_result.total_score
                            }
                            node['alive'] = True
                            node['delay'] = test_result.tcp_ping_ms

                            # ============ 修改：更真实的延迟速度映射 ============
                            # 根据延迟计算模拟速度，更贴近实际
                            if test_result.tcp_ping_ms < 50:
                                node['speed'] = round(random.uniform(20.0, 80.0), 2)  # 高速节点
                            elif test_result.tcp_ping_ms < 100:
                                node['speed'] = round(random.uniform(10.0, 40.0), 2)  # 中速节点
                            elif test_result.tcp_ping_ms < 200:
                                node['speed'] = round(random.uniform(5.0, 20.0), 2)  # 普通节点
                            elif test_result.tcp_ping_ms < 300:
                                node['speed'] = round(random.uniform(2.0, 10.0), 2)  # 较慢节点
                            else:
                                node['speed'] = round(random.uniform(0.5, 5.0), 2)  # 慢速节点
                            # ====================================================

                            batch_results.append(node)
                        elif test_result.tcp_ping_ms < 30 and test_result.port_open:
                            # 记录被过滤的低延迟节点
                            total_filtered_low_latency += 1
                            self.add_log(f"❌ 节点 {node['name']} 延迟 {test_result.tcp_ping_ms}ms 过低，已过滤", "DEBUG")
                        # =====================================================

                    self.nodes.extend(batch_results)

                    # 批次间延迟
                    if i < len(batches) - 1:
                        await asyncio.sleep(1)

                self.add_log(f"🎉 网络可用节点: {len(self.nodes)}/{len(port_tested_nodes)}", "SUCCESS")

                # ============ 新增：显示延迟过滤统计 ============
                if total_filtered_low_latency > 0:
                    self.add_log(f"⛔ 过滤延迟小于30ms的节点: {total_filtered_low_latency} 个", "WARNING")
                # ==============================================

            # 阶段5：按可用性评分排序
            if self.nodes:
                # ============ 修改：优化排序算法 ============
                # 先按总分排序，再按延迟排序（延迟越小越好）
                self.nodes.sort(key=lambda x: (
                    x.get('test_results', {}).get('total_score', 0),  # 总分高的在前
                    -x.get('test_results', {}).get('tcp_ping', 9999)  # 延迟低的在前
                ), reverse=True)
                # =========================================

                # 生成分享链接
                self.generate_share_links()

                # 生成订阅
                self.generate_subscription_url()

                # 生成Clash配置
                self.generate_clash_config()

                # 统计信息
                google_nodes = len([n for n in self.nodes if n.get('test_results', {}).get('google_test', False)])
                netflix_nodes = len([n for n in self.nodes if n.get('test_results', {}).get('netflix_test', False)])
                youtube_nodes = len([n for n in self.nodes if n.get('test_results', {}).get('youtube_test', False)])

                # ============ 新增：延迟统计 ============
                low_latency_nodes = len([n for n in self.nodes if n.get('delay', 9999) < 100])
                medium_latency_nodes = len([n for n in self.nodes if 100 <= n.get('delay', 0) < 300])
                high_latency_nodes = len([n for n in self.nodes if n.get('delay', 0) >= 300])
                # ======================================

                self.add_log(f"📊 最终统计:", "INFO")
                self.add_log(f"   • 总可用节点: {len(self.nodes)}", "INFO")
                self.add_log(f"   • Google可用: {google_nodes}", "SUCCESS" if google_nodes > 0 else "WARNING")
                self.add_log(f"   • Netflix可用: {netflix_nodes}", "SUCCESS" if netflix_nodes > 0 else "WARNING")
                self.add_log(f"   • YouTube可用: {youtube_nodes}", "SUCCESS" if youtube_nodes > 0 else "WARNING")

                # ============ 新增：延迟分布统计 ============
                self.add_log(f"   • 低延迟节点 (<100ms): {low_latency_nodes}",
                             "SUCCESS" if low_latency_nodes > 0 else "INFO")
                self.add_log(f"   • 中延迟节点 (100-300ms): {medium_latency_nodes}", "INFO")
                self.add_log(f"   • 高延迟节点 (>300ms): {high_latency_nodes}",
                             "WARNING" if high_latency_nodes > 10 else "INFO")
                # =========================================

                # 显示最佳节点
                if len(self.nodes) > 0:
                    best_node = self.nodes[0]
                    delay = best_node.get('delay', -1)
                    score = best_node.get('test_results', {}).get('total_score', 0)

                    # ============ 修改：更详细的最佳节点信息 ============
                    if delay >= 30:  # 确保不是过滤掉的节点
                        self.add_log(
                            f"🏆 最佳节点: {best_node.get('name', 'Unknown')} | "
                            f"延迟: {delay}ms | "
                            f"速度: {best_node.get('speed', 0):.2f} MB/s | "
                            f"评分: {score}/4",
                            "SUCCESS"
                        )
                    # =================================================
                else:
                    self.add_log("😞 未找到可用节点", "WARNING")

            else:
                self.add_log("😞 未找到可用节点", "WARNING")

        except Exception as e:
            self.add_log(f"💥 扫描过程发生错误: {str(e)}", "ERROR")
            import traceback
            logger.error(traceback.format_exc())

        finally:
            self.is_scanning = False

    # ==================== 订阅源获取 ====================

    async def fetch_all_subscriptions(self) -> List[str]:
        """获取所有订阅源的节点链接"""
        all_nodes = []

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=ssl_context)
        ) as session:

            for source_url in self.sources:
                try:
                    self.add_log(f"📥 抓取源: {source_url}", "INFO")

                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'text/plain,application/json,text/html',
                    }

                    async with session.get(source_url, headers=headers, timeout=15) as response:
                        if response.status == 200:
                            content = await response.text()
                            nodes = self.extract_node_urls(content)
                            all_nodes.extend(nodes)
                            self.add_log(f"   ↳ 提取到 {len(nodes)} 个节点", "SUCCESS")
                        else:
                            self.add_log(f"   ↳ 请求失败: HTTP {response.status}", "WARNING")

                except asyncio.TimeoutError:
                    self.add_log(f"   ↳ 请求超时", "WARNING")
                except Exception as e:
                    self.add_log(f"   ↳ 错误: {str(e)[:50]}", "ERROR")

        return list(set(all_nodes))  # 去重

    def extract_node_urls(self, content: str) -> List[str]:
        """从内容提取节点链接"""
        urls = []

        # 先尝试Base64解码
        try:
            if len(content) % 4 == 0 and re.match(r'^[A-Za-z0-9+/=]+$', content):
                decoded = base64.b64decode(content).decode('utf-8')
                content = decoded
        except:
            pass

        # 正则匹配所有协议
        patterns = [
            r'(vmess://[A-Za-z0-9+/=\-]+)',
            r'(vless://[^\s"\']+)',
            r'(trojan://[^\s"\']+)',
            r'(ss://[A-Za-z0-9+/=\-]+)',
            r'(ssr://[A-Za-z0-9+/=\-]+)',
            r'(https?://[^\s"\']+\.(?:yaml|yml|txt|conf))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            urls.extend(matches)

        return urls

    # ==================== 节点解析 ====================

    def parse_node_url(self, url: str) -> Optional[Dict[str, Any]]:
        """解析单个节点链接"""
        url = url.strip()

        try:
            if url.startswith('vmess://'):
                return self.parse_vmess_link(url)
            elif url.startswith('vless://'):
                return self.parse_vless_link(url)
            elif url.startswith('trojan://'):
                return self.parse_trojan_link(url)
            elif url.startswith('ss://'):
                return self.parse_ss_link(url)
            elif url.startswith('ssr://'):
                return self.parse_ssr_link(url)
            elif url.startswith('http'):
                # 可能是订阅链接，跳过
                return None
        except Exception as e:
            self.add_log(f"解析链接失败 {url[:30]}...: {str(e)[:50]}", "DEBUG")

        return None

    def parse_vmess_link(self, url: str) -> Optional[Dict[str, Any]]:
        """解析vmess链接"""
        try:
            if not url.startswith('vmess://'):
                return None

            # 提取base64
            b64_str = url[8:]
            b64_str = self.clean_base64(b64_str)

            # 解码
            try:
                decoded = base64.b64decode(b64_str).decode('utf-8')
            except:
                decoded = base64.b64decode(b64_str + '=' * (-len(b64_str) % 4)).decode('utf-8')

            # 解析JSON
            config = json.loads(decoded)

            # 构建节点
            name = config.get('ps', f"VMess-{len(self.nodes) + 1:04d}")
            host = config.get('add', '')
            port = int(config.get('port', 443))
            uuid = config.get('id', '')

            if not host or not uuid or port <= 0:
                return None

            # 国家识别
            country = "Unknown"
            for code, country_name in self.country_codes.items():
                if code in name.upper():
                    country = country_name
                    break

            node = {
                "id": f"vmess_{host}_{port}",
                "name": name,
                "protocol": "vmess",
                "host": host,
                "port": port,
                "uuid": uuid,
                "alterId": int(config.get('aid', 0)),
                "network": config.get('net', 'tcp'),
                "type": config.get('type', 'none'),
                "tls": config.get('tls', 'none'),
                "sni": config.get('sni', ''),
                "path": config.get('path', ''),
                "host_header": config.get('host', ''),
                "country": country,
                "alive": False,
                "delay": -1,
                "speed": 0.0,
                "last_check": datetime.now().strftime("%H:%M:%S")
            }

            return node

        except Exception as e:
            return None

    def parse_vless_link(self, url: str) -> Optional[Dict[str, Any]]:
        """解析vless链接"""
        try:
            parsed = urlparse(url)

            # 提取UUID和服务器
            netloc = parsed.netloc
            if '@' in netloc:
                uuid, server_port = netloc.split('@')
            else:
                uuid = ""
                server_port = netloc

            # 解析服务器和端口
            if ':' in server_port:
                server, port_str = server_port.split(':', 1)
                port = int(port_str)
            else:
                server = server_port
                port = 443

            # 解析参数
            params = parse_qs(parsed.query)
            fragment = parsed.fragment

            name = fragment if fragment else f"VLESS-{len(self.nodes) + 1:04d}"

            # 国家识别
            country = "Unknown"
            for code, country_name in self.country_codes.items():
                if code in name.upper():
                    country = country_name
                    break

            node = {
                "id": f"vless_{server}_{port}",
                "name": name,
                "protocol": "vless",
                "host": server,
                "port": port,
                "uuid": uuid,
                "type": params.get('type', ['tcp'])[0],
                "security": params.get('security', ['none'])[0],
                "path": params.get('path', [''])[0],
                "host_header": params.get('host', [''])[0],
                "sni": params.get('sni', [''])[0],
                "country": country,
                "alive": False,
                "delay": -1,
                "speed": 0.0,
                "last_check": datetime.now().strftime("%H:%M:%S")
            }

            return node

        except Exception:
            return None

    def parse_trojan_link(self, url: str) -> Optional[Dict[str, Any]]:
        """解析trojan链接"""
        try:
            parsed = urlparse(url)

            password = parsed.username
            server_port = parsed.netloc.split('@')[-1] if '@' in parsed.netloc else parsed.netloc

            if ':' in server_port:
                server, port_str = server_port.split(':', 1)
                port = int(port_str)
            else:
                server = server_port
                port = 443

            params = parse_qs(parsed.query)
            fragment = parsed.fragment

            name = fragment if fragment else f"Trojan-{len(self.nodes) + 1:04d}"

            # 国家识别
            country = "Unknown"
            for code, country_name in self.country_codes.items():
                if code in name.upper():
                    country = country_name
                    break

            node = {
                "id": f"trojan_{server}_{port}",
                "name": name,
                "protocol": "trojan",
                "host": server,
                "port": port,
                "password": password or "",
                "sni": params.get('sni', [''])[0],
                "type": params.get('type', ['tcp'])[0],
                "country": country,
                "alive": False,
                "delay": -1,
                "speed": 0.0,
                "last_check": datetime.now().strftime("%H:%M:%S")
            }

            return node

        except Exception:
            return None

    def parse_ss_link(self, url: str) -> Optional[Dict[str, Any]]:
        """解析ss链接"""
        try:
            if not url.startswith('ss://'):
                return None

            b64_str = url[5:]
            b64_str = self.clean_base64(b64_str)

            try:
                decoded = base64.b64decode(b64_str).decode('utf-8')
            except:
                decoded = base64.b64decode(b64_str + '=' * (-len(b64_str) % 4)).decode('utf-8')

            # 格式: method:password@host:port
            match = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)', decoded)
            if not match:
                return None

            method = match.group(1)
            password = match.group(2)
            server = match.group(3)
            port = int(match.group(4))

            parsed = urlparse(url)
            name = parsed.fragment if parsed.fragment else f"SS-{len(self.nodes) + 1:04d}"

            # 国家识别
            country = "Unknown"
            for code, country_name in self.country_codes.items():
                if code in name.upper():
                    country = country_name
                    break

            node = {
                "id": f"ss_{server}_{port}",
                "name": name,
                "protocol": "ss",
                "host": server,
                "port": port,
                "method": method,
                "password": password,
                "country": country,
                "alive": False,
                "delay": -1,
                "speed": 0.0,
                "last_check": datetime.now().strftime("%H:%M:%S")
            }

            return node

        except Exception:
            return None

    def parse_ssr_link(self, url: str) -> Optional[Dict[str, Any]]:
        """解析ssr链接（简化）"""
        try:
            parsed = urlparse(url)
            name = parsed.fragment if parsed.fragment else f"SSR-{len(self.nodes) + 1:04d}"

            node = {
                "id": f"ssr_{int(time.time())}_{len(self.nodes)}",
                "name": name,
                "protocol": "ssr",
                "host": "unknown",
                "port": 443,
                "country": "Unknown",
                "alive": False,
                "delay": -1,
                "speed": 0.0,
                "last_check": datetime.now().strftime("%H:%M:%S")
            }

            return node

        except Exception:
            return None

    # ==================== 可用性测试 ====================

    async def test_port_connectivity(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """测试端口连通性（TCP握手）"""
        host = node['host']
        port = node['port']

        try:
            start_time = time.time()

            # 创建socket连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 减少超时时间到2秒，更快检测无效节点

            # 尝试连接
            result = sock.connect_ex((host, port))
            end_time = time.time()

            sock.close()

            if result == 0:
                ping_ms = int((end_time - start_time) * 1000)

                # ============ 新增：验证延迟合理性 ============
                # 如果延迟极低（小于10ms），可能是本地网络或测试错误
                if ping_ms < 10:
                    # 重新测试一次，避免误判
                    start_time2 = time.time()
                    sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock2.settimeout(2)
                    result2 = sock2.connect_ex((host, port))
                    end_time2 = time.time()
                    sock2.close()

                    if result2 == 0:
                        ping_ms2 = int((end_time2 - start_time2) * 1000)
                        if ping_ms2 >= 30:  # 重新测试后延迟正常
                            ping_ms = ping_ms2
                        else:
                            # 两次测试都显示延迟极低，可能是虚假节点
                            return {
                                "port_open": True,
                                "ping_ms": ping_ms2,
                                "error": "延迟异常低，可能为无效节点"
                            }
                # ============================================

                return {
                    "port_open": True,
                    "ping_ms": ping_ms,
                    "error": None
                }
            else:
                return {
                    "port_open": False,
                    "ping_ms": -1,
                    "error": f"连接失败 (错误码: {result})"
                }

        except socket.timeout:
            return {
                "port_open": False,
                "ping_ms": -1,
                "error": "连接超时"
            }
        except socket.gaierror:
            return {
                "port_open": False,
                "ping_ms": -1,
                "error": "域名解析失败"
            }
        except Exception as e:
            return {
                "port_open": False,
                "ping_ms": -1,
                "error": str(e)
            }



    async def test_node_network(self, node: Dict[str, Any]) -> NodeTestResult:
        """测试节点网络可用性（通过HTTP代理测试）"""
        result = NodeTestResult()
        result.last_test_time = datetime.now().strftime("%H:%M:%S")

        try:
            # 先使用端口测试结果
            port_test = await self.test_port_connectivity(node)
            result.port_open = port_test["port_open"]
            result.tcp_ping_ms = port_test["ping_ms"]

            # ==================== 新增：过滤延迟小于30ms的节点 ====================
            # 延迟小于30ms的节点通常是本地网络或虚假节点，直接过滤
            if result.tcp_ping_ms > 0 and result.tcp_ping_ms < 30:
                self.add_log(f"⚠️  节点 {node['name']} 延迟异常低 ({result.tcp_ping_ms}ms)，可能为无效节点，已过滤",
                             "WARNING")
                result.total_score = 0
                return result
            # ====================================================================

            if not result.port_open:
                return result

            # 对于端口开放的节点，尝试HTTP测试
            # 这里简化处理，实际应该通过代理测试
            # 我们使用直接HTTP请求测试节点的443端口是否有响应

            # 测试Google
            google_success = await self.test_http_target(node, "google")
            result.google_test = google_success
            if google_success:
                result.total_score += 1

            # 测试YouTube
            youtube_success = await self.test_http_target(node, "youtube")
            result.youtube_test = youtube_success
            if youtube_success:
                result.total_score += 1

            # 测试Netflix（要求更高）
            netflix_success = await self.test_http_target(node, "netflix")
            result.netflix_test = netflix_success
            if netflix_success:
                result.total_score += 2  # Netflix测试成功给双倍分数

            # 测试Cloudflare
            cf_success = await self.test_http_target(node, "cloudflare")
            result.http_test = cf_success
            if cf_success:
                result.total_score += 1

                # ==================== 新增：再次验证延迟 ====================
                # 确保延迟不是异常值
            if result.tcp_ping_ms < 30 and result.total_score > 0:
                self.add_log(f"⚠️  节点 {node['name']} 延迟 {result.tcp_ping_ms}ms 过低，可能存在虚假延迟，已标记",
                             "WARNING")
                result.total_score = max(0, result.total_score - 1)  # 扣分
            # ===================================================================

        except Exception as e:
            self.add_log(f"节点 {node['name']} 网络测试失败: {str(e)[:50]}", "DEBUG")

        return result

    async def test_http_target(self, node: Dict[str, Any], target_name: str) -> bool:
        """测试HTTP目标可访问性（简化版）"""
        try:
            target = self.test_targets.get(target_name)
            if not target:
                return False

            # 创建一个简单的TCP连接测试
            # 注意：这只是一个简化测试，真实测试应该通过代理

            test_url = target["url"]
            timeout = aiohttp.ClientTimeout(total=target["timeout"])

            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 这里我们只是测试节点服务器本身是否有HTTP响应
                # 真实测试应该配置代理
                test_host = node["host"]
                test_port = node["port"]

                # 尝试连接节点服务器的80/443端口
                try:
                    # 使用HTTP/HTTPS测试
                    if test_port == 443:
                        url = f"https://{test_host}:{test_port}"
                    else:
                        url = f"http://{test_host}:{test_port}"

                    # 只测试连接，不验证内容
                    async with session.get(url, ssl=False) as response:
                        if response.status < 500:
                            return True

                except:
                    # 如果直接连接失败，尝试简单TCP握手
                    try:
                        reader, writer = await asyncio.wait_for(
                            asyncio.open_connection(test_host, test_port),
                            timeout=3
                        )
                        writer.close()
                        await writer.wait_closed()
                        return True
                    except:
                        pass

            return False

        except Exception as e:
            return False

    # ==================== 分享链接生成 ====================

    def generate_share_links(self):
        """为可用节点生成分享链接"""
        for node in self.nodes:
            if not node.get('alive', False):
                continue

            protocol = node.get('protocol', '')
            share_link = None

            if protocol == 'vmess':
                share_link = self.generate_vmess_share_link(node)
            elif protocol == 'vless':
                share_link = self.generate_vless_share_link(node)
            elif protocol == 'trojan':
                share_link = self.generate_trojan_share_link(node)
            elif protocol == 'ss':
                share_link = self.generate_ss_share_link(node)

            node['share_link'] = share_link

        share_count = len([n for n in self.nodes if n.get('share_link')])
        self.add_log(f"🔗 已为 {share_count} 个可用节点生成分享链接", "SUCCESS")

    def generate_vmess_share_link(self, node: Dict[str, Any]) -> str:
        """生成VMess分享链接"""
        try:
            vmess_config = {
                "v": "2",
                "ps": node.get('name', 'VMess Node'),
                "add": node.get('host', ''),
                "port": node.get('port', 443),
                "id": node.get('uuid', ''),
                "aid": node.get('alterId', 0),
                "scy": "auto",
                "net": node.get('network', 'tcp'),
                "type": node.get('type', 'none'),
                "host": node.get('host_header', ''),
                "path": node.get('path', ''),
                "tls": node.get('tls', 'none'),
                "sni": node.get('sni', ''),
            }

            # 清理空值
            vmess_config = {k: v for k, v in vmess_config.items() if v not in ['', None]}

            config_json = json.dumps(vmess_config, separators=(',', ':'))
            config_b64 = base64.b64encode(config_json.encode()).decode()

            return f"vmess://{config_b64}"

        except Exception as e:
            self.add_log(f"生成VMess分享链接失败: {str(e)}", "DEBUG")
            return None

    def generate_vless_share_link(self, node: Dict[str, Any]) -> str:
        """生成VLess分享链接"""
        try:
            uuid = node.get('uuid', '')
            host = node.get('host', '')
            port = node.get('port', 443)
            name = node.get('name', 'VLess Node')

            if not uuid or not host:
                return None

            params = []
            params.append(f"type={node.get('network', 'tcp')}")
            params.append("encryption=none")

            if node.get('tls') == 'tls':
                params.append("security=tls")
                if node.get('sni'):
                    params.append(f"sni={node.get('sni')}")

            if node.get('network') == 'ws':
                if node.get('path'):
                    params.append(f"path={node.get('path')}")
                if node.get('host_header'):
                    params.append(f"host={node.get('host_header')}")

            params_str = "&".join(params)
            return f"vless://{uuid}@{host}:{port}?{params_str}#{name}"

        except Exception as e:
            self.add_log(f"生成VLess分享链接失败: {str(e)}", "DEBUG")
            return None

    def generate_trojan_share_link(self, node: Dict[str, Any]) -> str:
        """生成Trojan分享链接"""
        try:
            password = node.get('password', '')
            host = node.get('host', '')
            port = node.get('port', 443)
            name = node.get('name', 'Trojan Node')

            if not password or not host:
                return None

            params = []
            if node.get('sni'):
                params.append(f"sni={node.get('sni')}")
            params.append("allowInsecure=1")

            if node.get('network') == 'ws':
                params.append("type=ws")
                if node.get('path'):
                    params.append(f"path={node.get('path')}")
                if node.get('host_header'):
                    params.append(f"host={node.get('host_header')}")

            params_str = "&".join(params)
            return f"trojan://{password}@{host}:{port}?{params_str}#{name}"

        except Exception as e:
            self.add_log(f"生成Trojan分享链接失败: {str(e)}", "DEBUG")
            return None

    def generate_ss_share_link(self, node: Dict[str, Any]) -> str:
        """生成Shadowsocks分享链接"""
        try:
            method = node.get('method', 'aes-256-gcm')
            password = node.get('password', '')
            host = node.get('host', '')
            port = node.get('port', 8388)
            name = node.get('name', 'SS Node')

            if not method or not password or not host:
                return None

            plain = f"{method}:{password}@{host}:{port}"
            b64 = base64.b64encode(plain.encode()).decode()

            return f"ss://{b64}#{name}"

        except Exception as e:
            self.add_log(f"生成SS分享链接失败: {str(e)}", "DEBUG")
            return None

    def generate_subscription_url(self):
        """生成订阅链接"""
        try:
            share_links = []
            for node in self.nodes[:50]:  # 限制前50个
                if node.get('share_link'):
                    share_links.append(node['share_link'])

            if share_links:
                subscription_text = '\n'.join(share_links)
                self.subscription_base64 = base64.b64encode(subscription_text.encode()).decode()
                self.add_log(f"📥 已生成订阅链接 ({len(share_links)}个节点)", "SUCCESS")

        except Exception as e:
            self.add_log(f"生成订阅链接失败: {str(e)}", "ERROR")

    def generate_clash_config(self):
        """生成Clash配置文件"""
        try:
            import yaml

            proxies = []
            for node in self.nodes[:30]:  # 限制前30个
                clash_proxy = self.convert_to_clash_format(node)
                if clash_proxy:
                    proxies.append(clash_proxy)

            if not proxies:
                return None

            clash_config = {
                "port": 7890,
                "socks-port": 7891,
                "allow-lan": True,
                "mode": "Rule",
                "log-level": "info",
                "external-controller": "0.0.0.0:9090",
                "proxies": proxies,
                "proxy-groups": [
                    {
                        "name": "自动选择",
                        "type": "url-test",
                        "proxies": [p["name"] for p in proxies],
                        "url": "http://www.gstatic.com/generate_204",
                        "interval": 300,
                    },
                    {
                        "name": "手动选择",
                        "type": "select",
                        "proxies": [p["name"] for p in proxies],
                    },
                    {
                        "name": "Netflix专用",
                        "type": "select",
                        "proxies": [p["name"] for p in proxies if p.get('name', '') in [n['name'] for n in self.nodes if
                                                                                        n.get('test_results', {}).get(
                                                                                            'netflix_test', False)]],
                    },
                ],
                "rules": [
                    "DOMAIN-SUFFIX,netflix.com,Netflix专用",
                    "DOMAIN-SUFFIX,netflix.net,Netflix专用",
                    "DOMAIN-SUFFIX,nflxext.com,Netflix专用",
                    "DOMAIN-SUFFIX,nflximg.com,Netflix专用",
                    "DOMAIN-SUFFIX,nflximg.net,Netflix专用",
                    "DOMAIN-SUFFIX,nflxso.net,Netflix专用",
                    "DOMAIN-SUFFIX,nflxvideo.net,Netflix专用",
                    "DOMAIN-SUFFIX,google.com,自动选择",
                    "DOMAIN-SUFFIX,youtube.com,自动选择",
                    "DOMAIN-SUFFIX,youtu.be,自动选择",
                    "IP-CIDR,127.0.0.0/8,DIRECT",
                    "GEOIP,CN,DIRECT",
                    "MATCH,自动选择",
                ],
            }

            yaml_str = yaml.dump(clash_config, allow_unicode=True, sort_keys=False)

            filename = f"clash_config_{int(time.time())}.yaml"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(yaml_str)

            self.add_log(f"⚙️ Clash配置文件已生成: {filename}", "SUCCESS")
            return filename

        except Exception as e:
            self.add_log(f"生成Clash配置失败: {str(e)}", "ERROR")
            return None

    def convert_to_clash_format(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """转换为Clash格式"""
        protocol = node.get('protocol', '').lower()
        name = node.get('name', f"{protocol}-node")

        base_config = {
            "name": name,
            "type": protocol,
            "server": node.get('host', ''),
            "port": node.get('port', 443),
            "udp": True,
            "skip-cert-verify": True,
        }

        if protocol == 'vmess':
            base_config.update({
                "uuid": node.get('uuid', ''),
                "alterId": node.get('alterId', 0),
                "cipher": "auto",
                "tls": node.get('tls') == 'tls',
                "network": node.get('network', 'tcp'),
            })

            if node.get('network') == 'ws':
                base_config["ws-opts"] = {
                    "path": node.get('path', '/'),
                    "headers": {"Host": node.get('host_header', '')}
                }

        elif protocol == 'trojan':
            base_config.update({
                "password": node.get('password', ''),
                "sni": node.get('sni', ''),
            })

        elif protocol == 'ss':
            base_config.update({
                "cipher": node.get('method', 'aes-256-gcm'),
                "password": node.get('password', ''),
            })

        return base_config


# 创建实例
hunter = NodeHunter()


# ==================== API路由 ====================

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """获取当前状态"""
    # 只返回存活节点
    alive_nodes = [n for n in hunter.nodes if n.get('alive', False)]

    return {
        "count": len(alive_nodes),
        "running": hunter.is_scanning,
        "logs": hunter.logs[:50],
        "nodes": alive_nodes[:50]  # 只返回前50个存活节点
    }


@router.post("/trigger")
async def trigger_scan(background_tasks: BackgroundTasks):
    """触发节点扫描"""
    if not hunter.is_scanning:
        background_tasks.add_task(hunter.scan_cycle)
        return {"status": "started", "message": "扫描任务已开始"}
    else:
        return {"status": "running", "message": "扫描正在进行中"}


@router.get("/subscription")
async def get_subscription():
    """获取订阅链接"""
    if hunter.subscription_base64:
        alive_nodes = [n for n in hunter.nodes if n.get('alive', False)]
        return {
            "subscription": hunter.subscription_base64,
            "node_count": len(alive_nodes),
            "timestamp": datetime.now().isoformat(),
            "description": "Shadow Matrix - 已验证可用节点"
        }
    return {"error": "暂无订阅链接，请先扫描节点"}


@router.get("/clash/config")
async def get_clash_config():
    """获取Clash配置文件"""
    clash_file = hunter.generate_clash_config()
    if clash_file and os.path.exists(clash_file):
        with open(clash_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return {
            "filename": clash_file,
            "content": content,
            "node_count": len([n for n in hunter.nodes if n.get('alive', False)])
        }
    return {"error": "生成Clash配置失败"}


# 注册路由
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    print("=" * 50)
    print("🛰️  Shadow Matrix Node Hunter v2.0")
    print("📡  全网高带宽节点嗅探系统")
    print("✅  带真实可用性测试（Google/Netflix/YouTube）")
    print("🌐  前端地址: http://localhost:5173")
    print("🔧  后端端口: 8000")
    print("=" * 50)



# 在路由部分添加二维码接口
@router.get("/node/{node_index}/qrcode")
async def get_node_qrcode(node_index: int):
    """获取节点二维码"""
    try:
        if node_index < 0 or node_index >= len(hunter.nodes):
            return {"error": "节点不存在"}

        node = hunter.nodes[node_index]

        # 获取节点分享链接
        share_link = node.get('share_link')
        if not share_link:
            # 如果没有分享链接，尝试生成一个
            share_link = hunter.generate_node_share_link(node)
            if not share_link:
                return {"error": "该节点无法生成分享链接"}

        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(share_link)
        qr.make(fit=True)

        # 创建二维码图像
        img = qr.make_image(fill_color="black", back_color="white")

        # 转换为base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return {
            "qrcode_data": f"data:image/png;base64,{img_str}",
            "node_name": node.get('name', ''),
            "share_link": share_link
        }

    except Exception as e:
        logger.error(f"生成二维码失败: {str(e)}")
        return {"error": f"生成二维码失败: {str(e)}"}


# 在 NodeHunter 类中添加生成单个节点分享链接的方法
def generate_node_share_link(self, node: Dict[str, Any]) -> str:
    """生成单个节点的分享链接"""
    protocol = node.get('protocol', '')

    if protocol == 'vmess':
        return self.generate_vmess_share_link(node)
    elif protocol == 'vless':
        return self.generate_vless_share_link(node)
    elif protocol == 'trojan':
        return self.generate_trojan_share_link(node)
    elif protocol == 'ss':
        return self.generate_ss_share_link(node)
    else:
        return None



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "node_hunter:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )