# backend/app/modules/node_hunter/parsers.py
import base64
import json
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

COUNTRY_CODES = {"CN": "中国", "US": "美国", "JP": "日本", "SG": "新加坡", "TW": "台湾", "HK": "香港", "KR": "韩国", "DE": "德国", "FR": "法国", "GB": "英国", "CA": "加拿大", "AU": "澳大利亚", "RU": "俄罗斯", "IN": "印度", "BR": "巴西", "TR": "土耳其", "NL": "荷兰", "SE": "瑞典", "NO": "挪威", "FI": "芬兰", "DK": "丹麦", "CH": "瑞士", "AT": "奥地利", "BE": "比利时"}

def clean_base64(b64_str: str) -> str:
    """Cleans a base64 string by removing invalid characters and adding padding."""
    cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', b64_str)
    padding = 4 - (len(cleaned) % 4)
    if padding != 4:
        cleaned += '=' * padding
    return cleaned

def parse_vmess_link(url: str) -> Optional[Dict[str, Any]]:
    """Parses a vmess:// link."""
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
        country = "Unknown"
        for code, country_name in COUNTRY_CODES.items():
            if code in name.upper():
                country = country_name
                break
        return {"id": f"vmess_{host}_{port}", "name": name, "protocol": "vmess", "host": host, "port": port, "uuid": uuid, "alterId": int(config.get('aid', 0)), "network": config.get('net', 'tcp'), "type": config.get('type', 'none'), "tls": config.get('tls', 'none'), "sni": config.get('sni', ''), "path": config.get('path', ''), "host_header": config.get('host', ''), "country": country}
    except:
        return None

def parse_vless_link(url: str) -> Optional[Dict[str, Any]]:
    """Parses a vless:// link."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if '@' in netloc: uuid, server_port = netloc.split('@')
        else: uuid, server_port = "", netloc
        if ':' in server_port: server, port_str = server_port.split(':', 1); port = int(port_str)
        else: server, port = server_port, 443
        params = parse_qs(parsed.query)
        name = parsed.fragment or f"VLESS-Node"
        country = "Unknown"
        for code, country_name in COUNTRY_CODES.items():
            if code in name.upper():
                country = country_name
                break
        return {"id": f"vless_{server}_{port}", "name": name, "protocol": "vless", "host": server, "port": port, "uuid": uuid, "type": params.get('type', ['tcp'])[0], "security": params.get('security', ['none'])[0], "path": params.get('path', [''])[0], "host_header": params.get('host', [''])[0], "sni": params.get('sni', [''])[0], "country": country}
    except:
        return None

def parse_trojan_link(url: str) -> Optional[Dict[str, Any]]:
    """Parses a trojan:// link."""
    try:
        parsed = urlparse(url)
        password = parsed.username
        server_port = parsed.netloc.split('@')[-1] if '@' in parsed.netloc else parsed.netloc
        if ':' in server_port: server, port_str = server_port.split(':', 1); port = int(port_str)
        else: server, port = server_port, 443
        params = parse_qs(parsed.query)
        name = parsed.fragment or f"Trojan-Node"
        country = "Unknown"
        for code, country_name in COUNTRY_CODES.items():
            if code in name.upper():
                country = country_name
                break
        return {"id": f"trojan_{server}_{port}", "name": name, "protocol": "trojan", "host": server, "port": port, "password": password or "", "sni": params.get('sni', [''])[0], "type": params.get('type', ['tcp'])[0], "country": country}
    except:
        return None

def parse_ss_link(url: str) -> Optional[Dict[str, Any]]:
    """Parses a ss:// link."""
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
        name = urlparse(url).fragment or f"SS-Node"
        country = "Unknown"
        for code, country_name in COUNTRY_CODES.items():
            if code in name.upper():
                country = country_name
                break
        return {"id": f"ss_{server}_{port}", "name": name, "protocol": "ss", "host": server, "port": port, "method": method, "password": password, "country": country}
    except:
        return None

def parse_ssr_link(url: str) -> Optional[Dict[str, Any]]:
    """Parses a ssr:// link (simplified)."""
    try:
        name = urlparse(url).fragment or f"SSR-Node"
        return {"id": f"ssr_node", "name": name, "protocol": "ssr", "host": "unknown", "port": 443, "country": "Unknown"}
    except:
        return None

def parse_node_url(url: str) -> Optional[Dict[str, Any]]:
    """Parses any supported node URL."""
    url = url.strip()
    if url.startswith('vmess://'): return parse_vmess_link(url)
    elif url.startswith('vless://'): return parse_vless_link(url)
    elif url.startswith('trojan://'): return parse_trojan_link(url)
    elif url.startswith('ss://'): return parse_ss_link(url)
    elif url.startswith('ssr://'): return parse_ssr_link(url)
    return None
