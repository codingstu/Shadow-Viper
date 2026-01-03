# backend/app/modules/node_hunter/supabase_helper.py
"""
Supabase 数据库助手模块
负责将已测速的节点数据上传到 Supabase
"""

import os
import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 🔥 关键：使用绝对路径加载 .env 文件
# 获取当前文件所在目录，向上找到 backend 目录
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent.parent  # supabase_helper.py -> node_hunter -> modules -> app -> backend
_env_path = _backend_dir / ".env"

logger.warning(f"🔍 尝试加载 .env 文件: {_env_path}")
logger.warning(f"   文件是否存在: {_env_path.exists()}")

if _env_path.exists():
    load_dotenv(_env_path)
    logger.warning(f"✅ 已加载 .env 文件: {_env_path}")
else:
    # 尝试从当前工作目录加载
    load_dotenv()
    logger.warning(f"⚠️ .env 文件不存在于 {_env_path}，尝试从当前工作目录加载")

def get_supabase_credentials():
    """在运行时读取 Supabase 凭证，优先使用 service_role key 以绕过 RLS"""
    url = os.getenv("SUPABASE_URL", "")
    # 优先使用 service_role key（绕过 RLS），如果没有则使用普通 key
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
    
    # 用 WARNING 级别确保在线上一定能看到
    logger.warning(f"🔍 Supabase 凭证读取状态:")
    logger.warning(f"   SUPABASE_URL: {'✅ 已设置' if url else '❌ 未设置'} {url[:40] + '...' if url else ''}")
    logger.warning(f"   SUPABASE_SERVICE_ROLE_KEY: {'✅ 已设置' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else '❌ 未设置'}")
    logger.warning(f"   SUPABASE_KEY: {'✅ 已设置' if os.getenv('SUPABASE_KEY') else '❌ 未设置'}")
    
    if not url or not key:
        logger.error(f"❌ Supabase 凭证不完整，无法上传数据！")
    
    return url, key


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
    logger.error("=" * 60)
    logger.error("🚀 开始执行 upload_to_supabase()")
    logger.error(f"   输入节点数: {len(nodes)}")
    
    SUPABASE_URL, SUPABASE_KEY = get_supabase_credentials()
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("❌ Supabase 凭证未配置，无法上传！")
        logger.error(f"   SUPABASE_URL: {SUPABASE_URL}")
        logger.error(f"   SUPABASE_KEY 长度: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")
        return False

    try:
        from supabase import create_client
        
        logger.error(f"📤 初始化 Supabase 连接: {SUPABASE_URL[:30]}...")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 转换节点格式（单个记录包含两个地区数据）
        all_data = []
        failed_count = 0
        
        for i, node in enumerate(nodes):
            try:
                # 🔥 关键：生成或提取 share_link
                share_link = node.get('share_link') or node.get('link', '')
                
                # 如果没有 share_link，尝试从 config_generator 生成
                if not share_link:
                    try:
                        from .config_generator import generate_node_share_link
                        share_link = generate_node_share_link(node)
                    except Exception as e:
                        logger.error(f"⚠️ 生成 share_link 失败: {e}")
                        share_link = ''
                
                # 检查必要的字段
                mainland_score = node.get('mainland_score', 0)
                overseas_score = node.get('overseas_score', 0)
                mainland_latency = node.get('mainland_latency', 9999)
                overseas_latency = node.get('overseas_latency', 9999)
                
                logger.error(f"   处理节点 {i+1}/{len(nodes)}: {node.get('host')}:{node.get('port')}")
                logger.error(f"      mainland_score={mainland_score}, overseas_score={overseas_score}")
                
                # 将节点转换为 Supabase 格式（包含两个地区的数据）
                converted = {
                    "id": f"{node.get('host')}:{node.get('port')}",
                    "content": node,  # 完整的节点数据
                    "link": share_link,  # 🔥 添加 link 字段！
                    "is_free": i < 20,  # 前 20 个标记为免费
                    "mainland_score": int(mainland_score),
                    "mainland_latency": int(mainland_latency),
                    "overseas_score": int(overseas_score),
                    "overseas_latency": int(overseas_latency),
                    "speed": int(max(mainland_score, overseas_score)),
                    "latency": int(min(mainland_latency, overseas_latency)),
                    "updated_at": datetime.now().isoformat()
                }
                all_data.append(converted)
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ 节点转换失败 {node.get('id')}: {e}")
                continue
        
        if not all_data:
            logger.error(f"❌ 没有有效节点可上传 (all_data 为空)")
            logger.error(f"   成功转换: 0/{len(nodes)}")
            logger.error(f"   失败转换: {failed_count}/{len(nodes)}")
            return False
        
        logger.error(f"📋 准备上传 {len(all_data)} 条节点记录... (成功转换: {len(all_data)}/{len(nodes)})")
        
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
            
    except ImportError as ie:
        logger.error("❌ supabase 库未安装！")
        logger.error(f"   错误: {ie}")
        logger.error("   请运行: pip install supabase")
        return False
    except Exception as e:
        logger.error(f"❌ Supabase 上传异常: {type(e).__name__}")
        logger.error(f"   错误详情: {str(e)}")
        import traceback
        logger.error(f"   堆栈跟踪:\n{traceback.format_exc()}")
        return False
    finally:
        logger.info("=" * 60)


async def check_supabase_connection() -> bool:
    """
    检查 Supabase 连接是否正常
    """
    SUPABASE_URL, SUPABASE_KEY = get_supabase_credentials()
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
