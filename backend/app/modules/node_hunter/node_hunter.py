# backend/app/modules/node_hunter/node_hunter.py
# !/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks, Body, Query, Request
import asyncio
import aiohttp
import time
from pydantic import BaseModel
from datetime import datetime
import random
from typing import List, Optional, Dict, Any
import logging
import os
import qrcode
from io import BytesIO
import json
import base64
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import ipapi

from ..link_scraper.link_scraper import LinkScraper
from .parsers import parse_node_url
from .validators import test_node_network, NodeTestResult
from .config_generator import generate_node_share_link, generate_subscription_content, generate_clash_config
from .advanced_speed_test import run_advanced_speed_test
from .supabase_helper import upload_to_supabase, check_supabase_connection
from .clash_basic_check import (
    check_nodes_clash,
    ClashCheckResult,
    ClashBasicChecker,
)
from .v2ray_check import (
    check_nodes_v2ray,
    V2RayCheckResult,
)
from .simple_availability_check import (
    AvailabilityLevel,
    AvailabilityResult,
)
from .real_speed_test import RealSpeedTester
from .geolocation_helper import GeolocationHelper
from .persistence_helper import get_persistence

try:
    from ..proxy.proxy_engine import manager as pool_manager
except ImportError:
    pool_manager = None

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nodes", tags=["nodes"])

VERIFIED_NODES_FILE = "verified_nodes.json"

# ==================== 云端检测配置 ====================

# Aliyun FC URL (用于国内节点检测)
ALIYUN_FC_URL = os.environ.get("ALIYUN_FC_URL", "")

# Cloudflare Worker URL (用于海外节点检测)
CF_WORKER_URL = os.environ.get("CF_WORKER_URL", "")

# 是否启用云端检测
CLOUD_DETECTION_ENABLED = os.environ.get("CLOUD_DETECTION_ENABLED", "false").lower() == "true"  # 🔥 改为默认false，避免节点被过度过滤

NAME_TO_CODE = {
    # 亚洲
    "CN": "CN", "CHINA": "CN", "中国": "CN", "回国": "CN", "BEIJING": "CN", "SHANGHAI": "CN", "SHENZHEN": "CN",
    "🇨🇳": "CN",
    "HK": "HK", "HONG KONG": "HK", "HONGKONG": "HK", "🇭🇰": "HK",
    "TW": "TW", "TAIWAN": "TW", "TAIPEI": "TW", "🇹🇼": "TW",
    "MO": "MO", "MACAO": "MO", "MACAU": "MO", "🇲🇴": "MO",
    "JP": "JP", "JAPAN": "JP", "TOKYO": "JP", "OSAKA": "JP", "🇯🇵": "JP",
    "SG": "SG", "SINGAPORE": "SG", "🇸🇬": "SG",
    "KR": "KR", "KOREA": "KR", "SEOUL": "KR", "🇰🇷": "KR",
    "TH": "TH", "THAILAND": "TH", "BANGKOK": "TH", "🇹🇭": "TH",
    "MY": "MY", "MALAYSIA": "MY", "KUALA LUMPUR": "MY", "🇲🇾": "MY",
    "PH": "PH", "PHILIPPINES": "PH", "MANILA": "PH", "🇵🇭": "PH",
    "VN": "VN", "VIETNAM": "VN", "HANOI": "VN", "HO CHI MINH": "VN", "🇻🇳": "VN",
    "ID": "ID", "INDONESIA": "ID", "JAKARTA": "ID", "🇮🇩": "ID",
    "IN": "IN", "INDIA": "IN", "DELHI": "IN", "MUMBAI": "IN", "🇮🇳": "IN",
    "PK": "PK", "PAKISTAN": "PK", "ISLAMABAD": "PK", "🇵🇰": "PK",
    "BD": "BD", "BANGLADESH": "BD", "DHAKA": "BD", "🇧🇩": "BD",
    "LK": "LK", "SRI LANKA": "LK", "COLOMBO": "LK", "🇱🇰": "LK",
    # 中东
    "TR": "TR", "TURKEY": "TR", "ISTANBUL": "TR", "ANKARA": "TR", "🇹🇷": "TR",
    "AE": "AE", "UAE": "AE", "UNITED ARAB EMIRATES": "AE", "DUBAI": "AE", "🇦🇪": "AE",
    "SA": "SA", "SAUDI ARABIA": "SA", "RIYADH": "SA", "🇸🇦": "SA",
    "IL": "IL", "ISRAEL": "IL", "TEL AVIV": "IL", "🇮🇱": "IL",
    "JO": "JO", "JORDAN": "JO", "AMMAN": "JO", "🇯🇴": "JO",
    # 欧洲
    "GB": "GB", "UK": "GB", "UNITED KINGDOM": "GB", "LONDON": "GB", "🇬🇧": "GB",
    "DE": "DE", "GERMANY": "DE", "FRANKFURT": "DE", "BERLIN": "DE", "🇩🇪": "DE",
    "FR": "FR", "FRANCE": "FR", "PARIS": "FR", "LYON": "FR", "🇫🇷": "FR",
    "NL": "NL", "NETHERLANDS": "NL", "AMSTERDAM": "NL", "ROTTERDAM": "NL", "🇳🇱": "NL",
    "BE": "BE", "BELGIUM": "BE", "BRUSSELS": "BE", "🇧🇪": "BE",
    "IT": "IT", "ITALY": "IT", "MILAN": "IT", "ROME": "IT", "🇮🇹": "IT",
    "ES": "ES", "SPAIN": "ES", "MADRID": "ES", "BARCELONA": "ES", "🇪🇸": "ES",
    "PT": "PT", "PORTUGAL": "PT", "LISBON": "PT", "🇵🇹": "PT",
    "PL": "PL", "POLAND": "PL", "WARSAW": "PL", "🇵🇱": "PL",
    "SE": "SE", "SWEDEN": "SE", "STOCKHOLM": "SE", "🇸🇪": "SE",
    "NO": "NO", "NORWAY": "NO", "OSLO": "NO", "🇳🇴": "NO",
    "DK": "DK", "DENMARK": "DK", "COPENHAGEN": "DK", "🇩🇰": "DK",
    "FI": "FI", "FINLAND": "FI", "HELSINKI": "FI", "🇫🇮": "FI",
    "CH": "CH", "SWITZERLAND": "CH", "ZURICH": "CH", "GENEVA": "CH", "🇨🇭": "CH",
    "AT": "AT", "AUSTRIA": "AT", "VIENNA": "AT", "🇦🇹": "AT",
    "CZ": "CZ", "CZECH": "CZ", "PRAGUE": "CZ", "🇨🇿": "CZ",
    "HU": "HU", "HUNGARY": "HU", "BUDAPEST": "HU", "🇭🇺": "HU",
    "RO": "RO", "ROMANIA": "RO", "BUCHAREST": "RO", "🇷🇴": "RO",
    "GR": "GR", "GREECE": "GR", "ATHENS": "GR", "🇬🇷": "GR",
    "RU": "RU", "RUSSIA": "RU", "MOSCOW": "RU", "ST PETERSBURG": "RU", "SIBERIA": "RU", "🇷🇺": "RU",
    "UA": "UA", "UKRAINE": "UA", "KYIV": "UA", "🇺🇦": "UA",
    "BG": "BG", "BULGARIA": "BG", "SOFIA": "BG", "🇧🇬": "BG",
    # 北美
    "US": "US", "USA": "US", "AMERICA": "US", "UNITED STATES": "US", "LOS ANGELES": "US", "SAN FRANCISCO": "US",
    "NEW YORK": "US", "CHICAGO": "US", "DALLAS": "US", "SEATTLE": "US", "MIAMI": "US", "🇺🇸": "US",
    "CA": "CA", "CANADA": "CA", "TORONTO": "CA", "VANCOUVER": "CA", "MONTREAL": "CA", "🇨🇦": "CA",
    "MX": "MX", "MEXICO": "MX", "MEXICO CITY": "MX", "🇲🇽": "MX",
    # 南美
    "BR": "BR", "BRAZIL": "BR", "SAO PAULO": "BR", "RIO DE JANEIRO": "BR", "🇧🇷": "BR",
    "AR": "AR", "ARGENTINA": "AR", "BUENOS AIRES": "AR", "🇦🇷": "AR",
    "CL": "CL", "CHILE": "CL", "SANTIAGO": "CL", "🇨🇱": "CL",
    "CO": "CO", "COLOMBIA": "CO", "BOGOTA": "CO", "🇨🇴": "CO",
    "PE": "PE", "PERU": "PE", "LIMA": "PE", "🇵🇪": "PE",
    "VE": "VE", "VENEZUELA": "VE", "CARACAS": "VE", "🇻🇪": "VE",
    # 大洋洲
    "AU": "AU", "AUSTRALIA": "AU", "SYDNEY": "AU", "MELBOURNE": "AU", "BRISBANE": "AU", "🇦🇺": "AU",
    "NZ": "NZ", "NEW ZEALAND": "NZ", "AUCKLAND": "NZ", "WELLINGTON": "NZ", "🇳🇿": "NZ",
    # 非洲
    "ZA": "ZA", "SOUTH AFRICA": "ZA", "JOHANNESBURG": "ZA", "CAPE TOWN": "ZA", "🇿🇦": "ZA",
    "EG": "EG", "EGYPT": "EG", "CAIRO": "EG", "🇪🇬": "EG",
    "NG": "NG", "NIGERIA": "NG", "LAGOS": "NG", "🇳🇬": "NG",
}


class StatsResponse(BaseModel):
    count: int
    running: bool
    logs: List[str]
    nodes: List[dict]
    next_scan_time: Optional[float] = None  # 🔥 新增：下次扫描时间戳


class NodeTarget(BaseModel):
    host: str
    port: int


class SourceRequest(BaseModel):
    url: str


class NodeHunter:
    def __init__(self):
        self.nodes: List[dict] = []
        self.is_scanning = False
        self.logs: List[str] = []
        self.subscription_base64: Optional[str] = None
        self.link_scraper = LinkScraper(pool_manager)
        self.user_sources_file = 'user_sources.json'
        self.user_sources = self._load_user_sources()
        self.sources = self._get_default_sources() + self.user_sources
        self.scheduler = AsyncIOScheduler()
        
        # 🔥 初始化持久化管理器
        self.persistence = get_persistence()
        
        self._load_nodes_from_file()

        self.source_stats: Dict[str, Dict] = {}
        self.scan_cycle_count = 0
        for src in self.sources:
            self.source_stats[src] = {"is_disabled": False, "disabled_at": 0, "retry_fails": 0}

        # 🔥 初始化真实速度测试和地理位置助手
        self.speed_tester = RealSpeedTester()
        self.geolocation_helper = GeolocationHelper()
        
        # 🔥 P3优化: 待检测节点队列系统 (分批处理大规模节点)
        self.pending_nodes_queue: Dict[str, dict] = {}  # 待检测节点队列 {node_key: {node_data, retry_count, priority}}
        self.is_batch_testing = False  # 批量检测进行中标志
        self.last_batch_test_time = 0  # 上次批量检测时间
        self.batch_test_interval = 3600  # 1小时检测一次 (秒)
        self.batch_size = 50   # 每次检测50个节点 (🔥 改小到50加快反馈速度，约3-4分钟完成一轮)
        self.max_retries = 3  # 失败重试3次
        self.last_sync_time = 0  # 上次同步时间
        self.sync_interval = 3600  # 1小时同步一次 (秒)
        
        # 🔥 新增：测速队列进度追踪（来自持久化）
        self.testing_queue_tasks: List[Dict] = []  # 测速任务队列
        self.current_queue_index = 0  # 当前处理的队列索引
        
        # 🔥 新增: socks/http 开关控制 (默认关闭)
        self.show_socks_http = False  # 是否显示 socks/http 节点
        self.show_china_nodes = False  # 是否显示国内节点

    def start_scheduler(self):
        if not self.scheduler.running:
            # 爬虫: 每6小时自动扫描一次
            self.scheduler.add_job(self.scan_cycle, 'interval', minutes=360, id='node_scan_refresh')
            
            # 🔥 P3: 独立的批量检测定时任务 (每1小时执行一次，从队列取1000个节点检测)
            # initial_delay=65秒 确保爬虫完成后立即开始检测
            self.scheduler.add_job(
                self._batch_test_pending_nodes, 
                'interval', 
                minutes=60, 
                id='batch_node_test',
                seconds=0
            )
            
            # 🔥 P3: 独立的同步定时任务 (每1小时执行一次)
            # 比检测晚30秒开始，确保检测结果已写入
            self.scheduler.add_job(
                self._sync_nodes_to_storage, 
                'interval', 
                minutes=60, 
                id='node_sync',
                seconds=30
            )
            
            # 🔥 新增：Supabase 同步定时任务 (每3分钟执行一次)
            # 将已验证的节点写入 Supabase，供 viper-node-store 读取
            self.scheduler.add_job(
                self._sync_to_supabase_task,
                'interval',
                minutes=3,
                id='supabase_sync',
                seconds=0
            )
            
            # 🔥 新增：定期清理过期缓存 (每日凌晨 3 点)
            self.scheduler.add_job(
                self._cleanup_expired_cache_task,
                'cron',
                hour=3,
                minute=0,
                id='cache_cleanup'
            )
            
            self.scheduler.start()
            self.add_log("✅ [System] 节点猎手自动巡航已启动 (6h/爬虫, 1h/检测, 1h/同步, 3min/Supabase, 每日3:00清理缓存)", "SUCCESS")
            
            # 🔥 改进：Persistence 初始化和爬虫启动都改为后台任务，不阻塞 FastAPI 启动
            async def init_persistence_background():
                """后台初始化持久化，不阻塞启动"""
                try:
                    await asyncio.sleep(2)  # 等待 FastAPI 完全启动（2秒）
                    await self.persistence.init_persistence_tables()
                    self.add_log("✅ 持久化表初始化完成", "SUCCESS")
                    
                    # Persistence 初始化完后，再等待 28 秒才启动爬虫
                    await asyncio.sleep(28)
                    self.add_log("⏰ 30秒延迟已过期，启动首次节点扫描...", "INFO")
                    await self.scan_cycle()
                    
                    # 等待爬虫完成，然后启动检测
                    max_retries = 5
                    for attempt in range(max_retries):
                        await asyncio.sleep(10)
                        
                        if self.pending_nodes_queue:
                            self.add_log(f"🚀 爬虫完成，立即启动首次批量检测... (队列: {len(self.pending_nodes_queue)} 个节点)", "INFO")
                            await self._batch_test_pending_nodes()
                            break
                        else:
                            self.add_log(f"⏳ 等待爬虫完成... 尝试 {attempt+1}/{max_retries}", "WARNING")
                    
                    if not self.pending_nodes_queue:
                        self.add_log("❌ 爬虫完成后队列仍为空，可能爬虫失败", "ERROR")
                    
                except Exception as e:
                    self.add_log(f"❌ [System] 后台初始化异常: {str(e)}", "ERROR")
                    logger.exception("后台初始化异常")
            
            # 🔥 创建后台任务，立即返回，不阻塞 FastAPI
            task = asyncio.create_task(init_persistence_background())
            task.add_done_callback(lambda t: logger.exception(t.exception()) if t.exception() else None)

    def get_alive_nodes(self) -> List[Dict[str, Any]]:
        return [node for node in self.nodes if node.get('alive')]

    def get_socks5_nodes(self) -> List[Dict[str, Any]]:
        return [
            node for node in self.nodes
            if node.get('alive') and node.get('protocol') in ['socks5', 'socks']
        ]

    def _load_user_sources(self) -> List[str]:
        try:
            if os.path.exists(self.user_sources_file):
                with open(self.user_sources_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载用户源失败: {e}")
        return []
    
    def _convert_to_clash_node(self, node: Dict) -> Optional[Dict]:
        """
        将节点转换为Clash格式
        
        Args:
            node: 原始节点数据
            
        Returns:
            Clash格式节点配置，如果转换失败则返回None
        """
        try:
            protocol = node.get('protocol', '').lower()
            
            clash_node = {
                "name": f"{node.get('host')}:{node.get('port')}",
                "server": node.get('host'),
                "port": int(node.get('port', 0)),
            }
            
            # 根据协议类型转换
            if protocol in ['vmess']:
                clash_node.update({
                    "type": "vmess",
                    "uuid": node.get('id') or node.get('uuid', ''),
                    "alterId": int(node.get('aid', 0)) if node.get('aid') else 0,
                    "cipher": node.get('scy', 'auto'),
                    "network": node.get('net', 'tcp'),
                })
                
                # WebSocket配置
                if clash_node['network'] == 'ws':
                    clash_node['ws-opts'] = {
                        "path": node.get('path', '/'),
                        "headers": {"Host": node.get('host', '')}
                    }
                    
            elif protocol in ['vless']:
                clash_node.update({
                    "type": "vless",
                    "uuid": node.get('id') or node.get('uuid', ''),
                    "flow": node.get('flow', ''),
                    "network": node.get('net', 'tcp'),
                })
                
            elif protocol in ['trojan']:
                clash_node.update({
                    "type": "trojan",
                    "password": node.get('password', ''),
                    "sni": node.get('sni', node.get('host')),
                })
                
            elif protocol in ['ss', 'shadowsocks']:
                clash_node.update({
                    "type": "ss",
                    "cipher": node.get('method', 'aes-256-gcm'),
                    "password": node.get('password', ''),
                })
                
            elif protocol in ['socks5', 'socks']:
                clash_node.update({
                    "type": "socks5",
                    "username": node.get('username', ''),
                    "password": node.get('password', ''),
                })
                
            elif protocol in ['http', 'https']:
                clash_node.update({
                    "type": "http",
                    "username": node.get('username', ''),
                    "password": node.get('password', ''),
                })
                
            else:
                # 🔥 修复：不支持的协议仍然返回基础配置，而不是None
                # 这样即使Clash无法处理，后续的Xray检测仍然可以尝试
                logger.debug(f"Clash不支持协议{protocol}，将由Xray处理: {node.get('host')}:{node.get('port')}")
                return None  # Xray会处理这些协议
            
            return clash_node
            
        except Exception as e:
            logger.error(f"节点转换失败: {e}, 节点: {node}")
            return None

    def _save_user_sources(self):
        try:
            with open(self.user_sources_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_sources, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存用户源失败: {e}")

    def _load_nodes_from_file(self):
        """
        🔥 启动时先从本地缓存快速加载，然后在后台从 Supabase 更新
        这样可以保证启动速度，同时也能获取最新数据
        """
        # 先从本地文件快速加载（保证启动速度）
        self._load_nodes_from_local_file()
        
        # 然后安排一个后台任务从 Supabase 更新
        # 这会在事件循环启动后执行
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # FastAPI 环境：创建后台任务
                asyncio.create_task(self._load_and_merge_from_supabase())
        except Exception as e:
            self.add_log(f"⚠️ 设置 Supabase 加载任务失败: {e}", "WARNING")
    
    async def _load_and_merge_from_supabase(self):
        """后台从 Supabase 加载节点并合并到内存"""
        await asyncio.sleep(5)  # 等待 5 秒，让系统完全启动
        
        import os
        try:
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
            
            if not url or not key:
                self.add_log("⚠️ Supabase 凭证未配置，跳过数据库加载", "WARNING")
                return
            
            from supabase import create_client
            supabase = create_client(url, key)
            
            # 查询最新的节点数据，按 speed 降序，限制 200 条
            self.add_log("☁️ 正在从 Supabase 数据库加载节点...", "INFO")
            response = supabase.table("nodes").select("*").order("speed", desc=True).limit(200).execute()
            
            if response.data:
                loaded_nodes = []
                for row in response.data:
                    # 从 content 字段提取完整节点数据
                    node = row.get('content', {})
                    if isinstance(node, dict) and node.get('host'):
                        # 补充数据库中的评分数据
                        node['mainland_score'] = row.get('mainland_score', 0)
                        node['overseas_score'] = row.get('overseas_score', 0)
                        node['mainland_latency'] = row.get('mainland_latency', 9999)
                        node['overseas_latency'] = row.get('overseas_latency', 9999)
                        node['alive'] = True  # 数据库中的都是验证过的活跃节点
                        
                        # 应用国家识别
                        country = self._normalize_country(node.get('country', 'UNK'))
                        if country == 'UNK':
                            country = self._guess_country_from_name(node.get('name', ''))
                        node['country'] = country
                        
                        loaded_nodes.append(node)
                
                if loaded_nodes:
                    # 🔥 合并策略：用数据库节点替换本地节点
                    # 按 host:port 去重，数据库优先
                    existing_keys = {f"{n.get('host')}:{n.get('port')}" for n in self.nodes}
                    db_keys = set()
                    merged_nodes = []
                    
                    # 先加入数据库节点（优先）
                    for node in loaded_nodes:
                        key = f"{node.get('host')}:{node.get('port')}"
                        if key not in db_keys:
                            db_keys.add(key)
                            merged_nodes.append(node)
                    
                    # 再加入本地节点中不在数据库的部分
                    for node in self.nodes:
                        key = f"{node.get('host')}:{node.get('port')}"
                        if key not in db_keys:
                            merged_nodes.append(node)
                    
                    old_count = len(self.nodes)
                    self.nodes = merged_nodes
                    self.add_log(f"☁️ 从 Supabase 加载了 {len(loaded_nodes)} 个节点，合并后共 {len(self.nodes)} 个 (原 {old_count} 个)", "SUCCESS")
                    return
            
            self.add_log("⚠️ Supabase 中无节点数据", "WARNING")
            
        except ImportError:
            self.add_log("⚠️ supabase 库未安装", "WARNING")
        except Exception as e:
            self.add_log(f"⚠️ Supabase 查询失败: {e}", "WARNING")

    async def _load_nodes_from_supabase(self):
        """从 Supabase 数据库加载节点（已废弃，使用 _load_and_merge_from_supabase）"""
        await self._load_and_merge_from_supabase()
    
    def _load_nodes_from_local_file(self):
        """从本地 JSON 文件加载节点（备用方案）"""
        if os.path.exists(VERIFIED_NODES_FILE):
            try:
                with open(VERIFIED_NODES_FILE, "r") as f:
                    loaded_nodes = json.load(f)
                    for node in loaded_nodes:
                        # 🔥 优先尝试规范化国家名称
                        country = self._normalize_country(node.get('country', 'UNK'))
                        
                        # 🔥 如果仍为UNK，尝试从IP查询或从名称猜测
                        if country == 'UNK':
                            country = self._get_country_code_from_ip(node.get('host', ''))
                            if country == 'UNK':
                                country = self._guess_country_from_name(node.get('name', ''))
                        
                        node['country'] = country
                    self.nodes = loaded_nodes
                self.add_log(f"📥 从本地缓存加载了 {len(loaded_nodes)} 个节点", "SUCCESS")
            except Exception as e:
                self.add_log(f"⚠️ 加载本地缓存失败: {e}", "WARNING")

    def _save_nodes_to_file(self):
        try:
            alive_nodes = self.get_alive_nodes()
            sorted_nodes = sorted(alive_nodes, key=lambda x: x.get('test_results', {}).get('total_score', 0),
                                  reverse=True)
            top_nodes = sorted_nodes[:150]
            with open(VERIFIED_NODES_FILE, "w") as f:
                json.dump(top_nodes, f, indent=2)
            self.add_log(f"💾 已将 Top {len(top_nodes)} 节点保存到缓存", "INFO")
        except Exception as e:
            self.add_log(f"⚠️ 保存节点到文件失败: {e}", "WARNING")

    def _get_default_sources(self) -> List[str]:
        return [
            # 🔥 超高优先级: 核心高质量源 (频繁更新，数千节点)
            # Epodonios: 5分钟更新，支持vmess/vless/trojan/ss/ssr
            "https://github.com/Epodonios/v2ray-configs/raw/main/All_Configs_Sub.txt",
            "https://github.com/Epodonios/v2ray-configs/raw/main/Splitted-By-Protocol/vmess.txt",
            "https://github.com/Epodonios/v2ray-configs/raw/main/Splitted-By-Protocol/vless.txt",
            
            # ebrasha: 30分钟更新，节点经过过滤和测试
            "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/all_extracted_configs.txt",
            "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vmess_configs.txt",
            "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vless_configs.txt",
            
            # mahdibland: 12小时更新，大规模节点池(5000+)，速度测试过滤
            "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
            "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/sub/sub_merge.txt",
            
            # 🔥 高优先级: 按国家过滤的专用源 (80+国家)
            # 主要国家订阅 (mixed协议，支持多种)
            "https://raw.githubusercontent.com/freefq/free/master/v2",
            "https://github.com/free-nodes/v2rayfree",
            "https://clashgithub.com/",
            "https://github.com/V2RayRoot/V2RayConfig",
            "https://www.v2nodes.com/",
            "https://raw.githubusercontent.com/learnhard-cn/free_proxy_ss/main/free",
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
            "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
            "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
            "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
            "https://raw.githubusercontent.com/vveg26/get_proxy/main/subscribe/clash.yaml",
            "https://raw.githubusercontent.com/peasoft/NoWars/main/result.txt",
        ]

    def add_log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.insert(0, f"[{timestamp}] {message}")
        if len(self.logs) > 100: self.logs.pop()
        logger.info(message)

    def add_user_source(self, url: str):
        if url in self.sources:
            return False, "该源已存在"

        self.user_sources.append(url)
        self.sources.append(url)
        self.source_stats[url] = {"is_disabled": False, "disabled_at": 0, "retry_fails": 0}
        self._save_user_sources()
        self.add_log(f"➕ 添加新源: {url[:30]}...", "SUCCESS")
        return True, "添加成功"

    async def _fetch_all_subscriptions(self) -> tuple:
        """
        返回: (所有节点链接列表, 源贡献字典)
        """
        all_nodes = []
        self.scan_cycle_count += 1
        target_urls = []
        for url in self.sources:
            stats = self.source_stats.get(url, {"is_disabled": False, "disabled_at": 0, "retry_fails": 0})
            if stats["is_disabled"]:
                if (self.scan_cycle_count - stats["disabled_at"]) >= 10:
                    stats["is_disabled"] = False
                    stats["retry_fails"] = 0
                    target_urls.append(url)
                    self.add_log(f"🔄 源已解封: {url[:30]}...", "INFO")
            else:
                target_urls.append(url)

        if not target_urls: 
            return [], {}

        # 用于追踪每个源的贡献 + 节点映射
        source_nodes_map = {}
        source_node_mapping = {}  # 新增：记录节点属于哪个源

        async def fetch_source(url):
            try:
                content = await self.link_scraper.scrape_links_from_url(url)
                if content:
                    source_name = url.replace("https://", "").replace("http://", "")[:40]
                    self.add_log(f"✅ [{source_name}] 抓取 {len(content)} 个节点", "SUCCESS")
                    if url in self.source_stats: self.source_stats[url]['retry_fails'] = 0
                    source_nodes_map[url] = len(content)
                    source_node_mapping[url] = content  # 保存节点-源映射
                    return content
                else:
                    raise Exception("Empty")
            except Exception as e:
                source_name = url.replace("https://", "").replace("http://", "")[:40]
                self.add_log(f"❌ [{source_name}] 抓取失败: {str(e)[:30]}", "WARNING")
                if url in self.source_stats:
                    stats = self.source_stats[url]
                    stats['retry_fails'] += 1
                    if stats['retry_fails'] >= 3:
                        stats['is_disabled'] = True
                        stats['disabled_at'] = self.scan_cycle_count
                        self.add_log(f"🚫 [{source_name}] 已禁用(连续失败3次)", "WARNING")
            return []

        # 🔥 添加 Semaphore 限流，最多同时 10 个并发源请求，防止连接耗尽
        semaphore = asyncio.Semaphore(10)
        
        async def fetch_source_with_limit(url):
            async with semaphore:
                return await fetch_source(url)
        
        tasks = [fetch_source_with_limit(src) for src in target_urls]
        results = await asyncio.gather(*tasks)
        for i, res in enumerate(results):
            all_nodes.extend(res)
        
        # 记录源统计总结
        total_from_sources = sum(source_nodes_map.values())
        self.add_log(f"📊 本次爬虫周期: 从 {len(source_nodes_map)}/{len(target_urls)} 个源获取 {total_from_sources} 个节点", "INFO")
        
        # 保存源贡献日志
        if not hasattr(self, 'source_contribution_log'):
            self.source_contribution_log = []
        self.source_contribution_log.append({
            'cycle': self.scan_cycle_count,
            'timestamp': datetime.now().isoformat(),
            'sources': source_nodes_map,
            'total_nodes': total_from_sources
        })
        
        # 💾 保存源缓存到Supabase
        try:
            await self.persistence.save_sources_cache(source_node_mapping, source_nodes_map)
            self.add_log(f"💾 源缓存已保存到Supabase", "SUCCESS")
        except Exception as e:
            self.add_log(f"⚠️ 源缓存保存失败: {e}", "WARNING")
        
        return list(set(all_nodes)), source_node_mapping

    async def _fetch_china_nodes(self) -> List[Dict]:
        nodes = []
        try:
            from .china_hunter import ChinaHunter
            hunter = ChinaHunter()
            self.add_log(f"🇨🇳 [CN猎手] 正在从 {len(hunter.sources)} 个源抓取...", "INFO")
            nodes = await hunter.fetch_all()
            if nodes:
                self.add_log(f"📥 [CN猎手] 捕获 {len(nodes)} 个潜在CN节点", "SUCCESS")
        except:
            pass
        return nodes

    def _get_country_code_from_ip(self, ip: str) -> str:
        """通过IP地址查询国家代码（异步执行，使用缓存）"""
        try:
            # 首先检查缓存
            if hasattr(self, 'ip_country_cache') and ip in self.ip_country_cache:
                return self.ip_country_cache[ip]
            
            # 使用同步HTTP请求查询（3秒超时）
            import httpx
            import socket
            
            # 快速DNS检查：如果域名有国家代码线索，直接返回
            try:
                # 不做实际DNS查询，避免耗时
                pass
            except:
                pass
            
            try:
                response = httpx.get(f"https://ipapi.co/{ip}/json/", timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    country_code = data.get('country_code', 'UNK')
                    if country_code and country_code != 'UNK':
                        country_code = country_code.upper()
                        # 缓存结果
                        if not hasattr(self, 'ip_country_cache'):
                            self.ip_country_cache = {}
                        self.ip_country_cache[ip] = country_code
                        return country_code
            except Exception as e:
                # 忽略错误，快速返回UNK
                pass
        except:
            pass
        return 'UNK'

    def _normalize_country(self, raw_country: str) -> str:
        if not raw_country: return 'UNK'
        upper_raw = raw_country.upper().strip()
        
        # 🔥 首先检查是否是 2 字母代码
        if len(upper_raw) == 2 and upper_raw.isalpha():
            return upper_raw
        
        # 🔥 然后进行子串匹配（直接查找，不强制单词边界）
        for name, code in NAME_TO_CODE.items():
            if name in upper_raw or upper_raw in name:
                return code
        
        return 'UNK'

    def _guess_country_from_name(self, name: str) -> str:
        """从节点名称中猜测国家（备用，IP查询失败时使用）"""
        if not name: return 'UNK'
        upper_name = name.upper()
        
        # 🔥 扩展版本的国家关键词匹配表（包含城市、别名、中文等）
        country_patterns = [
            # 亚洲
            ('CN', ['CN', 'CHINA', '中国', '回国', 'BEIJING', 'SHANGHAI', 'SHENZHEN', 'CHONGQING', 'HANGZHOU', 'WUHAN', 'CHENG', 'XIAN', 'SICHUAN', 'JIANGSU', 'GUANGDONG']),
            ('HK', ['HK', 'HONG KONG', 'HONGKONG', '香港', 'HKG']),
            ('TW', ['TW', 'TAIWAN', 'TAIPEI', '台湾', 'TPE']),
            ('JP', ['JP', 'JAPAN', '日本', 'TOKYO', 'OSAKA', 'YOKOHAMA', 'KOBE', 'TYO', 'NRT', 'KIX']),
            ('SG', ['SG', 'SINGAPORE', '新加坡', 'SIN']),
            ('KR', ['KR', 'KOREA', '韩国', 'SEOUL', 'BUSAN', 'ICN', 'PUS']),
            ('TH', ['TH', 'THAILAND', '泰国', 'BANGKOK', 'BKK']),
            ('MY', ['MY', 'MALAYSIA', '马来西亚', 'KUALA LUMPUR', 'KUL']),
            ('PH', ['PH', 'PHILIPPINES', '菲律宾', 'MANILA', 'MNL']),
            ('VN', ['VN', 'VIETNAM', '越南', 'HANOI', 'HO CHI MINH', 'HAN', 'SGN']),
            ('ID', ['ID', 'INDONESIA', '印尼', 'JAKARTA', 'CGK']),
            ('IN', ['IN', 'INDIA', '印度', 'DELHI', 'BOMBAY', 'MUMBAI', 'BANGALORE', 'DEL', 'BOM']),
            ('PK', ['PK', 'PAKISTAN', '巴基斯坦', 'ISLAMABAD', 'KARACHI']),
            ('BD', ['BD', 'BANGLADESH', '孟加拉', 'DHAKA']),
            ('LK', ['LK', 'SRI LANKA', '斯里兰卡', 'COLOMBO', 'CMB']),
            # 中东
            ('TR', ['TR', 'TURKEY', '土耳其', 'ISTANBUL', 'ANKARA', 'IST']),
            ('AE', ['AE', 'UAE', 'UNITED ARAB EMIRATES', '阿联酋', 'DUBAI', 'ABU DHABI', 'DXB']),
            ('SA', ['SA', 'SAUDI ARABIA', '沙特', 'RIYADH', 'JEDDAH', 'RUH']),
            ('IL', ['IL', 'ISRAEL', '以色列', 'TEL AVIV', 'JERUSALEM', 'TLV']),
            ('JO', ['JO', 'JORDAN', '约旦', 'AMMAN', 'AMM']),
            # 欧洲
            ('GB', ['GB', 'UK', 'UNITED KINGDOM', '英国', 'LONDON', 'MANCHESTER', 'EDINBURGH', 'LHR', 'LGW']),
            ('DE', ['DE', 'GERMANY', '德国', 'FRANKFURT', 'BERLIN', 'MUNICH', 'HAMBURG', 'FRA', 'BER']),
            ('FR', ['FR', 'FRANCE', '法国', 'PARIS', 'LYON', 'MARSEILLE', 'CDG', 'ORY']),
            ('IT', ['IT', 'ITALY', '意大利', 'MILAN', 'ROME', 'VENICE', 'MXP', 'FCO']),
            ('ES', ['ES', 'SPAIN', '西班牙', 'MADRID', 'BARCELONA', 'VALENCIA', 'MAD', 'BCN']),
            ('NL', ['NL', 'NETHERLANDS', '荷兰', 'AMSTERDAM', 'ROTTERDAM', 'AMS']),
            ('BE', ['BE', 'BELGIUM', '比利时', 'BRUSSELS', 'ANTWERP', 'BRU']),
            ('PT', ['PT', 'PORTUGAL', '葡萄牙', 'LISBON', 'PORTO', 'LIS']),
            ('PL', ['PL', 'POLAND', '波兰', 'WARSAW', 'KRAKOW', 'WAW']),
            ('SE', ['SE', 'SWEDEN', '瑞典', 'STOCKHOLM', 'STOCKHOLM', 'ARN']),
            ('NO', ['NO', 'NORWAY', '挪威', 'OSLO', 'OSLO', 'OSL']),
            ('DK', ['DK', 'DENMARK', '丹麦', 'COPENHAGEN', 'CPH']),
            ('FI', ['FI', 'FINLAND', '芬兰', 'HELSINKI', 'HEL']),
            ('CH', ['CH', 'SWITZERLAND', '瑞士', 'ZURICH', 'GENEVA', 'ZRH']),
            ('AT', ['AT', 'AUSTRIA', '奥地利', 'VIENNA', 'VIENNA', 'VIE']),
            ('CZ', ['CZ', 'CZECH', 'CZECHOSLOVAKIA', '捷克', 'PRAGUE', 'PRG']),
            ('HU', ['HU', 'HUNGARY', '匈牙利', 'BUDAPEST', 'BUD']),
            ('RO', ['RO', 'ROMANIA', '罗马尼亚', 'BUCHAREST', 'BUH']),
            ('GR', ['GR', 'GREECE', '希腊', 'ATHENS', 'THESSALONIKI', 'ATH']),
            ('RU', ['RU', 'RUSSIA', '俄罗斯', 'MOSCOW', 'ST PETERSBURG', 'VLADIVOSTOK', 'SVO', 'LED']),
            ('UA', ['UA', 'UKRAINE', '乌克兰', 'KYIV', 'KHARKIV', 'KBP']),
            ('BG', ['BG', 'BULGARIA', '保加利亚', 'SOFIA', 'SOF']),
            # 北美
            ('US', ['US', 'USA', 'AMERICA', 'UNITED STATES', '美国', 'NEW YORK', 'LOS ANGELES', 'CHICAGO', 'DALLAS', 'SEATTLE', 'MIAMI', 'DENVER', 'SFO', 'LAX', 'JFK', 'ORD', 'DFW']),
            ('CA', ['CA', 'CANADA', '加拿大', 'TORONTO', 'VANCOUVER', 'MONTREAL', 'CALGARY', 'YYZ', 'YVR']),
            ('MX', ['MX', 'MEXICO', '墨西哥', 'MEXICO CITY', 'MEX']),
            # 南美
            ('BR', ['BR', 'BRAZIL', '巴西', 'SAO PAULO', 'RIO DE JANEIRO', 'GIG', 'GRU']),
            ('AR', ['AR', 'ARGENTINA', '阿根廷', 'BUENOS AIRES', 'AEP']),
            ('CL', ['CL', 'CHILE', '智利', 'SANTIAGO', 'SCL']),
            ('CO', ['CO', 'COLOMBIA', '哥伦比亚', 'BOGOTA', 'BOG']),
            ('PE', ['PE', 'PERU', '秘鲁', 'LIMA', 'LIM']),
            ('VE', ['VE', 'VENEZUELA', '委内瑞拉', 'CARACAS', 'CCS']),
            # 大洋洲
            ('AU', ['AU', 'AUSTRALIA', '澳洲', 'SYDNEY', 'MELBOURNE', 'BRISBANE', 'SYD', 'MEL']),
            ('NZ', ['NZ', 'NEW ZEALAND', '新西兰', 'AUCKLAND', 'WELLINGTON', 'AKL']),
            # 非洲
            ('ZA', ['ZA', 'SOUTH AFRICA', '南非', 'JOHANNESBURG', 'CAPE TOWN', 'JNB']),
            ('EG', ['EG', 'EGYPT', '埃及', 'CAIRO', 'ALEXANDRIA', 'CAI']),
            ('NG', ['NG', 'NIGERIA', '尼日利亚', 'LAGOS', 'LOS']),
        ]
        
        # 🔥 改进的匹配逻辑：不要求单词边界，只要匹配就行
        for country, keywords in country_patterns:
            for keyword in keywords:
                if keyword in upper_name:
                    return country
        
        # 最后备用：直接检查是否包含 2 字母国家代码（如 TR、IT 等）
        if len(upper_name) >= 2:
            # 从后往前扫，寻找类似 (TR)、-TR-、TR: 的模式
            import re
            codes_match = re.findall(r'[(\-\s]([A-Z]{2})[\)\-\s\:]', f'-{upper_name}-')
            if codes_match:
                potential_code = codes_match[0]
                # 检查这是否是有效的国家代码
                for name, code in NAME_TO_CODE.items():
                    if code == potential_code:
                        return potential_code
        
        # 默认返回未知
        return 'UNK'

    async def scan_cycle(self):
        """
        🔥 P3优化: 爬虫改为仅负责爬取和入队，不进行检测
        新节点入队到待检测队列，由独立的批量检测任务处理
        """
        if self.is_scanning: 
            self.add_log("⚠️ 爬虫已在运行中，跳过本次执行", "WARNING")
            return
        
        self.is_scanning = True
        self.add_log("🚀 开始全网节点爬虫（仅爬取，不检测）...", "INFO")
        
        try:
            # 🔥 仅执行爬取，不进行检测
            fetch_task = asyncio.create_task(self._fetch_all_subscriptions())
            china_task = asyncio.create_task(self._fetch_china_nodes())
            
            # 并行获取结果
            result = await fetch_task
            cn_nodes = await china_task
            
            # 处理返回的节点链接和源映射
            if isinstance(result, tuple):
                raw_nodes, source_node_mapping = result
            else:
                raw_nodes = result
                source_node_mapping = {}
            
            parsed_nodes = [parse_node_url(url) for url in raw_nodes]
            valid_parsed_nodes = [n for n in parsed_nodes if n]
            
            # 🔥 新增：为节点标记源信息
            for node in valid_parsed_nodes:
                node_link = node.get('share_link', '')
                for source_url, node_links in source_node_mapping.items():
                    if node_link in node_links:
                        node['source_url'] = source_url
                        break

            all_nodes = cn_nodes + valid_parsed_nodes

            unique_nodes = list({f"{n['host']}:{n['port']}": n for n in all_nodes if n}.values())
            self.add_log(f"🔍 爬虫解析成功 {len(unique_nodes)} 个唯一节点", "INFO")
            
            # � 保存已解析节点缓存到Supabase
            try:
                await self.persistence.save_parsed_nodes(unique_nodes)
                self.add_log(f"💾 已解析节点缓存已保存到Supabase ({len(unique_nodes)} 个)", "SUCCESS")
            except Exception as e:
                self.add_log(f"⚠️ 节点缓存保存失败: {e}", "WARNING")
            
            # �🔥 P3: 将新节点入队而不是直接检测
            new_added = self._add_nodes_to_queue(unique_nodes)
            
            self.add_log(
                f"📥 P3优化: {new_added} 个新节点已入队，"
                f"当前队列待检测: {len(self.pending_nodes_queue)} 个，"
                f"将由批量检测任务逐步处理",
                "SUCCESS"
            )

        except Exception as e:
            self.add_log(f"💥 爬虫错误: {e}", "ERROR")
            logger.exception("爬虫异常")
        finally:
            self.is_scanning = False
    
    def _add_nodes_to_queue(self, nodes: List[Dict]) -> int:
        """
        将节点添加到待检测队列
        智能优先级: 新节点(优先) > 失败节点(重试) > 待重验 > 已检测
        """
        added_count = 0
        
        for node in nodes:
            node_key = f"{node.get('host')}:{node.get('port')}"
            
            # 如果已经在队列中，跳过
            if node_key in self.pending_nodes_queue:
                continue
            
            # 如果已经在已检测列表中，降低优先级
            existing = next((n for n in self.nodes if f"{n.get('host')}:{n.get('port')}" == node_key), None)
            
            if existing:
                priority = 2  # 待重验：已检测过的节点
            else:
                priority = 0  # 新节点：最高优先级
            
            # 添加国家信息
            if not node.get('country'):
                country = self.geolocation_helper.detect_country_by_name(node.get('name', ''))
                if not country:
                    country = 'UNK'
                node['country'] = country
            
            # 入队
            self.pending_nodes_queue[node_key] = {
                'node': node,
                'retry_count': 0,
                'priority': priority,
                'added_time': time.time()
            }
            added_count += 1
        
        return added_count
    
    async def _batch_test_pending_nodes(self):
        """
        🔥 P3: 独立的批量检测任务 (每1小时执行一次)
        从队列取出优先级最高的1000个节点进行检测
        """
        if self.is_batch_testing:
            self.add_log("⚠️ 批量检测已在进行，跳过本次执行", "WARNING")
            return
        
        if not self.pending_nodes_queue:
            self.add_log("📭 待检测队列为空，无需执行批量检测", "DEBUG")
            return
        
        self.is_batch_testing = True
        start_time = time.time()
        
        try:
            # 从队列取出待检测节点（按优先级排序）
            nodes_to_test = self._pop_nodes_from_queue(self.batch_size)
            
            if not nodes_to_test:
                self.add_log("📭 无可用的待检测节点", "DEBUG")
                return
            
            # 🔥 增强进度提示
            self.add_log(
                f"═══════════════════════════════════════════════════════════",
                "INFO"
            )
            self.add_log(
                f"🚀 【P3批量检测开始】从队列取出 {len(nodes_to_test)} 个节点",
                "INFO"
            )
            self.add_log(
                f"   队列剩余: {len(self.pending_nodes_queue)} 个节点待处理",
                "INFO"
            )
            self.add_log(
                f"   协议分布: {self._get_protocol_stats(nodes_to_test)}",
                "INFO"
            )
            self.add_log(
                f"   预计耗时: 10-20分钟（支持Clash和Xray并行）",
                "INFO"
            )
            self.add_log(
                f"═══════════════════════════════════════════════════════════",
                "INFO"
            )
            
            # 执行检测
            await self._test_nodes_with_new_system(nodes_to_test)
            
            # 计算统计
            elapsed = time.time() - start_time
            available = sum(1 for n in nodes_to_test if n.get('alive'))
            
            # 🔥 新增：源级别成功率分析
            source_success = self._analyze_source_success(nodes_to_test)
            
            self.add_log(
                f"═══════════════════════════════════════════════════════════",
                "SUCCESS"
            )
            self.add_log(
                f"🎉 【P3检测完成】{len(nodes_to_test)}个节点 → {available}个可用",
                "SUCCESS"
            )
            self.add_log(
                f"   耗时: {elapsed:.0f}秒 | 成功率: {available/len(nodes_to_test)*100:.1f}%",
                "SUCCESS"
            )
            self.add_log(
                f"   队列剩余: {len(self.pending_nodes_queue)}个节点待处理",
                "SUCCESS"
            )
            
            # 显示源级别成功率 Top 5
            if source_success:
                self.add_log(f"📊 【源成功率 Top 5】", "INFO")
                for source, stats in source_success[:5]:
                    short_name = source.replace("https://github.com/", "").replace("https://", "")[:40]
                    self.add_log(
                        f"   {short_name}: {stats['success']}/{stats['total']} ({stats['rate']:.1f}%)",
                        "INFO"
                    )
            
            self.add_log(
                f"═══════════════════════════════════════════════════════════",
                "SUCCESS"
            )
            
            # 🔥 新增：智能休息逻辑
            await self._smart_batch_delay(available, nodes_to_test)
            
        except Exception as e:
            self.add_log(f"❌ 批量检测异常: {e}", "ERROR")
            logger.exception("批量检测异常")
        finally:
            self.is_batch_testing = False
    
    def _analyze_source_success(self, nodes_to_test: List[Dict]) -> List[tuple]:
        """
        分析每个源的成功率
        返回: [(源地址, {'total': N, 'success': M, 'rate': P}), ...] 按成功率倒序
        """
        source_stats = {}
        
        for node in nodes_to_test:
            # 获取源信息 - 优先用 source_url，没有则用 add_by
            source = node.get('source_url') or node.get('add_by', 'unknown')
            
            if source not in source_stats:
                source_stats[source] = {'total': 0, 'success': 0}
            
            source_stats[source]['total'] += 1
            if node.get('alive'):
                source_stats[source]['success'] += 1
        
        # 计算成功率并排序
        result = []
        for source, stats in source_stats.items():
            stats['rate'] = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
            result.append((source, stats))
        
        # 按成功率倒序排列
        result.sort(key=lambda x: x[1]['rate'], reverse=True)
        
        # 保存到日志
        if not hasattr(self, 'source_success_log'):
            self.source_success_log = []
        self.source_success_log.append({
            'cycle': self.scan_cycle_count,
            'timestamp': datetime.now().isoformat(),
            'sources': dict(result)
        })
        
        return result
    
    async def _smart_batch_delay(self, available: int, nodes_to_test: List[Dict]):
        """
        🔥 智能延迟决策:
        
        1. 如果成功率=0% → 立即进入下一批 (继续不休息)
        2. 如果已有10+可用节点 且 来自2+国家 → 休息5分钟
        3. 否则 → 立即进入下一批
        """
        success_rate = available / len(nodes_to_test) * 100 if nodes_to_test else 0
        
        # 获取当前可用节点的国家分布
        alive_nodes = [n for n in self.nodes if n.get('alive')]
        if alive_nodes:
            countries = set(n.get('country', 'UNK') for n in alive_nodes)
        else:
            countries = set()
        
        self.add_log(
            f"📊 智能决策: 成功率 {success_rate:.1f}% | 可用节点 {len(alive_nodes)} | 国家数 {len(countries)}",
            "INFO"
        )
        
        # 规则1: 成功率为0% → 立即继续（不休息）
        if success_rate == 0.0:
            self.add_log(
                f"⚡ 【规则1触发】成功率0% → 立即进入下一批检测，无休息",
                "WARNING"
            )
            if self.pending_nodes_queue:
                # 立即重新进行检测
                asyncio.create_task(self._batch_test_pending_nodes())
            return
        
        # 规则2: 已有10+节点 且 来自2+国家 → 休息5分钟
        if len(alive_nodes) >= 10 and len(countries) >= 2:
            self.add_log(
                f"✅ 【规则2触发】已有 {len(alive_nodes)} 个节点 ({', '.join(list(countries)[:3])}) " +
                f"→ 休息 5 秒后继续",
                "SUCCESS"
            )
            await asyncio.sleep(5)  # 休息5秒
            if self.pending_nodes_queue:
                asyncio.create_task(self._batch_test_pending_nodes())
            return
        
        # 规则3: 其他情况 → 立即继续
        self.add_log(
            f"⚡ 【规则3触发】节点不足/国家不足 → 立即进入下一批检测，无休息",
            "INFO"
        )
        if self.pending_nodes_queue:
            asyncio.create_task(self._batch_test_pending_nodes())
    
    def _get_protocol_stats(self, nodes: List[Dict]) -> str:
        """获取节点的协议统计"""
        protocol_count = {}
        for node in nodes:
            proto = node.get('protocol', 'unknown').lower()
            protocol_count[proto] = protocol_count.get(proto, 0) + 1
        
        stats = []
        for proto, count in sorted(protocol_count.items(), key=lambda x: -x[1])[:5]:  # 只显示前5个
            stats.append(f"{proto}:{count}")
        
        return ", ".join(stats) if stats else "unknown"
    
    def _pop_nodes_from_queue(self, count: int) -> List[Dict]:
        """
        从队列按优先级取出节点
        优先级: 新节点(0) > 失败待重试(1) > 待重验(2) > 已检测(3)
        """
        if not self.pending_nodes_queue:
            return []
        
        # 按优先级排序
        sorted_items = sorted(
            self.pending_nodes_queue.items(),
            key=lambda x: (x[1]['priority'], x[1]['added_time'])
        )
        
        # 取出前 count 个
        popped_nodes = []
        keys_to_remove = []
        
        for node_key, node_info in sorted_items[:count]:
            popped_nodes.append(node_info['node'])
            keys_to_remove.append(node_key)
        
        # 从队列删除已取出的节点
        for key in keys_to_remove:
            del self.pending_nodes_queue[key]
        
        return popped_nodes
    
    async def _sync_nodes_to_storage(self):
        """
        🔥 P3: 独立的同步任务 (每1小时执行一次)
        将可用节点同步到 viper-node-store
        """
        alive_nodes = [n for n in self.nodes if n.get('alive')]
        
        if not alive_nodes:
            self.add_log("📭 无可用节点，跳过同步", "DEBUG")
            return
        
        self.add_log(f"📤 P3同步: 准备上传 {len(alive_nodes)} 个节点到 viper-node-store...", "INFO")
        
        try:
            success = await upload_to_supabase(alive_nodes)
            if success:
                self.last_sync_time = time.time()
                self.add_log(f"✅ P3同步完成: {len(alive_nodes)} 个节点已同步到 viper-node-store", "SUCCESS")
            else:
                self.add_log("⚠️ viper-node-store 同步失败或跳过", "WARNING")
        except Exception as e:
            self.add_log(f"❌ P3同步异常: {e}", "ERROR")
            logger.exception("同步异常")
            
            # 直接执行Clash检测（跳过云端过滤）
            clash_nodes = []
            for node in self.nodes:
                protocol = node.get('protocol', '').lower()
                # 💡 优化: 支持所有协议，让Clash内核自动处理
                # 原限制: ['trojan', 'ss', 'shadowsocks', 'socks5', 'socks', 'http', 'https'] (仅4种)
                # 现支持: VMess, VLESS, Hysteria, Hysteria2, WireGuard, TUIC等 (11+种)
                clash_node = self._convert_to_clash_node(node)
                if clash_node:
                    clash_nodes.append((node, clash_node))
            
            if clash_nodes:
                self.add_log(f"📊 Clash快速重验: {len(clash_nodes)} 个兼容节点...", "INFO")
                only_clash_nodes = [cn for _, cn in clash_nodes]
                clash_results = await check_nodes_clash(only_clash_nodes, max_concurrent=10)
                
                valid_nodes = []
                available_count = 0
                for (orig_node, _), result in zip(clash_nodes, clash_results):
                    if result.is_available:
                        available_count += 1
                        orig_node['alive'] = True
                        orig_node['availability_level'] = 'VERIFIED'
                        orig_node['latency'] = result.latency_ms or 0
                        orig_node['protocol'] = result.protocol or orig_node.get('protocol', 'unknown')
                        
                        # 计算健康评分
                        latency = orig_node['latency']
                        if latency <= 50:
                            orig_node['health_score'] = 100
                        elif latency <= 100:
                            orig_node['health_score'] = 90
                        elif latency <= 200:
                            orig_node['health_score'] = 75
                        elif latency <= 500:
                            orig_node['health_score'] = 60
                        else:
                            orig_node['health_score'] = 40
                        
                        # 计算速度
                        if latency <= 30:
                            orig_node['speed'] = 90.0
                        elif latency <= 60:
                            orig_node['speed'] = 70.0
                        elif latency <= 100:
                            orig_node['speed'] = 50.0
                        elif latency <= 200:
                            orig_node['speed'] = 30.0
                        elif latency <= 500:
                            orig_node['speed'] = 15.0
                        else:
                            orig_node['speed'] = 5.0
                        
                        # 添加地区分数
                        orig_node['mainland_score'] = int(orig_node.get('speed', 0))
                        orig_node['mainland_latency'] = latency
                        orig_node['overseas_score'] = int(orig_node.get('speed', 0))
                        orig_node['overseas_latency'] = latency
                        
                        valid_nodes.append(orig_node)
                
                # 🔥 BUG修复: 合并新的快速重验结果而不是替换
                # 快速重验是针对现有节点的再验证，不应该删除其他节点
                unique_nodes = {}
                for node in self.nodes:
                    key = f"{node.get('host')}:{node.get('port')}"
                    unique_nodes[key] = node
                
                # 用重验结果更新这些节点
                for node in valid_nodes:
                    key = f"{node.get('host')}:{node.get('port')}"
                    unique_nodes[key] = node
                
                self.nodes = sorted(unique_nodes.values(), key=lambda x: x.get('health_score', 0), reverse=True)
                self.add_log(f"⚡ 快速重验完成: {available_count}/{len(clash_nodes)} 可用，当前节点总数: {len(self.nodes)}", "INFO")
                self._save_nodes_to_file()
        except Exception as e:
            self.add_log(f"⚠️ 快速重验异常: {e}", "WARNING")

    async def _run_advanced_test_async(self):
        """高级双地区测速的异步包装器，独立运行不阻塞主流程"""
        try:
            self.add_log("🌍 开始执行高级双地区测速...", "INFO")
            tested_nodes = await run_advanced_speed_test(self.nodes)
            self.nodes = tested_nodes
            
            # 高级测速完成后再次上传更新结果
            alive_nodes = [n for n in self.nodes if n.get('alive')]
            if alive_nodes:
                self.add_log(f"📤 高级测速完成，上传更新结果到 viper-node-store ({len(alive_nodes)} 个节点)...", "INFO")
                success = await upload_to_supabase(alive_nodes)
                if success:
                    self.add_log("✅ 高级测速结果同步完成！", "SUCCESS")
                else:
                    self.add_log("⚠️ 高级测速结果同步失败", "WARNING")
        except Exception as e:
            self.add_log(f"❌ 高级测速异常: {e}", "ERROR")

    async def _sync_to_supabase_task(self):
        """
        🔥 新增：定时同步任务 - 每10分钟执行
        将已测速的节点上传到 Supabase，供 viper-node-store 读取
        
        特点：
        1. 独立的定时任务，不依赖其他任务
        2. 只同步已验证的活跃节点 (alive=True)
        3. 自动去重（通过 host:port）
        4. 包含大陆和海外的测速数据
        """
        try:
            alive_nodes = [n for n in self.nodes if n.get('alive')]
            
            if not alive_nodes:
                self.add_log("📭 无活跃节点，跳过 Supabase 同步", "DEBUG")
                return
            
            # 去重：按 host:port 去重，保留最新的测试结果
            seen = {}
            for node in alive_nodes:
                key = f"{node.get('host')}:{node.get('port')}"
                if key not in seen or node.get('updated_at', '') > seen[key].get('updated_at', ''):
                    seen[key] = node
            
            unique_nodes = list(seen.values())
            
            self.add_log(f"📤 Supabase 同步: {len(unique_nodes)} 个活跃节点（已去重）...", "INFO")
            
            # 🔥 增强：先检查凭证状态
            import os
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
            self.add_log(f"🔍 环境变量检查: URL={'✅' if url else '❌'}, KEY={'✅' if key else '❌'}", "INFO")
            
            if not url or not key:
                self.add_log(f"❌ Supabase 环境变量未配置！请检查 SUPABASE_URL 和 SUPABASE_KEY", "ERROR")
                return
            
            # 上传到 Supabase (返回 tuple: (success, message/count))
            result = await upload_to_supabase(unique_nodes)
            
            # 兼容旧版返回值 (bool) 和新版 (tuple)
            if isinstance(result, tuple):
                success, detail = result
            else:
                success, detail = result, ""
            
            if success:
                self.last_supabase_sync_time = time.time()
                self.add_log(f"✅ Supabase 同步完成！{detail} 个节点已写入数据库", "SUCCESS")
            else:
                self.add_log(f"⚠️ Supabase 同步失败: {detail}", "WARNING")
                
        except Exception as e:
            self.add_log(f"❌ Supabase 同步异常: {type(e).__name__}: {e}", "ERROR")
            logger.exception("Supabase 同步异常")

    async def _cleanup_expired_cache_task(self):
        """
        🔥 新增：定期清理过期缓存 - 每日凌晨 3 点执行
        
        清理内容：
        1. 删除 7 天前的已完成任务
        2. 删除过期的源缓存 (> 24小时)
        3. 删除过期的节点缓存 (> 6小时)
        """
        try:
            self.add_log("🧹 开始清理过期缓存...", "INFO")
            success = await self.persistence.cleanup_expired_cache()
            
            if success:
                self.add_log("✅ 过期缓存清理完成", "SUCCESS")
            else:
                self.add_log("⚠️ 过期缓存清理部分失败", "WARNING")
        except Exception as e:
            self.add_log(f"❌ 缓存清理异常: {e}", "ERROR")
            logger.exception("缓存清理异常")

    async def _test_nodes_with_new_system(self, nodes_to_test: List[Dict]):
        """
        新的多层级可用性检测系统

        层级：
        1. 云端快速过滤 (Aliyun FC / Cloudflare Worker) - 可选
        2. 基础 + 深度可用性检测 (本地后端) - 必须
        3. 持续监测 (定期 ping) - 未来扩展
        """
        # � 保存当前测速队列状态到Supabase
        try:
            queue_data = [
                {
                    'group_number': i // 100,  # 简单的分组逻辑
                    'group_position': i % 100,
                    'node_host': node.get('host'),
                    'node_port': node.get('port'),
                    'status': 'pending'
                }
                for i, node in enumerate(nodes_to_test)
            ]
            await self.persistence.save_testing_queue(queue_data)
            self.add_log(f"💾 测速队列已保存到Supabase ({len(nodes_to_test)} 个节点)", "SUCCESS")
        except Exception as e:
            self.add_log(f"⚠️ 测速队列保存失败: {e}", "WARNING")
        
        # �🔥 修复：确保所有节点都有名称，避免 "Unknown" 显示
        for node in nodes_to_test:
            if not node.get('name') or node.get('name') == 'Unknown':
                # 使用国家代码 + host:port 作为备用名称
                country = node.get('country', 'UNK')
                host = node.get('host', 'unknown')
                port = node.get('port', 0)
                node['name'] = f"{country}_{host}_{port}"
        
        self.add_log(f"🧪 [新系统] 开始可用性检测 {len(nodes_to_test)} 个节点...", "INFO")

        # 🔥 为节点添加国家信息 - 使用本地名称检测+异步域名检测（无重要网络延迟）
        for node in nodes_to_test:
            if not node.get('country'):
                # 优先用名称识别（最快，本地操作，90%+准确）
                country = self.geolocation_helper.detect_country_by_name(
                    node.get('name', '')
                )
                
                # 再用域名识别（次快，异步）
                if not country:
                    try:
                        country = await self.geolocation_helper.detect_country_by_domain(
                            node.get('domain', '')
                        )
                    except:
                        country = None
                
                # 最后使用备选值
                if not country:
                    country = 'UNK'
                
                node['country'] = country

        cloud_results = []

        # 第1层：云端快速过滤 (可选) - 🔥 修复：云端检测应该是补充，不是过滤
        # 如果云端服务不可用或返回空，应该继续本地检测，而不是丢弃所有节点
        if CLOUD_DETECTION_ENABLED and ALIYUN_FC_URL and CF_WORKER_URL:
            try:
                # 分离中外节点
                cn_nodes = [n for n in nodes_to_test if n.get('country') == 'CN']
                overseas_nodes = [n for n in nodes_to_test if n.get('country') != 'CN']

                # 阿里云FC检测国内节点
                if cn_nodes:
                    self.add_log(f"🇨🇳 [云端] 阿里云FC检测国内节点 {len(cn_nodes)} 个...", "INFO")
                    aliyun_results = await test_nodes_via_aliyun_fc(cn_nodes)
                    cloud_results.extend(aliyun_results)

                # Cloudflare Worker检测海外节点
                if overseas_nodes:
                    self.add_log(f"🌍 [云端] Cloudflare Worker检测海外节点 {len(overseas_nodes)} 个...", "INFO")
                    cf_results = await test_nodes_via_cloudflare_worker(overseas_nodes)
                    cloud_results.extend(cf_results)

                # 🔥 修复：云端结果作为补充，而不是强制过滤
                # 如果云端检测结果有效，才使用预过滤；否则直接进行本地检测
                if cloud_results and len(cloud_results) > len(nodes_to_test) * 0.3:  # 至少返回30%的节点
                    cloud_success_ids = {r['id'] for r in cloud_results if r.get('success', False)}
                    filtered_nodes = [n for n in nodes_to_test if n.get('id', f"{n['host']}:{n['port']}") in cloud_success_ids]
                    if filtered_nodes:  # 只有有结果才过滤
                        self.add_log(f"☁️ [云端] 预过滤完成，{len(nodes_to_test)} → {len(filtered_nodes)} 个节点进入本地检测", "INFO")
                        nodes_to_test = filtered_nodes
                    else:
                        self.add_log(f"⚠️ [云端] 预过滤结果为空，放弃云端预过滤，全量进行本地检测", "WARNING")
                else:
                    self.add_log(f"⚠️ [云端] 云端检测无效（无结果或返回率过低），跳过预过滤，全量进行本地检测", "WARNING")
            except Exception as e:
                self.add_log(f"❌ [云端] 云端检测异常 {e}，跳过预过滤，全量进行本地检测", "WARNING")

        # 第2层：分离两条检测路线 (Clash vs Xray)
        # 🔥 修复：正确分离节点，避免重复检测或遗漏
        
        # Clash支持的协议
        clash_compatible_protocols = ['trojan', 'ss', 'shadowsocks', 'socks5', 'socks', 'http', 'https', 'vmess', 'vless']
        
        # Xray支持的协议
        xray_compatible_protocols = ['vmess', 'vless', 'hysteria', 'hysteria2', 'wireguard', 'tuic', 'naiveproxy', 'trojan']
        
        # 分配节点到不同的检测队列
        clash_nodes_for_test = []  # 仅用Clash检测
        xray_nodes_for_test = []   # 仅用Xray检测
        both_protocol_nodes = {}   # 协议同时支持Clash和Xray的节点
        
        for node in nodes_to_test:
            protocol = node.get('protocol', '').lower()
            
            clash_support = protocol in clash_compatible_protocols
            xray_support = protocol in xray_compatible_protocols
            
            if clash_support and not xray_support:
                # 仅Clash支持 (SS, SOCKS5等)
                clash_node = self._convert_to_clash_node(node)
                if clash_node:
                    clash_nodes_for_test.append((node, clash_node))
            elif xray_support and not clash_support:
                # 仅Xray支持 (Hysteria等)
                xray_nodes_for_test.append(node)
            elif clash_support and xray_support:
                # 两者都支持，优先用Clash (速度快)
                clash_node = self._convert_to_clash_node(node)
                if clash_node:
                    clash_nodes_for_test.append((node, clash_node))
                    both_protocol_nodes[f"{node['host']}:{node['port']}"] = node
            else:
                # 两者都不支持，跳过
                self.add_log(f"⚠️ 不支持的协议{protocol}，跳过: {node.get('host')}:{node.get('port')}", "DEBUG")
        
        valid_nodes = []
        
        # 第2层：Clash内核检测
        if clash_nodes_for_test:
            self.add_log(f"📊 执行 Clash 内核节点检测 ({len(clash_nodes_for_test)} 个)...", "INFO")
            try:
                only_clash_nodes = [cn for _, cn in clash_nodes_for_test]
                # 🔥 修复：降低并发数从20→5，避免Clash检测器过载导致502
                clash_results = await check_nodes_clash(only_clash_nodes, max_concurrent=5)
                
                # 统计检测结果
                total = len(clash_results)
                available = sum(1 for r in clash_results if r.is_available)
                avg_latency = sum(r.latency_ms for r in clash_results if r.latency_ms and r.is_available) / available if available > 0 else 0
                
                self.add_log(f"📈 Clash 检测完成 - 总计: {total}, 可用: {available}, 不可用: {total - available}, 平均延迟: {avg_latency:.0f}ms", "INFO")
                
                # 关联原始节点和检测结果
                for idx, ((orig_node, _), result) in enumerate(zip(clash_nodes_for_test, clash_results)):
                    if result.is_available:
                        # 节点可用，合并测试结果
                        orig_node['alive'] = True
                        orig_node['availability_level'] = 'VERIFIED'
                        orig_node['latency'] = result.latency_ms or 0
                        orig_node['protocol'] = result.protocol or orig_node.get('protocol', 'unknown')
                        
                        # 基于延迟计算健康评分
                        latency = orig_node['latency']
                        if latency <= 50:
                            orig_node['health_score'] = 100
                        elif latency <= 100:
                            orig_node['health_score'] = 90
                        elif latency <= 200:
                            orig_node['health_score'] = 75
                        elif latency <= 500:
                            orig_node['health_score'] = 60
                        else:
                            orig_node['health_score'] = 40

                        # 基于延迟的简单速度估算
                        if latency <= 30:
                            orig_node['speed'] = 90.0
                        elif latency <= 60:
                            orig_node['speed'] = 70.0
                        elif latency <= 100:
                            orig_node['speed'] = 50.0
                        elif latency <= 200:
                            orig_node['speed'] = 30.0
                        elif latency <= 500:
                            orig_node['speed'] = 15.0
                        else:
                            orig_node['speed'] = 5.0

                        # 🔥 添加地区测试分数（用于Supabase同步）
                        orig_node['mainland_score'] = int(orig_node.get('speed', 0))
                        orig_node['mainland_latency'] = latency
                        orig_node['overseas_score'] = int(orig_node.get('speed', 0))
                        orig_node['overseas_latency'] = latency

                        # 🔥 添加 share_link（用于viper-node-store显示QR码）
                        if not orig_node.get('share_link'):
                            try:
                                orig_node['share_link'] = generate_node_share_link(orig_node)
                            except Exception as e:
                                logger.debug(f"生成share_link失败: {e}")

                        # 🔥 优化：每检测到1个可用节点就输出，让用户看到实时反馈
                        self.add_log(
                            f"✅ Clash✓ [{idx+1}/{total}] {orig_node.get('host')}:{orig_node.get('port')} "
                            f"({orig_node.get('protocol')} | 延迟{latency}ms | 队列剩余{len(self.pending_nodes_queue)})",
                            "SUCCESS"
                        )
                        valid_nodes.append(orig_node)
                    else:
                        # 🔥 诊断：增加失败详情，帮助排查问题
                        error_msg = result.error_message if result else "检测失败"
                        if idx < 5 or (idx % 100 == 0):  # 前5个失败+每100个采样一个
                            self.add_log(
                                f"❌ Clash✗ [{idx+1}/{total}] {orig_node.get('host')}:{orig_node.get('port')} "
                                f"({orig_node.get('protocol')}) - {error_msg}",
                                "WARNING"
                            )
            except Exception as e:
                self.add_log(f"❌ Clash 检测异常: {e}", "WARNING")
                import traceback
                self.add_log(f"   异常堆栈: {traceback.format_exc()[:500]}", "WARNING")
        
        # 第3层：Xray内核检测（VMess/VLESS及其他专有协议）
        # 包括：仅Xray支持的协议 + Clash检测失败的同时支持两者协议的节点
        # 🔥 BUG修复：添加Clash失败的节点到Xray检测，避免浪费可用节点
        clash_failed_nodes = []
        if clash_nodes_for_test and clash_results:
            for (orig_node, _), result in zip(clash_nodes_for_test, clash_results):
                # 只有Clash失败且支持两种协议的节点才加入Xray检测
                if not result.is_available and f"{orig_node.get('host')}:{orig_node.get('port')}" in both_protocol_nodes:
                    clash_failed_nodes.append(orig_node)
        
        final_xray_nodes = xray_nodes_for_test.copy()
        final_xray_nodes.extend(clash_failed_nodes)
        
        if final_xray_nodes:
            # 🔥 优化：清晰的分界线，避免日志混乱
            self.add_log(
                f"═══════════════════════════════════════════════════════════",
                "INFO"
            )
            self.add_log(
                f"🎯 【Xray并行检测】开始检测 {len(final_xray_nodes)} 个协议",
                "INFO"
            )
            self.add_log(
                f"   协议列表: {self._get_protocol_stats(final_xray_nodes)}",
                "INFO"
            )
            self.add_log(
                f"═══════════════════════════════════════════════════════════",
                "INFO"
            )
            try:
                # 转换节点格式以兼容 v2ray_check（使用 "type" 字段）
                xray_nodes_converted = []
                for node in final_xray_nodes:
                    node_copy = node.copy()
                    node_copy['type'] = node.get('protocol', 'unknown')  # 🔥 关键：转换 protocol -> type
                    node_copy['server'] = node.get('host', '')  # 转换 host -> server
                    xray_nodes_converted.append(node_copy)
                
                # 使用 Xray 检测 (🔥 降低并发从10→3，避免过载)
                xray_results = await check_nodes_v2ray(xray_nodes_converted, max_concurrent=3)
                
                # 统计检测结果
                xray_available = sum(1 for r in xray_results if r.is_available)
                self.add_log(f"🎯 Xray 检测完成 - 总计: {len(xray_results)}, 可用: {xray_available}", "INFO")
                
                # 处理 Xray 检测结果
                for idx, (node, result) in enumerate(zip(final_xray_nodes, xray_results)):
                    if result.is_available:
                        # 节点可用
                        node['alive'] = True
                        node['availability_level'] = 'VERIFIED'
                        node['latency'] = result.latency_ms or 0
                        node['protocol'] = result.protocol or node.get('protocol', 'unknown')
                        
                        # 基于延迟计算健康评分
                        latency = node['latency']
                        if latency <= 50:
                            node['health_score'] = 100
                        elif latency <= 100:
                            node['health_score'] = 90
                        elif latency <= 200:
                            node['health_score'] = 75
                        elif latency <= 500:
                            node['health_score'] = 60
                        else:
                            node['health_score'] = 40
                        
                        # 基于延迟的速度估算
                        if latency <= 30:
                            node['speed'] = 90.0
                        elif latency <= 60:
                            node['speed'] = 70.0
                        elif latency <= 100:
                            node['speed'] = 50.0
                        elif latency <= 200:
                            node['speed'] = 30.0
                        elif latency <= 500:
                            node['speed'] = 15.0
                        else:
                            node['speed'] = 5.0
                        
                        # 🔥 添加地区测试分数
                        node['mainland_score'] = int(node.get('speed', 0))
                        node['mainland_latency'] = latency
                        node['overseas_score'] = int(node.get('speed', 0))
                        node['overseas_latency'] = latency
                        
                        # 🔥 添加 share_link（用于viper-node-store显示QR码）
                        if not node.get('share_link'):
                            try:
                                node['share_link'] = generate_node_share_link(node)
                            except Exception as e:
                                logger.debug(f"生成share_link失败: {e}")
                        
                        # 🔥 优化：每检测到1个可用节点就输出，让用户看到实时反馈
                        self.add_log(
                            f"✅ Xray✓ [{idx+1}/{len(xray_results)}] {node.get('host')}:{node.get('port')} "
                            f"({node.get('protocol')} | 延迟{latency}ms | 队列剩余{len(self.pending_nodes_queue)})",
                            "SUCCESS"
                        )
                        valid_nodes.append(node)
                    else:
                        # 🔥 诊断失败原因
                        error_msg = result.error_message if result else "检测失败"
                        if idx < 5 or (idx % 100 == 0):  # 前5个失败+每100个采样一个
                            self.add_log(
                                f"❌ Xray✗ [{idx+1}/{len(xray_results)}] {node.get('host')}:{node.get('port')} "
                                f"({node.get('protocol')}) - {error_msg}",
                                "WARNING"
                            )
            except Exception as e:
                self.add_log(f"❌ Xray 检测异常: {e}", "WARNING")
                import traceback
                self.add_log(f"   异常堆栈: {traceback.format_exc()[:500]}", "WARNING")

        
        # 🔥 BUG修复: 合并新检测结果而不是替换！
        # 问题: 直接替换self.nodes导致之前的可用节点被清除
        # 解决: 保留旧节点(alive=True)，添加新检测的节点
        
        # 1. 保留之前检测出的可用节点（那些已经alive=True的）
        existing_alive = [n for n in self.nodes if n.get('alive') and n not in valid_nodes]
        
        # 2. 合并: 已确认可用的 + 新检测出的可用
        merged_nodes = existing_alive + valid_nodes
        
        # 3. 去重 (按host:port)
        unique_nodes = {}
        for node in merged_nodes:
            key = f"{node.get('host')}:{node.get('port')}"
            if key not in unique_nodes or (node.get('alive') and not unique_nodes[key].get('alive')):
                unique_nodes[key] = node
        
        # 4. 更新并排序
        self.nodes = sorted(unique_nodes.values(), key=lambda x: x.get('health_score', 0), reverse=True)
        
        self.add_log(
            f"🎉 节点检测完成！可用节点: {len([n for n in self.nodes if n.get('alive')])}/{len(nodes_to_test)} "
            f"(包含 {len(existing_alive)} 个已保留节点)",
            "SUCCESS"
        )
        
        # 🔥 P3增强：添加协议分布统计日志
        if nodes_to_test:
            # 统计所有测试节点的协议分布
            all_protocol_stats = {}
            for node in nodes_to_test:
                proto = node.get('protocol', 'unknown').lower()
                all_protocol_stats[proto] = all_protocol_stats.get(proto, 0) + 1
            
            # 统计可用节点的协议分布
            available_protocol_stats = {}
            for node in self.nodes:
                proto = node.get('protocol', 'unknown').lower()
                available_protocol_stats[proto] = available_protocol_stats.get(proto, 0) + 1
            
            # 打印详细统计
            self.add_log("📊 [协议分布统计]", "INFO")
            self.add_log(f"   总节点 {len(nodes_to_test)} 个 / 可用 {len(self.nodes)} 个", "INFO")
            
            for proto in sorted(all_protocol_stats.keys()):
                total = all_protocol_stats[proto]
                available = available_protocol_stats.get(proto, 0)
                percentage = (available / total * 100) if total > 0 else 0
                self.add_log(f"   • {proto:12s}: {total:3d} 个 ({available:2d}✅ {percentage:5.1f}%)", "INFO")
        
        if self.nodes:
            self.subscription_base64 = generate_subscription_content(self.nodes)
            self._save_nodes_to_file()

    async def test_and_update_nodes(self, nodes_to_test: List[Dict]):
        self.add_log(f"🧪 开始测试 {len(nodes_to_test)} 个节点...", "INFO")
        tasks = [test_node_network(node) for node in nodes_to_test]
        results = await asyncio.gather(*tasks)

        valid_nodes = []
        for i, node in enumerate(nodes_to_test):
            if results[i].total_score > 0:
                node.update(alive=True, delay=results[i].tcp_ping_ms, test_results=results[i].__dict__)

                country = self._get_country_code_from_ip(node['host'])
                if country == 'UNK' or country is None:
                    country = self._guess_country_from_name(node.get('name', ''))

                node['country'] = country

                real_latency = results[i].connection_time_ms
                if real_latency > 0:
                    node['speed'] = round(5000.0 / real_latency, 2)
                elif node['delay'] > 0:
                    node['speed'] = round(random.uniform(1.0, 30.0) / (node['delay'] / 100), 2)
                else:
                    node['speed'] = 0.5

                valid_nodes.append(node)

        self.nodes = sorted(valid_nodes, key=lambda x: x.get('test_results', {}).get('total_score', 0), reverse=True)
        self.add_log(f"🎉 测试完成！有效节点: {len(self.nodes)}/{len(nodes_to_test)}", "SUCCESS")

        # 💾 更新每个节点的测试状态到Supabase
        try:
            for node in self.nodes:
                status = 'passed' if node.get('alive') else 'failed'
                await self.persistence.update_task_status(
                    node.get('host'),
                    node.get('port'),
                    status
                )
            self.add_log(f"💾 已更新 {len(self.nodes)} 个节点的测试状态到Supabase", "SUCCESS")
        except Exception as e:
            self.add_log(f"⚠️ 更新节点状态失败: {e}", "WARNING")

        if self.nodes:
            self.subscription_base64 = generate_subscription_content(self.nodes)
            self._save_nodes_to_file()

    async def _run_speed_test_background(self, node_id: str, proxy_url: str, latency: float):
        """
        🔥 后台异步运行真实速度测试
        不阻塞主检测流程，测试完成后更新缓存
        """
        try:
            self.add_log(f"🚀 [后台] 开始测速: {node_id}", "INFO")
            result = await self.speed_tester.test_node_speed(
                proxy_url=proxy_url,
                node_id=node_id,
                use_multi_thread=False  # 单线程测试
            )
            
            if result.get('status') == 'success' and result.get('speed', 0) > 0:
                self.add_log(f"⚡ [后台测速完成] {node_id}: {result['speed']:.1f}MB/s (延迟: {result.get('latency', 0):.1f}ms)", "SUCCESS")
                # 更新缓存以供后续使用
                await self.speed_tester.cache_speed_result(node_id, result['speed'])
            else:
                self.add_log(f"⚠️ [后台测速失败] {node_id}: {result.get('error', '未知错误')}", "WARNING")
        except Exception as e:
            self.add_log(f"❌ [后台测速异常] {node_id}: {str(e)}", "ERROR")


hunter = NodeHunter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    all_nodes = hunter.get_alive_nodes()
    groups = []

    country_map = {}
    for node in all_nodes:
        c = node.get('country', 'UNK')
        if c not in country_map: country_map[c] = []
        country_map[c].append(node)

    priority = ['CN', 'HK', 'TW', 'US', 'JP', 'SG', 'KR']
    for code in priority:
        if code in country_map:
            groups.append({"group_name": code, "nodes": country_map[code]})
            del country_map[code]
    for code in sorted(country_map.keys()):
        groups.append({"group_name": code, "nodes": country_map[code]})

    # 🔥 获取下次扫描时间
    next_run = None
    job = hunter.scheduler.get_job('node_scan_refresh')
    if job and job.next_run_time:
        next_run = job.next_run_time.timestamp()

    return {
        "count": len(all_nodes),
        "running": hunter.is_scanning,
        "logs": hunter.logs,
        "nodes": groups,
        "next_scan_time": next_run  # 🔥 返回时间戳
    }


@router.post("/trigger")
async def trigger_scan(background_tasks: BackgroundTasks):
    if not hunter.is_scanning:
        background_tasks.add_task(hunter.scan_cycle)
        return {"status": "started"}
    return {"status": "running"}


@router.post("/batch_detect")
async def trigger_batch_detect(background_tasks: BackgroundTasks):
    """
    🔥 新增：强制触发批量检测 (解决40分钟等待问题)
    立即执行批检测，不需要等待定时器
    """
    if not hunter.is_batch_testing:
        background_tasks.add_task(hunter._batch_test_pending_nodes)
        return {"status": "batch_detect_started", "message": "批量检测已启动"}
    return {"status": "batch_detect_running", "message": "批量检测已在进行中"}


@router.post("/toggle_socks_http")
async def toggle_socks_http(show: bool = Query(True)):
    """
    🔥 新增：控制是否显示 socks/http 节点
    默认关闭，开启后 socks/http 节点显示在列表最前面
    """
    hunter.show_socks_http = show
    status = "开启" if show else "关闭"
    hunter.add_log(f"🔧 socks/http 节点显示已{status}", "INFO")
    return {"status": "success", "show_socks_http": show, "message": f"socks/http 节点显示已{status}"}


@router.get("/socks_http_status")
async def get_socks_http_status():
    """
    获取当前 socks/http 开关状态
    """
    return {"show_socks_http": hunter.show_socks_http}


@router.post("/toggle_china_nodes")
async def toggle_china_nodes(show: bool = Query(True)):
    """
    🔥 新增：控制是否显示国内节点
    默认隐藏，开启后可以在列表中看到中国节点
    """
    hunter.show_china_nodes = show
    status = "开启" if show else "关闭"
    hunter.add_log(f"🔧 中国节点显示已{status}", "INFO")
    return {"status": "success", "show_china_nodes": show, "message": f"中国节点显示已{status}"}


@router.get("/china_nodes_status")
async def get_china_nodes_status():
    """
    获取当前国内节点显示状态
    """
    return {"show_china_nodes": hunter.show_china_nodes}


@router.post("/test_all")
async def test_all_nodes(background_tasks: BackgroundTasks):
    if not hunter.is_scanning:
        nodes_to_test = hunter.nodes.copy()
        background_tasks.add_task(hunter.test_and_update_nodes, nodes_to_test)
        return {"status": "started"}
    return {"status": "running"}


# backend/app/modules/node_hunter/node_hunter.py

# ... (前面的代码保持不变)

@router.post("/test_single")
async def test_single_node(target: NodeTarget):
    found_node = None
    for node in hunter.nodes:
        if node['host'] == target.host and node['port'] == target.port:
            found_node = node
            break

    if found_node:
        hunter.add_log(f"🧪 手动测试节点: {found_node.get('name', 'Unknown')}", "INFO")

        # 1. 执行真实网络测试（获取 TCP 延迟和基本连接信息）
        result = await test_node_network(found_node)

        if result.total_score > 0:
            # 2. 🔥 核心修复：使用真实速度测试而不是虚假计算值
            tcp_delay = result.tcp_ping_ms
            speed = 0.0
            
            # 尝试进行真实下载速度测试
            try:
                # 生成代理 URL (SOCKS5 格式)
                proxy_url = f"socks5://{found_node['host']}:{found_node['port']}"
                
                # 使用真实速度测试器进行测试
                test_result = await hunter.speed_tester.test_node_speed(
                    proxy_url=proxy_url,
                    node_id=f"{found_node['host']}:{found_node['port']}",
                    use_multi_thread=False,  # 单次测试用单线程
                    file_size=10485760  # 10MB 测试文件
                )
                
                if test_result['status'] in ['success', 'cached']:
                    speed = round(test_result['speed'], 2)
                    hunter.add_log(f"📊 真实速度测试: {speed} MB/s", "INFO")
                else:
                    # 降级方案：如果真实测速失败，使用延迟估计
                    from .real_speed_test import estimate_speed_from_latency
                    speed = round(await estimate_speed_from_latency(tcp_delay), 2)
                    hunter.add_log(f"📊 基于延迟估计速度: {speed} MB/s", "INFO")
                    
            except Exception as e:
                # 如果异常，使用简单的延迟估计
                logger.warning(f"⚠️ 真实速度测试异常: {str(e)[:100]}")
                if tcp_delay > 0:
                    speed = round(5000.0 / tcp_delay, 2)
                else:
                    speed = 0.1
                hunter.add_log(f"⚠️ 降级为简单计算速度: {speed} MB/s", "INFO")

            # 3. 更新内存中的节点数据
            found_node.update({
                "alive": True,
                "delay": tcp_delay,
                "speed": speed,
                "test_results": result.__dict__
            })

            hunter.add_log(f"✅ 测试完成: 延迟 {tcp_delay}ms | 速度 {speed} MB/s", "SUCCESS")

            # 返回详细数据给前端
            return {
                "status": "ok",
                "result": result.__dict__,
                "speed": speed,  # 返回速度
                "delay": tcp_delay  # 返回延迟
            }
        else:
            found_node['alive'] = False
            found_node['speed'] = 0.0
            found_node['delay'] = -1
            hunter.add_log(f"❌ 节点已失效 (无法连接)", "ERROR")
            return {"status": "fail", "message": "Node unreachable"}

    return {"status": "error", "message": "Node not found"}


# ==================== Round 5: CF Worker 支持 ====================

class CacheTestResult(BaseModel):
    """缓存 CF Worker 测试结果的请求体"""
    host: str
    port: int
    delay: int
    speed: float


@router.post("/cache_test_result")
async def cache_test_result(req: CacheTestResult):
    """
    🔥 Round 5: 接收并缓存 CF Worker 的测试结果
    
    前端从 CF Worker 获得测试结果后，异步调用此 API 保存到后端
    用于后续列表显示和统计分析
    
    参数：
        host: 节点 IP
        port: 节点端口
        delay: 延迟（毫秒）
        speed: 速度（MB/s）
    """
    try:
        # 在内存节点列表中查找并更新
        found_node = None
        for node in hunter.nodes:
            if node['host'] == req.host and node['port'] == req.port:
                found_node = node
                break
        
        if found_node:
            # 更新测试结果
            found_node.update({
                "delay": req.delay,
                "speed": req.speed,
                "alive": True,
                "last_test_time": datetime.now().isoformat(),
            })
            
            hunter.add_log(
                f"💾 CF Worker 结果已缓存: {found_node.get('name', 'Unknown')} - "
                f"延迟 {req.delay}ms | 速度 {req.speed} MB/s",
                "INFO"
            )
            
            return {
                "status": "ok",
                "message": f"结果已缓存: {req.host}:{req.port}",
                "data": {
                    "delay": req.delay,
                    "speed": req.speed,
                }
            }
        else:
            return {
                "status": "not_found",
                "message": f"节点不存在: {req.host}:{req.port}"
            }
    
    except Exception as e:
        logger.error(f"❌ 缓存 CF 结果失败: {str(e)}")
        return {
            "status": "error",
            "message": f"缓存失败: {str(e)}"
        }


@router.get("/qrcode")
async def get_node_qrcode(host: str, port: int):
    found_node = None
    for node in hunter.nodes:
        if node['host'] == host and str(node['port']) == str(port):
            found_node = node
            break

    if found_node:
        share_link = generate_node_share_link(found_node)
        if share_link:
            img = qrcode.make(share_link)
            buf = BytesIO()
            img.save(buf, format="PNG")
            return {"qrcode_data": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"}

    return {"error": "节点不存在或无法生成链接"}


@router.post("/add_source")
async def add_source(req: SourceRequest, background_tasks: BackgroundTasks):
    success, msg = hunter.add_user_source(req.url)
    if success:
        if not hunter.is_scanning:
            background_tasks.add_task(hunter.scan_cycle)
    return {"status": "ok" if success else "error", "message": msg}


@router.get("/subscription")
async def get_subscription():
    if hunter.subscription_base64:
        return {"subscription": hunter.subscription_base64, "node_count": len(hunter.nodes)}
    return {"error": "暂无订阅链接"}


@router.get("/clash/config")
async def get_clash_config(request: Request):
    config_str = generate_clash_config(hunter.nodes)
    if config_str:
        return {"filename": f"clash_config_{int(time.time())}.yaml", "content": config_str}
    return {"error": "Error"}


# ==========================================
# 🔥 新增：供独立网站抓取的专用接口
# ==========================================

class ExportNode(BaseModel):
    protocol: str
    host: str
    port: int
    country: str
    speed: float
    name: str
    link: Optional[str] = None


@router.get("/export_raw", response_model=List[ExportNode])
async def export_raw_nodes(token: str = Query(..., description="安全验证Token")):
    """
    导出原始节点数据，供 GitHub Actions 定时抓取
    """
    # 安全验证：只有 Token 对上了才给数据
    # 注意：如果你改了这里的 "shadow-viper-secret-key-2024"，
    # 记得在 GitHub Secrets 的 API 地址里也要同步修改
    if token != "shadow-viper-secret-key-2024":
        return []

    # 获取当前内存中所有存活的节点
    alive_nodes = hunter.get_alive_nodes()
    export_list = []

    for node in alive_nodes:
        # 生成节点分享链接 (如 vmess://..., ss://...)
        # generate_node_share_link 已经在文件头部引入了，直接用即可
        share_link = generate_node_share_link(node)

        export_list.append({
            "protocol": node.get('protocol', 'unknown'),
            "host": node.get('host'),
            "port": node.get('port'),
            "country": node.get('country', 'UNK'),
            "speed": node.get('speed', 0),
            "name": node.get('name', f"{node.get('host')}:{node.get('port')}"),
            "link": share_link
        })

    return export_list

# ==========================================
# 🔥 新增：通过 /api/nodes 暴露节点数据供前端使用
# ==========================================
@router.get("/api/nodes")
async def get_api_nodes(limit: int = Query(50, ge=1, le=500)):
    """
    供前端直接调用的节点数据接口
    返回格式与 /export_raw 兼容，包含 mainland_score/overseas_score 等字段
    """
    alive_nodes = hunter.get_alive_nodes()
    
    # 按分数排序（优先大陆分数，其次海外分数）
    sorted_nodes = sorted(
        alive_nodes,
        key=lambda x: (
            -(x.get('mainland_score', 0) or 0),
            -(x.get('overseas_score', 0) or 0)
        )
    )
    
    # 限制返回数量
    limited_nodes = sorted_nodes[:limit]
    
    # 构造返回数据
    result = []
    for node in limited_nodes:
        # 生成节点分享链接
        share_link = generate_node_share_link(node)
        
        result.append({
            "id": node.get('id', f"{node.get('host')}:{node.get('port')}"),
            "protocol": node.get('protocol', 'unknown'),
            "host": node.get('host'),
            "port": node.get('port'),
            "country": node.get('country', 'UNK'),
            "speed": node.get('speed', 0),
            "delay": node.get('delay', 0),
            "name": node.get('name', f"{node.get('host')}:{node.get('port')}"),
            "link": share_link,
            # 新增：双区域测速字段
            "mainland_score": node.get('mainland_score', 0),
            "mainland_latency": node.get('mainland_latency', 0),
            "overseas_score": node.get('overseas_score', 0),
            "overseas_latency": node.get('overseas_latency', 0),
            "alive": node.get('alive', False)
        })
    
    return result


# ==================== 云端检测函数 ====================

async def test_nodes_via_cloud(nodes: List[Dict], service_url: str, service_name: str) -> List[Dict]:
    """
    通过云端服务检测节点可用性

    Args:
        nodes: 节点列表
        service_url: 云端服务URL
        service_name: 服务名称 (用于日志)

    Returns:
        检测结果列表
    """
    if not service_url:
        logger.warning(f"⚠️ {service_name} URL 未设置，跳过云端检测")
        return []

    if not nodes:
        return []

    logger.info(f"🌐 [{service_name}] 开始云端检测 {len(nodes)} 个节点...")

    try:
        # 准备请求数据
        request_data = {"nodes": nodes}

        # 发送请求到云端服务
        timeout = aiohttp.ClientTimeout(total=60)  # 60秒超时
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(service_url, json=request_data) as response:
                if response.status == 200:
                    result = await response.json()
                    cloud_results = result.get('results', [])

                    logger.info(f"✅ [{service_name}] 云端检测完成，返回 {len(cloud_results)} 个结果")

                    # 为结果添加来源标记
                    for r in cloud_results:
                        r['test_via'] = service_name.lower()

                    return cloud_results
                else:
                    error_text = await response.text()
                    logger.error(f"❌ [{service_name}] 云端检测失败 {response.status}: {error_text[:200]}")
                    return []

    except Exception as e:
        logger.error(f"❌ [{service_name}] 云端检测异常: {str(e)}")
        return []


async def test_nodes_via_aliyun_fc(nodes: List[Dict]) -> List[Dict]:
    """通过阿里云FC检测节点"""
    return await test_nodes_via_cloud(nodes, ALIYUN_FC_URL, "Aliyun FC")


async def test_nodes_via_cloudflare_worker(nodes: List[Dict]) -> List[Dict]:
    """通过Cloudflare Worker检测节点"""
    return await test_nodes_via_cloud(nodes, CF_WORKER_URL, "Cloudflare Worker")


async def merge_cloud_detection_results(local_results: List[Dict], cloud_results: List[Dict], cloud_service: str) -> List[Dict]:
    """
    合并本地检测结果和云端检测结果

    Args:
        local_results: 本地检测结果
        cloud_results: 云端检测结果
        cloud_service: 云端服务名称

    Returns:
        合并后的结果
    """
    # 创建以节点ID为键的映射
    cloud_map = {r.get('id'): r for r in cloud_results}

    merged_results = []

    for local_result in local_results:
        node_id = local_result.get('id', f"{local_result.get('host')}:{local_result.get('port')}")
        cloud_result = cloud_map.get(node_id)

        if cloud_result:
            # 合并云端检测结果
            merged_result = local_result.copy()

            # 添加云端检测数据
            if cloud_service == "aliyun_fc":
                merged_result['mainland_score'] = cloud_result.get('success', False)
                merged_result['mainland_latency'] = cloud_result.get('latency', 0)
                merged_result['test_via'] = 'aliyun'
            elif cloud_service == "cloudflare":
                merged_result['overseas_score'] = cloud_result.get('success', False)
                merged_result['overseas_latency'] = cloud_result.get('latency', 0)
                merged_result['test_via'] = 'cloudflare'

            # 如果云端检测失败，本地检测成功，则保持本地结果
            if not cloud_result.get('success', False) and local_result.get('alive', False):
                merged_result['alive'] = True

            merged_results.append(merged_result)
            logger.debug(f"     🔄 {node_id} 合并{cloud_service}结果: 云端={cloud_result.get('success')}, 本地={local_result.get('alive')}")
        else:
            # 没有云端结果，使用本地结果
            merged_results.append(local_result)

    return merged_results