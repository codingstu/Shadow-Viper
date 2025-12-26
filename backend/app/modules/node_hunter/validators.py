# backend/app/modules/node_hunter/validators.py
import asyncio
import socket
import time
import aiohttp
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class NodeTestResult:
    port_open: bool = False
    tcp_ping_ms: int = -1
    http_test: bool = False # 仅适用于 HTTP/SOCKS 代理
    google_test: bool = False
    youtube_test: bool = False
    netflix_test: bool = False
    juejin_test: bool = False
    connection_time_ms: int = -1
    total_score: int = 0

TEST_TARGETS = {
    "google": {"url": "https://www.google.com/generate_204", "timeout": 3},
    "juejin": {"url": "https://juejin.cn/robots.txt", "timeout": 5},
    "baidu": {"url": "https://www.baidu.com", "timeout": 3}  # <--- 新增：百度测试
}

async def test_port_connectivity(node: Dict[str, Any]) -> Dict[str, Any]:
    host, port = node['host'], node['port']
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0) # 稍微放宽一点 TCP 超时
        res = sock.connect_ex((host, port))
        sock.close()
        if res == 0:
            return {"port_open": True, "ping_ms": int((time.time() - start) * 1000), "error": None}
        return {"port_open": False, "ping_ms": -1, "error": f"Error {res}"}
    except Exception as e:
        return {"port_open": False, "ping_ms": -1, "error": str(e)}

async def test_http_proxy(node: Dict[str, Any], target_name: str) -> bool:
    """仅测试标准 HTTP/SOCKS 代理"""
    target = TEST_TARGETS.get(target_name)
    if not target: return False
    
    protocol = node.get('protocol', '').lower()
    # 如果不是标准代理协议，跳过此测试（视为通过，依赖 TCP 测试）
    if protocol not in ['http', 'https', 'socks4', 'socks5']:
        return True 

    try:
        proxy_url = f"{protocol}://{node['host']}:{node['port']}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=target["timeout"])) as session:
            async with session.get(target["url"], proxy=proxy_url, ssl=False) as resp:
                return resp.status < 500
    except:
        return False

async def test_node_network(node: Dict[str, Any]) -> NodeTestResult:
    res = NodeTestResult()
    
    # 1. TCP Ping (这是所有节点的基础)
    port_test = await test_port_connectivity(node)
    res.port_open = port_test["port_open"]
    res.tcp_ping_ms = port_test["ping_ms"]
    
    if not res.port_open: return res
    
    # 2. 协议感知测试
    # 对于 VMess/VLess/Trojan，我们无法在 Python 中直接测试 HTTP 连通性
    # 因此，如果 TCP 通了，我们就认为它大概率是活的，给予基础分
    
    protocol = node.get('protocol', '').lower()
    is_complex_proto = protocol in ['vmess', 'vless', 'trojan', 'ssr']

    # === 新增逻辑开始 ===
    # 如果是标记为 CN (回国) 的节点，只测百度，不测 Google
    if node.get('country') == 'CN':
        # ⏱️ 增加计时器
        start_time = time.time()
        res.china_test = await test_http_proxy(node, "baidu")
        end_time = time.time()
        if res.china_test:
            # 计算真实 HTTP 延迟 (毫秒)
            http_latency = int((end_time - start_time) * 1000)
            res.connection_time_ms = http_latency  # 记录下来

            # 🏆 动态评分系统 (速度越快，分数越高，排序越靠前)
            if http_latency < 800:
                res.total_score += 30  # 极速
            elif http_latency < 1500:
                res.total_score += 20  # 良好
            elif http_latency < 3000:
                res.total_score += 10  # 一般
            else:
                res.total_score += 5  # 勉强能用
            # 如果需要，也可以顺便测一下 juejin
            res.juejin_test = await test_http_proxy(node, "juejin")

        # 强制修正：如果 TCP 通了但 HTTP 没通，且是复杂协议，依然给基础分
        if is_complex_proto and res.total_score == 0:
            res.total_score = 5

        res.total_score = max(0, res.total_score)
        return res
    # === 新增逻辑结束 ===


    if is_complex_proto:
        # 对于复杂协议，TCP 通了就给分，但延迟必须低
        res.total_score = 5
        if res.tcp_ping_ms > 300: res.total_score -= 2
        if res.tcp_ping_ms > 800: res.total_score -= 2
        
        # 标记为“通过”，因为我们无法证伪
        res.google_test = True
        res.juejin_test = True
    else:
        # 对于标准代理，进行真实 HTTP 测试
        res.google_test = await test_http_proxy(node, "google")
        res.juejin_test = await test_http_proxy(node, "juejin")
        
        if res.google_test: res.total_score += 3
        if res.juejin_test: res.total_score += 3

    # 最终存活判定：分数 > 0
    res.total_score = max(0, res.total_score)
    
    return res
