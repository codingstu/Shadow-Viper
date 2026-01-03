#!/usr/bin/env python3
"""
Supabase 写入权限诊断脚本
用来检查是否能成功写入 Supabase nodes 表
"""
import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

async def test_supabase_write():
    """测试 Supabase 写入"""
    print("=" * 70)
    print("🔧 Supabase 写入权限诊断")
    print("=" * 70)
    
    # 1. 检查凭证
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
    
    print("\n📋 凭证检查:")
    print(f"  SUPABASE_URL: {url[:50] + '...' if url else '❌ 未设置'}")
    print(f"  SUPABASE_SERVICE_ROLE_KEY: {'✅ 已设置' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else '❌ 未设置'}")
    print(f"  SUPABASE_KEY: {'✅ 已设置' if os.getenv('SUPABASE_KEY') else '❌ 未设置'}")
    print(f"  使用的 Key: {'service_role' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'anon'}")
    
    if not url or not key:
        print("\n❌ 凭证不完整！")
        return False
    
    # 2. 尝试连接
    print("\n📡 连接 Supabase...")
    try:
        from supabase import create_client
        supabase = create_client(url, key)
        print("  ✅ 连接成功")
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        return False
    
    # 3. 测试读取
    print("\n📖 测试读取 nodes 表...")
    try:
        response = supabase.table("nodes").select("count", count="exact").execute()
        count = response.count if hasattr(response, 'count') else len(response.data)
        print(f"  ✅ 读取成功，当前有 {count} 条数据")
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return False
    
    # 4. 测试写入（创建测试数据）
    print("\n✍️  测试写入权限...")
    test_data = {
        "id": f"test-write-{datetime.now().timestamp()}",
        "content": {"test": True, "timestamp": datetime.now().isoformat()},
        "link": "test://write-permission-check",
        "is_free": False,
        "mainland_score": 99,
        "mainland_latency": 1,
        "overseas_score": 99,
        "overseas_latency": 1,
        "speed": 99,
        "latency": 1,
        "updated_at": datetime.now().isoformat()
    }
    
    try:
        response = supabase.table("nodes").insert(test_data).execute()
        print(f"  ✅ 写入成功！")
        print(f"     插入的数据 ID: {test_data['id']}")
        
        # 5. 测试删除（清理测试数据）
        print("\n🗑️  清理测试数据...")
        try:
            supabase.table("nodes").delete().eq("id", test_data['id']).execute()
            print(f"  ✅ 清理成功")
        except Exception as e:
            print(f"  ⚠️  清理失败（这不影响诊断）: {e}")
        
        return True
    except Exception as e:
        print(f"  ❌ 写入失败!")
        print(f"     错误类型: {type(e).__name__}")
        print(f"     错误信息: {str(e)}")
        
        # 诊断常见问题
        error_str = str(e).lower()
        if "permission" in error_str or "rls" in error_str or "policy" in error_str:
            print("\n💡 诊断: 这看起来是 RLS（行级安全）权限问题")
            print("   解决方案:")
            print("   1. 检查 Supabase 的 Authentication → Policies")
            print("   2. 确保 nodes 表的 INSERT 策略允许 service_role 写入")
            print("   3. 或者禁用 RLS (如果安全允许)")
        elif "key" in error_str or "auth" in error_str:
            print("\n💡 诊断: 这看起来是凭证问题")
            print("   解决方案:")
            print("   1. 检查 service_role key 是否正确")
            print("   2. 检查环境变量是否正确传入")
        
        return False

if __name__ == "__main__":
    result = asyncio.run(test_supabase_write())
    print("\n" + "=" * 70)
    if result:
        print("✅ 诊断完成：Supabase 写入权限正常")
    else:
        print("❌ 诊断完成：Supabase 写入权限存在问题")
    print("=" * 70)
    sys.exit(0 if result else 1)
