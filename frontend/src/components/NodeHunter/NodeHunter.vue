<template>
  <div class="node-hunter p-4 h-full flex flex-col gap-4 text-gray-200">
    <div class="header bg-[#1e1e20] border border-white/10 rounded-xl p-4 flex flex-col md:flex-row justify-between items-center shadow-lg">
      <div class="flex items-center gap-4 mb-4 md:mb-0">
        <div class="p-3 bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 rounded-lg border border-emerald-500/30">
          <span class="text-3xl filter drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]">🛰️</span>
        </div>
        <div>
          <h1 class="text-xl font-bold text-white m-0 flex items-center gap-2">
            节点猎手 
            <span class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs border border-emerald-500/30">Node Hunter</span>
          </h1>
          <p class="text-xs text-gray-400 m-0 mt-1 font-mono">全网高带宽节点嗅探系统 (Vmess/Vless/Trojan)</p>
        </div>
      </div>
      
      <div class="flex flex-wrap justify-center gap-3 items-center">
        <div class="flex flex-col items-center bg-black/40 px-5 py-1.5 rounded-lg border border-white/5">
          <span class="text-[10px] text-gray-500 uppercase tracking-wider">Active Nodes</span>
          <span class="text-xl font-bold text-emerald-400 font-mono">{{ stats.count }}</span>
        </div>
        
        <n-button secondary circle type="primary" @click="showAddSourceModal = true" title="添加自定义源">
          <template #icon>➕</template>
        </n-button>

        <n-button type="primary" secondary size="medium" @click="copySubscription">
          <template #icon>📥</template> 复制订阅
        </n-button>
        
        <n-button type="warning" secondary size="medium" @click="testAllNodes" :loading="testingAll" :disabled="stats.running">
          <template #icon>🧪</template> {{ testingAll ? '测试中...' : '测试全部' }}
        </n-button>

        <n-button type="info" size="medium" @click="triggerScan" :loading="stats.running" class="glow-effect">
          <template #icon>📡</template> {{ stats.running ? '正在嗅探...' : '扫描全网' }}
        </n-button>
      </div>
    </div>
    
    <div class="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
      
      <div class="lg:col-span-4 bg-[#1e1e20] border border-white/10 rounded-xl flex flex-col overflow-hidden shadow-lg h-[300px] lg:h-auto">
        <div class="p-3 border-b border-white/10 bg-black/20 flex justify-between items-center">
          <span class="font-bold text-emerald-400 text-sm flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            系统终端 (Terminal)
          </span>
        </div>
        <div class="flex-1 p-4 bg-[#121212] font-mono text-xs text-gray-300 overflow-y-auto custom-scrollbar" ref="logRef">
          <div v-for="(log, i) in stats.logs" :key="i" class="mb-1.5 leading-relaxed break-all">
            <span class="text-emerald-500/50 mr-2">></span>
            <span :class="{'text-yellow-400': log.includes('⚠️'), 'text-red-400': log.includes('❌'), 'text-emerald-400': log.includes('✅')}">{{ log }}</span>
          </div>
          <div v-if="!stats.logs?.length" class="h-full flex flex-col items-center justify-center text-gray-700 italic opacity-50">
            <span>_等待指令输入...</span>
          </div>
        </div>
      </div>
      
      <div class="lg:col-span-8 bg-[#1e1e20] border border-white/10 rounded-xl flex flex-col overflow-hidden shadow-lg">
        <div class="p-3 border-b border-white/10 bg-black/20 flex justify-between items-center shrink-0">
          <div class="font-bold text-emerald-400 text-sm">🌐 节点列表 (按 IP 归属地分组)</div>
          <n-tag size="small" round :bordered="false" type="primary" class="bg-emerald-500/20 text-emerald-400">
            共 {{ stats.count }} 个
          </n-tag>
        </div>
        
        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#161618]">
          <template v-if="stats.nodes && stats.nodes.length > 0">
            <div class="flex flex-col gap-4">
              <div 
                v-for="group in stats.nodes" 
                :key="group.group_name" 
                class="border border-white/10 rounded-xl overflow-hidden bg-[#1e1e20]"
              >
                <div class="px-4 py-3 bg-white/5 border-b border-white/5 flex justify-between items-center">
                  <div class="flex items-center gap-2 font-bold text-gray-200">
                    <span class="text-lg">{{ getCountryInfo(group.group_name).flag }}</span>
                    <span>{{ getCountryInfo(group.group_name).name }}</span>
                    <span class="text-xs text-gray-500 ml-1 font-mono">({{ group.group_name }})</span>
                  </div>
                  <n-tag size="small" round :bordered="false" class="bg-black/40 text-gray-400">
                    {{ group.nodes.length }}
                  </n-tag>
                </div>

                <div class="p-3 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-3 gap-3">
                  <div 
                    v-for="(node, index) in group.nodes" 
                    :key="node.id || `${node.host}:${node.port}`" 
                    class="relative group bg-black/30 border border-white/5 rounded-lg p-3 hover:border-emerald-500/50 hover:bg-black/50 transition-all duration-300"
                    :class="{ 'border-yellow-500/30 bg-yellow-500/5': node.isTesting }"
                  >
                    <div v-if="node.isTesting" class="absolute inset-0 bg-black/60 z-10 flex items-center justify-center rounded-lg backdrop-blur-sm">
                      <div class="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
                    </div>

                    <div class="flex items-center gap-2 mb-2">
                      <n-tag size="tiny" :bordered="false" :type="getProtocolColor(node.protocol)" class="uppercase font-bold shrink-0">
                        {{ node.protocol }}
                      </n-tag>
                      <span class="text-sm font-bold text-gray-200 truncate flex-1" :title="node.name">
                        {{ node.name.replace(/^[^\w]*/, '') }}
                      </span>
                    </div>

                    <div class="space-y-1.5 mb-3">
                      <div class="flex items-center justify-between text-xs text-gray-500 font-mono bg-black/20 px-2 py-1 rounded">
                        <span>HOST</span>
                        <span class="text-gray-400 truncate max-w-[120px]" :title="node.host">{{ node.host }}</span>
                      </div>
                      <div class="flex items-center justify-between text-xs font-mono px-2">
                        <span class="text-gray-500">PORT</span>
                        <span class="text-gray-300">{{ node.port }}</span>
                      </div>
                    </div>

                    <div class="flex items-center justify-between pt-2 border-t border-white/5">
                      <div class="flex gap-3 text-xs font-mono">
                        <span :class="getDelayClass(node.delay)" class="font-bold">
                           {{ node.delay > 0 ? node.delay + 'ms' : '- ms' }}
                        </span>
                        <span class="text-blue-400 font-bold">
                          {{ node.speed > 0 ? node.speed.toFixed(1) + ' MB/s' : '- MB/s' }}
                        </span>
                      </div>
                      
                      <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <n-button text size="tiny" class="text-gray-400 hover:text-emerald-400" @click="copyNode(node)">
                          复制
                        </n-button>
                        <span class="text-gray-700">|</span>
                        <n-button text size="tiny" class="text-gray-400 hover:text-emerald-400" @click="showQRCode(node)">
                          二维码
                        </n-button>
                         <span class="text-gray-700">|</span>
                        <n-button text size="tiny" class="text-gray-400 hover:text-emerald-400" @click="testSingleNode(node)">
                          测试
                        </n-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          
          <div v-else class="h-full flex flex-col items-center justify-center text-gray-500 py-20">
            <div class="w-20 h-20 rounded-full bg-white/5 flex items-center justify-center mb-4 animate-pulse">
              <span class="text-4xl opacity-50">📡</span>
            </div>
            <p class="mb-4 font-mono text-sm">暂无节点数据，请启动扫描</p>
            <n-button type="info" ghost @click="triggerScan">开始全网扫描</n-button>
          </div>
        </div>
      </div>
    </div>

    <n-modal v-model:show="showAddSourceModal">
      <n-card
        style="width: 600px; background: #1e1e20; border: 1px solid rgba(255,255,255,0.1);"
        title="添加自定义订阅源"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <div class="space-y-4">
          <p class="text-gray-400 text-sm">请输入 V2Ray / Clash / 纯文本 订阅链接 (HTTP/HTTPS)</p>
          <n-input v-model:value="newSourceUrl" placeholder="https://example.com/subscribe" type="text" />
          <div class="flex justify-end gap-2 mt-4">
            <n-button @click="showAddSourceModal = false">取消</n-button>
            <n-button type="primary" @click="addSource" :loading="addingSource">确定添加</n-button>
          </div>
        </div>
      </n-card>
    </n-modal>

    <n-modal v-model:show="showQRCodeModal">
       <div class="bg-[#1e1e20] p-6 rounded-xl border border-emerald-500/30 text-center flex flex-col items-center">
          <h3 class="text-emerald-400 font-bold mb-4 font-mono">节点二维码</h3>
          <img v-if="qrCodeData" :src="qrCodeData" class="rounded-lg w-48 h-48 bg-white p-2" />
          <div v-else class="w-48 h-48 flex items-center justify-center text-gray-500">生成中...</div>
          <p class="text-gray-500 text-xs mt-4">请使用客户端 (Shadowrocket/v2rayNG) 扫码</p>
       </div>
    </n-modal>

  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import axios from 'axios';
import { NButton, NTag, NModal, NCard, NInput, createDiscreteApi, darkTheme } from 'naive-ui';

const COUNTRY_MAP = {
  'CN': { flag: '🇨🇳', name: '中国' },
  'HK': { flag: '🇭🇰', name: '香港' },
  'TW': { flag: '🇹🇼', name: '台湾' },
  'MO': { flag: '🇲🇴', name: '澳门' },
  'US': { flag: '🇺🇸', name: '美国' },
  'JP': { flag: '🇯🇵', name: '日本' },
  'SG': { flag: '🇸🇬', name: '新加坡' },
  'KR': { flag: '🇰🇷', name: '韩国' },
  'RU': { flag: '🇷🇺', name: '俄罗斯' },
  'GB': { flag: '🇬🇧', name: '英国' },
  'DE': { flag: '🇩🇪', name: '德国' },
  'FR': { flag: '🇫🇷', name: '法国' },
  'CA': { flag: '🇨🇦', name: '加拿大' },
  'AU': { flag: '🇦🇺', name: '澳洲' },
  'IN': { flag: '🇮🇳', name: '印度' },
  'BR': { flag: '🇧🇷', name: '巴西' },
  'UNK': { flag: '🌐', name: '未知区域' }
};

const stats = ref({ count: 0, running: false, logs: [], nodes: [] });
const logRef = ref(null);
const testingAll = ref(false);

// 弹窗状态
const showAddSourceModal = ref(false);
const newSourceUrl = ref('');
const addingSource = ref(false);
const showQRCodeModal = ref(false);
const qrCodeData = ref('');

const { message } = createDiscreteApi(['message'], {
  configProviderProps: { theme: darkTheme }
});

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
});

function getCountryInfo(code) {
  if (!code) return COUNTRY_MAP['UNK'];
  const upperCode = code.toUpperCase();
  return COUNTRY_MAP[upperCode] || { flag: '🚩', name: upperCode };
}

function getProtocolColor(proto) {
  const p = (proto || '').toLowerCase();
  if (p.includes('vmess')) return 'success';
  if (p.includes('vless')) return 'info';
  if (p.includes('trojan')) return 'warning';
  if (p.includes('ss')) return 'error';
  return 'default';
}

function getDelayClass(delay) {
  if (!delay || delay < 0) return 'text-gray-500';
  if (delay < 200) return 'text-emerald-400';
  if (delay < 500) return 'text-yellow-400';
  return 'text-red-400';
}

async function fetchStats() {
  try {
    const response = await api.get('/nodes/stats');
    stats.value = response.data;
    await nextTick();
    if (logRef.value) logRef.value.scrollTop = 0;
  } catch (error) {
    // silent fail
  }
}

async function triggerScan() {
  try {
    addLog('🚀 正在启动全网扫描...');
    await api.post('/nodes/trigger');
    fetchStats();
  } catch (error) {
    addLog(`❌ 启动失败: ${error.message}`);
  }
}

async function testAllNodes() {
  testingAll.value = true;
  addLog('🧪 开始全量并发测试...');
  try {
    await api.post('/nodes/test_all');
    const interval = setInterval(async () => {
      await fetchStats();
      if (!stats.value.running) {
        testingAll.value = false;
        clearInterval(interval);
        addLog('🎉 全部测试完成');
      }
    }, 2000);
  } catch (error) {
    testingAll.value = false;
    addLog(`❌ 测试启动失败: ${error.message}`);
  }
}

// 🔥 真实测试单个节点
async function testSingleNode(node) {
  node.isTesting = true;
  try {
    const res = await api.post('/nodes/test_single', {
      host: node.host,
      port: node.port
    });
    
    if (res.data.status === 'ok') {
      message.success(`测试完成: ${res.data.result.total_score}分`);
      // 简单更新一下UI数据，不必等轮询
      node.delay = res.data.result.tcp_ping_ms;
      node.alive = res.data.result.total_score > 0;
    } else {
      message.error('测试失败');
    }
  } catch (e) {
    message.error('请求异常');
  } finally {
    node.isTesting = false;
  }
}

// 🔥 显示二维码
async function showQRCode(node) {
  showQRCodeModal.value = true;
  qrCodeData.value = ''; // clear previous
  try {
    const res = await api.get('/nodes/qrcode', {
      params: { host: node.host, port: node.port }
    });
    if (res.data.qrcode_data) {
      qrCodeData.value = res.data.qrcode_data;
    } else {
      message.error('无法生成二维码');
      showQRCodeModal.value = false;
    }
  } catch (e) {
    message.error('获取二维码失败');
    showQRCodeModal.value = false;
  }
}

// 🔥 添加自定义源
async function addSource() {
  if (!newSourceUrl.value) return;
  addingSource.value = true;
  try {
    const res = await api.post('/nodes/add_source', { url: newSourceUrl.value });
    if (res.data.status === 'ok') {
      message.success('添加成功，已加入扫描队列');
      showAddSourceModal.value = false;
      newSourceUrl.value = '';
    } else {
      message.error(res.data.message || '添加失败');
    }
  } catch (e) {
    message.error('请求失败');
  } finally {
    addingSource.value = false;
  }
}

function copyNode(node) {
  const link = node.share_link || `${node.protocol}://${node.host}:${node.port}`;
  navigator.clipboard.writeText(link).then(() => {
    message.success(`已复制: ${node.name}`);
  });
}

async function copySubscription() {
  try {
    const { data } = await api.get('/nodes/subscription');
    if (data.subscription) {
      await navigator.clipboard.writeText(data.subscription);
      message.success('订阅链接已复制');
      addLog('✅ 订阅链接已生成');
    } else {
      message.warning('暂无可用订阅');
    }
  } catch (e) {
    message.error('获取订阅失败');
  }
}

function addLog(msg) {
  const ts = new Date().toLocaleTimeString();
  stats.value.logs.unshift(`[${ts}] ${msg}`);
  if (stats.value.logs.length > 100) stats.value.logs.pop();
}

onMounted(() => {
  fetchStats();
  const timer = setInterval(fetchStats, 3000);
  return () => clearInterval(timer);
});
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #1e1e20;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #10b981; 
}

.glow-effect {
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
  transition: all 0.3s ease;
}
.glow-effect:hover {
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.5);
  transform: translateY(-1px);
}
</style>