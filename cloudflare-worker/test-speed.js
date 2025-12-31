/**
 * Cloudflare Worker - 节点速度测试脚本
 * 🎯 目的：在 CF 边缘节点执行真实速度测试，卸载后端 Azure 服务器压力
 * 
 * Round 5: CF Worker 迁移 (2026-01-01)
 * 用于替代后端 RealSpeedTester，直接在全球 CDN 节点执行测试
 */

// ============================================================================
// 🔧 配置部分
// ============================================================================

const CONFIG = {
  // 🔥 改进：使用多个轻量级测试资源
  TEST_SERVERS: [
    {
      name: 'github',
      url: 'https://raw.githubusercontent.com/cloudflare/workers-sdk/main/README.md', // 文本文件
      timeout: 10000,
    },
    {
      name: 'wikipedia-logo',
      url: 'https://en.wikipedia.org/static/images/project-logos/enwiki-1.5x.png',
      timeout: 10000,
    },
    {
      name: 'jsdelivr',
      url: 'https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js',
      timeout: 10000,
    },
  ],
  
  // 超时配置（单位：毫秒）
  LATENCY_TIMEOUT: 5000,     // 5 秒延迟测试超时
  
  // 测试配置
  LATENCY_TEST_URL: 'https://www.google.com',  // HTTP 延迟测试 URL
  LATENCY_RETRIES: 3,                          // 延迟测试重试次数
  
  // 🔥 真实测速优化
  ENABLE_REAL_SPEED_TEST: true,     // 启用真实下载测速
  MIN_DOWNLOAD_TIME: 0.1,           // 最小下载时间（秒）
  MAX_SPEED: 50000,                 // 最大合理速度（MB/s）
};

// ============================================================================
// 🌍 CORS 配置
// ============================================================================

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Cache-Control, Pragma',
  'Access-Control-Max-Age': '86400',
  'Content-Type': 'application/json',
};

// ============================================================================
// 📊 速度测试函数
// ============================================================================

/**
 * 测试 HTTP 延迟 (TCP Ping)
 * @param {string} testUrl - 测试 URL
 * @returns {Promise<number>} 延迟（毫秒）或 null
 */
async function testLatency(testUrl = CONFIG.LATENCY_TEST_URL) {
  try {
    const startTime = performance.now();
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CONFIG.LATENCY_TIMEOUT);
    
    const response = await fetch(testUrl, {
      method: 'HEAD',
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    const endTime = performance.now();
    const latency = Math.round(endTime - startTime);
    
    if (response.ok || response.status < 500) {
      return Math.max(1, latency); // 至少 1ms
    }
    
    return null;
  } catch (error) {
    // 超时或其他错误
    return null;
  }
}

/**
 * 测试下载速度（真实流量）
 * 🔥 改进：尝试多个测试服务器，使用其中最快的
 */
async function testDownloadSpeed() {
  let bestResult = null;
  
  for (const server of CONFIG.TEST_SERVERS) {
    try {
      const startTime = performance.now();
      let bytesReceived = 0;
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), server.timeout);
      
      const response = await fetch(server.url, {
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache',
        },
      });
      
      if (!response.ok) {
        clearTimeout(timeoutId);
        console.log(`[DEBUG] Server ${server.name} failed: status=${response.status}`);
        continue;
      }
      
      // 读取响应体
      const reader = response.body.getReader();
      
      while (true) {
        try {
          const { done, value } = await reader.read();
          if (done) break;
          bytesReceived += value.length;
        } catch (e) {
          break;
        }
      }
      
      clearTimeout(timeoutId);
      const endTime = performance.now();
      const elapsedSeconds = (endTime - startTime) / 1000;
      
      console.log(`[DEBUG] Server ${server.name}: ${bytesReceived} bytes in ${elapsedSeconds.toFixed(2)}s`);
      
      if (elapsedSeconds < CONFIG.MIN_DOWNLOAD_TIME) {
        // 下载太快，数据不可靠（通常是缓存）
        console.log(`[DEBUG] ${server.name} too fast, skipping`);
        continue;
      }
      
      // 计算速度（字节/秒 -> MB/s）
      const speedMBs = bytesReceived / elapsedSeconds / 1024 / 1024;
      
      console.log(`[DEBUG] ${server.name} speed: ${speedMBs.toFixed(2)} MB/s`);
      
      // 验证速度合理性
      if (speedMBs > 0.1 && speedMBs < CONFIG.MAX_SPEED) {
        // 返回第一个成功的结果
        if (!bestResult || speedMBs > bestResult.speed) {
          bestResult = {
            speed: Math.round(speedMBs * 100) / 100,
            server: server.name,
          };
        }
      }
    } catch (error) {
      console.log(`[DEBUG] ${server.name} error: ${error.message}`);
      // 继续尝试下一个服务器
    }
  }
  
  return bestResult ? bestResult.speed : null;
}

/**
 * 基于延迟估计速度（降级方案）
 * @param {number} latency - 延迟（毫秒）
 * @returns {number} 估计速度（MB/s）
 */
function estimateSpeedFromLatency(latency) {
  if (latency < 50) return 100.0;
  if (latency < 100) return 60.0;
  if (latency < 200) return 40.0;
  if (latency < 500) return 20.0;
  if (latency < 1000) return 10.0;
  return 5.0;
}

/**
 * 执行完整的速度测试
 * @returns {Promise<Object>} 包含 delay 和 speed 的结果对象
 */
async function executeSpeedTest() {
  try {
    // 第一步：测延迟
    let latency = null;
    for (let i = 0; i < CONFIG.LATENCY_RETRIES; i++) {
      latency = await testLatency();
      if (latency !== null) break;
      // 重试前等待一下
      await new Promise(r => setTimeout(r, 200));
    }
    
    if (latency === null) {
      latency = -1; // 标记延迟测试失败
    }
    
    // 第二步：测速度（优先真实测速）
    let speed = null;
    let method = 'unknown';
    
    if (CONFIG.ENABLE_REAL_SPEED_TEST) {
      // 🔥 尝试真实下载测速
      speed = await testDownloadSpeed();
      if (speed !== null) {
        method = 'real_download';
      } else {
        // 降级到基于延迟的估算
        if (latency > 0) {
          speed = Math.round(estimateSpeedFromLatency(latency) * 100) / 100;
          method = 'latency_estimate';
        } else {
          speed = 0;
          method = 'fallback';
        }
      }
    } else {
      // 禁用真实测速，直接用延迟估算
      if (latency > 0) {
        speed = Math.round(estimateSpeedFromLatency(latency) * 100) / 100;
        method = 'latency_estimate';
      } else {
        speed = 0;
        method = 'fallback';
      }
    }
    
    return {
      status: 'ok',
      delay: latency,
      speed: speed,
      method: method,  // 👈 新增：告诉前端用的是什么方法测速的
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    return {
      status: 'error',
      error: error.message || 'Unknown error',
      timestamp: new Date().toISOString(),
    };
  }
}

// ============================================================================
// 🔗 HTTP 请求处理
// ============================================================================

/**
 * 处理 OPTIONS 请求（CORS 预检）
 */
function handleCORS() {
  return new Response(null, {
    status: 204,
    headers: CORS_HEADERS,
  });
}

/**
 * 处理 GET 请求
 * @param {Request} request
 */
async function handleGET(request) {
  // 健康检查端点
  const url = new URL(request.url);
  if (url.pathname === '/health') {
    return new Response(JSON.stringify({ status: 'ok' }), {
      status: 200,
      headers: CORS_HEADERS,
    });
  }
  
  return new Response(JSON.stringify({ error: 'Not found' }), {
    status: 404,
    headers: CORS_HEADERS,
  });
}

/**
 * 处理 POST 请求（接收代理信息并测延迟）
 * 🔥 新架构：只测延迟，不传输任何数据
 * 
 * 请求格式：
 * {
 *   "host": "proxy.example.com",
 *   "port": 8080,
 *   "protocol": "http"  // 可选，默认 http
 * }
 */
async function handlePOST(request) {
  const url = new URL(request.url);
  
  // 测速端点
  if (url.pathname === '/test-speed') {
    let body = {};
    try {
      body = await request.json();
    } catch (e) {
      // 没有请求体
    }
    
    // 如果有代理信息，只测延迟
    if (body.host && body.port) {
      const delay = await testProxyLatency(body.host, body.port, body.protocol || 'http');
      
      return new Response(JSON.stringify({
        status: 'ok',
        delay: delay,
        host: body.host,
        port: body.port,
        timestamp: new Date().toISOString(),
      }), {
        status: delay > 0 ? 200 : 500,
        headers: CORS_HEADERS,
      });
    }
    
    // 没有代理信息，返回 CF 自身测试
    const result = await executeSpeedTest();
    return new Response(JSON.stringify(result), {
      status: result.status === 'ok' ? 200 : 500,
      headers: CORS_HEADERS,
    });
  }
  
  return new Response(JSON.stringify({ error: 'Not found' }), {
    status: 404,
    headers: CORS_HEADERS,
  });
}

/**
 * 测试到代理节点的延迟（只建立连接，不读取数据）
 * @param {string} host - 代理主机
 * @param {number} port - 代理端口
 * @param {string} protocol - 协议 (http/https)
 * @returns {Promise<number>} 延迟（毫秒）或 -1
 */
async function testProxyLatency(host, port, protocol = 'http') {
  try {
    const testUrl = `${protocol}://${host}:${port}/`;
    
    // 测延迟：建立连接就立即中止，测真实网络延迟
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const startTime = performance.now();
        
        const controller = new AbortController();
        // 50ms 后中止（足够建立 TCP 连接）
        const timeoutId = setTimeout(() => controller.abort(), 50);
        
        try {
          const res = await fetch(testUrl, {
            method: 'GET',
            signal: controller.signal,
            headers: {
              'User-Agent': 'CloudflareWorker/1.0',
              'Cache-Control': 'no-cache, no-store, max-age=0',
              'Pragma': 'no-cache',
            },
          });
          
          // 如果成功返回，立即中止
          if (res.body) {
            res.body.cancel();
          }
        } catch (e) {
          // 预期会超时或 abort，不是错误
        }
        
        clearTimeout(timeoutId);
        const latency = Math.round(performance.now() - startTime);
        
        console.log(`[DEBUG] ${host}:${port} latency: ${latency}ms (attempt ${attempt + 1})`);
        
        // 返回测得的时间（包括网络延迟 + 握手时间）
        if (latency > 0) {
          return latency;
        }
      } catch (err) {
        console.log(`[DEBUG] Attempt ${attempt + 1} error: ${err.message}`);
      }
    }
    
    return -1;
  } catch (error) {
    console.log(`[DEBUG] Latency test error: ${error.message}`);
    return -1;
  }
}

// ============================================================================
// 🚀 Workers 主函数
// ============================================================================

export default {
  async fetch(request) {
    // 处理 CORS 预检请求
    if (request.method === 'OPTIONS') {
      return handleCORS();
    }
    
    // 处理不同的 HTTP 方法
    if (request.method === 'GET') {
      return await handleGET(request);
    }
    
    if (request.method === 'POST') {
      return await handlePOST(request);
    }
    
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: CORS_HEADERS,
    });
  },
};
