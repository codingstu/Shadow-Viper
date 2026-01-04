# backend/app/modules/node_hunter/persistence_helper.py
# -*- coding: utf-8 -*-
"""
持久化助手 - 负责与数据库的缓存读写

功能：
1. 初始化三个持久化表 (sources_cache, parsed_nodes, testing_queue)
2. 缓存订阅源内容 (6小时 TTL)
3. 缓存解析后的节点 (6小时 TTL)
4. 保存和恢复测速队列进度
5. 定期清理过期数据
"""

import os
import logging
import json
import base64
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


class PersistenceHelper:
    """持久化管理器 - 统一管理所有缓存操作"""
    
    def __init__(self):
        self.supabase = None
        self.initialized = False
        
        # 内存缓存备份（当 Supabase 不可用时使用）
        self.memory_cache = {
            'sources_cache': {},
            'parsed_nodes': {},
            'testing_queue': []
        }
        self.use_memory_cache = False  # 标志：是否仅使用内存缓存
        
        self._init_supabase()
    
    def _init_supabase(self):
        """初始化 Supabase 客户端"""
        try:
            from supabase import create_client
            
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
            
            if not url or not key:
                logger.warning("⚠️ Supabase 凭证未配置，使用内存缓存")
                self.use_memory_cache = True
                return
            
            # 测试 URL 是否有效
            if "nxdomain" in url.lower() or "error" in url.lower():
                logger.warning("⚠️ Supabase URL 无效，使用内存缓存")
                self.use_memory_cache = True
                return
            
            self.supabase = create_client(url, key)
            logger.info("✅ Supabase 客户端初始化成功")
        except Exception as e:
            logger.error(f"❌ Supabase 初始化失败: {e}，改用内存缓存")
            self.use_memory_cache = True
    
    async def init_persistence_tables(self):
        """初始化持久化表（仅需执行一次，有超时保护）"""
        if not self.supabase or self.use_memory_cache:
            logger.warning("⚠️ Supabase 未初始化或使用内存缓存，跳过表创建")
            self.initialized = True  # 标记为已初始化，即使是内存模式
            return
        
        try:
            logger.info("🔧 检查并创建持久化表（最多2秒）...")
            
            try:
                # 🔥 加入 2 秒超时，防止 Supabase 慢导致后端卡住
                async with asyncio.timeout(2):
                    # 表1: sources_cache (订阅源缓存)
                    await self._create_sources_cache_table()
                    
                    # 表2: parsed_nodes (解析节点缓存)
                    await self._create_parsed_nodes_table()
                    
                    # 表3: testing_queue (测速队列)
                    await self._create_testing_queue_table()
                    
                    self.initialized = True
                    logger.info("✅ 持久化表初始化完成")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Supabase 响应超时（2秒），切换到内存缓存模式")
                self.use_memory_cache = True
                self.initialized = True
        except Exception as e:
            logger.warning(f"⚠️ 表初始化失败: {e}，切换到内存缓存模式（继续启动）")
            self.use_memory_cache = True
            self.initialized = True
    
    async def _create_sources_cache_table(self):
        """创建订阅源缓存表（异步，防止阻塞）"""
        try:
            # 🔥 改为异步运行在事件循环中，不阻塞
            await asyncio.get_event_loop().run_in_executor(None, lambda: self.supabase.table("sources_cache").select("id").limit(1).execute())
            logger.debug("✅ sources_cache 表已存在")
        except Exception as e:
            if "does not exist" in str(e) or "404" in str(e):
                logger.info("📝 sources_cache 表不存在（需要手动创建）")
            else:
                logger.debug(f"⚠️ 检查 sources_cache 失败: {e}")
    
    async def _create_parsed_nodes_table(self):
        """创建解析节点缓存表（异步，防止阻塞）"""
        try:
            # 🔥 改为异步运行，不阻塞
            await asyncio.get_event_loop().run_in_executor(None, lambda: self.supabase.table("parsed_nodes").select("id").limit(1).execute())
            logger.debug("✅ parsed_nodes 表已存在")
        except Exception as e:
            if "does not exist" in str(e) or "404" in str(e):
                logger.info("📝 parsed_nodes 表不存在（需要手动创建）")
            else:
                logger.debug(f"⚠️ 检查 parsed_nodes 失败: {e}")
    
    async def _create_testing_queue_table(self):
        """创建测速队列表（异步，防止阻塞）"""
        try:
            # 🔥 改为异步运行，不阻塞
            await asyncio.get_event_loop().run_in_executor(None, lambda: self.supabase.table("testing_queue").select("id").limit(1).execute())
            logger.debug("✅ testing_queue 表已存在")
        except Exception as e:
            if "does not exist" in str(e) or "404" in str(e):
                logger.info("📝 testing_queue 表不存在（需要手动创建）")
                # CREATE TABLE testing_queue (
                #   id BIGINT PRIMARY KEY,
                #   group_number INT,
                #   group_position INT,
                #   node_host VARCHAR(255),
                #   node_port INT,
                #   node_name VARCHAR(255),
                #   status VARCHAR(20),
                #   attempted_count INT DEFAULT 0,
                #   last_tested_at TIMESTAMP,
                #   created_at TIMESTAMP,
                #   updated_at TIMESTAMP
                # )
            else:
                raise e
    
    # ==================== 订阅源缓存 ====================
    
    async def save_sources_cache(self, sources: List[str], node_contents: Dict[str, List[str]]) -> bool:
        """
        保存订阅源和爬取内容到缓存
        
        Args:
            sources: 订阅源 URL 列表
            node_contents: 源URL -> 节点列表的映射
        """
        # 始终保存到内存缓存
        self.memory_cache['sources_cache'] = node_contents.copy()
        
        if not self.supabase or self.use_memory_cache:
            logger.info(f"💾 已保存到内存缓存 {len(sources)} 个订阅源")
            return True
        
        try:
            for source_url in sources:
                nodes = node_contents.get(source_url, [])
                if not nodes:
                    continue
                
                # 压缩内容并 base64 编码
                content_str = json.dumps(nodes, ensure_ascii=False)
                content_b64 = base64.b64encode(content_str.encode()).decode()
                
                # 生成唯一 ID
                content_hash = hashlib.md5(content_str.encode()).hexdigest()
                record_id = int(content_hash[:8], 16)
                
                record = {
                    "id": record_id,
                    "source_url": source_url[:500],
                    "content": content_b64,
                    "node_count": len(nodes),
                    "last_fetched_at": datetime.utcnow().isoformat(),
                    "ttl_hours": 6,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                # upsert (如果存在则更新，不存在则插入)
                self.supabase.table("sources_cache").upsert(record).execute()
            
            logger.info(f"✅ 已缓存 {len(sources)} 个订阅源")
            return True
        except Exception as e:
            logger.error(f"⚠️ Supabase 保存源缓存失败: {e}，但内存缓存已保存")
            return True  # 返回 True，因为内存缓存已保存
    
    async def load_sources_cache(self, sources: List[str]) -> Dict[str, List[str]]:
        """
        从缓存加载订阅源内容
        
        Returns:
            源URL -> 节点列表的映射
        """
        # 优先从内存缓存加载
        if self.memory_cache['sources_cache']:
            logger.info(f"💾 从内存缓存加载 {len(self.memory_cache['sources_cache'])} 个订阅源")
            return self.memory_cache['sources_cache'].copy()
        
        if not self.supabase or self.use_memory_cache:
            return {}
        
        try:
            result = {}
            for source_url in sources:
                # 尝试从缓存查询
                response = self.supabase.table("sources_cache")\
                    .select("*")\
                    .eq("source_url", source_url[:500])\
                    .execute()
                
                if not response.data:
                    continue
                
                record = response.data[0]
                
                # 检查是否过期
                last_fetched = datetime.fromisoformat(record["last_fetched_at"])
                ttl_hours = record.get("ttl_hours", 6)
                
                if datetime.utcnow() - last_fetched > timedelta(hours=ttl_hours):
                    logger.debug(f"⏰ 源缓存已过期: {source_url[:30]}")
                    continue
                
                # 解码内容
                try:
                    content_str = base64.b64decode(record["content"]).decode()
                    nodes = json.loads(content_str)
                    result[source_url] = nodes
                    logger.debug(f"✅ 加载缓存源: {source_url[:30]} ({len(nodes)} 个节点)")
                except Exception as e:
                    logger.warning(f"⚠️ 解码缓存失败: {e}")
            
            return result
        except Exception as e:
            logger.error(f"❌ 加载源缓存失败: {e}")
            return {}
    
    # ==================== 解析节点缓存 ====================
    
    async def save_parsed_nodes(self, nodes: List[Dict]) -> bool:
        """保存解析后的节点到缓存"""
        # 始终保存到内存缓存
        self.memory_cache['parsed_nodes'] = {}
        for node in nodes:
            key = f"{node.get('host')}:{node.get('port')}"
            self.memory_cache['parsed_nodes'][key] = node
        
        if not self.supabase or self.use_memory_cache:
            logger.info(f"💾 已保存到内存缓存 {len(nodes)} 个解析节点")
            return True
        
        try:
            records = []
            for node in nodes:
                record = {
                    "id": int(hashlib.md5(
                        f"{node.get('host')}:{node.get('port')}".encode()
                    ).hexdigest()[:8], 16),
                    "host": node.get("host", ""),
                    "port": node.get("port", 0),
                    "name": node.get("name", "")[:255],
                    "protocol": node.get("protocol", "")[:50],
                    "full_content": json.dumps(node, ensure_ascii=False),
                    "source_url": node.get("source_url", "")[:500],
                    "parsed_at": datetime.utcnow().isoformat(),
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                records.append(record)
            
            # 批量 upsert
            if records:
                self.supabase.table("parsed_nodes").upsert(records).execute()
                logger.info(f"✅ 已缓存 {len(records)} 个解析节点")
            
            return True
        except Exception as e:
            logger.error(f"⚠️ Supabase 保存节点缓存失败: {e}，但内存缓存已保存")
            return True  # 返回 True，因为内存缓存已保存
    
    async def load_parsed_nodes(self) -> List[Dict]:
        """从缓存加载解析节点"""
        # 优先从内存缓存加载
        if self.memory_cache['parsed_nodes']:
            nodes = list(self.memory_cache['parsed_nodes'].values())
            logger.info(f"💾 从内存缓存加载 {len(nodes)} 个解析节点")
            return nodes
        
        if not self.supabase or self.use_memory_cache:
            return []
        
        try:
            # 查询最近 6 小时内的节点
            six_hours_ago = (datetime.utcnow() - timedelta(hours=6)).isoformat()
            
            response = self.supabase.table("parsed_nodes")\
                .select("full_content")\
                .gte("updated_at", six_hours_ago)\
                .order("updated_at", desc=True)\
                .execute()
            
            nodes = []
            for record in response.data:
                try:
                    node = json.loads(record["full_content"])
                    nodes.append(node)
                except Exception as e:
                    logger.warning(f"⚠️ 解析节点失败: {e}")
            
            logger.info(f"✅ 从缓存加载 {len(nodes)} 个解析节点")
            return nodes
        except Exception as e:
            logger.error(f"❌ 加载节点缓存失败: {e}")
            return []
    
    # ==================== 测速队列 ====================
    
    async def save_testing_queue(self, queue_tasks: List[Dict]) -> bool:
        """保存测速队列任务"""
        # 始终保存到内存缓存
        self.memory_cache['testing_queue'] = queue_tasks.copy()
        
        if not self.supabase or self.use_memory_cache:
            logger.debug(f"💾 已保存到内存缓存 {len(queue_tasks)} 个队列任务")
            return True
        
        try:
            records = []
            for idx, task in enumerate(queue_tasks):
                record = {
                    "id": int(hashlib.md5(
                        f"{task['node_host']}:{task['node_port']}:{idx}".encode()
                    ).hexdigest()[:8], 16),
                    "group_number": task.get("group_number", 0),
                    "group_position": task.get("group_position", 0),
                    "node_host": task.get("node_host", ""),
                    "node_port": task.get("node_port", 0),
                    "node_name": task.get("node_name", "")[:255],
                    "status": task.get("status", "pending"),
                    "attempted_count": task.get("attempted_count", 0),
                    "last_tested_at": task.get("last_tested_at"),
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                records.append(record)
            
            if records:
                self.supabase.table("testing_queue").upsert(records).execute()
                logger.debug(f"✅ 已保存 {len(records)} 个队列任务")
            
            return True
        except Exception as e:
            logger.error(f"⚠️ Supabase 保存队列失败: {e}，但内存缓存已保存")
            return True  # 返回 True，因为内存缓存已保存
    
    async def load_testing_queue(self) -> List[Dict]:
        """加载未完成的测速队列"""
        # 优先从内存缓存加载
        if self.memory_cache['testing_queue']:
            logger.info(f"💾 从内存缓存加载 {len(self.memory_cache['testing_queue'])} 个队列任务")
            return self.memory_cache['testing_queue'].copy()
        
        if not self.supabase or self.use_memory_cache:
            return []
        
        try:
            # 查询所有未完成的任务，按组和位置排序
            response = self.supabase.table("testing_queue")\
                .select("*")\
                .neq("status", "completed")\
                .order("group_number", desc=False)\
                .order("group_position", desc=False)\
                .execute()
            
            if response.data:
                logger.info(f"✅ 恢复 {len(response.data)} 个未完成的队列任务")
                return response.data
            
            return []
        except Exception as e:
            logger.warning(f"⚠️ 加载队列失败: {e}")
            return []
    
    async def update_task_status(self, node_host: str, node_port: int, status: str) -> bool:
        """更新单个任务状态"""
        if not self.supabase:
            return False
        
        try:
            self.supabase.table("testing_queue")\
                .update({
                    "status": status,
                    "last_tested_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                })\
                .eq("node_host", node_host)\
                .eq("node_port", node_port)\
                .execute()
            
            return True
        except Exception as e:
            logger.warning(f"⚠️ 更新任务状态失败: {e}")
            return False
    
    # ==================== 数据清理 ====================
    
    async def cleanup_expired_cache(self) -> bool:
        """清理过期的缓存数据"""
        if not self.supabase:
            return False
        
        try:
            # 删除 7 天前的已完成任务
            seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            self.supabase.table("testing_queue")\
                .delete()\
                .eq("status", "completed")\
                .lt("created_at", seven_days_ago)\
                .execute()
            
            # 删除过期的源缓存 (> 24小时)
            twentyfour_hours_ago = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            self.supabase.table("sources_cache")\
                .delete()\
                .lt("last_fetched_at", twentyfour_hours_ago)\
                .execute()
            
            logger.info("✅ 过期缓存清理完成")
            return True
        except Exception as e:
            logger.warning(f"⚠️ 清理缓存失败: {e}")
            return False


# 全局持久化管理器实例
_persistence_instance = None


def get_persistence() -> PersistenceHelper:
    """获取全局持久化管理器实例"""
    global _persistence_instance
    if _persistence_instance is None:
        _persistence_instance = PersistenceHelper()
    return _persistence_instance
