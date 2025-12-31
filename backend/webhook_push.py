#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=== SpiderFlow Webhook推送模块 ===

功能：
- 当节点列表更新时，将数据推送到viper-node-store
- 使用签名验证确保数据安全
- 支持重试机制处理临时失败
- 记录所有推送历史

使用方式：
1. 在node_hunter.py中导入此模块
2. 在检测完成后调用 push_nodes_to_viper()
3. Webhook会在后台异步推送数据
"""

import asyncio
import aiohttp
import json
import hashlib
import hmac
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

# ==================== 配置 ====================

# viper-node-store的Webhook端点
VIPER_WEBHOOK_URL = os.environ.get(
    "VIPER_WEBHOOK_URL", 
    "http://localhost:8002/webhook/nodes-update"
)

# 用于签名的共享密钥（必须与viper-node-store的WEBHOOK_SECRET一致）
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "spiderflow-viper-sync-2026")

# 推送重试配置
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

# 推送历史记录文件
PUSH_HISTORY_FILE = "webhook_push_history.json"

# ==================== 签名生成 ====================

def generate_webhook_signature(payload: Dict[str, Any]) -> tuple[str, str]:
    """
    生成Webhook签名
    
    返回: (timestamp, signature)
    
    签名算法：
    1. 获取当前时间戳
    2. 构造消息: JSON序列化的payload + timestamp
    3. 使用HMAC-SHA256签名
    """
    timestamp = datetime.now().isoformat()
    
    # 构造消息
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    message = f"{payload_str}.{timestamp}"
    
    # 生成签名
    signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return timestamp, signature

# ==================== 推送历史记录 ====================

class PushHistory:
    """管理推送历史记录"""
    
    @staticmethod
    def load() -> List[Dict[str, Any]]:
        """加载推送历史"""
        if os.path.exists(PUSH_HISTORY_FILE):
            try:
                with open(PUSH_HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载推送历史失败: {e}")
        return []
    
    @staticmethod
    def save(history: List[Dict[str, Any]]):
        """保存推送历史"""
        try:
            # 只保留最近1000条记录
            history = history[-1000:]
            with open(PUSH_HISTORY_FILE, 'w') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存推送历史失败: {e}")
    
    @staticmethod
    def record(event_type: str, nodes_count: int, status: str, message: str = ""):
        """记录一次推送事件"""
        history = PushHistory.load()
        
        history.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "nodes_count": nodes_count,
            "status": status,  # success, failed, retrying
            "message": message,
            "webhook_url": VIPER_WEBHOOK_URL
        })
        
        PushHistory.save(history)

# ==================== 核心推送函数 ====================

async def push_nodes_to_viper(
    nodes: List[Dict[str, Any]],
    event_type: str = "nodes_updated",
    total_count: int = 0,
    verified_count: int = 0
) -> bool:
    """
    将节点数据推送到viper-node-store
    
    参数：
    - nodes: 节点列表
    - event_type: 事件类型（nodes_updated, batch_test_complete等）
    - total_count: 总节点数
    - verified_count: 验证通过的节点数
    
    返回：
    - True: 推送成功
    - False: 推送失败（尝试MAX_RETRIES次后）
    """
    
    if not nodes:
        logger.warning("⚠️ 节点列表为空，跳过推送")
        return False
    
    # 构造Webhook负载
    payload = {
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "nodes": nodes,
        "total_count": total_count or len(nodes),
        "verified_count": verified_count or len(nodes)
    }
    
    # 生成签名
    timestamp, signature = generate_webhook_signature(payload)
    
    # 添加签名到负载
    payload["timestamp"] = timestamp
    payload["signature"] = signature
    
    logger.info(f"🔄 准备推送{len(nodes)}个节点到viper-node-store...")
    
    # 重试推送
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    VIPER_WEBHOOK_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.info(f"✅ Webhook推送成功 | 响应: {result}")
                        
                        # 记录成功
                        PushHistory.record(
                            event_type=event_type,
                            nodes_count=len(nodes),
                            status="success"
                        )
                        return True
                    else:
                        error_text = await resp.text()
                        logger.warning(f"❌ Webhook返回错误状态 {resp.status} | {error_text}")
                        
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ 推送超时（第{attempt}/{MAX_RETRIES}次）")
            
        except Exception as e:
            logger.warning(f"❌ 推送失败（第{attempt}/{MAX_RETRIES}次）: {e}")
        
        # 如果不是最后一次，等待后重试
        if attempt < MAX_RETRIES:
            logger.info(f"⏳ {RETRY_DELAY}秒后重试...")
            await asyncio.sleep(RETRY_DELAY)
    
    logger.error(f"❌ 推送失败，已尝试{MAX_RETRIES}次")
    PushHistory.record(
        event_type=event_type,
        nodes_count=len(nodes),
        status="failed",
        message=f"尝试{MAX_RETRIES}次后仍失败"
    )
    return False

# ==================== 便捷包装函数 ====================

async def push_after_detection(
    nodes: List[Dict[str, Any]],
    background_tasks = None
):
    """
    检测完成后推送节点（常用）
    
    使用方式：
    await push_after_detection(verified_nodes, background_tasks)
    """
    if background_tasks:
        # 在后台任务中执行
        background_tasks.add_task(push_nodes_to_viper, nodes, "batch_test_complete")
    else:
        # 直接执行
        await push_nodes_to_viper(nodes, "batch_test_complete")

def push_after_detection_sync(nodes: List[Dict[str, Any]]):
    """
    同步版本的推送函数（如果不能使用async）
    
    注意：这会阻塞当前线程，建议使用异步版本
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(push_nodes_to_viper(nodes, "batch_test_complete"))

# ==================== 监控和调试 ====================

def get_push_statistics() -> Dict[str, Any]:
    """获取推送统计信息"""
    history = PushHistory.load()
    
    if not history:
        return {
            "total_pushes": 0,
            "successful_pushes": 0,
            "failed_pushes": 0,
            "success_rate": 0,
            "last_push": None
        }
    
    successful = len([h for h in history if h.get("status") == "success"])
    total = len(history)
    
    return {
        "total_pushes": total,
        "successful_pushes": successful,
        "failed_pushes": total - successful,
        "success_rate": f"{(successful / total * 100):.1f}%",
        "last_push": history[-1] if history else None,
        "total_nodes_pushed": sum(h.get("nodes_count", 0) for h in history)
    }

def get_push_history(limit: int = 50) -> List[Dict[str, Any]]:
    """获取最近的推送历史"""
    history = PushHistory.load()
    return history[-limit:]

# ==================== 测试函数 ====================

async def test_webhook_connection() -> bool:
    """
    测试与viper-node-store的Webhook连接
    
    返回：
    - True: 连接成功
    - False: 连接失败
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{VIPER_WEBHOOK_URL.replace('/nodes-update', '/test-connection')}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"✅ Webhook连接测试成功: {result}")
                    return True
                else:
                    logger.error(f"❌ Webhook连接测试失败: {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Webhook连接测试异常: {e}")
        return False

async def test_webhook_push():
    """
    测试推送功能（使用示例数据）
    """
    test_nodes = [
        {
            "url": "vmess://test1@proxy1.example.com",
            "name": "测试节点1",
            "country": "SG",
            "latency": 123.45,
            "speed": 45.67,
            "availability": 95.5,
            "last_checked": datetime.now().isoformat(),
            "protocol": "vmess"
        },
        {
            "url": "vmess://test2@proxy2.example.com",
            "name": "测试节点2",
            "country": "JP",
            "latency": 87.23,
            "speed": 78.90,
            "availability": 98.2,
            "last_checked": datetime.now().isoformat(),
            "protocol": "vmess"
        }
    ]
    
    success = await push_nodes_to_viper(
        test_nodes,
        event_type="test_push",
        total_count=100,
        verified_count=2
    )
    
    if success:
        logger.info("✅ 测试推送成功")
    else:
        logger.error("❌ 测试推送失败")
    
    return success
