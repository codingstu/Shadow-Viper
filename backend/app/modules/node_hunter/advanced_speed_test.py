# backend/app/modules/node_hunter/advanced_speed_test.py
"""
高级双地区测速模块
在基础测速后，为 CN 和非 CN 节点分别进行优化的测速
目标：为 viper-node-store 提供已测速的数据
"""

import asyncio
import aiohttp
import os
import logging
from typing import List, Dict
from datetime import datetime
from email.utils import formatdate

logger = logging.getLogger(__name__)

# ==================== 配置区域 ====================
def get_aliyun_url():
    """运行时读取 Aliyun FC URL"""
    return os.getenv("ALIYUN_FC_URL", "")

def get_cloudflare_url():
    """运行时读取 Cloudflare Worker URL"""
    return os.getenv("CLOUDFLARE_WORKER_URL", "")

def is_advanced_test_enabled():
    """运行时读取高级测速开关（解决环境变量加载时序问题）"""
    return os.getenv("ADVANCED_TEST_ENABLED", "false").lower() == "true"

# 注：为了向后兼容，保留这些变量但标记为过时
ALIYUN_FC_URL = get_aliyun_url()
CLOUDFLARE_WORKER_URL = get_cloudflare_url()
ADVANCED_TEST_ENABLED = is_advanced_test_enabled()


def extract_host_port(node: Dict) -> tuple:
    """从节点数据中提取 host 和 port"""
    host = node.get('host')
    port = node.get('port')
    
    if host and port:
        return host, int(port)
    
    return None, None


async def test_nodes_via_aliyun(nodes: List[Dict], mark_field: str = 'mainland') -> List[Dict]:
    """
    使用 Aliyun FC 为节点进行大陆测速
    优化参数：针对大陆用户的延迟标准
    mark_field: 结果字段前缀 (默认 'mainland')
    """
    aliyun_url = get_aliyun_url()
    if not aliyun_url:
        logger.warning("⚠️ ALIYUN_FC_URL not configured, skipping mainland test")
        return []

    logger.info(f"🚀 [Aliyun FC] 开始大陆测速 ({len(nodes)} 个节点)...")

    tested_nodes = []
    batch_size = 15
    total_success = 0
    total_failed = 0

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]

            payload_nodes = []
            for n in batch:
                host, port = extract_host_port(n)
                if not host or not port:
                    continue

                n_id = n.get("id") or f"{host}:{port}"
                payload_nodes.append({
                    "id": n_id,
                    "host": host,
                    "port": port
                })

            if not payload_nodes:
                continue

            request_payload = {"nodes": payload_nodes}

            try:
                logger.info(f"   📤 [Aliyun] 批次 {i // batch_size + 1} ({len(payload_nodes)} 个节点)...")

                request_headers = {
                    "Content-Type": "application/json",
                    "Date": formatdate(timeval=None, localtime=False, usegmt=True)
                }

                async with session.post(
                    aliyun_url,
                    json=request_payload,
                    headers=request_headers,
                    timeout=20
                ) as resp:
                    if resp.status == 200:
                        results = await resp.json()
                        total_success += len([r for r in results if r.get('success')])
                        total_failed += len([r for r in results if not r.get('success')])

                        for res in results:
                            if not res['success']:
                                continue

                            # 查找原始节点
                            orig = next((x for x in batch if
                                        (x.get("id") == res['id'] or 
                                         f"{x.get('host', '')}:{x.get('port', '')}" == res['id'])), None)

                            if orig:
                                latency = res['latency']
                                # 优先使用外部服务返回的 score（如果有的话），否则使用 latency
                                speed_score = res.get('score', 0)
                                
                                # 如果没有 score，则根据 latency 计算（备选方案）
                                if speed_score == 0 and latency > 0:
                                    # 大陆优化的评分规则
                                    if latency < 50:
                                        speed_score = 100
                                    elif latency < 100:
                                        speed_score = 80
                                    elif latency < 200:
                                        speed_score = 60
                                    elif latency < 350:
                                        speed_score = 40
                                    else:
                                        speed_score = 20

                                orig[f'{mark_field}_latency'] = latency
                                orig[f'{mark_field}_score'] = speed_score
                                tested_nodes.append(orig)
                                logger.info(f"     ✅ {orig.get('host')} | {mark_field} 延迟: {latency}ms (分数: {speed_score})")
                    else:
                        error_text = await resp.text()
                        logger.warning(f"     ⚠️ Aliyun 返回错误 {resp.status}: {error_text[:100]}")

            except Exception as e:
                logger.error(f"     ❌ Aliyun 批次异常: {type(e).__name__}: {str(e)}")

            await asyncio.sleep(0.5)

    logger.info(f"✅ [Aliyun] 测速完成: {len(tested_nodes)} / {len(nodes)} 节点成功 (成功: {total_success}, 失败: {total_failed})")
    return tested_nodes


async def test_nodes_via_cloudflare(nodes: List[Dict], mark_field: str = 'overseas') -> List[Dict]:
    """
    使用 Cloudflare Workers 为节点进行国外测速
    优化参数：针对国外用户的延迟标准
    mark_field: 结果字段前缀 (默认 'overseas')
    """
    cloudflare_url = get_cloudflare_url()
    if not cloudflare_url:
        logger.warning("⚠️ CLOUDFLARE_WORKER_URL not configured, skipping overseas test")
        return []

    logger.info(f"🚀 [Cloudflare] 开始国外测速 ({len(nodes)} 个节点)...")

    tested_nodes = []
    batch_size = 15
    total_success = 0
    total_failed = 0

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]

            payload_nodes = []
            for n in batch:
                host, port = extract_host_port(n)
                if not host or not port:
                    continue

                n_id = n.get("id") or f"{host}:{port}"
                payload_nodes.append({
                    "id": n_id,
                    "host": host,
                    "port": port
                })

            if not payload_nodes:
                continue

            request_payload = {"nodes": payload_nodes}

            try:
                logger.info(f"   📤 [Cloudflare] 批次 {i // batch_size + 1} ({len(payload_nodes)} 个节点)...")

                request_headers = {
                    "Content-Type": "application/json",
                    "Date": formatdate(timeval=None, localtime=False, usegmt=True)
                }

                async with session.post(
                    cloudflare_url,
                    json=request_payload,
                    headers=request_headers,
                    timeout=20
                ) as resp:
                    if resp.status == 200:
                        results = await resp.json()
                        total_success += len([r for r in results if r.get('success')])
                        total_failed += len([r for r in results if not r.get('success')])

                        for res in results:
                            if not res['success']:
                                continue

                            orig = next((x for x in batch if
                                        (x.get("id") == res['id'] or 
                                         f"{x.get('host', '')}:{x.get('port', '')}" == res['id'])), None)

                            if orig:
                                latency = res['latency']
                                # 优先使用外部服务返回的 score（如果有的话），否则使用 latency
                                speed_score = res.get('score', 0)
                                
                                # 如果没有 score，则根据 latency 计算（备选方案）
                                if speed_score == 0 and latency > 0:
                                    # 国外优化的评分规则
                                    if latency < 100:
                                        speed_score = 100
                                    elif latency < 150:
                                        speed_score = 80
                                    elif latency < 250:
                                        speed_score = 60
                                    elif latency < 400:
                                        speed_score = 40
                                    else:
                                        speed_score = 20

                                orig[f'{mark_field}_latency'] = latency
                                orig[f'{mark_field}_score'] = speed_score
                                tested_nodes.append(orig)
                                logger.info(f"     ✅ {orig.get('host')} | {mark_field} 延迟: {latency}ms (分数: {speed_score})")
                    else:
                        error_text = await resp.text()
                        logger.warning(f"     ⚠️ Cloudflare 返回错误 {resp.status}: {error_text[:100]}")

            except Exception as e:
                logger.error(f"     ❌ Cloudflare 批次异常: {type(e).__name__}: {str(e)}")

            await asyncio.sleep(0.5)

    logger.info(f"✅ [Cloudflare] 测速完成: {len(tested_nodes)} / {len(nodes)} 节点成功 (成功: {total_success}, 失败: {total_failed})")
    return tested_nodes


async def run_advanced_speed_test(nodes: List[Dict]) -> List[Dict]:
    """
    主函数：运行双地区高级测速
    为所有节点同时进行 Aliyun（大陆）和 Cloudflare（海外）测速
    
    输入：从基础测速得到的活跃节点
    输出：添加了 mainland_score/latency 和 overseas_score/latency 的节点列表
    """
    # 运行时读取配置
    if not is_advanced_test_enabled():
        logger.info("⏭️ 高级测速未启用，跳过（设置 ADVANCED_TEST_ENABLED=true 启用）")
        return nodes
    
    aliyun_url = get_aliyun_url()
    cloudflare_url = get_cloudflare_url()

    logger.info(f"🚀 开始高级双地区测速（{len(nodes)} 个节点）...")

    all_tested = {}
    
    # 同时对所有节点进行大陆测速
    if aliyun_url:
        mainland_results = await test_nodes_via_aliyun(nodes, mark_field='mainland')
        for node in mainland_results:
            node_key = f"{node.get('host')}:{node.get('port')}"
            if node_key not in all_tested:
                all_tested[node_key] = {}
            all_tested[node_key].update(node)

    # 同时对所有节点进行国外测速
    if cloudflare_url:
        overseas_results = await test_nodes_via_cloudflare(nodes, mark_field='overseas')
        for node in overseas_results:
            node_key = f"{node.get('host')}:{node.get('port')}"
            if node_key not in all_tested:
                all_tested[node_key] = {}
            all_tested[node_key].update(node)

    # 合并结果
    final_nodes = []
    for orig_node in nodes:
        node_key = f"{orig_node.get('host')}:{orig_node.get('port')}"
        if node_key in all_tested:
            # 将测速结果合并回原始节点
            orig_node.update(all_tested[node_key])
        final_nodes.append(orig_node)

    logger.info(f"✅ 高级测速完成: {len(all_tested)} / {len(nodes)} 个节点成功测速")
    return final_nodes
