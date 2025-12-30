# backend/app/modules/node_hunter/supabase_helper.py
"""
Supabase 数据库助手模块
负责将已测速的节点数据上传到 Supabase
"""

import os
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def convert_node_to_supabase_format(node: Dict, index: int = 0) -> Dict:
    """
    将 SpiderFlow 节点格式转换为 viper-node-store Supabase 格式
    
    输入格式（SpiderFlow）:
    {
        "id": "...",
        "name": "...",
        "host": "...",
        "port": 123,
        "country": "CN",
        "advanced_speed_score": 50,
        "advanced_latency_mainland": 45,
        ...
    }
    
    输出格式（Supabase）:
    {
        "id": "host:port",
        "content": {...完整节点...},
        "is_free": true/false,
        "speed": 50,
        "latency": 45,
        "updated_at": "..."
    }
    """
    host = node.get('host')
    port = node.get('port')
    
    # 使用 host:port 作为唯一 ID
    node_id = f"{host}:{port}"
    
    # 确定评分
    speed_score = node.get('advanced_speed_score', 
                          int(node.get('speed', 0) * 10))  # 降级：用原来的速度值
    
    # 确定延迟（优先用高级测速的结果）
    latency = node.get('advanced_latency_mainland') or \
              node.get('advanced_latency_overseas') or \
              node.get('delay', 9999)
    
    return {
        "id": node_id,
        "content": node,  # 完整的节点数据
        "is_free": index < 20,  # 前 20 个标记为免费
        "speed": int(speed_score),  # 评分 1-50
        "latency": int(latency),  # 延迟 ms
        "updated_at": datetime.now().isoformat()
    }


async def upload_to_supabase(nodes: List[Dict]) -> bool:
    """
    将节点数据上传到 Supabase
    
    返回：是否上传成功
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("⚠️ Supabase 凭证未配置，跳过上传")
        return False

    try:
        from supabase import create_client
        
        logger.info(f"📤 初始化 Supabase 连接: {SUPABASE_URL[:30]}...")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 转换节点格式
        data = []
        for i, node in enumerate(nodes):
            try:
                converted = convert_node_to_supabase_format(node, i)
                data.append(converted)
            except Exception as e:
                logger.warning(f"⚠️ 节点转换失败 {node.get('id')}: {e}")
                continue
        
        if not data:
            logger.warning("⚠️ 没有有效节点可上传")
            return False
        
        logger.info(f"📋 准备上传 {len(data)} 个节点...")
        
        # 分批上传（避免单次请求过大）
        batch_size = 50
        total_uploaded = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            try:
                logger.info(f"   📤 批次 {i // batch_size + 1}: 上传 {len(batch)} 条...")
                
                # 使用 upsert 替换存在的数据，插入新数据
                response = supabase.table("nodes").upsert(batch).execute()
                
                total_uploaded += len(batch)
                logger.info(f"   ✅ 批次成功: {len(batch)} 条数据")
                
            except Exception as batch_error:
                logger.error(f"   ❌ 批次失败: {batch_error}")
                # 继续处理下一批，不中断整个流程
                continue
        
        if total_uploaded > 0:
            logger.info(f"✅ Supabase 上传完成: 共 {total_uploaded} / {len(data)} 条数据")
            return True
        else:
            logger.error("❌ Supabase 上传失败: 没有数据成功上传")
            return False
            
    except ImportError:
        logger.error("❌ supabase 库未安装，请运行: pip install supabase")
        return False
    except Exception as e:
        logger.error(f"❌ Supabase 上传异常: {type(e).__name__}: {e}")
        return False


async def check_supabase_connection() -> bool:
    """
    检查 Supabase 连接是否正常
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("⚠️ Supabase 凭证未配置")
        return False
    
    try:
        from supabase import create_client
        
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 尝试查询 nodes 表的行数
        response = supabase.table("nodes").select("count", count="exact").execute()
        
        logger.info(f"✅ Supabase 连接正常，当前 nodes 表有 {response.count} 条数据")
        return True
        
    except Exception as e:
        logger.error(f"❌ Supabase 连接失败: {e}")
        return False
