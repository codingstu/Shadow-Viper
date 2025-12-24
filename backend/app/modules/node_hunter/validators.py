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
    http_test: bool = False
    google_test: bool = False
    youtube_test: bool = False
    netflix_test: bool = False
    connection_time_ms: int = -1
    total_score: int = 0

TEST_TARGETS = {
    "google": {"url": "https://www.google.com/generate_204", "timeout": 5},
    "netflix": {"url": "https://www.netflix.com/nfavicon.ico", "timeout": 8},
    "youtube": {"url": "https://www.youtube.com/favicon.ico", "timeout": 6},
    "cloudflare": {"url": "https://1.1.1.1/cdn-cgi/trace", "timeout": 4}
}

async def test_port_connectivity(node: Dict[str, Any]) -> Dict[str, Any]:
    host, port = node['host'], node['port']
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        res = sock.connect_ex((host, port))
        sock.close()
        if res == 0:
            return {"port_open": True, "ping_ms": int((time.time() - start) * 1000), "error": None}
        return {"port_open": False, "ping_ms": -1, "error": f"Error {res}"}
    except Exception as e:
        return {"port_open": False, "ping_ms": -1, "error": str(e)}

async def test_http_target(node: Dict[str, Any], target_name: str) -> bool:
    target = TEST_TARGETS.get(target_name)
    if not target: return False
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=target["timeout"])) as session:
            url = f"http://{node['host']}:{node['port']}" if node['port'] != 443 else f"https://{node['host']}:{node['port']}"
            async with session.get(url, ssl=False) as resp:
                return resp.status < 500
    except:
        return False

async def test_node_network(node: Dict[str, Any]) -> NodeTestResult:
    res = NodeTestResult()
    port_test = await test_port_connectivity(node)
    res.port_open = port_test["port_open"]
    res.tcp_ping_ms = port_test["ping_ms"]
    
    if not res.port_open: return res
    
    # Parallel tests
    tasks = [
        test_http_target(node, "google"),
        test_http_target(node, "youtube"),
        test_http_target(node, "netflix"),
        test_http_target(node, "cloudflare")
    ]
    results = await asyncio.gather(*tasks)
    
    res.google_test, res.youtube_test, res.netflix_test, res.http_test = results
    res.total_score = sum(results) + (1 if res.netflix_test else 0) # Bonus for Netflix
    
    return res
