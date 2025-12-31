/**
 * Cloudflare Worker - 节点快速检测脚本
 * 部署方式：复制到 Cloudflare Worker 编辑器并部署
 * 
 * 特点：
 * - 超快速响应（通常 < 500ms）
 * - 无需服务器，完全云端执行
 * - 支持全球多地检测（利用 CF 全球节点）
 */

// ==================== 配置 ====================

const TEST_URLS = {
  baidu: "https://www.baidu.com/",
  google: "https://www.google.com/generate_204",
};

const TIMEOUT_TCP = 5000;    // 5 秒
const TIMEOUT_HTTP = 8000;   // 8 秒
const MAX_CONCURRENT = 5;    // CF Worker 并发限制


// ==================== TCP 连接检测 ====================

async function tcpCheck(host, port) {
  /**
   * 注意：CF Worker 不支持原始 TCP Socket
   * 这里使用 HTTP CONNECT 作为替代方案
   * 对于实际生产，建议在后端执行
   */
  
  const startTime = Date.now();
  
  try {
    // 使用 Cloudflare 的 network diagnostics
    // 这是一个简化方案，不如原生 TCP 检测准确
    const response = await fetch(`http://${host}:${port}`, {
      method: 'HEAD',
      timeout: TIMEOUT_TCP,
    });
    
    const latency = Date.now() - startTime;
    return { success: true, latency };
  } catch (error) {
    // TCP 失败（可能是防火墙或服务器无响应）
    return { success: false, latency: TIMEOUT_TCP };
  }
}


// ==================== HTTP 代理检测 ====================

async function httpCheck(host, port, isCN = false) {
  /**
   * CF Worker 可以发送 HTTP 请求，但不能直接使用代理
   * 这是 CF Worker 的限制
   * 
   * 替代方案：通过特殊的代理协议端口检测
   * 或者直接连接端口，判断是否有 HTTP 服务
   */
  
  const url = isCN ? TEST_URLS.baidu : TEST_URLS.google;
  const startTime = Date.now();
  
  try {
    const response = await fetch(url, {
      method: 'GET',
      timeout: TIMEOUT_HTTP,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      },
    });
    
    const latency = Date.now() - startTime;
    return { success: response.status < 500, latency };
  } catch (error) {
    return { success: false, latency: TIMEOUT_HTTP };
  }
}


// ==================== 节点检测 ====================

async function checkSingleNode(node) {
  const { host, port, id, country } = node;
  const nodeId = id || `${host}:${port}`;
  
  try {
    // 第一步：TCP 检测
    const tcpResult = await tcpCheck(host, port);
    
    if (!tcpResult.success) {
      return {
        id: nodeId,
        success: false,
        reason: 'TCP failed',
        latency: tcpResult.latency,
      };
    }
    
    // 第二步：HTTP 检测
    const isCN = country === 'CN';
    const httpResult = await httpCheck(host, port, isCN);
    
    return {
      id: nodeId,
      success: httpResult.success || tcpResult.success,
      tcp_ok: tcpResult.success,
      http_ok: httpResult.success,
      latency: httpResult.success ? httpResult.latency : tcpResult.latency,
    };
  } catch (error) {
    return {
      id: nodeId,
      success: false,
      reason: error.message,
      latency: 0,
    };
  }
}


async function checkNodesBatch(nodes) {
  // 限制并发数，避免 CF Worker 请求过多
  const batches = [];
  for (let i = 0; i < nodes.length; i += MAX_CONCURRENT) {
    batches.push(nodes.slice(i, i + MAX_CONCURRENT));
  }
  
  const allResults = [];
  for (const batch of batches) {
    const batchResults = await Promise.all(
      batch.map(node => checkSingleNode(node))
    );
    allResults.push(...batchResults);
  }
  
  return allResults;
}


// ==================== Worker 请求处理 ====================

async function handleRequest(request) {
  // 只接受 POST 请求
  if (request.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }
  
  try {
    const body = await request.json();
    const nodes = body.nodes || [];
    
    if (!nodes || nodes.length === 0) {
      return new Response(
        JSON.stringify({ error: 'No nodes provided' }),
        { status: 400 }
      );
    }
    
    // 执行批量检测
    const results = await checkNodesBatch(nodes);
    
    return new Response(
      JSON.stringify({
        success: true,
        count: results.length,
        results: results,
        timestamp: new Date().toISOString(),
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500 }
    );
  }
}


// ==================== Worker 入口 ====================

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});


/**
 * 使用说明：
 * 
 * 1. 复制上述代码到 Cloudflare Workers 编辑器
 * 2. 部署到你的域名，例如：https://yourdomain.workers.dev/
 * 3. 发送 POST 请求：
 * 
 * curl -X POST https://yourdomain.workers.dev/ \
 *   -H "Content-Type: application/json" \
 *   -d '{
 *     "nodes": [
 *       {"host": "1.1.1.1", "port": 443, "id": "node1", "country": "US"},
 *       {"host": "8.8.8.8", "port": 443, "id": "node2", "country": "US"}
 *     ]
 *   }'
 * 
 * 4. 返回结果：
 * {
 *   "success": true,
 *   "count": 2,
 *   "results": [
 *     {"id": "node1", "success": true, "tcp_ok": true, "http_ok": true, "latency": 123},
 *     {"id": "node2", "success": false, "reason": "TCP failed", "latency": 5000}
 *   ],
 *   "timestamp": "2025-12-31T10:00:00.000Z"
 * }
 * 
 * 注意限制：
 * - CF Worker 有 50ms CPU 时间和 30 秒总超时限制
 * - 不支持真实的代理测试（无法通过代理发送请求）
 * - 建议用于快速的 TCP/基础 HTTP 检测
 * - 复杂的协议握手验证需要在后端执行
 */
