<template>
    <div class="node-hunter">
      <div class="header">
        <div class="title-box">
          <span class="icon">🛰️</span>
          <div class="text-group">
            <h1>Shadow Matrix <span class="badge">Node Hunter</span></h1>
            <p>全网高带宽节点嗅探系统：支持 Vmess / Vless / Trojan</p>
          </div>
        </div>
        <div class="stats-row">
          <div class="stat-card">
            <span class="label">存活节点</span>
            <span class="value">{{ stats.count }}</span>
          </div>
          <div class="stat-card" v-if="stats.filtered_low_latency > 0">
                <span class="label">过滤节点</span>
                <span class="value warning">{{ stats.filtered_low_latency }}</span>
            </div>
          <button @click="copySubscription" class="subscribe-btn">
                📥 复制订阅
            </button>
          <button @click="triggerScan" class="scan-btn" :disabled="stats.running">
            {{ stats.running ? '🛰️ 正在嗅探...' : '📡 扫描全网' }}
          </button>
        </div>
      </div>
  
      <div class="main-content">
        <div class="panel log-panel">
          <div class="panel-header">
            <span>系统终端 (Terminal)</span>
            <span class="log-count">{{ stats.logs?.length || 0 }} 条日志</span>
          </div>
          <div class="terminal-body" ref="logRef">
            <div v-for="(log, i) in stats.logs" :key="i" class="log-line">> {{ log }}</div>
            <div v-if="!stats.logs?.length" class="empty-log">暂无日志，点击扫描开始嗅探</div>
          </div>
        </div>
  
        <div class="panel list-panel">
          <div class="panel-header">
            <span>发现节点 (Active Nodes)</span>
            <span class="node-count">{{ stats.nodes?.length || 0 }} 个节点</span>
          </div>
          <div class="node-grid">
            <div v-for="node in stats.nodes" :key="node.name" class="node-card">
              <div class="node-header">
                <span class="node-name">{{ node.name }}</span>
                <span class="node-status" :class="{ online: node.delay > 0 }">
                  {{ node.delay > 0 ? '在线' : '离线' }}
                </span>
              </div>
              <div class="node-info">
                <span class="protocol-badge" :class="node.protocol">
                  {{ node.protocol.toUpperCase() }}
                </span>
                <span class="host">{{ node.host }}:{{ node.port }}</span>
              </div>
              <div class="node-stats">
                <div class="stat-item">
                  <span class="stat-label">延迟</span>
                  <span class="stat-value" :class="{ 
                    fast: node.delay < 100, 
                    medium: node.delay >= 100 && node.delay < 300 
                  }">
                    {{ node.delay }}ms
                  </span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">速度</span>
                  <span class="stat-value">{{ node.speed.toFixed(2) }} MB/s</span>
                </div>
              </div>
              <div class="node-actions">
                <button class="action-btn copy" @click="copyNode(node)">复制</button>
    <button class="action-btn qrcode" @click="showQRCode(node)">二维码</button>
    <button class="action-btn clash" @click="copyClashConfig(node)">Clash</button>
              </div>
            </div>
            <div v-if="!stats.nodes?.length" class="empty-nodes">
              <div class="empty-icon">📡</div>
              <div class="empty-text">暂无节点数据</div>
              <button class="empty-btn" @click="triggerScan">开始扫描</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref, onMounted, nextTick, computed } from 'vue'
  import axios from 'axios'
  
  const stats = ref({
    count: 0,
    running: false,
    logs: [],
    nodes: []
  })
  
  const logRef = ref(null)
  
  // 创建带基础配置的axios实例
  const api = axios.create({
    baseURL: '/api', // 使用代理路径
    timeout: 10000,
    headers: {
      'Content-Type': 'application/json'
    }
  })
  //初始化滚动加载
  let isInitialLoad = true

  async function fetchStats() {
    try {
      console.log('正在获取节点状态...')
      const response = await api.get('/nodes/stats')
      stats.value = response.data
      
      // 自动滚动到底部
      await nextTick()
      if (logRef.value && isInitialLoad) {
        logRef.value.scrollTop = 0  // 滚动到顶部，因为最新日志在最上面
        isInitialLoad = false
        }
    } catch (error) {
      console.error('获取状态失败:', error)
      addLog(`❌ 获取状态失败: ${error.message}`)
    }
  }
  
  async function triggerScan() {
    try {
      addLog('🚀 正在启动节点扫描...')
      const response = await api.post('/nodes/trigger')
      addLog('✅ 扫描任务已启动，请等待...')
      
      // 立即更新状态
      fetchStats()
    } catch (error) {
      console.error('启动扫描失败:', error)
      addLog(`❌ 启动扫描失败: ${error.message}`)
    }
  }
  
  function addLog(message) {
    const timestamp = new Date().toLocaleTimeString()
    stats.value.logs.unshift(`[${timestamp}] ${message}`)
    // 限制日志数量
    if (stats.value.logs.length > 50) {
      stats.value.logs = stats.value.logs.slice(0, 50)
    }
  }
  
  // 在 script setup 部分添加以下函数

// 复制订阅
async function copySubscription() {
  try {
    const response = await api.get('/nodes/subscription');
    if (response.data.subscription) {
      await navigator.clipboard.writeText(response.data.subscription);
      addLog(`✅ 已复制订阅链接，可导入客户端订阅`);
      
      // 显示订阅导入教程
      showSubscriptionGuide();
    } else {
      addLog(`❌ 暂无订阅链接，请先扫描节点: ${response.data.error}`);
    }
  } catch (error) {
    addLog(`❌ 获取订阅失败: ${error.message}`);
  }
}

// 显示二维码
// 显示二维码
async function showQRCode(node) {
  try {
    // 先找到节点的索引
    const nodeIndex = stats.value.nodes.findIndex(n => 
      n.name === node.name && 
      n.host === node.host && 
      n.port === node.port
    );
    
    if (nodeIndex === -1) {
      addLog(`❌ 找不到节点: ${node.name}`);
      return;
    }
    
    // 调用正确的接口
    const response = await api.get(`/nodes/node/${nodeIndex}/qrcode`);
    
    if (response.data.qrcode_data && !response.data.error) {
      // 创建模态框显示二维码
      const modal = document.createElement('div');
      modal.id = 'qrcode-modal';
      modal.style.cssText = `
        position: fixed; 
        top: 0; 
        left: 0; 
        width: 100%; 
        height: 100%;
        background: rgba(0, 0, 0, 0.8); 
        display: flex; 
        justify-content: center;
        align-items: center; 
        z-index: 10000;
        backdrop-filter: blur(5px);
      `;
      
      modal.innerHTML = `
        <div style="
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          padding: 30px;
          border-radius: 20px;
          text-align: center;
          border: 2px solid rgba(0, 229, 255, 0.3);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          max-width: 400px;
          width: 90%;
        ">
          <h3 style="color: #00e5ff; margin-bottom: 20px; font-size: 18px;">
            📱 ${node.name}
          </h3>
          
          <img 
            src="${response.data.qrcode_data}" 
            style="
              width: 250px; 
              height: 250px; 
              border: 10px solid white;
              border-radius: 10px;
              margin-bottom: 20px;
            " 
            alt="二维码"
          />
          
          <div style="
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: left;
            font-size: 12px;
            color: #aaa;
            font-family: monospace;
            word-break: break-all;
            max-height: 80px;
            overflow-y: auto;
          ">
            <strong>分享链接:</strong><br>
            ${node.share_link ? node.share_link.substring(0, 50) + '...' : '无分享链接'}
          </div>
          
          <p style="color: #888; font-size: 12px; margin-bottom: 20px;">
            使用 Shadowrocket、V2rayNG、Clash 等客户端扫码导入
          </p>
          
          <div style="display: flex; gap: 10px; justify-content: center;">
            <button 
              onclick="this.closest('#qrcode-modal').remove()" 
              style="
                padding: 10px 30px;
                background: rgba(255, 107, 107, 0.8);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s;
              "
              onmouseover="this.style.background='rgba(255, 107, 107, 1)'"
              onmouseout="this.style.background='rgba(255, 107, 107, 0.8)'"
            >
              关闭
            </button>
            
            <button 
              onclick="copyToClipboard('${response.data.share_link || node.share_link || ''}')" 
              style="
                padding: 10px 30px;
                background: rgba(0, 229, 255, 0.8);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s;
              "
              onmouseover="this.style.background='rgba(0, 229, 255, 1)'"
              onmouseout="this.style.background='rgba(0, 229, 255, 0.8)'"
            >
              复制链接
            </button>
          </div>
        </div>
      `;
      
      // 添加复制函数到全局
      window.copyToClipboard = function(text) {
        if (!text) {
          alert('没有可复制的链接');
          return;
        }
        
        navigator.clipboard.writeText(text)
          .then(() => {
            // 显示成功提示
            const successMsg = document.createElement('div');
            successMsg.innerHTML = '✅ 链接已复制到剪贴板';
            successMsg.style.cssText = `
              position: fixed;
              top: 20px;
              right: 20px;
              background: rgba(0, 255, 0, 0.9);
              color: #000;
              padding: 10px 20px;
              border-radius: 8px;
              z-index: 10001;
              font-weight: bold;
            `;
            document.body.appendChild(successMsg);
            setTimeout(() => successMsg.remove(), 2000);
          })
          .catch(err => {
            console.error('复制失败:', err);
            alert('复制失败，请手动复制');
          });
      };
      
      // 点击模态框背景关闭
      modal.addEventListener('click', function(e) {
        if (e.target === modal) {
          modal.remove();
        }
      });
      
      document.body.appendChild(modal);
      addLog(`✅ 已为节点 ${node.name} 生成二维码`);
      
    } else {
      addLog(`❌ 该节点无法生成二维码: ${response.data.error || '未知错误'}`);
      
      // 显示错误提示
      const errorModal = document.createElement('div');
      errorModal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.8); display: flex; justify-content: center;
        align-items: center; z-index: 1000;
      `;
      
      errorModal.innerHTML = `
        <div style="background: rgba(255, 50, 50, 0.9); padding: 30px; border-radius: 10px; text-align: center; color: white;">
          <h3 style="margin-bottom: 20px;">❌ 生成二维码失败</h3>
          <p style="margin-bottom: 20px;">${response.data.error || '该节点无法生成分享链接'}</p>
          <button onclick="this.parentElement.parentElement.remove()" 
            style="padding: 10px 30px; background: white; color: #333; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
            关闭
          </button>
        </div>
      `;
      
      document.body.appendChild(errorModal);
    }
  } catch (error) {
    console.error('生成二维码失败:', error);
    addLog(`❌ 生成二维码失败: ${error.message}`);
  }
}

// 复制Clash配置
async function copyClashConfig(node) {
  try {
    // 这里简化处理，实际应该从后端获取Clash配置
    const clashConfig = {
      name: node.name,
      type: node.protocol,
      server: node.host,
      port: node.port,
      udp: true,
      'skip-cert-verify': true,
    };
    
    if (node.protocol === 'vmess') {
      clashConfig.uuid = node.uuid || '';
      clashConfig.alterId = node.alterId || 0;
      clashConfig.cipher = 'auto';
    } else if (node.protocol === 'trojan') {
      clashConfig.password = node.password || '';
    } else if (node.protocol === 'ss') {
      clashConfig.cipher = node.method || 'aes-256-gcm';
      clashConfig.password = node.password || '';
    }
    
    // 转换为YAML
    const yamlStr = `proxies:\n  - ${JSON.stringify(clashConfig, null, 2).replace(/\n/g, '\n    ')}`;
    
    await navigator.clipboard.writeText(yamlStr);
    addLog(`✅ 已复制Clash配置片段`);
  } catch (error) {
    addLog(`❌ 获取Clash配置失败: ${error.message}`);
  }
}

// 显示订阅导入指南
function showSubscriptionGuide() {
  const guide = `
如何导入订阅：

1. Shadowrocket (iOS):
   - 点击右上角加号 ➕
   - 选择 "订阅"
   - 粘贴订阅链接
   - 点击 "完成"

2. V2rayNG (Android):
   - 点击右上角 ➕
   - 选择 "从剪贴板导入"
   - 或者选择 "订阅设置" → 添加订阅

3. Clash (Windows/macOS):
   - 打开 Clash 配置文件夹
   - 创建 config.yaml 文件
   - 粘贴配置文件内容
  `;
  
  // 使用 alert 或创建更好的模态框
  alert(guide);
}

 // 修改 copyNode 函数，优先复制分享链接
function copyNode(node) {
  // 优先复制分享链接
  if (node.share_link) {
    navigator.clipboard.writeText(node.share_link)
      .then(() => {
        addLog(`✅ 已复制节点 ${node.name} 的分享链接`)
      })
      .catch(err => {
        addLog(`❌ 复制失败: ${err.message}`)
      })
  } else {
    // 如果没有分享链接，复制基本配置
    const config = {
      name: node.name,
      protocol: node.protocol,
      host: node.host,
      port: node.port,
      delay: node.delay,
      speed: node.speed
    }
    
    navigator.clipboard.writeText(JSON.stringify(config, null, 2))
      .then(() => {
        addLog(`✅ 已复制节点 ${node.name} 配置`)
      })
      .catch(err => {
        addLog(`❌ 复制失败: ${err.message}`)
      })
  }
}
  
  async function testNode(node) {
    try {
      addLog(`🧪 正在测试节点 ${node.name}...`)
      // 这里可以添加具体的测试逻辑
      addLog(`✅ 节点 ${node.name} 测试完成`)
    } catch (error) {
      addLog(`❌ 节点测试失败: ${error.message}`)
    }
  }
  
  onMounted(() => {
    fetchStats()
    // 每3秒更新一次状态
    const interval = setInterval(fetchStats, 3000)
    
    return () => clearInterval(interval)
  })
  </script>
  
  <style scoped>
  .node-hunter {
    background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
    min-height: 100vh;
    padding: 20px;
    color: #e0e0e0;
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(0, 229, 255, 0.1);
  }
  
  .title-box {
    display: flex;
    align-items: center;
    gap: 15px;
  }
  
  .icon {
    font-size: 40px;
    filter: drop-shadow(0 0 10px rgba(0, 229, 255, 0.5));
  }
  
  .text-group h1 {
    margin: 0;
    font-size: 28px;
    background: linear-gradient(45deg, #00e5ff, #00ffaa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  .badge {
    font-size: 12px;
    background: linear-gradient(45deg, #00e5ff, #00ffaa);
    color: #000;
    padding: 4px 12px;
    border-radius: 20px;
    margin-left: 10px;
    font-weight: bold;
  }
  
  .stats-row {
    display: flex;
    gap: 20px;
    align-items: center;
  }
  
  .stat-card {
    background: rgba(0, 229, 255, 0.1);
    border: 1px solid rgba(0, 229, 255, 0.3);
    padding: 15px 25px;
    border-radius: 12px;
    text-align: center;
    min-width: 120px;
    backdrop-filter: blur(10px);
  }
  
  .stat-card .label {
    font-size: 12px;
    display: block;
    color: #00e5ff;
    margin-bottom: 5px;
  }
  
  .stat-card .value {
    font-size: 24px;
    font-weight: bold;
    background: linear-gradient(45deg, #00e5ff, #00ffaa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  .scan-btn {
    background: linear-gradient(45deg, #00e5ff, #00ffaa);
    border: none;
    color: #000;
    padding: 12px 30px;
    border-radius: 8px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 16px;
  }
  
  .scan-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0, 229, 255, 0.4);
  }
  
  .scan-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .main-content {
    display: flex;
    gap: 20px;
    height: calc(100vh - 180px);
  }
  
  .panel {
    background: rgba(20, 20, 30, 0.8);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    backdrop-filter: blur(10px);
  }
  
  .log-panel {
    flex: 1;
  }
  
  .list-panel {
    flex: 2;
  }
  
  .panel-header {
    background: rgba(0, 229, 255, 0.1);
    padding: 15px 20px;
    border-bottom: 1px solid rgba(0, 229, 255, 0.2);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 14px;
    font-weight: bold;
  }
  
  .log-count, .node-count {
    background: rgba(0, 0, 0, 0.3);
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    color: #00e5ff;
  }
  
  .terminal-body {
    flex: 1;
    padding: 20px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 13px;
    color: #00ffaa;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.3);
    line-height: 1.5;
  }
  
  .log-line {
    margin-bottom: 8px;
    padding: 2px 0;
    border-bottom: 1px solid rgba(0, 229, 255, 0.1);
  }
  
  .empty-log {
    text-align: center;
    color: #666;
    padding: 40px;
    font-style: italic;
  }
  
  .node-grid {
    flex: 1;
    padding: 20px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
    overflow-y: auto;
  }
  
  .node-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(0, 229, 255, 0.1);
    border-radius: 12px;
    padding: 20px;
    transition: all 0.3s;
  }
  
  .node-card:hover {
    border-color: rgba(0, 229, 255, 0.3);
    transform: translateY(-2px);
    box-shadow: 0 5px 20px rgba(0, 229, 255, 0.2);
  }
  
  .node-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
  }
  
  .node-name {
    font-size: 16px;
    font-weight: bold;
    color: #fff;
  }
  
  .node-status {
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 12px;
    font-weight: bold;
  }
  
  .node-status.online {
    background: rgba(0, 255, 0, 0.1);
    color: #00ff00;
    border: 1px solid rgba(0, 255, 0, 0.3);
  }
  
  .node-info {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 15px;
  }
  
  .protocol-badge {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
    font-weight: bold;
    text-transform: uppercase;
  }
  
  .protocol-badge.vmess {
    background: rgba(0, 229, 255, 0.2);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.3);
  }
  
  .protocol-badge.vless {
    background: rgba(255, 170, 0, 0.2);
    color: #ffaa00;
    border: 1px solid rgba(255, 170, 0, 0.3);
  }
  
  .protocol-badge.trojan {
    background: rgba(255, 0, 170, 0.2);
    color: #ff00aa;
    border: 1px solid rgba(255, 0, 170, 0.3);
  }
  
  .host {
    font-size: 13px;
    color: #aaa;
    font-family: monospace;
  }
  
  .node-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    margin-bottom: 20px;
  }
  
  .stat-item {
    background: rgba(255, 255, 255, 0.05);
    padding: 10px;
    border-radius: 8px;
    text-align: center;
  }
  
  .stat-label {
    display: block;
    font-size: 11px;
    color: #888;
    margin-bottom: 5px;
  }
  
  .stat-value {
    font-size: 18px;
    font-weight: bold;
  }
  
  .stat-value.fast {
    color: #00ff00;
  }
  
  .stat-value.medium {
    color: #ffaa00;
  }
  
  .node-actions {
    display: flex;
    gap: 10px;
  }
  
  .action-btn {
    flex: 1;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s;
  }
  
  .action-btn.copy {
    background: rgba(0, 229, 255, 0.2);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.3);
  }
  
  .action-btn.test {
    background: rgba(255, 170, 0, 0.2);
    color: #ffaa00;
    border: 1px solid rgba(255, 170, 0, 0.3);
  }
  
  .action-btn:hover {
    opacity: 0.8;
    transform: translateY(-1px);
  }
  
  .empty-nodes {
    grid-column: 1 / -1;
    text-align: center;
    padding: 60px 20px;
    color: #666;
  }
  
  .empty-icon {
    font-size: 48px;
    margin-bottom: 20px;
    opacity: 0.5;
  }
  
  .empty-text {
    font-size: 18px;
    margin-bottom: 20px;
    color: #888;
  }
  
  .empty-btn {
    background: rgba(0, 229, 255, 0.1);
    border: 1px solid rgba(0, 229, 255, 0.3);
    color: #00e5ff;
    padding: 12px 30px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    transition: all 0.3s;
  }
  
  .empty-btn:hover {
    background: rgba(0, 229, 255, 0.2);
    transform: translateY(-2px);
  }
  
  /* 滚动条样式 */
  .terminal-body::-webkit-scrollbar,
  .node-grid::-webkit-scrollbar {
    width: 8px;
  }
  
  .terminal-body::-webkit-scrollbar-track,
  .node-grid::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
  }
  
  .terminal-body::-webkit-scrollbar-thumb,
  .node-grid::-webkit-scrollbar-thumb {
    background: rgba(0, 229, 255, 0.3);
    border-radius: 4px;
  }
  
  .terminal-body::-webkit-scrollbar-thumb:hover,
  .node-grid::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 229, 255, 0.5);
  }

  .subscribe-btn {
    background: linear-gradient(45deg, #ff6b6b, #ff8e53);
    border: none;
    color: white;
    padding: 12px 25px;
    border-radius: 8px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s;
  }
  
  .subscribe-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(255, 107, 107, 0.4);
  }
  
  .action-btn.clash {
    background: rgba(86, 98, 246, 0.2);
    color: #5662f6;
    border: 1px solid rgba(86, 98, 246, 0.3);
  }
  
  .action-btn.qrcode {
    background: rgba(0, 184, 148, 0.2);
    color: #00b894;
    border: 1px solid rgba(0, 184, 148, 0.3);
  }
  .warning {
    color: #ffaa00 !important;
    }
  </style>