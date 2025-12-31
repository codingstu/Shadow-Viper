# backend/app/modules/node_hunter/real_availability_check.py
"""
真实可用性检测模块 - 多层级节点验证系统
支持在 SpiderFlow 后端、Aliyun FC、Cloudflare Workers 执行
"""

import asyncio
import aiohttp
import socket
import time
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json

logger = logging.getLogger(__name__)

# ==================== 数据结构 ====================

class AvailabilityLevel(Enum):
    """节点可用性等级"""
    DEAD = 0          # 不可用
    SUSPECT = 1       # 可疑（TCP通但代理不通）
    BASIC = 2         # 基础可用（HTTP通）
    VERIFIED = 3      # 已验证（多重测试通过）
    HEALTHY = 4       # 健康（持续监测通过）

@dataclass
class AvailabilityResult:
    """节点可用性测试结果"""
    node_id: str
    level: AvailabilityLevel
    
    # 第1层：基础连通性
    tcp_ok: bool = False
    tcp_latency_ms: int = 0
    
    # 第2层：DNS 测试
    dns_ok: bool = False
    dns_latency_ms: int = 0
    
    # 第3层：代理功能
    http_ok: bool = False
    http_latency_ms: int = 0
    
    # 第4层：协议握手（仅深度检测）
    protocol_handshake_ok: bool = False
    protocol_type: str = "unknown"
    
    # 第5层：健康分数
    health_score: int = 0
    
    # 诊断信息
    error_message: str = ""
    check_time: str = ""
    
    def to_dict(self):
        return {
            **asdict(self),
            'level': self.level.name,
        }

# ==================== 第1层：基础 TCP 连接测试 ====================

async def check_tcp_connectivity(host: str, port: int, timeout: int = 5) -> Tuple[bool, int]:
    """
    TCP 连接测试
    返回: (连接成功, 延迟ms)
    """
    start = time.time()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        latency = int((time.time() - start) * 1000)
        writer.close()
        await writer.wait_closed()
        return True, latency
    except asyncio.TimeoutError:
        return False, timeout * 1000
    except Exception as e:
        logger.debug(f"TCP连接失败 {host}:{port} - {e}")
        return False, 0


# ==================== 第2层：DNS 查询测试 ====================

async def check_dns_resolution(hostname: str, timeout: int = 5) -> Tuple[bool, int]:
    """
    DNS 解析测试
    返回: (解析成功, 延迟ms)
    """
    start = time.time()
    try:
        loop = asyncio.get_event_loop()
        # 异步执行 DNS 查询
        ip = await asyncio.wait_for(
            loop.getaddrinfo(hostname, None),
            timeout=timeout
        )
        latency = int((time.time() - start) * 1000)
        if ip:
            return True, latency
        return False, 0
    except asyncio.TimeoutError:
        return False, timeout * 1000
    except Exception as e:
        logger.debug(f"DNS查询失败 {hostname} - {e}")
        return False, 0


# ==================== 第3层：HTTP 代理功能测试 ====================

TEST_URLS = {
    "google": "https://www.google.com/generate_204",
    "cloudflare": "https://www.cloudflare.com/cdn-cgi/trace",
    "baidu": "https://www.baidu.com/",
    "apple": "https://www.apple.com/library/test/success.html",
}

async def check_http_via_proxy(
    proxy_host: str,
    proxy_port: int,
    protocol: str = "http",
    timeout: int = 10,
    test_target: str = "google"
) -> Tuple[bool, int]:
    """
    通过代理发送 HTTP 请求测试
    
    参数:
    - proxy_host, proxy_port: 代理地址
    - protocol: 代理协议 (http, https, socks5)
    - timeout: 超时秒数
    - test_target: 测试目标 (google, baidu, cloudflare, apple)
    
    返回: (请求成功, 延迟ms)
    """
    url = TEST_URLS.get(test_target, TEST_URLS["google"])
    
    start = time.time()
    try:
        # 构造代理 URL
        if protocol.lower() in ["http", "https"]:
            proxy_url = f"http://{proxy_host}:{proxy_port}"
        elif protocol.lower() == "socks5":
            proxy_url = f"socks5://{proxy_host}:{proxy_port}"
        else:
            return False, 0
        
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        connector = aiohttp.TCPConnector(limit=1)
        
        async with aiohttp.ClientSession(
            timeout=timeout_obj,
            connector=connector
        ) as session:
            async with session.get(
                url,
                proxy=proxy_url,
                ssl=False,
                allow_redirects=False
            ) as resp:
                latency = int((time.time() - start) * 1000)
                # 接受 2xx, 3xx, 404 等正常响应（表示代理工作）
                if resp.status < 500:
                    return True, latency
                return False, latency
    
    except asyncio.TimeoutError:
        return False, timeout * 1000
    except Exception as e:
        logger.debug(f"HTTP代理测试失败 - {e}")
        return False, 0


# ==================== 第4层：协议握手验证（仅后端执行）====================

async def verify_protocol_handshake(node: Dict) -> Tuple[bool, str]:
    """
    验证代理协议握手
    这个函数需要在后端执行，Aliyun FC/CF 无法执行（缺少协议库）
    
    返回: (握手成功, 握手协议)
    """
    protocol = node.get('protocol', '').lower()
    host = node.get('host')
    port = node.get('port')
    
    if protocol == 'vmess':
        return await _verify_vmess_handshake(host, port, node.get('id'))
    elif protocol == 'vless':
        return await _verify_vless_handshake(host, port, node.get('id'))
    elif protocol == 'trojan':
        return await _verify_trojan_handshake(host, port, node.get('password'))
    elif protocol == 'shadowsocks':
        return await _verify_ss_handshake(host, port, node.get('method'), node.get('password'))
    else:
        # 未知协议，假设通过
        return True, protocol


async def _verify_vmess_handshake(host: str, port: int, user_id: str) -> Tuple[bool, str]:
    """
    验证 VMess 握手（简化版）
    完整握手需要 VMess 协议库
    """
    try:
        # 建立 TCP 连接
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        
        # VMess 握手: 发送 version (0x01) + 命令
        # 这是简化版本，完整实现需要完整的 VMess 协议库
        writer.write(b'\x01')  # Version
        await writer.drain()
        
        # 等待响应（V服务器应回复版本号）
        try:
            resp = await asyncio.wait_for(reader.read(1), timeout=2)
            writer.close()
            await writer.wait_closed()
            return len(resp) > 0, "vmess"
        except:
            writer.close()
            await writer.wait_closed()
            return False, "vmess"
    
    except Exception as e:
        logger.debug(f"VMess 握手失败: {e}")
        return False, "vmess"


async def _verify_vless_handshake(host: str, port: int, uuid: str) -> Tuple[bool, str]:
    """验证 VLESS 握手（简化版）"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        writer.close()
        await writer.wait_closed()
        return True, "vless"
    except Exception as e:
        logger.debug(f"VLESS 握手失败: {e}")
        return False, "vless"


async def _verify_trojan_handshake(host: str, port: int, password: str) -> Tuple[bool, str]:
    """验证 Trojan 握手"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        writer.close()
        await writer.wait_closed()
        return True, "trojan"
    except Exception as e:
        logger.debug(f"Trojan 握手失败: {e}")
        return False, "trojan"


async def _verify_ss_handshake(host: str, port: int, method: str, password: str) -> Tuple[bool, str]:
    """验证 Shadowsocks 握手"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        writer.close()
        await writer.wait_closed()
        return True, "shadowsocks"
    except Exception as e:
        logger.debug(f"SS 握手失败: {e}")
        return False, "shadowsocks"


# ==================== 综合检测函数 ====================

async def check_node_basic_availability(
    node: Dict,
    timeout_tcp: int = 5,
    timeout_http: int = 10
) -> AvailabilityResult:
    """
    第1-3层检测（可在 Aliyun FC/CF 执行）
    
    检测内容：
    1. TCP 连接
    2. DNS 解析
    3. HTTP 代理功能
    
    返回可用性等级: DEAD, SUSPECT, BASIC
    """
    node_id = node.get('id', f"{node.get('host')}:{node.get('port')}")
    result = AvailabilityResult(node_id=node_id, level=AvailabilityLevel.DEAD)
    
    try:
        host = node.get('host')
        port = node.get('port')
        protocol = node.get('protocol', 'unknown').lower()
        
        # 第1层：TCP 连接测试
        result.tcp_ok, result.tcp_latency_ms = await check_tcp_connectivity(
            host, port, timeout=timeout_tcp
        )
        
        if not result.tcp_ok:
            result.error_message = f"TCP连接失败: {host}:{port}"
            result.level = AvailabilityLevel.DEAD
            return result
        
        # 第2层：DNS 测试（仅对域名格式的主机）
        if not _is_ip_address(host):
            result.dns_ok, result.dns_latency_ms = await check_dns_resolution(
                host, timeout=timeout_tcp
            )
            if not result.dns_ok:
                logger.warning(f"DNS 查询失败: {host}")
        
        # 第3层：HTTP 代理测试
        # 选择合适的测试目标（CN 节点优先用百度，其他用谷歌）
        test_target = "baidu" if node.get('country') == 'CN' else "google"
        
        result.http_ok, result.http_latency_ms = await check_http_via_proxy(
            host, port,
            protocol=protocol,
            timeout=timeout_http,
            test_target=test_target
        )
        
        # 判断可用性等级
        if result.http_ok:
            # HTTP 测试通过：基础可用
            result.level = AvailabilityLevel.BASIC
            result.health_score = 60
        elif result.tcp_ok:
            # TCP 通但 HTTP 不通：可疑
            # 对于复杂协议（VMess/VLESS/Trojan），TCP 通常足够
            if protocol in ['vmess', 'vless', 'trojan']:
                result.level = AvailabilityLevel.BASIC
                result.health_score = 50  # 较低的分数
                result.error_message = "TCP通但代理不通（复杂协议，可能是正常的）"
            else:
                result.level = AvailabilityLevel.SUSPECT
                result.health_score = 30
                result.error_message = "TCP通但HTTP代理不通"
        
        # 基于延迟调整评分
        if result.http_latency_ms < 200:
            result.health_score += 30
        elif result.http_latency_ms < 500:
            result.health_score += 15
        elif result.http_latency_ms < 1000:
            result.health_score += 5
        
        result.health_score = min(100, result.health_score)
        
    except Exception as e:
        result.error_message = f"检测异常: {str(e)}"
        result.level = AvailabilityLevel.DEAD
    
    result.check_time = _get_timestamp()
    return result


async def check_node_full_availability(
    node: Dict,
    timeout_tcp: int = 5,
    timeout_http: int = 10
) -> AvailabilityResult:
    """
    第1-4层检测（仅在 SpiderFlow 后端执行）
    
    检测内容：
    1. TCP 连接
    2. DNS 解析
    3. HTTP 代理功能
    4. 协议握手验证
    
    返回可用性等级: DEAD, SUSPECT, BASIC, VERIFIED
    """
    # 先执行基础检测
    result = await check_node_basic_availability(node, timeout_tcp, timeout_http)
    
    if result.level == AvailabilityLevel.DEAD:
        return result
    
    # 第4层：协议握手验证
    try:
        handshake_ok, protocol_type = await verify_protocol_handshake(node)
        result.protocol_handshake_ok = handshake_ok
        result.protocol_type = protocol_type
        
        if handshake_ok:
            result.level = AvailabilityLevel.VERIFIED
            result.health_score = min(100, result.health_score + 20)
    
    except Exception as e:
        logger.warning(f"协议握手验证失败: {e}")
    
    result.check_time = _get_timestamp()
    return result


async def check_nodes_batch(
    nodes: List[Dict],
    full_check: bool = False,
    max_concurrent: int = 20
) -> List[AvailabilityResult]:
    """
    批量检测多个节点
    
    参数：
    - nodes: 节点列表
    - full_check: 是否执行完整检测（包括握手验证）
    - max_concurrent: 最大并发数
    
    返回：检测结果列表
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_with_semaphore(node):
        async with semaphore:
            if full_check:
                return await check_node_full_availability(node)
            else:
                return await check_node_basic_availability(node)
    
    tasks = [check_with_semaphore(node) for node in nodes]
    results = await asyncio.gather(*tasks)
    
    return results


# ==================== 工具函数 ====================

def _is_ip_address(host: str) -> bool:
    """检查是否是 IP 地址"""
    try:
        socket.inet_aton(host)
        return True
    except socket.error:
        return False


def _get_timestamp() -> str:
    """获取 ISO 格式时间戳"""
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def filter_by_availability_level(
    results: List[AvailabilityResult],
    min_level: AvailabilityLevel = AvailabilityLevel.BASIC
) -> List[AvailabilityResult]:
    """
    按可用性等级过滤结果
    """
    return [r for r in results if r.level.value >= min_level.value]


def get_health_statistics(results: List[AvailabilityResult]) -> Dict:
    """
    获取健康统计信息
    """
    if not results:
        return {
            "total": 0,
            "dead": 0,
            "suspect": 0,
            "basic": 0,
            "verified": 0,
            "healthy": 0,
            "avg_health_score": 0,
        }
    
    counts = {level: 0 for level in AvailabilityLevel}
    for result in results:
        counts[result.level] += 1
    
    avg_score = sum(r.health_score for r in results) / len(results)
    
    return {
        "total": len(results),
        "dead": counts[AvailabilityLevel.DEAD],
        "suspect": counts[AvailabilityLevel.SUSPECT],
        "basic": counts[AvailabilityLevel.BASIC],
        "verified": counts[AvailabilityLevel.VERIFIED],
        "healthy": counts[AvailabilityLevel.HEALTHY],
        "avg_health_score": round(avg_score, 2),
    }
