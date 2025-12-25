<template>
  <div class="node-hunter">
    <!-- 头部 -->
    <div class="header">
      <div class="title-box">
        <span class="icon">🛰️</span>
        <div class="text-group">
          <h1>节点猎手 <span class="badge">Node Hunter</span></h1>
          <p>全网高带宽节点嗅探系统：支持 Vmess / Vless / Trojan</p>
        </div>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <span class="label">存活节点</span>
          <span class="value">{{ stats.count }}</span>
        </div>

        <button @click="copySubscription" class="subscribe-btn">
          📥 复制订阅
        </button>

        <button @click="testAllNodes" class="test-all-btn" :disabled="stats.running || testingAll">
          {{ testingAll ? '🧪 测试中...' : '🧪 测试全部' }}
        </button>

        <button @click="triggerScan" class="scan-btn" :disabled="stats.running">
          {{ stats.running ? '🛰️ 正在嗅探...' : '📡 扫描全网' }}
        </button>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="main-content">
      <!-- 日志面板 -->
      <div class="panel log-panel">
        <div class="panel-header">
          <span>系统终端 (Terminal)</span>
        </div>
        <div class="terminal-body" ref="logRef">
          <div v-for="(log, i) in stats.logs" :key="i" class="log-line">> {{ log }}</div>
          <div v-if="!stats.logs?.length" class="empty-log">
            点击 "扫描全网" 开始
          </div>
        </div>
      </div>

      <!-- 节点列表面板 -->
      <div class="panel list-panel">
        <div class="panel-header">
          <div class="panel-title">
            <span>🌐 全网扫描节点</span>
          </div>
          <div class="panel-actions">
            <span class="node-count">{{ stats.count }} 个节点</span>
          </div>
        </div>

        <!-- 节点网格 -->
        <div class="node-grid">
          <div v-for="(node, index) in stats.nodes" :key="node.id || `${node.host}:${node.port}`" class="node-card"
            :class="{ 'testing': node.isTesting, 'offline': !node.alive }">
            <div class="node-header">
              <span class="node-name">{{ node.name }}</span>
              <span class="node-status" :class="{ online: node.alive }">
                {{ node.isTesting ? '测试中' : (node.alive ? '在线' : '离线') }}
              </span>
            </div>
            <div class="node-info">
              <span class="protocol-badge" :class="node.protocol">
                {{ node.protocol?.toUpperCase() || 'UNKNOWN' }}
              </span>
              <span class="host">{{ node.host }}:{{ node.port }}</span>
            </div>
            <div class="node-stats">
              <div class="stat-item">
                <span class="stat-label">延迟</span>
                <span class="stat-value" :class="getDelayClass(node.delay)">
                  {{ node.delay }}ms
                </span>
              </div>
              <div class="stat-item">
                <span class="stat-label">速度</span>
                <span class="stat-value">{{ node.speed?.toFixed(2) || '0.00' }} MB/s</span>
              </div>
            </div>
            <div class="node-actions">
              <button class="action-btn copy" @click="copyNode(node)">复制</button>
              <button class="action-btn qrcode" @click="showQRCode(node, index)">二维码</button>
              <button class="action-btn test" @click="testSingleNode(node, index)"
                :disabled="node.isTesting">测试</button>
            </div>
          </div>

          <div v-if="!stats.nodes?.length" class="empty-nodes">
            <div class="empty-icon">🌐</div>
            <div class="empty-text">暂无节点数据</div>
            <button class="empty-btn" @click="triggerScan">开始扫描</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import axios from 'axios';

const stats = ref({ count: 0, running: false, logs: [], nodes: [] });
const logRef = ref(null);
const testingAll = ref(false);

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
});

async function fetchStats() {
  try {
    const response = await api.get('/nodes/stats');
    const newNodes = response.data.nodes.map(newNode => {
      const oldNode = stats.value.nodes.find(n => n.host === newNode.host && n.port === newNode.port);
      return { ...newNode, isTesting: oldNode ? oldNode.isTesting : false };
    });
    stats.value = { ...response.data, nodes: newNodes };

    await nextTick();
    if (logRef.value) {
      logRef.value.scrollTop = 0;
    }
  } catch (error) {
    addLog(`❌ 获取状态失败: ${error.message}`);
  }
}

async function triggerScan() {
  try {
    addLog('🚀 正在启动节点扫描...');
    await api.post('/nodes/trigger');
    fetchStats();
  } catch (error) {
    addLog(`❌ 启动扫描失败: ${error.message}`);
  }
}

async function testAllNodes() {
  testingAll.value = true;
  addLog('🧪 开始测试所有节点...');
  try {
    await api.post('/nodes/test_all');
    const interval = setInterval(async () => {
      await fetchStats();
      if (!stats.value.running) {
        testingAll.value = false;
        clearInterval(interval);
        addLog('🎉 全部节点测试完成');
      }
    }, 2000);
  } catch (error) {
    testingAll.value = false;
    addLog(`❌ 测试任务启动失败: ${error.message}`);
  }
}

async function testSingleNode(node, index) {
  node.isTesting = true;
  try {
    const response = await api.post(`/nodes/test_node/${index}`);
    if (response.data.status === 'ok') {
      const result = response.data.result;
      node.alive = result.total_score > 0;
      node.delay = result.tcp_ping_ms;
      node.test_results = result;
    }
  } catch (error) {
    addLog(`❌ 节点 ${node.name} 测试失败: ${error.message}`);
    node.alive = false;
  } finally {
    node.isTesting = false;
  }
}

function addLog(message) {
  const timestamp = new Date().toLocaleTimeString();
  stats.value.logs.unshift(`[${timestamp}] ${message}`);
  if (stats.value.logs.length > 100) {
    stats.value.logs.pop();
  }
}

async function copySubscription() {
  try {
    const response = await api.get('/nodes/subscription');
    if (response.data.subscription) {
      await navigator.clipboard.writeText(response.data.subscription);
      addLog('✅ 已复制订阅链接');
    } else {
      addLog(`❌ 暂无订阅链接: ${response.data.error}`);
    }
  } catch (error) {
    addLog(`❌ 获取订阅失败: ${error.message}`);
  }
}

async function showQRCode(node, index) {
  try {
    const response = await api.get(`/nodes/node/${index}/qrcode`);
    if (response.data.qrcode_data) {
      const modal = document.createElement('div');
      modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; justify-content: center; align-items: center; z-index: 1000;`;
      modal.innerHTML = `<div style="background: #1e1e24; padding: 20px; border-radius: 10px; text-align: center;"><h3 style="color: #fff;">${node.name}</h3><img src="${response.data.qrcode_data}" alt="QR Code" /><p style="color:#888; font-size:12px;">使用客户端扫码</p></div>`;
      modal.onclick = () => modal.remove();
      document.body.appendChild(modal);
    } else {
      addLog(`❌ 生成二维码失败: ${response.data.error}`);
    }
  } catch (error) {
    addLog(`❌ 生成二维码失败: ${error.message}`);
  }
}

function copyNode(node) {
  if (node.share_link) {
    navigator.clipboard.writeText(node.share_link).then(() => addLog(`✅ 已复制分享链接: ${node.name}`));
  }
}

function getDelayClass(delay) {
  if (delay < 100) return 'good';
  if (delay < 300) return 'medium';
  return 'bad';
}

onMounted(() => {
  fetchStats();
  const interval = setInterval(fetchStats, 3000);
  return () => clearInterval(interval);
});
</script>

<style scoped>
.node-hunter {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.header {
  background: rgba(20, 20, 30, 0.8);
  border-radius: 12px;
  padding: 12px 15px;
  margin-bottom: 10px;
  border: 1px solid rgba(0, 229, 255, 0.2);
}

.title-box {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.icon {
  font-size: 28px;
}

.text-group h1 {
  margin: 0 0 4px 0;
  font-size: 20px;
  color: #fff;
}

.badge {
  background: linear-gradient(45deg, #00e5ff, #00ffaa);
  color: #000;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  margin-left: 6px;
}

.text-group p {
  margin: 0;
  color: #aaa;
  font-size: 11px;
}

.stats-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 12px;
}

.stat-card {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  padding: 8px 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 90px;
}

.stat-card .label {
  font-size: 10px;
  color: #888;
  margin-bottom: 2px;
}

.stat-card .value {
  font-size: 20px;
  font-weight: bold;
  color: #00e5ff;
}

.subscribe-btn,
.scan-btn,
.test-all-btn {
  padding: 8px 15px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
  font-size: 12px;
}

.subscribe-btn {
  background: linear-gradient(45deg, #00b894, #00cec9);
  color: white;
}

.scan-btn {
  background: linear-gradient(45deg, #00e5ff, #00ffaa);
  color: #000;
}

.test-all-btn {
  background: linear-gradient(45deg, #ff9800, #ffc107);
  color: #000;
}

.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 15px;
  min-height: 0;
  overflow: hidden;
}

.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: rgba(20, 20, 30, 0.8);
  border-radius: 12px;
  border: 1px solid rgba(0, 229, 255, 0.2);
}

.panel-header {
  padding: 12px 15px;
  background: rgba(0, 229, 255, 0.1);
  border-bottom: 1px solid rgba(0, 229, 255, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header span {
  font-size: 14px;
  font-weight: bold;
  color: #00e5ff;
}

.terminal-body {
  flex: 1;
  min-height: 0;
  padding: 12px;
  background: rgba(0, 0, 0, 0.5);
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #00ffaa;
  overflow-y: auto;
}

.log-line {
  margin-bottom: 5px;
  line-height: 1.4;
}

.empty-log {
  color: #666;
  font-style: italic;
  text-align: center;
  padding: 40px 20px;
}

.panel-title {
  font-size: 18px;
  font-weight: bold;
  color: #00e5ff;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.node-count {
  font-size: 14px;
  color: #aaa;
}

.node-grid {
  flex: 1;
  min-height: 0;
  padding: 12px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.node-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(0, 229, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  transition: all 0.3s;
}

.node-card.testing {
  border-color: #ff9800;
  animation: pulse 1s infinite;
}

.node-card.offline {
  opacity: 0.4;
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
  color: #e0e0e0;
}

.node-status {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 10px;
  font-weight: bold;
}

.node-status.online {
  background: rgba(0, 255, 0, 0.1);
  color: #00ffaa;
  border: 1px solid rgba(0, 255, 0, 0.3);
}

.node-status:not(.online) {
  background: rgba(255, 0, 0, 0.1);
  color: #ff6b6b;
  border: 1px solid rgba(255, 0, 0, 0.3);
}

.node-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.protocol-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 10px;
  font-weight: bold;
}

.protocol-badge.vmess {
  background: rgba(0, 229, 255, 0.2);
  color: #00e5ff;
}

.protocol-badge.vless {
  background: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.protocol-badge.trojan {
  background: rgba(0, 255, 170, 0.2);
  color: #00ffaa;
}

.host {
  font-size: 13px;
  color: #888;
  font-family: monospace;
}

.node-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: bold;
}

.good {
  color: #00ffaa !important;
}

.medium {
  color: #ffaa00 !important;
}

.bad {
  color: #ff6b6b !important;
}

.node-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(0, 229, 255, 0.2);
  background: rgba(0, 229, 255, 0.05);
  color: #00e5ff;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.empty-nodes {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px 15px;
  background: rgba(255, 255, 255, 0.02);
  border: 2px dashed rgba(0, 229, 255, 0.1);
  border-radius: 12px;
  margin: 15px;
}

.empty-icon {
  font-size: 36px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  font-size: 14px;
  color: #888;
  margin-bottom: 8px;
}

.empty-btn {
  background: linear-gradient(45deg, rgba(0, 229, 255, 0.2), rgba(0, 255, 170, 0.2));
  border: 1px solid rgba(0, 229, 255, 0.3);
  color: #00e5ff;
  padding: 8px 20px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 12px;
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}
</style>