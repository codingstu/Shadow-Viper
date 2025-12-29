# backend/app/modules/system/monitor.py
from fastapi import APIRouter
import psutil
import os

# 注意：main.py 中前缀是 /api，这里是 /system，所以最终路径是 /api/system/monitor
router = APIRouter(prefix="/system", tags=["system"])


@router.get("/monitor")  # 修正：前端请求的是 /monitor，不是 /stats
async def get_system_stats():
    # 1. 获取 CPU 使用率
    cpu_percent = psutil.cpu_percent(interval=None)

    # 2. 获取内存使用情况
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_used_gb = round(mem.used / (1024 ** 3), 1)
    mem_total_gb = round(mem.total / (1024 ** 3), 1)

    # 3. 🔥 新增：获取网络 I/O (用于前端仪表盘 Net I/O)
    net_io = psutil.net_io_counters()

    return {
        "cpu": cpu_percent,
        "memory": {
            "percent": mem_percent,
            "used": mem_used_gb,
            "total": mem_total_gb
        },
        # 🔥 必须返回这个结构，前端才能计算网速
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv
        }
    }
