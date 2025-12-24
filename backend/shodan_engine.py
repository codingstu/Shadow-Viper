# backend/shodan_engine.py
import shodan
import asyncio
from datetime import datetime
from typing import List, Dict


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

# 测试用的 (你需要填入你自己的 Key)
# if __name__ == "__main__":
#     hunter = ShodanHunter("YOUR_SHODAN_API_KEY")
#     print(hunter.search_camera("Server: Hikvision-Webs", 5))