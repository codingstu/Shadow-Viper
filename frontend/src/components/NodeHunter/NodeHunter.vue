<template>
  <div class="node-hunter p-4 h-full flex flex-col gap-4 text-gray-200 relative">
    
    <transition name="fade">
      <div v-if="testingAll || stats.running" class="absolute top-0 left-0 right-0 z-50">
        <n-progress 
          type="line" 
          :percentage="progressPercentage" 
          :show-indicator="false" 
          processing 
          color="#10b981" 
          height="3" 
        />
      </div>
    </transition>

    <div class="header bg-[#1e1e20]/90 backdrop-blur-md border border-white/10 rounded-full p-2 mb-3 shadow-2xl flex flex-wrap justify-center items-center gap-4 mx-auto w-fit max-w-full">
      
      <div class="flex items-center gap-3 pl-2">
        <div class="p-1.5 bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 rounded-full border border-emerald-500/30">
          <span class="text-lg">🛰️</span>
        </div>
        <div class="flex flex-col leading-none">
          <h1 class="text-sm font-bold text-white m-0">节点猎手</h1>
          <span class="text-[10px] text-emerald-400 font-mono scale-90 origin-left">Node Hunter</span>
        </div>
      </div>

      <div class="w-px h-6 bg-white/10 hidden sm:block"></div>

      <div class="flex items-center gap-3 hidden sm:flex">
        <div class="flex flex-col items-center leading-none">
          <span class="text-[9px] text-gray-500 uppercase">ACTIVE</span>
          <span class="text-xs font-bold text-emerald-400 font-mono">{{ stats.count }}</span>
        </div>
        <n-tag v-if="nextScanTimeStr" size="tiny" :bordered="false" class="bg-black/40 text-gray-400 font-mono scale-90">
          ⏱️ {{ nextScanTimeStr }}
        </n-tag>
      </div>

      <div class="w-px h-6 bg-white/10 hidden sm:block"></div>

      <div class="flex items-center gap-3 pr-2">
        <div class="flex items-center gap-2 bg-black/30 px-2 py-1 rounded-full text-xs text-gray-300">
          <span class="text-gray-500">Socks/HTTP</span>
          <n-switch size="small" :value="showSocksHttp" @update:value="toggleSocksHttp" />
        </div>

        <div class="flex items-center gap-2 bg-black/30 px-2 py-1 rounded-full text-xs text-gray-300">
          <span class="text-gray-500">中国节点</span>
          <n-switch size="small" :value="showChinaNodes" @update:value="toggleChinaNodes" />
        </div>

        <n-button secondary circle size="tiny" type="primary" @click="showAddSourceModal = true" title="添加源">
          <template #icon>➕</template>
        </n-button>

        <n-button-group size="tiny">
          <n-button type="primary" secondary @click="copySubscription" title="复制订阅">
            <template #icon>📥</template>
          </n-button>
          <n-button type="primary" secondary @click="importToClash" title="导入 Clash">
            <template #icon>🚀</template>
          </n-button>
        </n-button-group>
        
        <n-button type="warning" secondary size="tiny" @click="testAllNodes" :loading="testingAll" :disabled="stats.running">
          {{ testingAll ? '测试中' : '测速' }}
        </n-button>

        <n-button type="info" size="tiny" @click="triggerScan" :loading="stats.running" class="glow-effect">
          <template #icon>📡</template> {{ stats.running ? '扫描中' : '扫描' }}
        </n-button>

        <n-button type="success" size="tiny" @click="syncToSupabase" :loading="syncing" :disabled="syncing">
          <template #icon>☁️</template> {{ syncing ? '同步中' : '同步DB' }}
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
        <div class="flex-1 p-4 bg-[#121212] font-mono text-xs text-gray-300 overflow-y-auto custom-scrollbar" ref="logRef" @scroll="handleLogScroll">
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
            显示 {{ filteredCount }} / 总计 {{ stats.count }}
          </n-tag>
        </div>
        
        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#161618]">
          <template v-if="filteredGroups.length > 0">
            <div class="flex flex-col gap-4">
              <div 
                v-for="group in filteredGroups" 
                :key="group.group_name" 
                class="border border-white/10 rounded-xl overflow-hidden bg-[#1e1e20]"
              >
                <div class="px-4 py-3 bg-white/5 border-b border-white/5 flex justify-between items-center">
                  <div class="flex items-center gap-2 font-bold text-gray-200">
                    <span class="text-lg">{{ getCountryInfo(group.group_name).flag }}</span>
                    <span>{{ getCountryInfo(group.group_name).name }}</span>
                    <span class="text-xs text-gray-500 ml-1 font-mono">({{ group.group_name }})</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <n-tag size="small" round :bordered="false" class="bg-black/40 text-gray-400">
                      {{ group.nodes.length }}
                    </n-tag>
                    <n-button text size="tiny" class="text-gray-400 hover:text-emerald-400" @click="toggleGroup(group.group_name)">
                      {{ isGroupExpanded(group.group_name) ? '折叠' : '展开' }}
                    </n-button>
                  </div>
                </div>

                <div v-if="isGroupExpanded(group.group_name)" class="p-3 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-3 gap-3">
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
                          快速测速
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
import { ref, onMounted, computed, nextTick } from 'vue';
import axios from 'axios';
import { NButton, NButtonGroup, NTag, NModal, NCard, NInput, NProgress, NSwitch, createDiscreteApi, darkTheme } from 'naive-ui';

const COUNTRY_MAP = {
  // 亚洲
  'CN': { flag: '🇨🇳', name: '中国' },
  'HK': { flag: '🇭🇰', name: '香港' },
  'TW': { flag: '🇹🇼', name: '台湾' },
  'MO': { flag: '🇲🇴', name: '澳门' },
  'JP': { flag: '🇯🇵', name: '日本' },
  'SG': { flag: '🇸🇬', name: '新加坡' },
  'KR': { flag: '🇰🇷', name: '韩国' },
  'TH': { flag: '🇹🇭', name: '泰国' },
  'MY': { flag: '🇲🇾', name: '马来西亚' },
  'PH': { flag: '🇵🇭', name: '菲律宾' },
  'VN': { flag: '🇻🇳', name: '越南' },
  'ID': { flag: '🇮🇩', name: '印度尼西亚' },
  'IN': { flag: '🇮🇳', name: '印度' },
  'PK': { flag: '🇵🇰', name: '巴基斯坦' },
  'BD': { flag: '🇧🇩', name: '孟加拉国' },
  'LK': { flag: '🇱🇰', name: '斯里兰卡' },
  // 中东
  'TR': { flag: '🇹🇷', name: '土耳其' },
  'AE': { flag: '🇦🇪', name: '阿联酋' },
  'SA': { flag: '🇸🇦', name: '沙特阿拉伯' },
  'IL': { flag: '🇮🇱', name: '以色列' },
  'JO': { flag: '🇯🇴', name: '约旦' },
  // 欧洲
  'GB': { flag: '🇬🇧', name: '英国' },
  'DE': { flag: '🇩🇪', name: '德国' },
  'FR': { flag: '🇫🇷', name: '法国' },
  'NL': { flag: '🇳🇱', name: '荷兰' },
  'BE': { flag: '🇧🇪', name: '比利时' },
  'IT': { flag: '🇮🇹', name: '意大利' },
  'ES': { flag: '🇪🇸', name: '西班牙' },
  'PT': { flag: '🇵🇹', name: '葡萄牙' },
  'PL': { flag: '🇵🇱', name: '波兰' },
  'SE': { flag: '🇸🇪', name: '瑞典' },
  'NO': { flag: '🇳🇴', name: '挪威' },
  'DK': { flag: '🇩🇰', name: '丹麦' },
  'FI': { flag: '🇫🇮', name: '芬兰' },
  'CH': { flag: '🇨🇭', name: '瑞士' },
  'AT': { flag: '🇦🇹', name: '奥地利' },
  'CZ': { flag: '🇨🇿', name: '捷克' },
  'HU': { flag: '🇭🇺', name: '匈牙利' },
  'RO': { flag: '🇷🇴', name: '罗马尼亚' },
  'GR': { flag: '🇬🇷', name: '希腊' },
  'RU': { flag: '🇷🇺', name: '俄罗斯' },
  'UA': { flag: '🇺🇦', name: '乌克兰' },
  'BG': { flag: '🇧🇬', name: '保加利亚' },
  // 北美
  'US': { flag: '🇺🇸', name: '美国' },
  'CA': { flag: '🇨🇦', name: '加拿大' },
  'MX': { flag: '🇲🇽', name: '墨西哥' },
  // 南美
  'BR': { flag: '🇧🇷', name: '巴西' },
  'AR': { flag: '🇦🇷', name: '阿根廷' },
  'CL': { flag: '🇨🇱', name: '智利' },
  'CO': { flag: '🇨🇴', name: '哥伦比亚' },
  'PE': { flag: '🇵🇪', name: '秘鲁' },
  'VE': { flag: '🇻🇪', name: '委内瑞拉' },
  // 大洋洲
  'AU': { flag: '🇦🇺', name: '澳洲' },
  'NZ': { flag: '🇳🇿', name: '新西兰' },
  // 非洲
  'ZA': { flag: '🇿🇦', name: '南非' },
  'EG': { flag: '🇪🇬', name: '埃及' },
  'NG': { flag: '🇳🇬', name: '尼日利亚' },
  'UNK': { flag: '🌐', name: '未知区域' }
};

const stats = ref({ count: 0, running: false, logs: [], nodes: [], next_scan_time: null });
const logRef = ref(null);
const testingAll = ref(false);
const syncing = ref(false);  // 🔥 Supabase 同步状态
// 为了动画效果
const progressPercentage = ref(0);

// 展示控制
const showSocksHttp = ref(false);
const showChinaNodes = ref(false);
const expandedGroups = ref({});

// 日志滚动控制
const userScrolling = ref(false);
const scrollCheckTimeout = ref(null);

// 弹窗状态
const showAddSourceModal = ref(false);
const newSourceUrl = ref('');
const addingSource = ref(false);
const showQRCodeModal = ref(false);
const qrCodeData = ref('');
const currentTime = ref(Date.now());

const { message } = createDiscreteApi(['message'], {
  configProviderProps: { theme: darkTheme }
});

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
});

// 🔥 计算倒计时
const nextScanTimeStr = computed(() => {
  if (!stats.value.next_scan_time) return '';
  const diff = stats.value.next_scan_time * 1000 - currentTime.value;
  if (diff <= 0) return '00:00';
  const minutes = Math.floor(diff / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
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

function groupNodesByCountry(nodes = []) {
  const countryMap = {};
  nodes.forEach(node => {
    const code = (node.country || 'UNK').toUpperCase();
    if (!countryMap[code]) countryMap[code] = [];
    countryMap[code].push(node);
  });

  const priority = ['CN', 'HK', 'TW', 'US', 'JP', 'SG', 'KR'];
  const groups = [];
  priority.forEach(code => {
    if (countryMap[code]) {
      groups.push({ group_name: code, nodes: countryMap[code] });
      delete countryMap[code];
    }
  });
  Object.keys(countryMap).sort().forEach(code => {
    groups.push({ group_name: code, nodes: countryMap[code] });
  });
  return groups;
}

async function fetchStats() {
  try {
    const [metaRes, nodesRes] = await Promise.all([
      api.get('/nodes/stats'),
      api.get('/api/nodes', {
        params: {
          show_socks_http: showSocksHttp.value,
          show_china_nodes: showChinaNodes.value,
          limit: 500,
        },
      })
    ]);

    const groups = groupNodesByCountry(nodesRes.data || []);
    seedGroupExpansion(groups);

    stats.value = {
      ...metaRes.data,
      nodes: groups,
    };

    await nextTick();
    // 🔥 智能滚动：只在用户处于顶部时保持在顶部（最新日志在顶部），防止干扰用户阅读
    if (logRef.value && !userScrolling.value) {
      logRef.value.scrollTop = 0;
    }
  } catch (error) {
    // silent fail
  }
}

function seedGroupExpansion(groups) {
  groups.forEach(group => {
    if (expandedGroups.value[group.group_name] === undefined) {
      expandedGroups.value[group.group_name] = group.group_name !== 'CN';
    }
  });
}

function handleLogScroll() {
  // 🔥 检测用户是否离开顶部：如果 scrollTop > 10px，说明用户在阅读历史日志
  if (logRef.value) {
    userScrolling.value = logRef.value.scrollTop > 10;
    
    // 清除之前的延时，重新设置
    if (scrollCheckTimeout.value) clearTimeout(scrollCheckTimeout.value);
    
    // 3秒后如果用户仍未滚动，恢复自动更新（回到顶部）
    scrollCheckTimeout.value = setTimeout(() => {
      if (logRef.value && logRef.value.scrollTop <= 10) {
        userScrolling.value = false;
      }
    }, 3000);
  }
}

async function fetchToggleStatus() {
  try {
    const [{ data: socksStatus }, { data: chinaStatus }] = await Promise.all([
      api.get('/nodes/socks_http_status'),
      api.get('/nodes/china_nodes_status'),
    ]);
    showSocksHttp.value = !!socksStatus.show_socks_http;
    showChinaNodes.value = !!chinaStatus.show_china_nodes;
  } catch (error) {
    // silent fail, keep defaults (hidden)
  }
}

async function triggerScan() {
  try {
    addLog('🚀 正在启动全网扫描...');
    progressPercentage.value = 0; // Reset
    await api.post('/nodes/trigger');
    fetchStats();
  } catch (error) {
    addLog(`❌ 启动失败: ${error.message}`);
  }
}

// 🔥 手动触发 Supabase 数据库同步
async function syncToSupabase() {
  syncing.value = true;
  addLog('☁️ 正在同步数据到 Supabase...');
  try {
    const { data } = await api.post('/api/sync');
    if (data.success) {
      addLog(`✅ ${data.message}`);
      message.success(data.message);
    } else {
      addLog(`⚠️ 同步失败: ${data.message}`);
      message.warning(data.message);
    }
  } catch (error) {
    const errMsg = error.response?.data?.message || error.message;
    addLog(`❌ 同步出错: ${errMsg}`);
    message.error(`同步出错: ${errMsg}`);
  } finally {
    syncing.value = false;
  }
}

const filteredGroups = computed(() => stats.value.nodes || []);

const filteredCount = computed(() => filteredGroups.value.reduce((sum, group) => sum + group.nodes.length, 0));

async function testAllNodes() {
  testingAll.value = true;
  progressPercentage.value = 0;
  addLog('🧪 开始全量并发测试...');
  try {
    await api.post('/nodes/test_all');
    // 模拟进度条增加 (因为后端没返回实时进度)
    const pTimer = setInterval(() => {
      if (progressPercentage.value < 90) progressPercentage.value += 5;
    }, 500);
    
    const interval = setInterval(async () => {
      await fetchStats();
      if (!stats.value.running) {
        testingAll.value = false;
        clearInterval(interval);
        clearInterval(pTimer);
        progressPercentage.value = 100;
        setTimeout(() => progressPercentage.value = 0, 1000);
        addLog('🎉 全部测试完成');
      }
    }, 2000);
  } catch (error) {
    testingAll.value = false;
    addLog(`❌ 测试启动失败: ${error.message}`);
  }
}


async function testSingleNode(node) {
  node.isTesting = true;
  
  // 🔥 智能测速：前端先试 → 失败则后端降级（HEAD 请求 < 1KB 流量）
  
  try {
    let delay = -1;
    let speed = 0;
    let method = 'unknown';
    
    // 方案 1：前端直测（如果没有 CORS 问题）
    try {
      const testUrl = `http://${node.host}:${node.port}/`;
      const startTime = performance.now();
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      
      await fetch(testUrl, {
        method: 'HEAD',
        mode: 'no-cors', // 绕过 CORS
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      delay = Math.round(performance.now() - startTime);
      method = 'frontend';
      
      console.log(`[前端测试成功] ${delay}ms`);
    } catch (frontendErr) {
      console.log(`[前端测试失败] ${frontendErr.message}，降级到后端`);
      
      // 方案 2：后端测试（HEAD 请求，极少流量 < 1KB）
      const res = await api.post('/nodes/test_single', {
        host: node.host,
        port: node.port,
      });
      
      if (res.data.status === 'ok') {
        delay = Number(res.data.delay) || -1;
        method = 'backend';
        console.log(`[后端测试成功] ${delay}ms`);
      } else {
        throw new Error('后端测试也失败');
      }
    }
    
    // 基于真实延迟估算速度
    if (delay > 0) {
      if (delay < 50) speed = 500;
      else if (delay < 100) speed = 200;
      else if (delay < 200) speed = 100;
      else if (delay < 500) speed = 50;
      else if (delay < 1000) speed = 20;
      else speed = 5;
    }
    
    console.log(`[${method}] ${delay}ms → ${speed} MB/s`);
    message.success(`✅ 测试完成 - 延迟: ${delay}ms | 速度: ${speed.toFixed(1)} MB/s`);
    
    node.delay = delay;
    node.speed = speed;
    node.alive = true;
    
    // 异步缓存（可选）
    try {
      await api.post('/nodes/cache_test_result', {
        host: node.host,
        port: node.port,
        delay: delay,
        speed: speed,
      });
    } catch (cacheErr) {
      console.warn('缓存失败:', cacheErr.message);
    }
  } catch (e) {
    message.error(`❌ 测试失败: ${e.message}`);
    node.alive = false;
    node.speed = 0;
    node.delay = -1;
  } finally {
    node.isTesting = false;
  }
}


async function showQRCode(node) {
  showQRCodeModal.value = true;
  qrCodeData.value = '';
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

// 🔥 一键导入 Clash
function importToClash() {
  // 构造 clash:// 协议链接
  // 需要后端的完整 Clash 订阅地址
  const baseUrl = import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '');
  const configUrl = encodeURIComponent(`${baseUrl}/nodes/clash/config`);
  const clashUrl = `clash://install-config?url=${configUrl}&name=SpiderFlow_Nodes`;
  
  // 尝试打开
  window.location.href = clashUrl;
  message.success('正在尝试唤起 Clash...');
}

function copyNode(node) {
  const link = node.share_link || `${node.protocol}://${node.host}:${node.port}`;
  navigator.clipboard.writeText(link).then(() => {
    message.success(`已复制: ${node.name}`);
  });
}

async function toggleSocksHttp(value) {
  showSocksHttp.value = value;
  try {
    await api.post('/nodes/toggle_socks_http', null, { params: { show: value } });
    fetchStats();
  } catch (e) {
    showSocksHttp.value = !value;
    message.error('更新 socks/http 显示状态失败');
  }
}

async function toggleChinaNodes(value) {
  showChinaNodes.value = value;
  try {
    await api.post('/nodes/toggle_china_nodes', null, { params: { show: value } });
    if (value && expandedGroups.value['CN'] === undefined) {
      expandedGroups.value['CN'] = false;
    }
    fetchStats();
  } catch (e) {
    showChinaNodes.value = !value;
    message.error('更新中国节点显示状态失败');
  }
}

function isGroupExpanded(name) {
  const val = expandedGroups.value[name];
  return val === undefined ? name !== 'CN' : val;
}

function toggleGroup(name) {
  expandedGroups.value[name] = !isGroupExpanded(name);
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
  fetchToggleStatus();
  fetchStats();
  const timer = setInterval(fetchStats, 3000);
  const timeTimer = setInterval(() => { currentTime.value = Date.now(); }, 1000); // 倒计时刷新
  return () => {
    clearInterval(timer);
    clearInterval(timeTimer);
  };
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

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>