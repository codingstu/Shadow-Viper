#!/usr/bin/env python3
"""
Clash基础检测模块 - 使用mihomo内核进行节点可用性检测
支持 VMess, VLESS, Trojan, Shadowsocks 等协议
"""

import asyncio
import json
import subprocess
import tempfile
import os
import yaml
import httpx
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClashCheckResult:
    """Clash检测结果"""
    is_available: bool
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    protocol: Optional[str] = None


class ClashBasicChecker:
    """Clash基础检测器"""
    
    def __init__(self, mihomo_path: str = None):
        """
        初始化检测器
        
        Args:
            mihomo_path: mihomo内核路径，默认使用backend/bin/mihomo
        """
        if mihomo_path is None:
            # 获取项目根目录
            current_dir = Path(__file__).parent
            backend_dir = current_dir.parent.parent.parent
            mihomo_path = backend_dir / "bin" / "mihomo"
        
        self.mihomo_path = Path(mihomo_path)
        if not self.mihomo_path.exists():
            raise FileNotFoundError(f"Mihomo内核不存在: {self.mihomo_path}")
        
        # 确保可执行权限
        os.chmod(self.mihomo_path, 0o755)
        
        self.test_url = "http://www.gstatic.com/generate_204"
        self.timeout = 10  # 秒
        
    def generate_clash_config(self, node: Dict, port: int = 7890) -> Dict:
        """
        生成Clash配置
        
        Args:
            node: 节点配置
            port: 代理端口
            
        Returns:
            Clash配置字典
        """
        config = {
            "mixed-port": port,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "silent",
            "proxies": [node],
            "proxy-groups": [{
                "name": "PROXY",
                "type": "select",
                "proxies": [node.get("name", "proxy")]
            }],
            "rules": ["MATCH,PROXY"]
        }
        return config
    
    async def test_node_with_clash(self, node: Dict, port: int = None) -> ClashCheckResult:
        """
        使用Clash测试单个节点
        
        Args:
            node: 节点配置
            port: 代理端口（随机分配）
            
        Returns:
            检测结果
        """
        if port is None:
            # 随机选择一个未使用的端口 (10000-20000)
            import random
            port = random.randint(10000, 20000)
        
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = self.generate_clash_config(node, port)
            yaml.dump(config, f, allow_unicode=True)
            config_path = f.name
        
        process = None
        try:
            # 启动mihomo进程
            process = await asyncio.create_subprocess_exec(
                str(self.mihomo_path),
                "-f", config_path,
                "-d", tempfile.gettempdir(),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            # 等待mihomo启动并准备好接收请求（增加等待时间）
            await asyncio.sleep(3)
            
            # 测试连接
            start_time = asyncio.get_event_loop().time()
            
            # 使用 AsyncHTTPTransport + mounts（httpx 0.25+ 异步方式）
            http_transport = httpx.AsyncHTTPTransport(proxy=f"http://127.0.0.1:{port}")
            https_transport = httpx.AsyncHTTPTransport(proxy=f"http://127.0.0.1:{port}")
            
            async with httpx.AsyncClient(
                mounts={
                    "http://": http_transport,
                    "https://": https_transport
                },
                timeout=self.timeout,
                follow_redirects=False,
                verify=False
            ) as client:
                response = await client.get(self.test_url)
                
            elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # 接受204和200状态码
            if response.status_code in [204, 200]:
                return ClashCheckResult(
                    is_available=True,
                    latency_ms=elapsed_ms,
                    protocol=node.get("type", "unknown")
                )
            else:
                return ClashCheckResult(
                    is_available=False,
                    error_message=f"HTTP {response.status_code}",
                    protocol=node.get("type", "unknown")
                )
                
        except asyncio.TimeoutError:
            return ClashCheckResult(
                is_available=False,
                error_message="连接超时",
                protocol=node.get("type", "unknown")
            )
        except Exception as e:
            return ClashCheckResult(
                is_available=False,
                error_message=str(e),
                protocol=node.get("type", "unknown")
            )
        finally:
            # 清理：停止进程和删除配置文件
            if process and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=2)
                except:
                    process.kill()
            
            try:
                os.unlink(config_path)
            except:
                pass
    
    async def check_nodes_batch(self, nodes: List[Dict], max_concurrent: int = 5) -> List[ClashCheckResult]:
        """
        批量检测节点
        
        Args:
            nodes: 节点列表
            max_concurrent: 最大并发数
            
        Returns:
            检测结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def check_with_semaphore(node):
            async with semaphore:
                return await self.test_node_with_clash(node)
        
        tasks = [check_with_semaphore(node) for node in nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ClashCheckResult(
                    is_available=False,
                    error_message=f"检测异常: {str(result)}",
                    protocol=nodes[i].get("type", "unknown")
                ))
            else:
                final_results.append(result)
        
        return final_results


async def check_node_clash(node: Dict) -> ClashCheckResult:
    """
    便捷函数：检测单个节点
    
    Args:
        node: 节点配置
        
    Returns:
        检测结果
    """
    checker = ClashBasicChecker()
    return await checker.test_node_with_clash(node)


async def check_nodes_clash(nodes: List[Dict], max_concurrent: int = 5) -> List[ClashCheckResult]:
    """
    便捷函数：批量检测节点
    
    Args:
        nodes: 节点列表
        max_concurrent: 最大并发数
        
    Returns:
        检测结果列表
    """
    checker = ClashBasicChecker()
    return await checker.check_nodes_batch(nodes, max_concurrent)


# 测试代码
if __name__ == "__main__":
    # 测试节点示例（VMess）
    test_node = {
        "name": "测试节点",
        "type": "vmess",
        "server": "example.com",
        "port": 443,
        "uuid": "12345678-1234-1234-1234-123456789012",
        "alterId": 0,
        "cipher": "auto",
        "network": "ws",
        "ws-opts": {
            "path": "/",
            "headers": {
                "Host": "example.com"
            }
        }
    }
    
    async def test():
        result = await check_node_clash(test_node)
        print(f"检测结果: {result}")
    
    asyncio.run(test())
