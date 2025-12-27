# backend/app/modules/node_hunter/china_hunter.py
import asyncio
import aiohttp
import re
import logging
import base64
import yaml
from typing import List, Dict, Any, Tuple

try:
    from .parsers import parse_node_url
except ImportError:
    from parsers import parse_node_url

logger = logging.getLogger(__name__)


class ChinaHunter:
    """
    🇨🇳 智能回国节点猎手 (V4: TG/Discord/Twitter 全网聚合版)
    特性：
    1. 接入 TelegramV2rayCollector & LalatinaHub (数万节点的大池子)。
    2. 增强型关键字过滤，覆盖中国主流城市和云厂商。
    3. 智能解析混合格式 (Base64, YAML, Text)。
    """

    def __init__(self):
        self.scan_cycle_count = 0
        self.source_stats = {}

        # 🎯 关键字过滤器：大幅扩充国内城市和运营商
        self.cn_keywords = [
            "回国", "back", "CN", "China", "中国",
            "上海", "北京", "杭州", "深圳", "广州", "成都", "武汉", "天津", "重庆", "南京", "长沙", "苏州",
            "Shanghai", "Beijing", "Shenzhen", "Hangzhou", "Guangzhou", "Chengdu", "Wuhan",
            "Aliyun", "Tencent", "Huawei", "Qcloud", "BGP", "CT", "CU", "CM",  # 运营商/云厂商
            "江苏", "浙江", "广东", "四川", "山东"
        ]

        self.sources = [
            # === 👑 神级聚合 (专门爬取 TG/Discord/Twitter) ===
            "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/mix",
            "https://raw.githubusercontent.com/LalatinaHub/Mineral/master/result/nodes",
            "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/EternityAir",

            # === 🔵 Telegram 订阅源 (Clash/YAML 格式) ===
            "https://raw.githubusercontent.com/vveg26/get_proxy/main/dist/clash.config.yaml",
            "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
            "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
            "https://raw.githubusercontent.com/juewuy/ShellClash/master/public/public.yaml",

            # === 🟠 经典订阅源 (Base64/Txt) ===
            "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
            "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
            "https://raw.githubusercontent.com/learnhard-cn/free_proxy_ss/main/free",
            "https://raw.githubusercontent.com/tbbatbb/Proxy/master/dist/v2ray.config.txt",

            # === 🟢 专精 CN/IP 直连列表 (HTTP/SOCKS5) ===
            "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CN/data.txt",
            "https://raw.githubusercontent.com/juepile/Proxy-List/main/China.txt",
            "https://raw.githubusercontent.com/list-404/CN-Proxy/main/http.txt",
            "https://raw.githubusercontent.com/peasoft/NoWars/main/result.txt",
            # 🔥 新增：更多 HTTP/SOCKS5 源
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
            "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        ]

        # 初始化状态
        for src in self.sources:
            self.source_stats[src] = {"is_disabled": False, "disabled_at": 0, "retry_fails": 0}

    async def fetch_all(self) -> List[Dict[str, Any]]:
        self.scan_cycle_count += 1
        current_cycle = self.scan_cycle_count

        target_urls = []
        for url in list(self.sources):
            stats = self.source_stats.get(url, {"is_disabled": False, "disabled_at": 0, "retry_fails": 0})
            if stats["is_disabled"]:
                if (current_cycle - stats["disabled_at"]) >= 10: target_urls.append(url)
            else:
                target_urls.append(url)

        if not target_urls: return []

        logger.info(f"🇨🇳 [全网猎手] 扫描 {len(target_urls)} 个聚合源 (含TG/Discord采集库)...")

        tasks = [self._fetch_url(url) for url in target_urls]
        results = await asyncio.gather(*tasks)

        merged_nodes = []
        seen = set()

        for i, (nodes, is_success) in enumerate(results):
            url = target_urls[i]
            if url not in self.source_stats: self.source_stats[url] = {"is_disabled": False, "disabled_at": 0,
                                                                       "retry_fails": 0}
            stats = self.source_stats[url]

            if is_success:
                if stats["is_disabled"]:
                    stats["is_disabled"] = False
                    stats["retry_fails"] = 0

                for node in nodes:
                    # 🔍 核心筛选
                    if self._is_cn_node(node, url):
                        # 强制加上国旗
                        if "🇨🇳" not in node.get('name', ''):
                            node['name'] = f"🇨🇳 {node.get('name')}"

                        node['country'] = 'CN'
                        node['type'] = 'back_to_china'

                        unique_id = f"{node['host']}:{node['port']}"
                        if unique_id not in seen:
                            seen.add(unique_id)
                            merged_nodes.append(node)
            else:
                if not stats["is_disabled"]:
                    stats["is_disabled"] = True
                    stats["disabled_at"] = current_cycle

        logger.info(f"🇨🇳 [全网猎手] 经深度筛选，捕获 {len(merged_nodes)} 个回国节点")
        return merged_nodes

    def _is_cn_node(self, node: Dict, source_url: str) -> bool:
        """判断是否为回国节点"""
        # 🔥 核心修复：更严格的判断，防止误伤
        # 1. 专精源直通
        if "CN" in source_url or "China" in source_url or "cn-proxies" in source_url:
            return True

        # 2. 关键字匹配 (不区分大小写)
        name = node.get('name', '').upper()
        
        # 明确的回国关键字
        back_home_keywords = ["回国", "BACK"]
        for kw in back_home_keywords:
            if kw in name:
                return True

        # 城市和运营商关键字 (仅当没有明确的“出境”标志时)
        exit_keywords = ["US", "JP", "HK", "SG", "TW", "KR", "出", "->"]
        has_exit_keyword = any(kw in name for kw in exit_keywords)
        
        if not has_exit_keyword:
            for kw in self.cn_keywords:
                if kw.upper() in name:
                    return True

        return False

    async def _fetch_url(self, url: str) -> Tuple[List[Dict[str, Any]], bool]:
        nodes = []
        try:
            # 增加超时，因为 TelegramV2rayCollector 文件很大
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status != 200: return [], False
                    text = await resp.text()

                    # 🕵️ 智能格式识别
                    if "proxies:" in text or url.endswith(".yaml") or url.endswith(".yml"):
                        nodes.extend(self._parse_yaml(text))

                    elif self._is_likely_base64(text):
                        decoded = self._safe_base64_decode(text)
                        if decoded:
                            nodes.extend(self._extract_links(decoded))

                    else:
                        nodes.extend(self._extract_links(text))
                        nodes.extend(self._extract_raw_ips(text))

            return nodes, True
        except Exception:
            return [], False

    def _parse_yaml(self, text: str) -> List[Dict[str, Any]]:
        nodes = []
        try:
            data = yaml.safe_load(text)
            proxies = data.get('proxies', [])
            for p in proxies:
                node = self._convert_clash_proxy(p)
                if node: nodes.append(node)
        except:
            pass
        return nodes

    def _convert_clash_proxy(self, p: Dict) -> Dict:
        try:
            proto = p.get('type')
            # 🔥 核心修复：允许 socks5 和 http
            if proto not in ['vmess', 'ss', 'trojan', 'vless', 'socks5', 'http']: return None

            return {
                "id": f"clash_{proto}_{p.get('server')}_{p.get('port')}",
                "name": p.get('name'),
                "protocol": proto,
                "host": p.get('server'),
                "port": int(p.get('port')),
                "uuid": p.get('uuid'),
                "password": p.get('password'),
                "cipher": p.get('cipher'),
                "network": p.get('network', 'tcp'),
                "tls": 'tls' if p.get('tls') else 'none',
                "sni": p.get('servername'),
                "path": p.get('ws-path') or p.get('ws-opts', {}).get('path'),
                "host_header": p.get('ws-headers', {}).get('Host')
            }
        except:
            return None

    def _extract_links(self, text: str) -> List[Dict[str, Any]]:
        nodes = []
        for line in text.splitlines():
            line = line.strip()
            if not line: continue
            
            # 🔥 核心修复：手动解析 socks5:// 和 http:// 链接
            if line.startswith("socks5://"):
                try:
                    # 简单解析 socks5://user:pass@host:port 或 socks5://host:port
                    parts = line.replace("socks5://", "").split("@")
                    if len(parts) == 2:
                        auth, server = parts
                        host, port = server.split(":")
                        nodes.append({
                            "id": f"socks5_{host}_{port}",
                            "name": f"SOCKS5 {host}",
                            "protocol": "socks5",
                            "host": host,
                            "port": int(port),
                        })
                    else:
                        host, port = parts[0].split(":")
                        nodes.append({
                            "id": f"socks5_{host}_{port}",
                            "name": f"SOCKS5 {host}",
                            "protocol": "socks5",
                            "host": host,
                            "port": int(port),
                        })
                except: pass
                continue

            node = parse_node_url(line)
            if node: nodes.append(node)
        return nodes

    def _extract_raw_ips(self, text: str) -> List[Dict[str, Any]]:
        nodes = []
        regex = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)'
        matches = re.findall(regex, text)
        for ip, port in matches:
            nodes.append({
                "id": f"cn_http_{ip}_{port}",
                "name": f"HTTP Proxy {ip}",
                "protocol": "http",
                "host": ip,
                "port": int(port),
            })
        return nodes

    def _is_likely_base64(self, text: str) -> bool:
        clean = text.strip()
        if " " in clean or "\n" in clean or len(clean) < 20: return False
        if clean.startswith("vmess://") or clean.startswith("ss://"): return False
        return True

    def _safe_base64_decode(self, text: str) -> str:
        try:
            text = text.strip()
            return base64.b64decode(text + '=' * (-len(text) % 4)).decode('utf-8', errors='ignore')
        except:
            return None
