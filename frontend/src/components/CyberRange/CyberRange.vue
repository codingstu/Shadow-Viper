<template>
    <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
      <n-global-style />
      <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
        
        <div class="header bg-[#1e1e20]/90 backdrop-blur-md border border-white/10 rounded-full p-2 mb-3 shadow-2xl flex flex-wrap justify-center items-center gap-4 mx-auto w-fit max-w-full">
      
      <div class="flex items-center gap-3 pl-2">
        <div class="p-1.5 bg-gradient-to-br from-red-500/20 to-rose-500/20 rounded-full border border-red-500/30">
          <span class="text-lg">🛡️</span>
        </div>
        <div class="flex flex-col leading-none">
          <h1 class="text-sm font-bold text-white m-0">Cyber Range</h1>
          <span class="text-[10px] text-red-400 font-mono scale-90 origin-left">Security Lab</span>
        </div>
      </div>

      <div class="w-px h-6 bg-white/10 hidden sm:block"></div>

      <div class="flex items-center gap-3 bg-black/20 px-3 py-1 rounded-full border border-white/5">
        <div class="flex items-center gap-1.5">
          <span class="text-[9px] text-gray-500">TARGETS</span>
          <span class="text-xs font-bold text-red-400 font-mono">{{ activeTargets }}/{{ totalTargets }}</span>
        </div>
        <div class="w-px h-3 bg-gray-700"></div>
        <div class="flex items-center gap-1.5">
          <span class="text-[9px] text-gray-500">LOGS</span>
          <span class="text-xs font-bold text-amber-400 font-mono">{{ capturedRequests }}</span>
        </div>
      </div>

      <div class="w-px h-6 bg-white/10 hidden sm:block"></div>

      <div class="flex items-center gap-2 pr-2">
        <n-button secondary type="info" size="tiny" @click="checkBackend">
          <template #icon>🔄</template>
        </n-button>
        <n-button secondary size="tiny" @click="showConfigPanel = true">
          <template #icon>⚙️</template> 配置
        </n-button>
      </div>
    </div>
  
        <div class="shrink-0 mb-4 max-w-7xl mx-auto w-full">
          <div class="bg-[#1e1e1e] p-3 rounded-xl border border-gray-800 shadow-lg flex flex-col md:flex-row items-center justify-between gap-4">
            
            <div class="flex items-center gap-6 w-full md:w-auto justify-center md:justify-start">
              <div class="flex flex-col items-center px-4 border-r border-gray-700">
                <span class="text-xs text-gray-500 mb-1">活跃靶机</span>
                <span class="text-xl font-bold text-cyan-400 font-mono">
                  {{ activeTargets }}<span class="text-gray-600 text-sm">/{{ totalTargets }}</span>
                </span>
              </div>
              <div class="flex flex-col items-center">
                <span class="text-xs text-gray-500 mb-1">捕获请求</span>
                <span class="text-xl font-bold text-amber-400 font-mono">{{ capturedRequests }}</span>
              </div>
            </div>
  
            <div class="flex gap-2 w-full md:w-auto">
              <n-button 
                secondary 
                type="info" 
                class="flex-1 md:flex-none"
                @click="checkBackend"
              >
                <template #icon>🔄</template> 刷新状态
              </n-button>
              <n-button 
                secondary 
                class="flex-1 md:flex-none"
                @click="showConfigPanel = true"
              >
                <template #icon>⚙️</template> 配置
              </n-button>
            </div>
          </div>
        </div>
  
        <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
          
          <div class="w-full lg:w-1/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden min-h-[300px]">
            <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
              <span class="font-bold text-gray-300">🎯 靶机与控制台</span>
              <n-tag size="small" :bordered="false" class="bg-gray-800 text-gray-400">{{ targets.length }} 靶机</n-tag>
            </div>
            
            <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#161616] flex flex-col gap-4">
              <div class="flex flex-col gap-3">
                <div 
                  v-for="target in targets" 
                  :key="target.id" 
                  class="bg-[#202020] border border-gray-700 rounded-lg p-3 transition-colors hover:border-blue-500/50"
                >
                  <div class="flex justify-between items-start mb-2">
                    <div>
                      <div class="font-bold text-gray-200 text-sm">{{ target.name }}</div>
                      <div class="text-[10px] text-gray-500 mt-1 flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full" 
                          :class="target.status === 'running' ? 'bg-emerald-500 animate-pulse' : (target.status === 'starting' ? 'bg-amber-500 animate-bounce' : 'bg-red-500')">
                        </span>
                        {{ target.status.toUpperCase() }}
                        <span v-if="target.status === 'running'" class="ml-2 text-cyan-500">
                          PORT: {{ getTargetPort(target.id) }}
                        </span>
                      </div>
                    </div>
                  </div>
  
                  <div class="grid grid-cols-4 gap-2 mt-2">
                    <n-button 
                      size="tiny" 
                      :type="target.status === 'running' ? 'error' : 'primary'"
                      secondary
                      @click="target.status === 'running' ? stopTarget(target.id) : startTarget(target.id)"
                      :disabled="isProcessing || target.status === 'starting'"
                      :loading="target.status === 'starting'"
                    >
                      {{ target.status === 'running' ? '停止' : '启动' }}
                    </n-button>
                    
                    <n-button size="tiny" secondary disabled class="opacity-50">重启</n-button>
                    
                    <n-button 
                      size="tiny" 
                      secondary 
                      type="info"
                      :disabled="target.status !== 'running'"
                      @click="accessTarget(target.id)"
                    >
                      访问
                    </n-button>
                    
                    <n-button 
                      size="tiny" 
                      secondary 
                      type="warning"
                      :disabled="target.status !== 'running'"
                      @click="attackTarget(target.id)"
                    >
                      攻击
                    </n-button>
                  </div>
                </div>
              </div>
  
              <div class="flex-1 bg-black rounded border border-gray-800 flex flex-col min-h-[150px] shadow-inner">
                <div class="px-2 py-1 bg-[#111] border-b border-gray-800 text-[10px] text-gray-500 flex justify-between">
                  <span>TERMINAL</span>
                  <span class="text-green-500">● CONNECTED</span>
                </div>
                <div class="flex-1 p-2 overflow-y-auto font-mono text-[10px] text-green-400 space-y-1 custom-scrollbar" ref="consoleRef">
                  <div v-for="(log, idx) in consoleLogs" :key="idx" class="break-all">
                    <span class="text-blue-500 mr-1">$</span>{{ log }}
                  </div>
                </div>
              </div>
            </div>
          </div>
  
          <div class="w-full lg:w-1/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden min-h-[300px]">
            <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
              <span class="font-bold text-gray-300">⚔️ 攻击工具集</span>
            </div>
            
            <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#161616]">
              <div class="bg-[#252525] border border-gray-700 rounded-lg p-4">
                <div class="flex items-center gap-2 mb-3">
                  <div class="w-8 h-8 rounded bg-gray-800 flex items-center justify-center text-lg">📡</div>
                  <div>
                    <h3 class="font-bold text-gray-200 text-sm">端口扫描 (Nmap)</h3>
                    <p class="text-[10px] text-gray-500">快速探测目标开放端口与服务版本</p>
                  </div>
                </div>
                
                <div class="flex gap-2 mb-4">
                  <input 
                    type="text" 
                    v-model="scanTarget" 
                    placeholder="目标 IP (如 127.0.0.1)"
                    class="flex-1 bg-[#1a1a1a] border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-cyan-500 outline-none transition-colors"
                  />
                  <n-button size="small" type="primary" @click="runPortScan">扫描</n-button>
                </div>
  
                <div class="bg-[#1a1a1a] rounded border border-gray-700 p-2 min-h-[100px]">
                  <div v-if="portScanResult.length > 0" class="space-y-1">
                    <div class="grid grid-cols-3 text-[10px] text-gray-500 border-b border-gray-700 pb-1 mb-1">
                      <span>PORT</span><span>SERVICE</span><span>STATE</span>
                    </div>
                    <div v-for="(result, i) in portScanResult" :key="i" class="grid grid-cols-3 text-[11px] items-center">
                      <span class="text-cyan-400 font-mono">{{ result.port }}</span>
                      <span class="text-gray-300">{{ result.service }}</span>
                      <span :class="result.state === 'open' ? 'text-emerald-400' : 'text-red-400'">
                        {{ result.state.toUpperCase() }}
                      </span>
                    </div>
                  </div>
                  <div v-else class="h-full flex flex-col items-center justify-center text-gray-600 text-xs py-4">
                    <span class="text-2xl mb-2 opacity-20">🔍</span>
                    等待任务执行...
                  </div>
                </div>
              </div>
            </div>
          </div>
  
          <div class="w-full lg:w-1/3 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden min-h-[300px]">
            <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
              <span class="font-bold text-gray-300">📡 实时流量监控</span>
              <n-tag size="tiny" type="warning" round>{{ trafficLogs.length }} 条记录</n-tag>
            </div>
            
            <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#161616] space-y-2">
              <div v-for="(traffic, idx) in trafficLogs" :key="idx" class="bg-[#202020] border-l-2 border-gray-700 p-2 text-xs hover:bg-[#252525] transition-colors group">
                <div class="flex justify-between items-center mb-1">
                  <div class="flex items-center gap-2">
                    <span class="font-bold px-1 rounded text-[10px]" 
                      :class="traffic.method === 'GET' ? 'bg-blue-900/50 text-blue-300' : 'bg-orange-900/50 text-orange-300'">
                      {{ traffic.method }}
                    </span>
                    <span class="text-gray-400 truncate max-w-[150px]" :title="traffic.url">{{ traffic.url }}</span>
                  </div>
                  <span :class="getStatusClass(traffic.status)">{{ traffic.status }}</span>
                </div>
                <div class="flex justify-between text-[10px] text-gray-600 font-mono mt-1">
                  <span>SRC: {{ traffic.src }}</span>
                  <span>DST: {{ traffic.dst }}</span>
                </div>
              </div>
              
              <div v-if="trafficLogs.length === 0" class="flex flex-col items-center justify-center h-full text-gray-600">
                <span class="text-4xl mb-2 opacity-20">📶</span>
                <p class="text-xs">暂无流量捕获</p>
              </div>
            </div>
          </div>
  
        </div>
  
        <div v-if="showConfigPanel" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center" @click.self="showConfigPanel = false">
          <div class="bg-[#1e1e1e] border border-gray-700 rounded-xl p-6 w-96 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div class="flex justify-between items-center mb-6 border-b border-gray-700 pb-2">
              <h3 class="text-lg font-bold text-gray-200">靶场端口配置</h3>
              <button @click="showConfigPanel = false" class="text-gray-500 hover:text-white transition-colors text-xl">×</button>
            </div>
            
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <label class="text-sm text-gray-400">DVWA Port</label>
                <input type="number" v-model="targetPorts.dvwa" class="w-20 bg-[#111] border border-gray-600 rounded px-2 py-1 text-right text-cyan-400 font-mono text-sm focus:border-cyan-500 outline-none">
              </div>
              <div class="flex items-center justify-between">
                <label class="text-sm text-gray-400">Metasploitable</label>
                <input type="number" v-model="targetPorts.metasploitable" class="w-20 bg-[#111] border border-gray-600 rounded px-2 py-1 text-right text-cyan-400 font-mono text-sm focus:border-cyan-500 outline-none">
              </div>
              <div class="flex items-center justify-between">
                <label class="text-sm text-gray-400">WebGoat Port</label>
                <input type="number" v-model="targetPorts.webgoat" class="w-20 bg-[#111] border border-gray-600 rounded px-2 py-1 text-right text-cyan-400 font-mono text-sm focus:border-cyan-500 outline-none">
              </div>
            </div>
  
            <div class="mt-8 flex justify-end">
              <n-button type="primary" @click="saveConfig" class="w-full">💾 保存并应用</n-button>
            </div>
          </div>
        </div>
  
      </div>
    </n-config-provider>
  </template>
  
  <script setup>
  import { ref, onMounted, nextTick } from 'vue';
  import axios from 'axios';
  // 🔥 引入 Naive UI
  import { NConfigProvider, NGlobalStyle, NButton, NTag, darkTheme } from 'naive-ui';
  
  // 🔥 主题配置 (蓝色系)
  const themeOverrides = {
    common: {
      primaryColor: '#00bfff',
      primaryColorHover: '#33ccff',
      primaryColorPressed: '#0099cc',
    },
  };
  
  // --- 以下业务逻辑保持 100% 原样 ---
  
  // 基础配置
  const apiBaseUrl = ref(import.meta.env.VITE_API_BASE_URL); 
  const showConfigPanel = ref(false);
  const isProcessing = ref(false);
  const consoleRef = ref(null);
  
  // 端口配置
  const targetPorts = ref({ dvwa: 8081, metasploitable: 8082, webgoat: 8083 });
  
  // 状态数据
  const activeTargets = ref(0);
  const totalTargets = ref(3);
  const capturedRequests = ref(0);
  
  const targets = ref([
      { id: 1, name: 'DVWA - Web漏洞平台', status: 'stopped', type: 'dvwa' },
      { id: 2, name: 'Metasploitable2', status: 'stopped', type: 'metasploitable' },
      { id: 3, name: 'WebGoat - Java漏洞', status: 'stopped', type: 'webgoat' }
  ]);
  
  const consoleLogs = ref(['系统就绪，正在检查 Docker 环境...']);
  const trafficLogs = ref([]);
  const scanTarget = ref('127.0.0.1');
  const portScanResult = ref([]);
  
  // 辅助函数：写日志
  const addLog = (msg) => {
      const time = new Date().toLocaleTimeString();
      consoleLogs.value.push(`[${time}] ${msg}`);
      nextTick(() => {
          if (consoleRef.value) consoleRef.value.scrollTop = consoleRef.value.scrollHeight;
      });
  };
  
  // 获取端口
  const getTargetPort = (id) => {
      if (id === 1) return targetPorts.value.dvwa;
      if (id === 2) return targetPorts.value.metasploitable;
      if (id === 3) return targetPorts.value.webgoat;
      return 80;
  };
  
  const getTargetUrl = (id) => `http://localhost:${getTargetPort(id)}`;
  
  // 🔥 核心修复：真实启动逻辑
  // 🔥 核心修复：真实启动逻辑 (适配线上域名)
const startTarget = async (id) => {
    const target = targets.value.find(t => t.id === id);
    if (!target) return;

    isProcessing.value = true;
    target.status = 'starting';
    addLog(`正在启动 ${target.name} (需 Docker)...`);

    try {
        let endpoint = '';
        if (target.type === 'dvwa') endpoint = `${apiBaseUrl.value}/api/cyber/targets/dvwa/start`;
        if (target.type === 'metasploitable') endpoint = `${apiBaseUrl.value}/api/cyber/targets/metasploitable/start`;
        if (target.type === 'webgoat') endpoint = `${apiBaseUrl.value}/api/cyber/targets/webgoat/start`;

        // 发送请求
        const res = await axios.post(endpoint, { target_id: id, port: getTargetPort(id) });
        const data = res.data;

        // 🟢 [修正] 兼容两种成功判断 (success=true 或 status='success')
        const isSuccess = data.success || data.status === 'success';

        if (isSuccess) {
            target.status = 'running';

            // 🟢 [核心] 获取后端返回的 access_url (环境变量里的域名)，如果没有则回退到本地
            const dynamicUrl = data.access_url || getTargetUrl(id);

            // 将该地址存入 target 对象，供“访问”按钮使用
            target.accessUrl = dynamicUrl;

            addLog(`✅ 启动成功! 访问地址: ${dynamicUrl}`);

            // 🚀 自动在新标签页打开靶场
            window.open(dynamicUrl, '_blank');

            checkBackend();
        } else {
            target.status = 'stopped';
            addLog(`❌ 启动失败: ${data.message}`);
            if (data.message && data.message.includes("Docker")) {
                addLog("💡 提示: 请确保服务器已安装 Docker 并正在运行！");
            }
        }
    } catch (e) {
        target.status = 'stopped';
        addLog(`❌ 请求异常: ${e.message}`);
    } finally {
        isProcessing.value = false;
    }
};
  
  const stopTarget = async (id) => {
      const target = targets.value.find(t => t.id === id);
      isProcessing.value = true;
      addLog(`正在停止 ${target.name}...`);
  
      try {
          let endpoint = `${apiBaseUrl.value}/api/cyber/targets/${target.type}/stop`;
          const res = await axios.post(endpoint, { target_id: id });
  
          if (res.data.success) {
              target.status = 'stopped';
              addLog(`🛑 已停止`);
          } else {
              addLog(`⚠️ 停止失败: ${res.data.message}`);
          }
      } catch (e) {
          addLog(`❌ 异常: ${e.message}`);
      } finally {
          isProcessing.value = false;
          checkBackend();
      }
  };
  
  const accessTarget = (id) => {
        const target = targets.value.find(t => t.id === id);
        // 🟢 [修正] 优先使用后端返回的动态地址
        const url = target.accessUrl || getTargetUrl(id);
        window.open(url, '_blank');
    };
  
  const attackTarget = async (id) => {
      addLog(`⚔️ 发起模拟攻击 (SQL Injection)...`);
      try {
          await axios.post(`${apiBaseUrl.value}/api/cyber/target/attack`, {
              target_id: id,
              attack_type: "sql_injection"
          });
          // 模拟生成流量日志
          trafficLogs.value.unshift({
              method: 'POST',
              url: '/login.php?id=1 OR 1=1',
              status: 200,
              src: '192.168.1.5',
              dst: '10.0.0.2'
          });
          capturedRequests.value++;
      } catch (e) {
          addLog(`攻击请求失败: ${e.message}`);
      }
  };
  
  // 🔥 核心修改：调用真实后端 Nmap 接口
  const runPortScan = async () => {
    if (!scanTarget.value) return;
  
    // 1. 清空旧结果并显示日志
    portScanResult.value = [];
    addLog(`🚀 正在调用 Nmap 扫描目标: ${scanTarget.value} (请耐心等待)...`);
  
    try {
      // 2. 发送请求给后端
      const res = await axios.post(`${apiBaseUrl.value}/api/cyber/tools/port-scan`, {
        target: scanTarget.value,
        scan_type: "quick", // 快速扫描
        ports: "22,80,443,3306,8080-8090" // 重点扫描常用端口和靶机端口
      });
  
      // 3. 处理真实结果
      const data = res.data;
      if (data.results && data.results.length > 0) {
        portScanResult.value = data.results;
        addLog(`✅ 扫描完成，发现 ${data.results.length} 个开放端口`);
      } else {
        addLog(`⚠️ 扫描完成，但在目标上未发现开放端口 (或防火墙拦截)`);
      }
  
    } catch (e) {
      console.error(e);
      addLog(`❌ 扫描出错: ${e.response?.data?.message || e.message}`);
      // 如果是后端报错，提示安装 Nmap
      if (e.message.includes("500")) {
          addLog("💡 提示: 请检查服务器是否已安装 nmap 工具");
      }
    }
  };
  
  const checkBackend = async () => {
      try {
          const res = await axios.get(`${apiBaseUrl.value}/api/cyber/stats`);
          activeTargets.value = res.data.active_targets;
          capturedRequests.value = res.data.captured_requests;
      } catch (e) {
          addLog("⚠️ 无法连接后端，请检查 main.py 是否运行");
      }
  };
  
  const getStatusClass = (s) => s < 300 ? 'text-emerald-400' : (s < 500 ? 'text-amber-400' : 'text-red-400');
  const saveConfig = () => { showConfigPanel.value = false; addLog("配置已保存"); };
  
  onMounted(() => {
      checkBackend();
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
    background: #00bfff;
  }
  </style>