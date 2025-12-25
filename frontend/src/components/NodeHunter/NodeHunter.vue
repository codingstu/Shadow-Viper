<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-global-style />
    <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
      
      <div class="shrink-0 text-center mb-4 md:mb-6">
        <h1 class="text-2xl md:text-3xl font-bold text-primary bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500">
          🛰️ 节点猎手 Node Hunter
        </h1>
        <p class="text-xs md:text-sm text-gray-500 mt-2">
          全网高带宽节点嗅探系统：支持 Vmess / Vless / Trojan
        </p>
      </div>

      <div class="shrink-0 mb-4 max-w-6xl mx-auto w-full">
        <div class="flex flex-col md:flex-row gap-3 items-center justify-between bg-[#1e1e1e] p-3 rounded-xl border border-gray-800 shadow-lg">
          
          <div class="flex items-center gap-4">
            <div class="flex flex-col items-center px-4 border-r border-gray-700">
              <span class="text-xs text-gray-500">存活节点</span>
              <span class="text-xl font-bold text-emerald-400">{{ stats.count }}</span>
            </div>
            <n-tag type="info" size="small" :bordered="false" class="bg-gray-800">
              状态: {{ stats.running ? '⚡ 扫描运行中' : '💤 待机' }}
            </n-tag>
          </div>

          <div class="flex gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
            <n-button 
              type="info" 
              ghost 
              @click="copySubscription"
              size="medium"
              class="flex-1 md:flex-none"
            >
              <template #icon>📥</template> 复制订阅
            </n-button>

            <n-button 
              type="warning" 
              ghost
              @click="testAllNodes" 
              :disabled="stats.running || testingAll"
              :loading="testingAll"
              size="medium"
              class="flex-1 md:flex-none"
            >
              <template #icon>🧪</template> {{ testingAll ? '测试中...' : '测试全部' }}
            </n-button>

            <n-button 
              type="primary" 
              @click="triggerScan" 
              :disabled="stats.running"
              :loading="stats.running"
              size="medium"
              class="flex-1 md:flex-none shadow-[0_0_15px_rgba(66,185,131,0.4)]"
            >
              <template #icon>📡</template> {{ stats.running ? '嗅探中...' : '扫描全网' }}
            </n-button>
          </div>
        </div>
      </div>

      <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
        
        <div class="w-full lg:w-1/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden order-2 lg:order-1 h-1/3 lg:h-auto">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <span class="font-bold text-gray-300">📟 系统终端 (Terminal)</span>
          </div>
          
          <div class="flex-1 overflow-y-auto p-4 bg-[#1a1a1a] font-mono text-xs space-y-1 custom-scrollbar" ref="logRef">
            <div v-for="(log, i) in stats.logs" :key="i" class="break-all leading-relaxed">
              <span class="text-emerald-500 mr-2">></span>
              <span class="text-gray-400">{{ log }}</span>
            </div>
            <div v-if="!stats.logs?.length" class="flex items-center justify-center h-full text-gray-600 italic">
              _等待指令输入...
            </div>
          </div>
        </div>

        <div class="w-full lg:w-2/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden order-1 lg:order-2 flex-1">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <span class="font-bold text-gray-300">🌐 全网扫描节点</span>
            <n-tag size="small" round type="primary">{{ stats.count }} 个节点</n-tag>
          </div>

          <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#161616]">
            <div v-if="stats.nodes && stats.nodes.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              
              <div 
                v-for="(node, index) in stats.nodes" 
                :key="node.id || `${node.host}:${node.port}`" 
                class="bg-[#252525] border border-gray-700 rounded-lg p-4 transition-all hover:border-emerald-500/50 flex flex-col gap-3 relative overflow-hidden group"
                :class="{ 'border-amber-500/50': node.isTesting, 'opacity-60': !node.alive }"
              >
                <div v-if="node.isTesting" class="absolute top-0 left-0 h-1 bg-amber-500 animate-pulse w-full"></div>

                <div class="flex justify-between items-start">
                  <div class="flex flex-col min-w-0">
                    <span class="font-bold text-gray-200 truncate pr-2" :title="node.name">{{ node.name }}</span>
                    <span class="text-xs text-gray-500 font-mono mt-1">{{ node.host }}:{{ node.port }}</span>
                  </div>
                  <n-tag 
                    size="tiny" 
                    :type="node.isTesting ? 'warning' : (node.alive ? 'success' : 'error')"
                    :bordered="false"
                  >
                    {{ node.isTesting ? 'TESTING' : (node.alive ? 'ONLINE' : 'OFFLINE') }}
                  </n-tag>
                </div>

                <div class="flex items-center justify-between text-xs bg-[#1a1a1a] p-2 rounded">
                  <n-tag size="tiny" :bordered="false" class="bg-gray-800 text-gray-300 uppercase">
                    {{ node.protocol || 'Unknown' }}
                  </n-tag>
                  <div class="flex gap-3">
                    <span :class="getDelayTextColor(node.delay)" class="font-bold">
                      {{ node.delay }}ms
                    </span>
                    <span class="text-blue-400">
                      {{ node.speed?.toFixed(2) || '0.00' }} MB/s
                    </span>
                  </div>
                </div>

                <div class="grid grid-cols-3 gap-2 mt-auto pt-2 border-t border-gray-700/50">
                  <n-button size="tiny" secondary type="info" @click="copyNode(node)">
                    复制
                  </n-button>
                  <n-button size="tiny" secondary @click="showQRCode(node, index)">
                    二维码
                  </n-button>
                  <n-button 
                    size="tiny" 
                    secondary 
                    :type="node.isTesting ? 'warning' : 'primary'"
                    :loading="node.isTesting" 
                    @click="testSingleNode(node, index)"
                  >
                    测试
                  </n-button>
                </div>
              </div>

            </div>

            <div v-else class="flex flex-col items-center justify-center h-full text-gray-600">
              <span class="text-6xl mb-4 opacity-20">📡</span>
              <p>暂无节点数据，请点击“扫描全网”</p>
            </div>
          </div>
        </div>
      </div>

    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import axios from 'axios';
// 🔥 引入 Naive UI 组件
import { NConfigProvider, NGlobalStyle, NButton, NTag, darkTheme } from 'naive-ui';

// 🔥 定义 Naive UI 的主题覆盖 (保持与爬虫模块一致)
const themeOverrides = {
  common: {
    primaryColor: '#42b983',
    primaryColorHover: '#5cd29d',
    primaryColorPressed: '#2a9163',
  },
  Button: {
    textColor: '#fff',
  }
};

// --- 以下业务逻辑保持 100% 原样 ---

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
      logRef.value.scrollTop = 0; // 注意：这里原逻辑可能是 scrollHeight，暂保持原样
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
      // 保持原有内联样式，确保兼容性
      modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; justify-content: center; align-items: center; z-index: 1000; backdrop-filter: blur(5px);`;
      modal.innerHTML = `<div style="background: #1e1e24; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #42b983; box-shadow: 0 0 20px rgba(66,185,131,0.2);"><h3 style="color: #42b983; margin-bottom: 10px; font-family: monospace;">${node.name}</h3><img src="${response.data.qrcode_data}" alt="QR Code" style="border-radius: 8px;" /><p style="color:#888; font-size:12px; margin-top:10px;">点击任意处关闭</p></div>`;
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

// 辅助函数：根据延迟返回 Tailwind 文字颜色类
function getDelayTextColor(delay) {
  if (delay < 100) return 'text-emerald-400';
  if (delay < 300) return 'text-amber-400';
  return 'text-red-400';
}

onMounted(() => {
  fetchStats();
  const interval = setInterval(fetchStats, 3000);
  return () => clearInterval(interval);
});
</script>

<style scoped>
/* 滚动条美化 */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #1a1a1a;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #42b983;
}
</style>