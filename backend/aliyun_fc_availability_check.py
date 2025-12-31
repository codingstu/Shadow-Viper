"""
Aliyun Function Compute 版本 - 轻量级节点检测
可直接部署到 Aliyun FC 作为 HTTP 触发函数
"""

import json
import asyncio
import aiohttp
import socket
import time
from typing import Dict, List, Tuple

# ==================== 简化版配置 ====================

TEST_URLS = {
    "baidu": "https://www.baidu.com/",
    "google": "https://www.google.com/generate_204",
}

TIMEOUT_TCP = 5
TIMEOUT_HTTP = 8


# ==================== 核心检测函数 ====================

async def tcp_check(host: str, port: int) -> Tuple[bool, int]:
    """TCP 连接检测"""
    start = time.time()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=TIMEOUT_TCP
        )
        latency = int((time.time() - start) * 1000)
        writer.close()
        await writer.wait_closed()
        return True, latency
    except:
        return False, TIMEOUT_TCP * 1000


async def http_check(host: str, port: int, is_cn: bool = False) -> Tuple[bool, int]:
    """HTTP 代理检测"""
    url = TEST_URLS["baidu"] if is_cn else TEST_URLS["google"]
    proxy_url = f"http://{host}:{port}"
    
    start = time.time()
    try:
        timeout_obj = aiohttp.ClientTimeout(total=TIMEOUT_HTTP)
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(url, proxy=proxy_url, ssl=False) as resp:
                latency = int((time.time() - start) * 1000)
                return resp.status < 500, latency
    except:
        return False, TIMEOUT_HTTP * 1000


async def check_single_node(node: Dict) -> Dict:
    """检测单个节点（轻量级）"""
    host = node.get('host')
    port = node.get('port')
    node_id = node.get('id', f"{host}:{port}")
    
    try:
        # TCP 检测
        tcp_ok, tcp_lat = await tcp_check(host, port)
        if not tcp_ok:
            return {
                'id': node_id,
                'success': False,
                'reason': 'TCP failed',
                'latency': tcp_lat
            }
        
        # HTTP 检测
        is_cn = node.get('country') == 'CN'
        http_ok, http_lat = await http_check(host, port, is_cn)
        
        return {
            'id': node_id,
            'success': http_ok or tcp_ok,  # TCP 通就认为可用
            'tcp_ok': tcp_ok,
            'http_ok': http_ok,
            'latency': http_lat if http_ok else tcp_lat,
        }
    
    except Exception as e:
        return {
            'id': node_id,
            'success': False,
            'reason': str(e),
            'latency': 0
        }


async def check_nodes_batch(nodes: List[Dict]) -> List[Dict]:
    """批量检测节点"""
    semaphore = asyncio.Semaphore(10)  # 最多 10 并发
    
    async def check_with_semaphore(node):
        async with semaphore:
            return await check_single_node(node)
    
    tasks = [check_with_semaphore(node) for node in nodes]
    return await asyncio.gather(*tasks)


# ==================== Aliyun FC 入口函数 ====================

def handler(event, context):
    """
    Aliyun FC HTTP 触发函数入口
    
    请求格式:
    POST /nodes/check
    {
        "nodes": [
            {"host": "1.1.1.1", "port": 443, "id": "node1", "country": "US"},
            ...
        ]
    }
    
    返回:
    {
        "success": true,
        "count": 10,
        "results": [
            {"id": "node1", "success": true, "latency": 100},
            ...
        ]
    }
    """
    try:
        # 解析请求
        body = json.loads(event.get('body', '{}'))
        nodes = body.get('nodes', [])
        
        if not nodes:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No nodes provided'})
            }
        
        # 执行异步检测
        results = asyncio.run(check_nodes_batch(nodes))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'count': len(results),
                'results': results
            }, ensure_ascii=False)
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


# ==================== 本地测试（用于开发） ====================

async def main():
    """本地测试"""
    test_nodes = [
        {"host": "1.1.1.1", "port": 443, "id": "node1", "country": "US"},
        {"host": "8.8.8.8", "port": 443, "id": "node2", "country": "US"},
    ]
    
    results = await check_nodes_batch(test_nodes)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
