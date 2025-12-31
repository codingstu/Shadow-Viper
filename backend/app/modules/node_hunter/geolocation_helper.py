# backend/app/modules/node_hunter/geolocation_helper.py
"""
🌍 地理位置助手模块
使用多种方法检测节点国家：
1. IP地址查询（优先级高）
2. 节点名称分析（关键词匹配）
3. 域名WHOIS查询（作为备份）
"""

import asyncio
import httpx
from typing import Optional, Dict, List
from loguru import logger
import re

# 国家代码到名称的映射
COUNTRY_CODE_MAP = {
    "US": ["USA", "AMERICA", "UNITED STATES", "NEW YORK", "LOS ANGELES", "SAN FRANCISCO", "CHICAGO", "DALLAS"],
    "JP": ["JAPAN", "TOKYO", "OSAKA", "KYOTO", "KOBE"],
    "GB": ["UNITED KINGDOM", "UK", "LONDON", "MANCHESTER", "LIVERPOOL"],
    "DE": ["GERMANY", "FRANKFURT", "BERLIN", "MUNICH"],
    "FR": ["FRANCE", "PARIS", "LYON", "MARSEILLE"],
    "CA": ["CANADA", "TORONTO", "VANCOUVER", "MONTREAL"],
    "AU": ["AUSTRALIA", "SYDNEY", "MELBOURNE", "BRISBANE"],
    "SG": ["SINGAPORE"],
    "HK": ["HONG KONG", "HONGKONG"],
    "TW": ["TAIWAN", "TAIPEI"],
    "KR": ["KOREA", "SEOUL", "BUSAN"],
    "IN": ["INDIA", "DELHI", "MUMBAI"],
    "BR": ["BRAZIL", "SÃO PAULO", "RIO"],
    "RU": ["RUSSIA", "MOSCOW", "SAINT PETERSBURG"],
    "SE": ["SWEDEN", "STOCKHOLM"],
    "NO": ["NORWAY", "OSLO"],
    "NL": ["NETHERLANDS", "AMSTERDAM"],
    "CH": ["SWITZERLAND", "ZURICH", "GENEVA"],
    "AT": ["AUSTRIA", "VIENNA"],
    "BE": ["BELGIUM", "BRUSSELS"],
    "IT": ["ITALY", "ROME", "MILAN", "VENICE"],
    "ES": ["SPAIN", "MADRID", "BARCELONA"],
    "PT": ["PORTUGAL", "LISBON"],
    "GR": ["GREECE", "ATHENS"],
    "TR": ["TURKEY", "ISTANBUL"],
    "MX": ["MEXICO", "MEXICO CITY"],
    "TH": ["THAILAND", "BANGKOK"],
    "MY": ["MALAYSIA", "KUALA LUMPUR"],
    "PH": ["PHILIPPINES", "MANILA"],
    "VN": ["VIETNAM", "HANOI", "HO CHI MINH"],
    "ID": ["INDONESIA", "JAKARTA"],
    "NZ": ["NEW ZEALAND", "AUCKLAND"],
    "IE": ["IRELAND", "DUBLIN"],
    "ZA": ["SOUTH AFRICA", "JOHANNESBURG"],
    "CN": ["CHINA", "中国", "回国", "BEIJING", "SHANGHAI", "SHENZHEN", "GUANGZHOU", "HANGZHOU"],
}

# 反向映射：关键词 -> 国家代码
KEYWORD_TO_COUNTRY = {}
for country_code, keywords in COUNTRY_CODE_MAP.items():
    for keyword in keywords:
        KEYWORD_TO_COUNTRY[keyword] = country_code


class GeolocationHelper:
    """地理位置检测辅助类"""

    def __init__(self):
        self.ip_cache: Dict[str, str] = {}  # IP -> 国家代码缓存

    async def detect_country_by_ip(self, ip: str, timeout: int = 3) -> Optional[str]:
        """
        通过IP地址检测国家（优先级最高）

        使用多个地理位置服务：
        1. ipapi.co (免费，快速)
        2. ip-api.com (免费，备选)

        Args:
            ip: IP地址
            timeout: 超时时间

        Returns:
            国家代码 (如 "US", "CN") 或 None
        """
        # 检查缓存
        if ip in self.ip_cache:
            return self.ip_cache[ip]

        try:
            # 方案1: 使用 ipapi.co
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.get(f"https://ipapi.co/{ip}/json/")
                    if response.status_code == 200:
                        data = response.json()
                        country_code = data.get("country_code", "").upper()
                        if country_code and len(country_code) == 2:
                            self.ip_cache[ip] = country_code
                            logger.debug(f"✅ IP查询成功 ({ip}): {country_code}")
                            return country_code
                except Exception as e:
                    logger.debug(f"⚠️ ipapi.co 查询失败: {str(e)[:50]}")

                # 方案2: 使用 ip-api.com (备选)
                try:
                    response = await client.get(f"http://ip-api.com/json/{ip}")
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success":
                            country_code = data.get("countryCode", "").upper()
                            if country_code and len(country_code) == 2:
                                self.ip_cache[ip] = country_code
                                logger.debug(f"✅ IP查询成功 ({ip}): {country_code}")
                                return country_code
                except Exception as e:
                    logger.debug(f"⚠️ ip-api.com 查询失败: {str(e)[:50]}")

        except Exception as e:
            logger.debug(f"❌ IP地址查询异常: {str(e)[:80]}")

        return None

    def detect_country_by_name(self, name: str) -> Optional[str]:
        """
        通过节点名称检测国家（优先级次高）

        使用精确关键词匹配，避免误匹配

        Args:
            name: 节点名称

        Returns:
            国家代码或 None
        """
        if not name:
            return None

        upper_name = name.upper()

        # 清理名称，提取有用信息
        # 移除 Emoji 和特殊符号，保留字母数字和空格
        cleaned_name = re.sub(r'[^A-Z0-9\s]', ' ', upper_name)
        cleaned_name = ' ' + cleaned_name + ' '  # 添加前后空格以进行单词匹配

        # 优先匹配精确关键词
        for keyword, country_code in KEYWORD_TO_COUNTRY.items():
            # 使用单词边界匹配，避免部分匹配
            if f' {keyword} ' in cleaned_name:
                logger.debug(f"✅ 名称匹配: {name} -> {country_code}")
                return country_code

        # 次级匹配：检查是否包含关键词（不要求单词边界）
        for keyword, country_code in KEYWORD_TO_COUNTRY.items():
            if keyword in cleaned_name:
                logger.debug(f"✅ 部分匹配: {name} -> {country_code}")
                return country_code

        return None

    async def detect_country_by_domain(self, domain: str, timeout: int = 3) -> Optional[str]:
        """
        通过域名检测国家（优先级最低）

        使用 WHOIS 查询域名顶级域名信息

        Args:
            domain: 域名

        Returns:
            国家代码或 None
        """
        if not domain:
            return None

        try:
            # 提取顶级域名 (TLD)
            parts = domain.split('.')
            if len(parts) < 2:
                return None

            tld = parts[-1].upper()

            # 国家代码 TLD 映射（常见的）
            country_tld_map = {
                "JP": "JP",  # .jp
                "CN": "CN",  # .cn
                "TW": "TW",  # .tw
                "HK": "HK",  # .hk
                "SG": "SG",  # .sg
                "KR": "KR",  # .kr
                "IN": "IN",  # .in
                "BR": "BR",  # .br
                "RU": "RU",  # .ru
                "DE": "DE",  # .de
                "FR": "FR",  # .fr
                "GB": "GB",  # .uk
                "AU": "AU",  # .au
                "CA": "CA",  # .ca
                "US": "US",  # .us
                "MX": "MX",  # .mx
                "TR": "TR",  # .tr
                "IT": "IT",  # .it
                "ES": "ES",  # .es
                "NL": "NL",  # .nl
                "BE": "BE",  # .be
                "AT": "AT",  # .at
                "CH": "CH",  # .ch
                "SE": "SE",  # .se
                "NO": "NO",  # .no
                "TH": "TH",  # .th
                "MY": "MY",  # .my
                "PH": "PH",  # .ph
                "ID": "ID",  # .id
                "VN": "VN",  # .vn
                "ZA": "ZA",  # .za
                "IE": "IE",  # .ie
                "NZ": "NZ",  # .nz
            }

            if tld in country_tld_map:
                logger.debug(f"✅ 域名TLD检测: {domain} -> {country_tld_map[tld]}")
                return country_tld_map[tld]

        except Exception as e:
            logger.debug(f"⚠️ 域名检测异常: {str(e)[:80]}")

        return None

    async def detect_country(
        self, ip: str = None, name: str = None, domain: str = None
    ) -> str:
        """
        综合多种方法检测国家

        优先级：名称匹配 > 域名检测 > IP查询 > 未知
        
        ⚠️ 改进说明：
        - IP API 容易误判（如显示印度实际美国），所以优先级降低
        - 节点名称通常包含真实位置信息，优先级最高
        - 域名 TLD 也比 IP API 更可靠

        Args:
            ip: IP地址
            name: 节点名称
            domain: 域名

        Returns:
            国家代码 (如 "US", "CN") 或 "UNK" (未知)
        """
        # 🔥 方法1: 节点名称分析（最可靠）
        if name:
            country = self.detect_country_by_name(name)
            if country:
                return country

        # 🔥 方法2: 域名检测（次可靠）
        if domain:
            country = await self.detect_country_by_domain(domain)
            if country:
                return country

        # 🔥 方法3: IP地址查询（仅作为备用）
        if ip:
            country = await self.detect_country_by_ip(ip, timeout=2)  # 降低超时
            if country:
                return country

        logger.debug(f"❌ 无法检测国家: name={name[:20] if name else None}, ip={ip}")
        return "UNK"

    def clear_cache(self):
        """清除IP缓存"""
        self.ip_cache.clear()
        logger.info("✅ 地理位置缓存已清除")
