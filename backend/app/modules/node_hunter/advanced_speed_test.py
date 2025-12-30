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
ALIYUN_FC_URL = os.getenv("ALIYUN_FC_URL", "")
CLOUDFLARE_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL", "")
ADVANCED_TEST_ENABLED = os.getenv("ADVANCED_TEST_ENABLED", "false").lower() == "true"


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
    if not ALIYUN_FC_URL:
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
                    ALIYUN_FC_URL,
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
                                
                                # 大陆优化的评分
                                if latency < 50:
                                    speed_score = 50
                                elif latency < 100:
                                    speed_score = 30
                                elif latency < 200:
                                    speed_score = 10
                                elif latency < 350:
                                    speed_score = 3
                                else:
                                    speed_score = 1

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
    if not CLOUDFLARE_WORKER_URL:
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
                    CLOUDFLARE_WORKER_URL,
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
                                
                                # 国外优化的评分
                                if latency < 100:
                                    speed_score = 50
                                elif latency < 150:
                                    speed_score = 30
                                elif latency < 250:
                                    speed_score = 10
                                elif latency < 400:
                                    speed_score = 3
                                else:
                                    speed_score = 1

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
    if not ADVANCED_TEST_ENABLED:
        logger.info("⏭️ 高级测速未启用，跳过（设置 ADVANCED_TEST_ENABLED=true 启用）")
        return nodes

    logger.info(f"🚀 开始高级双地区测速（{len(nodes)} 个节点）...")

    all_tested = {}
    
    # 同时对所有节点进行大陆测速
    if ALIYUN_FC_URL:
        mainland_results = await test_nodes_via_aliyun(nodes, mark_field='mainland')
        for node in mainland_results:
            node_key = f"{node.get('host')}:{node.get('port')}"
            if node_key not in all_tested:
                all_tested[node_key] = {}
            all_tested[node_key].update(node)

    # 同时对所有节点进行国外测速
    if CLOUDFLARE_WORKER_URL:
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
