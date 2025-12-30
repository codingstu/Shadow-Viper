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


def convert_node_to_supabase_format(node: Dict, index: int = 0, region: str = 'mainland') -> Dict:
    """
    将 SpiderFlow 节点格式转换为 viper-node-store Supabase 格式
    
    输入格式（SpiderFlow）:
    {
        "id": "...",
        "name": "...",
        "host": "...",
        "port": 123,
        "country": "CN",
        "mainland_score": 50,
        "mainland_latency": 45,
        "overseas_score": 48,
        "overseas_latency": 60,
        ...
    }
    
    输出格式（Supabase）- 同时存储两个地区的数据:
    {
        "id": "host:port",
        "content": {...完整节点...},
        "is_free": true/false,
        "mainland_score": 50,
        "mainland_latency": 45,
        "overseas_score": 48,
        "overseas_latency": 60,
        "speed": 50,              # 优先使用请求地区的分数
        "latency": 45,            # 优先使用请求地区的延迟
        "region": "mainland",     # 标记这条数据对应的地区
        "updated_at": "..."
    }
    """
    host = node.get('host')
    port = node.get('port')
    
    # 使用 host:port 作为唯一 ID
    node_id = f"{host}:{port}"
    
    # 获取两个地区的分数
    mainland_score = node.get('mainland_score', 0)
    overseas_score = node.get('overseas_score', 0)
    mainland_latency = node.get('mainland_latency', 9999)
    overseas_latency = node.get('overseas_latency', 9999)
    
    # 根据指定地区选择主分数
    if region == 'overseas':
        primary_score = overseas_score or mainland_score
        primary_latency = overseas_latency if overseas_latency != 9999 else mainland_latency
    else:  # mainland
        primary_score = mainland_score or overseas_score
        primary_latency = mainland_latency if mainland_latency != 9999 else overseas_latency
    
    return {
        "id": node_id,
        "content": node,  # 完整的节点数据
        "is_free": index < 20,  # 前 20 个标记为免费
        "mainland_score": int(mainland_score),  # 大陆分数
        "mainland_latency": int(mainland_latency),  # 大陆延迟
        "overseas_score": int(overseas_score),  # 海外分数
        "overseas_latency": int(overseas_latency),  # 海外延迟
        "speed": int(primary_score),  # 主要分数（根据地区选择）
        "latency": int(primary_latency),  # 主要延迟（根据地区选择）
        "region": region,  # 数据对应的地区标记
        "updated_at": datetime.now().isoformat()
    }


async def upload_to_supabase(nodes: List[Dict]) -> bool:
    """
    将节点数据上传到 Supabase
    每个节点只上传一条记录，包含 mainland_score/mainland_latency 和 overseas_score/overseas_latency
    
    返回：是否上传成功
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("⚠️ Supabase 凭证未配置，跳过上传")
        return False

    try:
        from supabase import create_client
        
        logger.info(f"📤 初始化 Supabase 连接: {SUPABASE_URL[:30]}...")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 转换节点格式（单个记录包含两个地区数据）
        all_data = []
        
        for i, node in enumerate(nodes):
            try:
                # 将节点转换为 Supabase 格式（包含两个地区的数据）
                converted = {
                    "id": f"{node.get('host')}:{node.get('port')}",
                    "content": node,  # 完整的节点数据
                    "is_free": i < 20,  # 前 20 个标记为免费
                    "mainland_score": int(node.get('mainland_score', 0)),
                    "mainland_latency": int(node.get('mainland_latency', 9999)),
                    "overseas_score": int(node.get('overseas_score', 0)),
                    "overseas_latency": int(node.get('overseas_latency', 9999)),
                    "speed": int(max(node.get('mainland_score', 0), node.get('overseas_score', 0))),
                    "latency": int(min(node.get('mainland_latency', 9999), node.get('overseas_latency', 9999))),
                    "updated_at": datetime.now().isoformat()
                }
                all_data.append(converted)
            except Exception as e:
                logger.warning(f"⚠️ 节点转换失败 {node.get('id')}: {e}")
                continue
        
        if not all_data:
            logger.warning("⚠️ 没有有效节点可上传")
            return False
        
        logger.info(f"📋 准备上传 {len(all_data)} 条节点记录（每条包含大陆和海外测试数据）...")
        
        # 分批上传（避免单次请求过大）
        batch_size = 50
        total_uploaded = 0
        
        for i in range(0, len(all_data), batch_size):
            batch = all_data[i:i + batch_size]
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
            logger.info(f"✅ Supabase 上传完成: 共 {total_uploaded} / {len(all_data)} 条数据")
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
