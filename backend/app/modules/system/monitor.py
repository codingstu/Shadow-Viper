# backend/app/modules/system/monitor.py
from fastapi import APIRouter
import psutil
import os

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/stats")
async def get_system_stats():
    # 获取 CPU 使用率
    cpu_percent = psutil.cpu_percent(interval=None)

    # 获取内存使用情况
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_used_gb = round(mem.used / (1024 ** 3), 1)
    mem_total_gb = round(mem.total / (1024 ** 3), 1)

    return {
        "cpu": cpu_percent,
        "memory": {
            "percent": mem_percent,
            "used": mem_used_gb,
            "total": mem_total_gb
        }
    }
