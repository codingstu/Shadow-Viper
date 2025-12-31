# backend/app/modules/node_hunter/parsers.py
import base64
import json
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
from urllib.parse import unquote

# 🔥 修复：使用国家代码而不是中文名字，以保证前端能正确显示国旗
COUNTRY_CODES = {"CN": "CN", "US": "US", "JP": "JP", "SG": "SG", "TW": "TW", "HK": "HK", "KR": "KR",
                 "DE": "DE", "FR": "FR", "GB": "GB", "CA": "CA", "AU": "AU", "RU": "RU",
                 "IN": "IN", "BR": "BR", "TR": "TR", "NL": "NL", "SE": "SE", "NO": "NO", "FI": "FI",
                 "DK": "DK", "CH": "CH", "AT": "AT", "BE": "BE"}


def clean_base64(b64_str: str) -> str:
    """Cleans a base64 string by removing invalid characters and adding padding."""
    cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', b64_str)
    padding = 4 - (len(cleaned) % 4)
    if padding != 4:
        cleaned += '=' * padding
    return cleaned


def parse_vmess_link(url: str) -> Optional[Dict[str, Any]]:
    try:
        if not url.startswith('vmess://'): return None
        b64_str = url[8:]
        b64_str = clean_base64(b64_str)
        try:
            decoded = base64.b64decode(b64_str).decode('utf-8')
        except:
            decoded = base64.b64decode(b64_str + '=' * (-len(b64_str) % 4)).decode('utf-8')
        config = json.loads(decoded)
        name = config.get('ps', f"VMess-Node")
        host = config.get('add', '')
        port = int(config.get('port', 443))
        uuid = config.get('id', '')
        if not host or not uuid or port <= 0: return None
        
        # 改进的国家识别逻辑：使用更灵活的匹配
        country = _extract_country_from_name(name)
        
        return {"id": f"vmess_{host}_{port}", "name": name, "protocol": "vmess", "host": host, "port": port,
                "uuid": uuid, "alterId": int(config.get('aid', 0)), "network": config.get('net', 'tcp'),
                "type": config.get('type', 'none'), "tls": config.get('tls', 'none'), "sni": config.get('sni', ''),
                "path": config.get('path', ''), "host_header": config.get('host', ''), "country": country}
    except:
        return None


def _extract_country_from_name(name: str) -> str:
    """从节点名称中提取国家代码"""
    if not name:
        return "UNK"
    
    upper_name = name.upper()
    
    # 精确匹配：整个单词匹配
    exact_matches = {
        "CA": ["CANADA"],
        "US": ["USA", "UNITED STATES", "AMERICA"],
        "JP": ["JAPAN", "TOKYO", "OSAKA"],
        "GB": ["UNITED KINGDOM", "LONDON"],
        "DE": ["GERMANY", "FRANKFURT"],
        "FR": ["FRANCE", "PARIS"],
        "SG": ["SINGAPORE"],
        "HK": ["HONG KONG", "HONGKONG"],
        "TW": ["TAIWAN", "TAIPEI"],
        "IN": ["INDIA"],
        "BR": ["BRAZIL"],
        "RU": ["RUSSIA", "MOSCOW"],
        "KR": ["KOREA", "SEOUL"],
        "AU": ["AUSTRALIA", "SYDNEY"],
        "NL": ["NETHERLANDS"],
        "SE": ["SWEDEN"],
        "CH": ["SWITZERLAND", "ZURICH"],
        "FI": ["FINLAND"],
        "NO": ["NORWAY"],
        "TR": ["TURKEY"],
    }
    
    for country_code, keywords in exact_matches.items():
        for keyword in keywords:
            # 检查关键词是否作为独立单词出现
            if keyword in upper_name:
                return country_code
    
    # 检查中文国家名称
    if any(cn_name in name for cn_name in ["中国", "回国", "CN", "CHINA"]):
        return "CN"
    
    return "UNK"


def parse_vless_link(url: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if '@' in netloc:
            uuid, server_port = netloc.split('@')
        else:
            uuid, server_port = "", netloc
        if ':' in server_port:
            server, port_str = server_port.split(':', 1); port = int(port_str)
        else:
            server, port = server_port, 443
        params = parse_qs(parsed.query)

        # ❌ 原代码: name = parsed.fragment or f"VLESS-Node"
        # ✅ 修正后: 使用 unquote 解码
        raw_name = parsed.fragment
        name = unquote(raw_name) if raw_name else "VLESS-Node"

        # 改进的国家识别逻辑
        country = _extract_country_from_name(name)
        
        return {"id": f"vless_{server}_{port}", "name": name, "protocol": "vless", "host": server, "port": port,
                "uuid": uuid, "type": params.get('type', ['tcp'])[0], "security": params.get('security', ['none'])[0],
                "path": params.get('path', [''])[0], "host_header": params.get('host', [''])[0],
                "sni": params.get('sni', [''])[0], "country": country}
    except:
        return None


def parse_trojan_link(url: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = urlparse(url)
        password = parsed.username
        server_port = parsed.netloc.split('@')[-1] if '@' in parsed.netloc else parsed.netloc
        if ':' in server_port:
            server, port_str = server_port.split(':', 1); port = int(port_str)
        else:
            server, port = server_port, 443
        params = parse_qs(parsed.query)
        # ❌ 原代码: name = parsed.fragment or f"Trojan-Node"
        # ✅ 修正后:
        raw_name = parsed.fragment
        name = unquote(raw_name) if raw_name else "Trojan-Node"

        # 改进的国家识别逻辑
        country = _extract_country_from_name(name)
        
        return {"id": f"trojan_{server}_{port}", "name": name, "protocol": "trojan", "host": server, "port": port,
                "password": password or "", "sni": params.get('sni', [''])[0], "type": params.get('type', ['tcp'])[0],
                "country": country}
    except:
        return None


def parse_ss_link(url: str) -> Optional[Dict[str, Any]]:
    try:
        if not url.startswith('ss://'): return None
        b64_str = url[5:]
        b64_str = clean_base64(b64_str)
        try:
            decoded = base64.b64decode(b64_str).decode('utf-8')
        except:
            decoded = base64.b64decode(b64_str + '=' * (-len(b64_str) % 4)).decode('utf-8')
        match = re.match(r'([^:]+):([^@]+)@([^:]+):(\d+)', decoded)
        if not match: return None
        method, password, server, port = match.group(1), match.group(2), match.group(3), int(match.group(4))
        # ✅ 修正后:
        raw_name = urlparse(url).fragment
        name = unquote(raw_name) if raw_name else "SS-Node"

        # 改进的国家识别逻辑
        country = _extract_country_from_name(name)
        
        return {"id": f"ss_{server}_{port}", "name": name, "protocol": "ss", "host": server, "port": port,
                "method": method, "password": password, "country": country}
    except:
        return None


def parse_standard_proxy_link(url: str) -> Optional[Dict[str, Any]]:
    """🔥 新增：解析 socks5:// 或 http:// 链接"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['socks5', 'socks4', 'http', 'https']: return None

        server = parsed.hostname
        port = parsed.port
        if not server or not port: return None

        # ❌ 原代码: name = parsed.fragment or f"{parsed.scheme.upper()}-Node"
        # ✅ 修正后:
        raw_name = parsed.fragment
        name = unquote(raw_name) if raw_name else f"{parsed.scheme.upper()}-Node"

        user = parsed.username
        password = parsed.password

        # 改进的国家识别逻辑
        country = _extract_country_from_name(name)

        return {
            "id": f"{parsed.scheme}_{server}_{port}",
            "name": name,
            "protocol": parsed.scheme,
            "host": server,
            "port": port,
            "username": user,
            "password": password,
            "country": country
        }
    except:
        return None


def parse_node_url(url: str) -> Optional[Dict[str, Any]]:
    url = url.strip()
    if url.startswith('vmess://'):
        return parse_vmess_link(url)
    elif url.startswith('vless://'):
        return parse_vless_link(url)
    elif url.startswith('trojan://'):
        return parse_trojan_link(url)
    elif url.startswith('ss://'):
        return parse_ss_link(url)
    # 优先解析标准代理协议
    elif url.startswith('socks5://') or url.startswith('http://') or url.startswith('https://'):
        return parse_standard_proxy_link(url)
    return None