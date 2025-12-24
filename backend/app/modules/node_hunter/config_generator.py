# backend/app/modules/node_hunter/config_generator.py
import base64
import json
import time
from typing import Dict, Any, List, Optional
import yaml

def generate_vmess_share_link(node: Dict[str, Any]) -> str:
    try:
        config = {"v": "2", "ps": node.get('name'), "add": node.get('host'), "port": node.get('port'), "id": node.get('uuid'), "aid": node.get('alterId', 0), "net": node.get('network', 'tcp'), "type": "none", "tls": node.get('tls', 'none'), "path": node.get('path', ''), "sni": node.get('sni', '')}
        return f"vmess://{base64.b64encode(json.dumps(config, separators=(',', ':')).encode()).decode()}"
    except:
        return None

def generate_vless_share_link(node: Dict[str, Any]) -> str:
    try:
        params = f"type={node.get('network', 'tcp')}&encryption=none"
        if node.get('tls') == 'tls':
            params += f"&security=tls&sni={node.get('sni', '')}"
        if node.get('network') == 'ws':
            params += f"&path={node.get('path', '')}&host={node.get('host_header', '')}"
        return f"vless://{node.get('uuid')}@{node.get('host')}:{node.get('port')}?{params}#{node.get('name')}"
    except:
        return None

def generate_trojan_share_link(node: Dict[str, Any]) -> str:
    try:
        params = f"sni={node.get('sni', '')}&allowInsecure=1"
        if node.get('network') == 'ws':
            params += f"&type=ws&path={node.get('path', '')}&host={node.get('host_header', '')}"
        return f"trojan://{node.get('password')}@{node.get('host')}:{node.get('port')}?{params}#{node.get('name')}"
    except:
        return None

def generate_ss_share_link(node: Dict[str, Any]) -> str:
    try:
        plain = f"{node.get('method', 'aes-256-gcm')}:{node.get('password')}@{node.get('host')}:{node.get('port')}"
        return f"ss://{base64.b64encode(plain.encode()).decode()}#{node.get('name')}"
    except:
        return None

def generate_node_share_link(node: Dict[str, Any]) -> Optional[str]:
    protocol = node.get('protocol', '')
    if protocol == 'vmess': return generate_vmess_share_link(node)
    if protocol == 'vless': return generate_vless_share_link(node)
    if protocol == 'trojan': return generate_trojan_share_link(node)
    if protocol == 'ss': return generate_ss_share_link(node)
    return None

def generate_subscription_content(nodes: List[Dict[str, Any]]) -> str:
    links = [generate_node_share_link(n) for n in nodes if n.get('alive')]
    return base64.b64encode("\n".join(filter(None, links)).encode()).decode()

def convert_to_clash_format(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    base = {"name": node.get('name'), "type": node.get('protocol'), "server": node.get('host'), "port": node.get('port'), "udp": True, "skip-cert-verify": True}
    if node.get('protocol') == 'vmess':
        base.update({"uuid": node.get('uuid'), "alterId": node.get('alterId'), "cipher": "auto", "tls": node.get('tls') == 'tls', "network": node.get('network')})
        if node.get('network') == 'ws':
            base["ws-opts"] = {"path": node.get('path', '/'), "headers": {"Host": node.get('host_header', '')}}
    elif node.get('protocol') == 'trojan':
        base.update({"password": node.get('password'), "sni": node.get('sni')})
    elif node.get('protocol') == 'ss':
        base.update({"cipher": node.get('method'), "password": node.get('password')})
    else:
        return None
    return base

def generate_clash_config(nodes: List[Dict[str, Any]]) -> Optional[str]:
    proxies = [convert_to_clash_format(n) for n in nodes if n.get('alive')]
    proxies = list(filter(None, proxies))
    if not proxies: return None
    
    proxy_names = [p['name'] for p in proxies]
    netflix_proxies = [p['name'] for i, p in enumerate(proxies) if nodes[i].get('test_results', {}).get('netflix_test')]

    config = {
        "port": 7890, "socks-port": 7891, "allow-lan": True, "mode": "Rule", "log-level": "info",
        "external-controller": "0.0.0.0:9090", "proxies": proxies,
        "proxy-groups": [
            {"name": "自动选择", "type": "url-test", "proxies": proxy_names, "url": "http://www.gstatic.com/generate_204", "interval": 300},
            {"name": "手动选择", "type": "select", "proxies": proxy_names},
            {"name": "Netflix专用", "type": "select", "proxies": netflix_proxies or proxy_names},
        ],
        "rules": [
            "DOMAIN-SUFFIX,netflix.com,Netflix专用", "DOMAIN-SUFFIX,netflix.net,Netflix专用",
            "DOMAIN-SUFFIX,google.com,自动选择", "DOMAIN-SUFFIX,youtube.com,自动选择",
            "IP-CIDR,127.0.0.0/8,DIRECT", "GEOIP,CN,DIRECT", "MATCH,自动选择",
        ],
    }
    return yaml.dump(config, allow_unicode=True, sort_keys=False)
