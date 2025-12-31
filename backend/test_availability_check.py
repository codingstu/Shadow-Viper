#!/usr/bin/env python3
"""
快速测试脚本 - 验证新的可用性检测系统
"""

import asyncio
import sys
import json

sys.path.insert(0, '/Users/ikun/study/Learning/SpiderFlow/backend')

from app.modules.node_hunter.real_availability_check import (
    check_node_basic_availability,
    check_node_full_availability,
    check_nodes_batch,
    AvailabilityLevel,
    get_health_statistics
)

async def test_single_node():
    """测试单个节点"""
    print("\n" + "="*60)
    print("🧪 测试 1: 单个节点基础检测")
    print("="*60)
    
    node = {
        "id": "test_node_1",
        "host": "1.1.1.1",
        "port": 443,
        "protocol": "vmess",
        "country": "US",
        "name": "Test Node"
    }
    
    print(f"\n📝 测试节点: {node['host']}:{node['port']} ({node['country']})")
    print("⏳ 执行中...")
    
    result = await check_node_basic_availability(node, timeout_tcp=5, timeout_http=10)
    
    print(f"\n✅ 检测完成:")
    print(f"   ID: {result.node_id}")
    print(f"   等级: {result.level.name} (值: {result.level.value})")
    print(f"   TCP: {'✓' if result.tcp_ok else '✗'} ({result.tcp_latency_ms}ms)")
    print(f"   HTTP: {'✓' if result.http_ok else '✗'} ({result.http_latency_ms}ms)")
    print(f"   DNS: {'✓' if result.dns_ok else '✗'} ({result.dns_latency_ms}ms)")
    print(f"   健康评分: {result.health_score}/100")
    
    if result.error_message:
        print(f"   错误: {result.error_message}")
    
    return result


async def test_batch_nodes():
    """测试批量节点"""
    print("\n" + "="*60)
    print("🧪 测试 2: 批量节点检测")
    print("="*60)
    
    nodes = [
        {"id": "node_1", "host": "1.1.1.1", "port": 443, "protocol": "vmess", "country": "US", "name": "Cloudflare DNS"},
        {"id": "node_2", "host": "8.8.8.8", "port": 443, "protocol": "trojan", "country": "US", "name": "Google DNS"},
        {"id": "node_3", "host": "114.114.114.114", "port": 80, "protocol": "ss", "country": "CN", "name": "CN DNS"},
    ]
    
    print(f"\n📝 测试 {len(nodes)} 个节点...")
    print("⏳ 执行中 (并发: 3)...")
    
    results = await check_nodes_batch(nodes, full_check=False, max_concurrent=3)
    
    print(f"\n✅ 批量检测完成:\n")
    for result in results:
        status = "✓" if result.level.value >= AvailabilityLevel.BASIC.value else "✗"
        print(f"   {status} {result.node_id}: {result.level.name} (评分: {result.health_score}/100)")
    
    # 统计信息
    stats = get_health_statistics(results)
    print(f"\n📊 统计信息:")
    print(f"   总计: {stats['total']}")
    print(f"   可用 (BASIC+): {stats['basic'] + stats['verified']}")
    print(f"   可疑 (SUSPECT): {stats['suspect']}")
    print(f"   不可用 (DEAD): {stats['dead']}")
    print(f"   平均评分: {stats['avg_health_score']}/100")
    
    return results


async def test_full_check():
    """测试完整检测（包括握手）"""
    print("\n" + "="*60)
    print("🧪 测试 3: 完整检测（包括协议握手）")
    print("="*60)
    
    node = {
        "id": "full_check_test",
        "host": "1.1.1.1",
        "port": 443,
        "protocol": "vless",
        "id": "test-uuid",
        "country": "US",
        "name": "Full Check Test"
    }
    
    print(f"\n📝 测试节点: {node['host']}:{node['port']}")
    print("⏳ 执行完整检测中 (包括握手验证)...")
    
    result = await check_node_full_availability(node)
    
    print(f"\n✅ 完整检测完成:")
    print(f"   等级: {result.level.name}")
    print(f"   TCP: {'✓' if result.tcp_ok else '✗'}")
    print(f"   HTTP: {'✓' if result.http_ok else '✗'}")
    print(f"   DNS: {'✓' if result.dns_ok else '✗'}")
    print(f"   协议握手: {'✓' if result.protocol_handshake_ok else '✗'} ({result.protocol_type})")
    print(f"   健康评分: {result.health_score}/100")
    
    return result


async def main():
    """主测试函数"""
    print("\n" + "🚀"*30)
    print("\n🧪 多层级节点可用性检测系统 - 快速测试")
    print("\n" + "🚀"*30)
    
    try:
        # 测试 1: 单个节点
        result1 = await test_single_node()
        
        # 测试 2: 批量节点
        results2 = await test_batch_nodes()
        
        # 测试 3: 完整检测
        result3 = await test_full_check()
        
        # 总结
        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        print("="*60)
        
        print("\n📋 测试总结:")
        print("   ✓ 单个节点检测")
        print("   ✓ 批量节点检测")
        print("   ✓ 完整检测（握手验证）")
        print("   ✓ 统计信息提取")
        
        print("\n🎯 系统状态: ✅ 就绪")
        print("\n后续步骤:")
        print("   1. 启用新系统: 在 node_hunter.py 中将 test_and_update_nodes 改为 _test_nodes_with_new_system")
        print("   2. 重启后端测试完整节点扫描")
        print("   3. 监控日志查看检测进度")
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
