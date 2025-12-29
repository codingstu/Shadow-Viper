# backend/app/modules/system/monitor.py
from fastapi import APIRouter
import psutil

# 路由前缀是 /system，挂载在 /api 下 -> 最终为 /api/system
router = APIRouter(prefix="/system", tags=["system"])


@router.get("/stats")  # 🔥 改回 /stats 以匹配 ServerMonitor.vue
async def get_system_stats():
    # 1. 获取 CPU 使用率
    cpu_percent = psutil.cpu_percent(interval=None)

    # 2. 获取内存使用情况
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_used_gb = round(mem.used / (1024 ** 3), 1)
    mem_total_gb = round(mem.total / (1024 ** 3), 1)

    # 3. 网络 I/O (保留此字段，index.html 可能还需要它)
    net_io = psutil.net_io_counters()

    return {
        "cpu": cpu_percent,
        "memory": {
            "percent": mem_percent,
            "used": mem_used_gb,
            "total": mem_total_gb
        },
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv
        }
    }
