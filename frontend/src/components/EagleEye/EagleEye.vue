<template>
    <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
      <n-global-style />
      <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
        
        <div class="header bg-[#1e1e20]/90 backdrop-blur-md border border-white/10 rounded-full p-2 mb-3 shadow-2xl flex flex-wrap justify-center items-center gap-4 mx-auto w-fit max-w-full">
      
      <div class="flex items-center gap-3 pl-2">
        <div class="p-1.5 bg-gradient-to-br from-teal-500/20 to-emerald-500/20 rounded-full border border-teal-500/30">
          <span class="text-lg">🦅</span>
        </div>
        <div class="flex flex-col leading-none">
          <h1 class="text-sm font-bold text-white m-0">Eagle Eye</h1>
          <span class="text-[10px] text-teal-400 font-mono scale-90 origin-left">Pro Audit</span>
        </div>
      </div>

      <div class="w-px h-6 bg-white/10 hidden sm:block"></div>

      <div class="flex items-center gap-3 pr-2 text-[10px] font-mono">
        <div class="flex items-center gap-1.5 bg-black/30 px-2 py-1 rounded-full">
          <span class="text-gray-500">ID:</span>
          <span class="text-amber-400 font-bold">{{ status.identity?.mac || 'Init...' }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="text-gray-500">CHAIN:</span>
          <span v-if="status.active_chain?.length" class="text-teal-400 font-bold">{{ status.active_chain.length }} Nodes</span>
          <span v-else class="text-red-500 font-bold">OFF</span>
        </div>
      </div>
    </div>
  
        <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
          
          <div class="w-full lg:w-1/3 flex flex-col gap-4 min-h-[400px]">
            
            <div class="flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden shrink-0">
              <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center">
                <span class="font-bold text-gray-300">🎯 TARGET INPUT</span>
                <div class="flex bg-black rounded p-0.5 border border-gray-700">
                  <button 
                    @click="scanMode = 'active'"
                    class="px-3 py-1 text-xs rounded transition-all duration-300 flex items-center gap-1"
                    :class="scanMode === 'active' ? 'bg-cyan-600 text-white shadow-[0_0_10px_rgba(8,145,178,0.5)]' : 'text-gray-500 hover:text-gray-300'"
                  >
                    <span>🔫</span> 实战
                  </button>
                  <button 
                    @click="scanMode = 'shodan'"
                    class="px-3 py-1 text-xs rounded transition-all duration-300 flex items-center gap-1"
                    :class="scanMode === 'shodan' ? 'bg-orange-600 text-white shadow-[0_0_10px_rgba(234,88,12,0.5)]' : 'text-gray-500 hover:text-gray-300'"
                  >
                    <span>🔍</span> Shodan
                  </button>
                </div>
              </div>
              
              <div class="p-4 bg-[#161616]">
                <n-input
                  v-model:value="targetInput"
                  type="textarea"
                  placeholder="[实战模式] 输入 IP: 192.168.1.0/24
  [Shodan模式] 输入关键词:
  - webcam
  - Hikvision
  - port:554 country:CN"
                  :disabled="status.running"
                  class="font-mono text-xs !bg-[#0a0a0a] !border-gray-800 text-cyan-300"
                  :rows="5"
                />
                
                <div class="mt-4">
                  <n-button 
                    v-if="!status.running" 
                    type="primary" 
                    class="w-full font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]"
                    :class="scanMode === 'shodan' ? '!bg-orange-600 hover:!bg-orange-500' : ''"
                    @click="startScan"
                    :disabled="!targetInput"
                    size="large"
                  >
                    <template #icon>{{ scanMode === 'shodan' ? '🔍' : '⚡' }}</template>
                    {{ scanMode === 'shodan' ? 'SHODAN SEARCH' : 'START AUDIT' }}
                  </n-button>
  
                  <n-button 
                    v-else 
                    type="error" 
                    class="w-full font-bold animate-pulse shadow-[0_0_15px_rgba(239,68,68,0.6)]"
                    @click="stopScan"
                    size="large"
                  >
                    <template #icon>🛑</template> STOP TASK
                  </n-button>
                </div>
              </div>
            </div>
  
            <div class="flex-1 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden min-h-[200px]">
              <div class="p-2 bg-[#111] border-b border-gray-800 flex items-center justify-between">
                <span class="text-[10px] text-gray-500 font-mono">AUDIT PROCESS LOGS</span>
                <div v-if="status.running" class="flex items-center gap-1">
                  <span class="w-2 h-2 bg-emerald-500 rounded-full animate-ping"></span>
                  <span class="text-[10px] text-emerald-500">LIVE</span>
                </div>
              </div>
              <div class="flex-1 p-3 overflow-y-auto font-mono text-[10px] space-y-1 custom-scrollbar bg-black" ref="logRef">
                <div v-for="(log, i) in status.logs" :key="i" class="text-gray-400 border-b border-gray-900/50 pb-0.5 mb-0.5 last:text-cyan-400 last:font-bold break-all">
                  > {{ log }}
                </div>
              </div>
            </div>
          </div>
  
          <div class="w-full lg:w-2/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden">
            <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
              <span class="font-bold text-gray-300">ASSETS DISCOVERED</span>
              <n-tag type="info" size="small" round>{{ status.results.length }} RESULTS</n-tag>
            </div>
            
            <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#161616]">
              <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 content-start">
                
                <div v-for="(item, i) in status.results" :key="i" 
                     class="bg-[#202020] border border-gray-700 rounded-lg p-3 hover:border-cyan-500/50 transition-all group relative overflow-hidden"
                     :class="{'border-l-4 !border-l-orange-500': item.risk === 'HIGH'}">
                  
                  <div class="flex justify-between items-start mb-2 border-b border-gray-700 pb-2">
                    <span class="font-bold text-gray-200 text-sm tracking-wide">{{ item.ip }}:{{ item.port }}</span>
                    <span class="text-[10px] text-gray-500">{{ item.timestamp }}</span>
                  </div>
  
                  <div class="flex flex-col gap-1 mb-3">
                    <div class="flex items-center gap-2">
                      <span class="text-cyan-400 text-xs font-bold">📷 {{ item.brand }}</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-[10px] bg-[#1a1a1a] px-1.5 rounded text-gray-400">via {{ item.proxy }}</span>
                    </div>
                  </div>
  
                  <div class="flex justify-between items-center mt-auto pt-2">
                    <span class="font-bold text-xs" :class="item.status === 'OPEN' ? 'text-emerald-400' : 'text-red-400'">
                      {{ item.status }}
                    </span>
                    
                    <n-button 
                      size="tiny" 
                      type="error" 
                      ghost
                      class="group-hover:bg-red-500/10"
                      @click="crack(item.ip)" 
                      :disabled="item.status === 'OPEN'"
                    >
                      <template #icon>🔨</template> CRACK
                    </n-button>
                  </div>
                </div>
  
              </div>
  
              <div v-if="status.results.length === 0" class="flex flex-col items-center justify-center h-full text-gray-600 py-10">
                <span class="text-6xl mb-4 opacity-20">📡</span>
                <p class="text-sm font-mono">等待任务指令...</p>
              </div>
            </div>
          </div>
  
        </div>
  
      </div>
    </n-config-provider>
  </template>
  
  <script setup>
  import { ref, onMounted, onUnmounted, nextTick } from 'vue';
  import axios from 'axios';
  // 🔥 引入 Naive UI
  import { NConfigProvider, NGlobalStyle, NButton, NTag, NInput, darkTheme } from 'naive-ui';
  
  // 🔥 主题配置 (青色系)
  const themeOverrides = {
    common: {
      primaryColor: '#06b6d4', // Cyan 500
      primaryColorHover: '#22d3ee',
      primaryColorPressed: '#0891b2',
    },
  };
  
  // --- 以下业务逻辑保持 100% 原样 ---
  
  const targetInput = ref('127.0.0.1\n192.168.1.0/24');
  const scanMode = ref('active'); // 默认模式
  const status = ref({ running: false, logs: [], results: [] });
  const logRef = ref(null);
  let timer = null;
  
  const api = axios.create({ baseURL: `${import.meta.env.VITE_API_BASE_URL}/api/eagle-eye` }); 
  
  const startScan = async () => {
      if (!targetInput.value) return;
      try {
          await api.post('/scan', {
              target: targetInput.value,
              mode: scanMode.value
          });
      } catch (e) {
          alert("启动失败: " + e.message);
      }
  };
  
  const stopScan = async () => {
      try {
          await api.post('/stop');
      } catch (e) {
          alert("停止指令发送失败");
      }
  };
  
  const crack = async (ip) => {
      await api.post('/crack', null, { params: { ip } });
      alert("已加入爆破队列");
  };
  
  const fetchStatus = async () => {
      try {
          const res = await api.get('/status');
          status.value = res.data;
          nextTick(() => { if (logRef.value && status.value.running) logRef.value.scrollTop = 0; });
      } catch (e) { }
  };
  
  onMounted(() => {
      fetchStatus();
      timer = setInterval(fetchStatus, 1000);
  });
  
  onUnmounted(() => clearInterval(timer));
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
    background: #06b6d4;
  }
  </style>