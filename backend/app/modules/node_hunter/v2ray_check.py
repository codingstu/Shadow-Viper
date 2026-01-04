#!/usr/bin/env python3
"""
V2Ray 内核检测模块 - 用于检测 VMess, VLESS, Trojan 等多种协议
支持 Windows, macOS, Linux
"""

import asyncio
import json
import subprocess
import tempfile
import os
import httpx
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class V2RayCheckResult:
    """V2Ray检测结果"""
    is_available: bool
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    protocol: Optional[str] = None


class V2RayChecker:
    """V2Ray 检测器（使用 Xray 内核）"""
    
    def __init__(self, v2ray_path: str = None):
        """
        初始化检测器
        
        Args:
            v2ray_path: Xray 可执行文件路径
        """
        if v2ray_path is None:
            # 优先使用 Xray（更好的协议支持）
            candidates = [
                Path(__file__).parent.parent.parent.parent / 'bin' / 'xray',
                Path(__file__).parent.parent.parent.parent / 'bin' / 'v2ray',
                '/usr/local/bin/xray',
                '/usr/local/bin/v2ray',
                '/usr/bin/xray',
                '/usr/bin/v2ray',
                '/opt/xray/xray',
                '/opt/v2ray/v2ray',
            ]
            
            for path in candidates:
                if isinstance(path, str):
                    path = Path(path)
                if path.exists():
                    v2ray_path = str(path)
                    break
            
            if not v2ray_path:
                raise FileNotFoundError("找不到 Xray/V2Ray 可执行文件，请下载配置")
        
        self.v2ray_path = Path(v2ray_path)
        if not self.v2ray_path.exists():
            raise FileNotFoundError(f"Xray/V2Ray 不存在: {self.v2ray_path}")
        
        os.chmod(self.v2ray_path, 0o755)
        
        self.test_url = "http://www.gstatic.com/generate_204"
        self.timeout = 15  # V2Ray 启动可能较慢
    
    def generate_v2ray_config(self, node: Dict, port: int = 10808) -> Dict:
        """
        生成 V2Ray 配置
        
        Args:
            node: 节点配置（Clash 格式）
            port: 监听端口
            
        Returns:
            V2Ray 配置字典
        """
        config = {
            "inbounds": [{
                "port": port,
                "protocol": "http",
                "settings": {
                    "timeout": 300
                },
                "tag": "http-in"
            }],
            "outbounds": [{
                "protocol": node.get("type", "vmess"),
                "settings": self._build_outbound_settings(node),
                "streamSettings": self._build_stream_settings(node),
                "tag": "proxy-out"
            }],
            "routing": {
                "rules": [{
                    "type": "field",
                    "inboundTag": ["http-in"],
                    "outboundTag": "proxy-out"
                }]
            },
            "log": {
                "loglevel": "error"
            }
        }
        
        return config
    
    def _build_outbound_settings(self, node: Dict) -> Dict:
        """构建出站设置"""
        protocol = node.get("type", "vmess").lower()
        
        if protocol == "vmess":
            return {
                "vnext": [{
                    "address": node.get("server"),
                    "port": int(node.get("port", 443)),
                    "users": [{
                        "id": node.get("uuid"),
                        "alterId": int(node.get("alterId", 0)),
                        "security": node.get("cipher", "auto")
                    }]
                }]
            }
        elif protocol == "vless":
            return {
                "vnext": [{
                    "address": node.get("server"),
                    "port": int(node.get("port", 443)),
                    "users": [{
                        "id": node.get("uuid"),
                        "encryption": node.get("encryption", "none"),
                        "flow": node.get("flow", "")
                    }]
                }]
            }
        elif protocol == "trojan":
            return {
                "servers": [{
                    "address": node.get("server"),
                    "port": int(node.get("port", 443)),
                    "password": node.get("password", "")
                }]
            }
        elif protocol == "shadowsocks":
            return {
                "servers": [{
                    "address": node.get("server"),
                    "port": int(node.get("port", 443)),
                    "password": node.get("password", ""),
                    "method": node.get("cipher", "aes-256-gcm")
                }]
            }
        else:
            return {}
    
    def _build_stream_settings(self, node: Dict) -> Dict:
        """构建流设置"""
        protocol = node.get("type", "vmess").lower()
        stream_settings = {}
        
        network = node.get("network", "tcp")
        if network:
            stream_settings["network"] = network
        
        # TLS 设置
        if node.get("tls") or node.get("security") == "tls":
            stream_settings["security"] = "tls"
            stream_settings["tlsSettings"] = {
                "serverName": node.get("sni", node.get("server", ""))
            }
        
        # WebSocket 设置
        if network == "ws":
            stream_settings["wsSettings"] = {
                "path": node.get("path", "/"),
                "headers": {
                    "Host": node.get("host", node.get("server", ""))
                }
            }
        
        # Reality 设置 (VLESS)
        if protocol == "vless" and node.get("security") == "reality":
            stream_settings["security"] = "reality"
            stream_settings["realitySettings"] = {
                "serverName": node.get("sni", ""),
                "publicKey": node.get("pbk", ""),
                "shortId": node.get("sid", "")
            }
        
        return stream_settings
    
    async def test_node_with_v2ray(self, node: Dict, port: int = None) -> V2RayCheckResult:
        """
        使用 V2Ray 测试单个节点
        
        Args:
            node: 节点配置（Clash 格式）
            port: 监听端口
            
        Returns:
            检测结果
        """
        if port is None:
            import random
            port = random.randint(10000, 20000)
        
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = self.generate_v2ray_config(node, port)
            json.dump(config, f)
            config_path = f.name
        
        process = None
        try:
            # 启动 V2Ray 进程
            process = await asyncio.create_subprocess_exec(
                str(self.v2ray_path),
                "run", "-c", config_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            # 等待 V2Ray 启动（可能较慢）
            await asyncio.sleep(5)  # 增加到 5 秒，给 Xray 更多启动时间
            
            # 测试连接
            start_time = asyncio.get_event_loop().time()
            
            try:
                async with httpx.AsyncClient(
                    proxy=f"http://127.0.0.1:{port}",
                    timeout=10,
                    follow_redirects=False,
                    verify=False
                ) as client:
                    response = await client.get(self.test_url)
                
                elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                
                if response.status_code in [204, 200]:
                    return V2RayCheckResult(
                        is_available=True,
                        latency_ms=elapsed_ms,
                        protocol=node.get("type", "unknown")
                    )
                else:
                    return V2RayCheckResult(
                        is_available=False,
                        error_message=f"HTTP {response.status_code}",
                        protocol=node.get("type", "unknown")
                    )
            except asyncio.TimeoutError:
                return V2RayCheckResult(
                    is_available=False,
                    error_message="连接超时",
                    protocol=node.get("type", "unknown")
                )
            except Exception as e:
                return V2RayCheckResult(
                    is_available=False,
                    error_message=f"测试异常: {str(e)[:50]}",
                    protocol=node.get("type", "unknown")
                )
                
        except Exception as e:
            return V2RayCheckResult(
                is_available=False,
                error_message=f"启动异常: {str(e)[:50]}",
                protocol=node.get("type", "unknown")
            )
        finally:
            # 清理
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


async def check_node_v2ray(node: Dict) -> V2RayCheckResult:
    """便捷函数：检测单个节点"""
    try:
        checker = V2RayChecker()
        return await checker.test_node_with_v2ray(node)
    except FileNotFoundError:
        return V2RayCheckResult(
            is_available=False,
            error_message="Xray/V2Ray 未安装",
            protocol=node.get("type", "unknown")
        )


async def check_nodes_v2ray(nodes: List[Dict], max_concurrent: int = 3) -> List[V2RayCheckResult]:
    """便捷函数：批量检测节点（并发数较低因为 V2Ray 启动较慢）"""
    try:
        checker = V2RayChecker()
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def check_with_semaphore(node):
            async with semaphore:
                return await checker.test_node_with_v2ray(node)
        
        tasks = [check_with_semaphore(node) for node in nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(V2RayCheckResult(
                    is_available=False,
                    error_message=f"检测异常: {str(result)[:50]}",
                    protocol=nodes[i].get("type", "unknown")
                ))
            else:
                final_results.append(result)
        
        return final_results
    except FileNotFoundError:
        return [V2RayCheckResult(
            is_available=False,
            error_message="Xray/V2Ray 未安装",
            protocol=node.get("type", "unknown")
        ) for node in nodes]
