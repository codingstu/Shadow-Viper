#!/usr/bin/env python3
"""
测试线上 SpiderFlow 和 Supabase 同步的诊断脚本
直接在线上环境中测试 Supabase 写入
"""
import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

async def test_online_supabase():
    """测试线上 Supabase 同步"""
    print("\n" + "=" * 70)
    print("🔧 线上 SpiderFlow Supabase 同步诊断")
    print("=" * 70)
    
    # 1. 凭证检查
    print("\n📋 1. 凭证检查：")
    url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    anon_key = os.getenv("SUPABASE_KEY", "").strip()
    
    print(f"   SUPABASE_URL: {'✅' if url else '❌'} {url[:50] + '...' if url else '未设置'}")
    print(f"   SUPABASE_SERVICE_ROLE_KEY: {'✅' if service_key else '❌'} {'已设置' if service_key else '未设置'}")
    print(f"   SUPABASE_KEY: {'✅' if anon_key else '❌'} {'已设置' if anon_key else '未设置'}")
    
    if not url or not service_key:
        print("\n❌ 凭证不完整！")
        return False
    
    # 2. 导入和连接
    print("\n📡 2. 连接 Supabase：")
    try:
        from supabase import create_client
        supabase = create_client(url, service_key)
        print("   ✅ 连接成功")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return False
    
    # 3. 查询现有数据
    print("\n📊 3. 查询现有数据：")
    try:
        # 获取节点总数
        response = supabase.table("nodes").select("count", count="exact").execute()
        count = response.count if hasattr(response, 'count') else 0
        print(f"   ✅ nodes 表当前有 {count} 条数据")
        
        # 获取最新的几条
        latest = supabase.table("nodes").select("id, speed, mainland_score, overseas_score, updated_at").order("updated_at", desc=True).limit(3).execute()
        if latest.data:
            print(f"\n   📌 最新的 3 条数据：")
            for item in latest.data:
                updated_time = item.get("updated_at", "").split("T")[0]  # 只显示日期
                print(f"      - {item['id']}: speed={item.get('speed', 0)}, mainland={item.get('mainland_score', 0)}, updated={updated_time}")
        
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")
        return False
    
    # 4. 测试写入
    print("\n✍️  4. 测试写入权限：")
    test_node_id = f"sync-test-{datetime.now().timestamp()}"
    test_data = {
        "id": test_node_id,
        "content": {"test": True, "environment": "online", "timestamp": datetime.now().isoformat()},
        "link": "test://online-sync-check",
        "is_free": False,
        "mainland_score": 88,
        "mainland_latency": 50,
        "overseas_score": 85,
        "overseas_latency": 60,
        "speed": 88,
        "latency": 50,
        "updated_at": datetime.now().isoformat()
    }
    
    try:
        response = supabase.table("nodes").insert(test_data).execute()
        print(f"   ✅ 写入成功！")
        print(f"      插入的数据 ID: {test_node_id}")
        
        # 5. 验证写入
        print("\n✔️  5. 验证写入的数据：")
        verify = supabase.table("nodes").select("*").eq("id", test_node_id).execute()
        if verify.data:
            print(f"   ✅ 数据已成功写入并可读取")
            item = verify.data[0]
            print(f"      - mainland_score: {item.get('mainland_score')}")
            print(f"      - overseas_score: {item.get('overseas_score')}")
            print(f"      - updated_at: {item.get('updated_at')}")
        
        # 6. 清理测试数据
        print("\n🗑️  6. 清理测试数据：")
        try:
            supabase.table("nodes").delete().eq("id", test_node_id).execute()
            print(f"   ✅ 清理成功")
        except Exception as e:
            print(f"   ⚠️  清理失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 写入失败！")
        print(f"      错误类型: {type(e).__name__}")
        print(f"      错误信息: {str(e)}")
        
        # 诊断
        error_str = str(e).lower()
        if "permission" in error_str or "rls" in error_str:
            print(f"\n   💡 可能是 RLS 权限问题（虽然你已禁用了 RLS）")
        elif "auth" in error_str or "key" in error_str:
            print(f"\n   💡 可能是凭证问题")
        elif "connection" in error_str or "network" in error_str:
            print(f"\n   💡 可能是网络连接问题")
        
        return False

if __name__ == "__main__":
    result = asyncio.run(test_online_supabase())
    print("\n" + "=" * 70)
    if result:
        print("✅ 诊断完成：线上 Supabase 同步正常")
    else:
        print("❌ 诊断完成：线上 Supabase 同步存在问题")
    print("=" * 70 + "\n")
    sys.exit(0 if result else 1)
