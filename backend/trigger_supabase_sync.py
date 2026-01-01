#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFlow 立即同步脚本
立即将已验证的节点同步到 Supabase 数据库
用于初始化或手动触发数据同步
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 在导入之前，确保环境变量已设置
# 如果 env 中没有配置，提示用户需要配置
def check_and_setup_env():
    """检查并提示用户设置 Supabase 环境变量"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("\n" + "=" * 70)
        print("⚠️  警告：Supabase 环境变量未配置")
        print("=" * 70)
        print("\n您可以通过以下方式设置环境变量：\n")
        print("方式1 - 本地开发（设置 .env 文件或导出变量）：")
        print('  export SUPABASE_URL="<your_supabase_url>"')
        print('  export SUPABASE_KEY="<your_supabase_anon_key>"')
        print("  python trigger_supabase_sync.py")
        print("\n方式2 - GitHub Actions（已在仓库 Settings > Secrets 中配置）：")
        print("  脚本会自动从 GitHub 环境变量中读取")
        print("\n方式3 - Docker/CI环境：")
        print("  通过 -e 参数传入：")
        print('  docker run -e SUPABASE_URL="<url>" -e SUPABASE_KEY="<key>" ...')
        print()
        return False
    
    print(f"✅ Supabase 环境变量已配置")
    print(f"   URL: {supabase_url[:40]}...")
    print(f"   Key: {supabase_key[:30]}...")
    
    if supabase_service_key:
        print(f"   Service Role Key: ✅ 已配置（可绕过 RLS）\n")
    else:
        print(f"   Service Role Key: ⚠️ 未配置（若需写入数据，请添加此密钥）\n")
    
    return True

# 在导入之前检查
if not check_and_setup_env():
    sys.exit(1)

from app.modules.node_hunter.supabase_helper import upload_to_supabase

async def main():
    """
    从 verified_nodes.json 读取已验证的节点，立即上传到 Supabase
    """
    
    print("=" * 70)
    print("🚀 SpiderFlow -> Supabase 立即同步")
    print("=" * 70)
    
    # 读取已验证的节点
    verified_file = "verified_nodes.json"
    
    if not os.path.exists(verified_file):
        print(f"❌ 错误：找不到 {verified_file}")
        print("   请确保已运行过至少一次节点检测")
        return False
    
    try:
        with open(verified_file, 'r', encoding='utf-8') as f:
            nodes = json.load(f)
        
        print(f"📖 已读取 {verified_file}")
        print(f"📊 文件中共有 {len(nodes)} 个节点")
        
        # 过滤已验证的活跃节点
        alive_nodes = [n for n in nodes if n.get('alive')]
        print(f"✅ 已验证的活跃节点：{len(alive_nodes)} 个")
        
        if not alive_nodes:
            print("⚠️  没有已验证的活跃节点，无法同步")
            return False
        
        # 显示前几个节点信息
        print("\n📋 节点预览（前 3 个）：")
        for i, node in enumerate(alive_nodes[:3]):
            print(f"  {i+1}. {node.get('name', 'Unknown')} - {node.get('host')}:{node.get('port')}")
            print(f"     大陆评分: {node.get('mainland_score')} | 海外评分: {node.get('overseas_score')}")
        
        # 去重：按 host:port 去重
        print("\n🔍 正在去重...")
        seen = {}
        for node in alive_nodes:
            key = f"{node.get('host')}:{node.get('port')}"
            if key not in seen or node.get('updated_at', '') > seen[key].get('updated_at', ''):
                seen[key] = node
        
        unique_nodes = list(seen.values())
        print(f"✅ 去重后：{len(unique_nodes)} 个独立节点")
        
        # 上传到 Supabase
        print("\n📤 开始上传到 Supabase...")
        success = await upload_to_supabase(unique_nodes)
        
        if success:
            print("\n" + "=" * 70)
            print("✅ 成功！节点数据已上传到 Supabase")
            print("=" * 70)
            print(f"\n📊 统计信息：")
            print(f"   - 上传节点数：{len(unique_nodes)}")
            print(f"   - 时间戳：{datetime.now().isoformat()}")
            print(f"\n💡 下一步：")
            print(f"   1. viper-node-store 每12分钟自动拉取一次数据")
            print(f"   2. SpiderFlow 每10分钟自动同步一次数据")
            print(f"   3. 前端可以从 /api/nodes 获取节点列表")
            return True
        else:
            print("\n❌ 上传失败，请检查 Supabase 连接")
            return False
            
    except json.JSONDecodeError:
        print(f"❌ 错误：{verified_file} 不是有效的 JSON 文件")
        return False
    except Exception as e:
        print(f"❌ 错误：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
