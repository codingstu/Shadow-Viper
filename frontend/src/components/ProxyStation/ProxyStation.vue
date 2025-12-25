<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-global-style />
    <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
      
      <div class="shrink-0 text-center mb-4 md:mb-6">
        <h1 class="text-2xl md:text-3xl font-bold text-primary bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500">
          🌐 代理猎手池 Proxy Hunter Pool
        </h1>
        <p class="text-xs md:text-sm text-gray-500 mt-2">
          <n-tag size="small" :bordered="false" class="bg-emerald-900/30 text-emerald-400 mr-2">v1.3 HTTPS版</n-tag>
          基于付费通道的全球免费代理采集与清洗系统
        </p>
      </div>

      <div class="shrink-0 mb-4 max-w-7xl mx-auto w-full">
        <div class="bg-[#1e1e1e] p-3 rounded-xl border border-gray-800 shadow-lg flex flex-col md:flex-row items-center justify-between gap-4">
          
          <div class="flex items-center gap-6 w-full md:w-auto justify-center md:justify-start">
            <div class="flex flex-col items-center">
              <span class="text-xs text-gray-500 mb-1">存活数量</span>
              <span class="text-2xl font-bold text-emerald-400 font-mono">{{ stats.count }}</span>
            </div>
            <div class="h-8 w-px bg-gray-700"></div>
            <div class="flex flex-col items-center">
              <span class="text-xs text-gray-500 mb-1">引擎状态</span>
              <div class="flex items-center gap-2">
                <span class="relative flex h-3 w-3" v-if="stats.running">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
                </span>
                <span :class="stats.running ? 'text-amber-400' : 'text-gray-400'" class="font-bold text-sm">
                  {{ stats.running ? '清洗中...' : '等待指令' }}
                </span>
              </div>
            </div>
          </div>

          <div class="flex gap-2 w-full md:w-auto">
            <n-button 
              type="primary" 
              class="flex-1 md:flex-none shadow-[0_0_15px_rgba(66,185,131,0.4)]"
              @click="triggerTask"
              :loading="stats.running"
              :disabled="stats.running"
            >
              <template #icon>🚀</template>
              {{ stats.running ? '扫描全球节点...' : '启动 IP 狩猎' }}
            </n-button>
            <n-button secondary type="info" @click="fetchData" class="flex-1 md:flex-none">
              <template #icon>🔄</template> 刷新
            </n-button>
            <n-button secondary type="error" @click="cleanPool" class="flex-1 md:flex-none">
              <template #icon>🗑️</template> 清空
            </n-button>
          </div>
        </div>
      </div>

      <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
        
        <div class="w-full lg:w-1/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden order-2 lg:order-1 h-1/3 lg:h-auto">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <span class="font-bold text-gray-300">📟 运行终端 (Terminal)</span>
          </div>
          <div class="flex-1 overflow-y-auto p-4 bg-black font-mono text-xs space-y-1 custom-scrollbar">
            <div v-for="(log, i) in stats.logs" :key="i" class="border-b border-gray-800/50 pb-1 mb-1 text-gray-400 last:text-emerald-400 last:font-bold">
              <span class="text-gray-600 mr-2">></span>{{ log }}
            </div>
            <div v-if="stats.logs.length === 0" class="text-gray-600 italic mt-4 text-center">
              > 系统就绪，等待启动...
            </div>
          </div>
        </div>

        <div class="w-full lg:w-2/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden order-1 lg:order-2 flex-1">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <div class="flex items-center gap-2">
              <span class="font-bold text-gray-300">🏆 优质代理排行榜 (Top 100)</span>
            </div>
            <code class="text-[10px] text-gray-600 bg-[#121212] px-2 py-1 rounded">API: /api/proxy_pool/pop</code>
          </div>

          <div class="flex-1 overflow-auto custom-scrollbar bg-[#161616]">
            <table class="w-full text-left border-collapse">
              <thead class="bg-[#252525] sticky top-0 z-10 text-xs uppercase text-gray-500 font-bold">
                <tr>
                  <th class="p-3 w-40">IP 地址</th>
                  <th class="p-3 w-24">端口</th>
                  <th class="p-3 w-24">协议</th>
                  <th class="p-3 w-32">响应速度</th>
                  <th class="p-3">最后验证</th>
                </tr>
              </thead>
              <tbody class="text-sm font-mono divide-y divide-gray-800">
                <tr v-for="p in proxyList" :key="p.ip + p.port" class="hover:bg-white/5 transition-colors group">
                  <td class="p-3 text-emerald-400 font-bold tracking-wide">{{ p.ip }}</td>
                  <td class="p-3 text-gray-300">{{ p.port }}</td>
                  <td class="p-3">
                    <n-tag size="tiny" :bordered="false" class="bg-gray-800 text-gray-400 group-hover:bg-gray-700 transition-colors">
                      {{ p.protocol.toUpperCase() }}
                    </n-tag>
                  </td>
                  <td class="p-3">
                    <div class="flex items-center gap-2">
                      <span class="w-2 h-2 rounded-full" :class="{
                        'bg-emerald-500 shadow-[0_0_5px_#10b981]': getSpeedLevel(p.speed) === 'fast',
                        'bg-amber-500': getSpeedLevel(p.speed) === 'medium',
                        'bg-red-500': getSpeedLevel(p.speed) === 'slow'
                      }"></span>
                      <span :class="{
                        'text-emerald-400': getSpeedLevel(p.speed) === 'fast',
                        'text-amber-400': getSpeedLevel(p.speed) === 'medium',
                        'text-red-400': getSpeedLevel(p.speed) === 'slow'
                      }">{{ p.speed }} ms</span>
                    </div>
                  </td>
                  <td class="p-3 text-gray-500 text-xs">{{ formatTime(p.last_check) }}</td>
                </tr>
                
                <tr v-if="proxyList.length === 0">
                  <td colspan="5" class="p-10 text-center text-gray-600">
                    <div class="text-5xl mb-4 opacity-20">🕸️</div>
                    <p>暂无有效代理</p>
                    <p class="text-xs mt-2">请点击左上方按钮开始抓取</p>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
// 🔥 引入 Naive UI
import { NConfigProvider, NGlobalStyle, NButton, NTag, darkTheme } from 'naive-ui';

// 🔥 主题配置 (保持统一)
const themeOverrides = {
  common: {
    primaryColor: '#42b983',
    primaryColorHover: '#5cd29d',
    primaryColorPressed: '#2a9163',
  },
};

// --- 以下业务逻辑保持 100% 原样 ---

const stats = ref({ count: 0, running: false, logs: [] });
const proxyList = ref([]);
let timer = null;

const getSpeedLevel = (ms) => {
  if (ms < 500) return 'fast';
  if (ms < 1500) return 'medium';
  return 'slow';
};

const formatTime = (timeStr) => {
  return timeStr.split(' ')[1];
};

const fetchData = async () => {
  try {
    const resStats = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/proxy_pool/stats`); 
    stats.value = await resStats.json();

    const resList = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/proxy_pool/list`); 
    proxyList.value = await resList.json();
  } catch (e) {
    console.error("API Error", e);
  }
};

const triggerTask = async () => {
  if (stats.value.running) return;
  try {
    await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/proxy_pool/trigger`, { method: 'POST' }); 
    fetchData();
  } catch (e) { alert("连接后端失败"); }
};

const cleanPool = async () => {
  if (!confirm("确定要清空所有代理吗？")) return;
  try {
    await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/proxy_pool/clean`, { method: 'DELETE' }); 
    fetchData();
  } catch (e) { alert("清空失败"); }
};


onMounted(() => {
  fetchData();
  timer = setInterval(fetchData, 2000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
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