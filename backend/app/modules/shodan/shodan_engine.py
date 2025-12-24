# backend/app/modules/shodan/shodan_engine.py
import shodan
import asyncio
from datetime import datetime
from typing import List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

# 🔥 修复：定义 APIRouter
router = APIRouter(prefix="/api/shodan", tags=["shodan"])

class ShodanSearchRequest(BaseModel):
    query: str
    limit: int = 20
    api_key: str = ""  # 可选，如果不传则使用环境变量

class ShodanHunter:
    def __init__(self, api_key: str):
        self.api = shodan.Shodan(api_key)
        self.results = []

    def search_camera(self, query: str = "webcam", limit: int = 20) -> List[Dict]:
        """
        核心逻辑：调用 Shodan API 获取真实资产数据
        query 示例:
        - "Server: Hikvision-Webs" (海康)
        - "Server: Dahua-Webs" (大华)
        - "webcam has_screenshot:true" (有截图的摄像头)
        """
        try:
            # 这里的搜索是查数据库，没有任何发包行为，非常安全
            results = self.api.search(query, limit=limit)

            parsed_data = []
            for result in results['matches']:
                # 提取关键信息
                ip = result['ip_str']
                port = result['port']
                org = result.get('org', 'Unknown')
                location = result.get('location', {}).get('country_name', 'Unknown')
                data_preview = result.get('data', '')[:100]  # Banner信息

                # 简单的指纹清洗
                brand = "Unknown"
                if "Hikvision" in data_preview:
                    brand = "Hikvision"
                elif "Dahua" in data_preview:
                    brand = "Dahua"
                elif "GoAhead" in data_preview:
                    brand = "GoAhead"

                parsed_data.append({
                    "ip": ip,
                    "port": port,
                    "brand": brand,
                    "location": location,
                    "org": org,
                    "source": "Shodan API",
                    "status": "Alive (Cached)",  # Shodan 数据是缓存的
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
            return parsed_data

        except shodan.APIError as e:
            print(f"Error: {e}")
            return []
        except Exception as e:
            print(f"System Error: {e}")
            return []

# ==================== API 接口 ====================

@router.post("/search")
async def search_shodan(req: ShodanSearchRequest):
    # 优先使用请求中的 Key，其次使用环境变量
    api_key = req.api_key or os.getenv("SHODAN_API_KEY")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing Shodan API Key")

    hunter = ShodanHunter(api_key)
    
    # 在线程池中运行同步的 Shodan API 调用，避免阻塞
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, hunter.search_camera, req.query, req.limit)
    
    return {"count": len(results), "results": results}
