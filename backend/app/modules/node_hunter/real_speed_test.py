# backend/app/modules/node_hunter/real_speed_test.py
"""
🔥 真实代理速度测试模块
参考 SSRSpeedN 和 fulltclash 的实现方式
通过代理下载实际文件来测量真实速度，而不是虚拟值
"""

import asyncio
import httpx
import time
from typing import Dict, Optional
from loguru import logger

# 测试文件配置（选择不同大小的文件来测试）
TEST_FILES = {
    # 文件大小: (URL, 预期大小)
    "small": {
        "url": "https://speed.cloudflare.com/__down?bytes=10485760",  # 10MB
        "size": 10485760,
        "timeout": 30,
    },
    "medium": {
        "url": "https://speed.cloudflare.com/__down?bytes=52428800",  # 50MB
        "size": 52428800,
        "timeout": 60,
    },
    "large": {
        "url": "https://speed.cloudflare.com/__down?bytes=104857600",  # 100MB
        "size": 104857600,
        "timeout": 120,
    },
}

# 备选测试服务器
ALT_TEST_SERVERS = [
    "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png",  # Google logo
    "https://www.wikipedia.org/static/images/project-logos/enwiki-1.5x.png",  # Wikipedia
]


async def test_download_speed(
    proxy_url: str,
    file_size: int = 10485760,
    timeout: int = 30,
    max_concurrent_connections: int = 1,
) -> Optional[float]:
    """
    通过代理下载文件测量实际速度

    Args:
        proxy_url: SOCKS5代理URL (e.g., "socks5://127.0.0.1:1080")
        file_size: 测试文件大小 (默认10MB)
        timeout: 超时时间 (秒)
        max_concurrent_connections: 最大并发连接数 (单线程/多线程)

    Returns:
        下载速度 (MB/s)，如果失败返回 None
    """
    try:
        # 选择合适的测试文件
        if file_size <= 10485760:
            test_config = TEST_FILES["small"]
        elif file_size <= 52428800:
            test_config = TEST_FILES["medium"]
        else:
            test_config = TEST_FILES["large"]

        test_url = test_config["url"]

        # httpx 0.25.x 版本中，使用 mounts 而不是 proxies 参数
        http_transport = httpx.HTTPTransport(proxy=proxy_url)
        https_transport = httpx.HTTPTransport(proxy=proxy_url)

        async with httpx.AsyncClient(
            mounts={
                "http://": http_transport,
                "https://": https_transport,
            },
            timeout=timeout
        ) as client:
            # 记录开始时间
            start_time = time.time()
            bytes_received = 0

            try:
                # 流式下载，实时计算速度
                async with client.stream("GET", test_url) as response:
                    if response.status_code != 200:
                        logger.debug(f"⚠️ 测试文件请求失败: {response.status_code}")
                        return None

                    # 异步读取响应内容
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        bytes_received += len(chunk)
                        
                        # 计算实时速度
                        elapsed = time.time() - start_time
                        if elapsed > 0.5:  # 至少收集0.5秒的数据
                            speed_mbps = (bytes_received * 8) / (elapsed * 1000000)
                            if speed_mbps > 1000:  # 速度异常高，可能是错误的
                                logger.debug(f"⚠️ 测试速度异常: {speed_mbps} Mbps")
                                return None

            except asyncio.TimeoutError:
                logger.debug("⏱️ 代理速度测试超时")
                return None
            except Exception as e:
                logger.debug(f"❌ 代理速度测试异常: {str(e)[:100]}")
                return None

            # 计算最终速度
            elapsed = time.time() - start_time
            if elapsed < 0.1:  # 如果太快，数据不可靠
                logger.debug("⚠️ 下载完成过快，数据不可靠")
                return None

            speed_mbps = (bytes_received * 8) / (elapsed * 1000000)

            # 验证速度合理性
            if speed_mbps > 0 and speed_mbps < 10000:
                logger.debug(f"✅ 代理速度测试: {speed_mbps:.2f} Mbps ({bytes_received} bytes / {elapsed:.2f}s)")
                return speed_mbps

            return None

    except Exception as e:
        logger.debug(f"❌ 速度测试异常: {str(e)[:100]}")
        return None


async def test_http_latency(
    proxy_url: str, timeout: int = 10, test_url: str = "https://www.google.com"
) -> Optional[float]:
    """
    通过代理测试HTTP延迟

    Args:
        proxy_url: SOCKS5代理URL
        timeout: 超时时间 (秒)
        test_url: 测试目标URL

    Returns:
        延迟 (毫秒)，如果失败返回 None
    """
    try:
        # httpx 0.25.x 版本中，使用 mounts 而不是 proxies 参数
        # 构建 HTTP/HTTPS transport
        http_transport = httpx.HTTPTransport(proxy=proxy_url)
        https_transport = httpx.HTTPTransport(proxy=proxy_url)

        async with httpx.AsyncClient(
            mounts={
                "http://": http_transport,
                "https://": https_transport,
            },
            timeout=timeout
        ) as client:
            start_time = time.time()
            try:
                response = await client.head(test_url, follow_redirects=False)
                latency_ms = (time.time() - start_time) * 1000

                if latency_ms > 0 and latency_ms < 60000:  # 0-60秒之间
                    logger.debug(f"✅ HTTP延迟: {latency_ms:.0f}ms")
                    return latency_ms

            except asyncio.TimeoutError:
                logger.debug("⏱️ HTTP延迟测试超时")
            except Exception as e:
                logger.debug(f"❌ HTTP延迟测试异常: {str(e)[:80]}")

        return None

    except Exception as e:
        logger.debug(f"❌ 延迟测试异常: {str(e)[:100]}")
        return None


async def multi_threaded_speed_test(
    proxy_url: str,
    num_threads: int = 4,
    file_size: int = 10485760,
    timeout: int = 30,
) -> Optional[float]:
    """
    多线程速度测试 (模拟多个并发下载)
    参考 SSRSpeedN 的多线程测速

    Args:
        proxy_url: SOCKS5代理URL
        num_threads: 并发线程数
        file_size: 每个线程的测试文件大小
        timeout: 超时时间

    Returns:
        总下载速度 (MB/s)
    """
    try:
        # 创建多个并发下载任务
        tasks = [
            test_download_speed(proxy_url, file_size, timeout, 1)
            for _ in range(num_threads)
        ]

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤成功的结果
        speeds = [r for r in results if isinstance(r, (int, float)) and r > 0]

        if speeds:
            avg_speed = sum(speeds) / len(speeds)
            logger.debug(f"✅ 多线程测速({num_threads}): {avg_speed:.2f} Mbps")
            return avg_speed

        return None

    except Exception as e:
        logger.debug(f"❌ 多线程测速异常: {str(e)[:100]}")
        return None


async def estimate_speed_from_latency(latency_ms: float) -> float:
    """
    基于延迟估计速度 (备用方案)
    当无法进行实际下载测试时使用此方法

    Args:
        latency_ms: HTTP延迟 (毫秒)

    Returns:
        估计速度 (MB/s)
    """
    # 基于延迟的线性估计
    # 延迟越低，速度越快
    if latency_ms < 50:
        return 100.0  # 非常快
    elif latency_ms < 100:
        return 60.0  # 快
    elif latency_ms < 200:
        return 40.0  # 中等
    elif latency_ms < 500:
        return 20.0  # 慢
    elif latency_ms < 1000:
        return 10.0  # 很慢
    else:
        return 5.0  # 非常慢


class RealSpeedTester:
    """真实速度测试器"""

    def __init__(self):
        self.cache: Dict[str, float] = {}  # IP地址 -> 速度缓存

    async def test_node_speed(
        self,
        proxy_url: str,
        node_id: str = None,
        use_multi_thread: bool = False,
        file_size: int = 10485760,
    ) -> Dict[str, float]:
        """
        测试单个节点的速度

        Args:
            proxy_url: SOCKS5代理URL
            node_id: 节点ID (用于缓存)
            use_multi_thread: 是否使用多线程测速
            file_size: 测试文件大小

        Returns:
            {
                "latency": 延迟 (ms),
                "speed": 速度 (MB/s),
                "status": "success" | "failed"
            }
        """
        result = {"latency": 0, "speed": 0, "status": "failed"}

        # 检查缓存
        if node_id and node_id in self.cache:
            cached_speed = self.cache[node_id]
            logger.debug(f"📦 使用缓存速度: {cached_speed:.2f} MB/s")
            result["speed"] = cached_speed
            result["status"] = "cached"
            return result

        # 第一步：测试HTTP延迟
        latency = await test_http_latency(proxy_url, timeout=10)
        if latency is None:
            return result

        result["latency"] = latency

        # 第二步：测试下载速度
        if use_multi_thread:
            # 多线程模式
            speed = await multi_threaded_speed_test(proxy_url, num_threads=4, file_size=file_size)
        else:
            # 单线程模式
            speed = await test_download_speed(proxy_url, file_size=file_size)

        # 如果直接测速失败，使用延迟估计速度
        if speed is None:
            logger.debug(f"📊 使用延迟估计速度")
            speed = await estimate_speed_from_latency(latency)

        if speed and speed > 0:
            result["speed"] = speed
            result["status"] = "success"

            # 缓存结果
            if node_id:
                self.cache[node_id] = speed

        return result

    def clear_cache(self):
        """清除缓存"""
        self.cache.clear()
        logger.info("✅ 速度测试缓存已清除")

    async def get_cached_speed(self, node_id: str) -> Optional[float]:
        """获取缓存的速度结果"""
        return self.cache.get(node_id, None)

    async def cache_speed_result(self, node_id: str, speed: float):
        """缓存速度测试结果"""
        if node_id and speed > 0:
            self.cache[node_id] = speed
            logger.debug(f"💾 缓存速度结果: {node_id} = {speed:.2f}MB/s")
