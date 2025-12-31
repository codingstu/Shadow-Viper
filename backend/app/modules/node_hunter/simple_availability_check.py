#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔥 简化版节点可用性检测 - 去除有问题的模块
只做基础的：SOCKS5/HTTP 代理连接测试 + 延迟测量
不做复杂的速度测试（暂时放弃）
"""

import asyncio
import httpx
import time
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AvailabilityLevel(Enum):
    DEAD = 0
    BASIC = 2
    VERIFIED = 3

@dataclass
class AvailabilityResult:
    node_id: str
    level: AvailabilityLevel
    http_latency_ms: int = 0
    tcp_latency_ms: int = 0
    http_ok: bool = False
    protocol_handshake_ok: bool = False
    health_score: int = 0
    error_message: str = ""

async def check_node_simple(host: str, port: int, protocol: str = "socks5", timeout: int = 10) -> AvailabilityResult:
    """
    简单节点检测：通过代理访问测试网站
    """
    node_id = f"{host}:{port}"
    
    try:
        # 构建代理 URL
        proxy_url = f"{protocol}://{host}:{port}"
        
        # 建立 httpx 客户端并通过代理测试连接
        start = time.time()
        
        # 使用统一的 proxy 参数（适用于 httpx 0.28+）
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=timeout,
            verify=False,
        ) as client:
            # 尝试访问简单的网站（使用 HTTP 而不是 HTTPS 来加快速度）
            try:
                response = await client.get("http://www.gstatic.com/generate_204", follow_redirects=True)
                latency = int((time.time() - start) * 1000)
                
                # 204 或 200 都表示成功
                if response.status_code in [200, 204]:
                    return AvailabilityResult(
                        node_id=node_id,
                        level=AvailabilityLevel.VERIFIED,
                        http_latency_ms=latency,
                        http_ok=True,
                        protocol_handshake_ok=True,
                        health_score=100,
                    )
                else:
                    return AvailabilityResult(
                        node_id=node_id,
                        level=AvailabilityLevel.BASIC,
                        http_latency_ms=latency,
                        http_ok=False,
                        error_message=f"HTTP {response.status_code}",
                        health_score=50,
                    )
            except httpx.ProxyError as e:
                # 代理本身的问题
                return AvailabilityResult(
                    node_id=node_id,
                    level=AvailabilityLevel.DEAD,
                    error_message=f"Proxy Error: {str(e)[:80]}",
                    health_score=0,
                )
    except asyncio.TimeoutError:
        return AvailabilityResult(
            node_id=node_id,
            level=AvailabilityLevel.DEAD,
            error_message="Timeout",
            health_score=0,
        )
    except Exception as e:
        error = str(e)
        # 判断是否是网络问题而不是代理问题
        if "closed pipe" in error or "connection refused" in error.lower():
            level = AvailabilityLevel.DEAD
            health = 0
        else:
            level = AvailabilityLevel.BASIC
            health = 30
            
        return AvailabilityResult(
            node_id=node_id,
            level=level,
            error_message=error[:100],
            health_score=health,
        )

async def check_nodes_batch_simple(nodes: List[Dict], max_concurrent: int = 20) -> List[AvailabilityResult]:
    """
    批量检测节点 - 简化版
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_with_semaphore(node):
        async with semaphore:
            protocol = node.get('protocol', 'socks5')
            # 转换协议名称
            if protocol in ['ss', 'ssr', 'trojan']:
                protocol = 'socks5'
            elif protocol in ['http']:
                protocol = 'http'
            else:
                protocol = 'socks5'
                
            result = await check_node_simple(
                node.get('host'),
                node.get('port'),
                protocol=protocol,
                timeout=8
            )
            return result
    
    # 并发检测所有节点
    results = await asyncio.gather(
        *[check_with_semaphore(n) for n in nodes],
        return_exceptions=True
    )
    
    # 过滤异常
    return [r for r in results if isinstance(r, AvailabilityResult)]

def get_health_statistics(results: List[AvailabilityResult]) -> Dict:
    """统计检测结果"""
    total = len(results)
    verified = len([r for r in results if r.level == AvailabilityLevel.VERIFIED])
    basic = len([r for r in results if r.level == AvailabilityLevel.BASIC])
    dead = len([r for r in results if r.level == AvailabilityLevel.DEAD])
    avg_score = sum(r.health_score for r in results) / total if total > 0 else 0
    
    return {
        'total': total,
        'verified': verified,
        'basic': basic,
        'dead': dead,
        'avg_health_score': avg_score,
    }
