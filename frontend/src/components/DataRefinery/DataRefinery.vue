<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-global-style />
    <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
      
      <div class="shrink-0 mb-4 max-w-full mx-auto w-full">
        <div class="bg-[#1e1e1e] p-4 rounded-xl border border-gray-800 shadow-lg flex flex-col md:flex-row items-center justify-between gap-4">
          
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-[0_0_15px_rgba(16,185,129,0.4)]">
              <span class="text-2xl">🏭</span>
            </div>
            <div>
              <h1 class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300">
                Data Refinery <span class="text-xs bg-emerald-900/30 text-emerald-300 px-2 py-0.5 rounded ml-1 border border-emerald-500/30 align-middle">PRO</span>
              </h1>
              <p class="text-xs text-gray-500 mt-1">智能数据清洗与增强流水线</p>
            </div>
          </div>

          <div v-if="status === 'processing'" class="flex items-center gap-2 bg-[#1a1a1a] px-3 py-1.5 rounded-full border border-emerald-500/30">
            <span class="relative flex h-3 w-3">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <span class="text-emerald-400 text-xs font-bold tracking-wider">ENGINE RUNNING</span>
          </div>
        </div>
      </div>

      <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
        
        <div class="w-full lg:w-1/3 flex flex-col gap-4 min-h-[500px]">
          
          <div class="bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden shrink-0">
            <div class="p-3 bg-[#252525] border-b border-gray-700">
              <span class="font-bold text-gray-300">⚙️ TASK CONFIG</span>
            </div>
            
            <div class="p-4 space-y-4">
              <div
                class="relative border-2 border-dashed rounded-lg p-6 text-center transition-all duration-300 cursor-pointer group"
                :class="file ? 'border-emerald-500 bg-emerald-900/10' : 'border-gray-700 hover:border-emerald-500 hover:bg-[#252525]'"
                @dragover.prevent @drop.prevent="handleDrop"
                @click="$refs.fileInput.click()"
              >
                <input type="file" ref="fileInput" class="hidden" accept=".csv,.xlsx,.xls" @change="handleFileSelect">

                <div v-if="!file" class="flex flex-col items-center gap-2 text-gray-500 group-hover:text-emerald-400 transition-colors">
                  <span class="text-4xl mb-2">📂</span>
                  <p class="text-xs">拖入 CSV / Excel 文件 或 点击上传</p>
                </div>

                <div v-else class="flex items-center justify-between w-full">
                  <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded bg-emerald-900/50 flex items-center justify-center text-xl">📄</div>
                    <div class="text-left">
                      <p class="text-sm font-bold text-gray-200 truncate max-w-[150px]">{{ file.name }}</p>
                      <p class="text-[10px] text-gray-500">{{ (file.size / 1024).toFixed(1) }} KB</p>
                    </div>
                  </div>
                  <n-button circle size="small" secondary type="error" @click.stop="file = null">
                    <template #icon>✕</template>
                  </n-button>
                </div>
              </div>

              <div class="grid grid-cols-1 gap-3 bg-[#161616] p-3 rounded-lg border border-gray-800">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2 text-gray-400 text-xs">
                    <span class="text-lg">🌐</span> 网络巡检 (验证死链)
                  </div>
                  <n-switch v-model:value="config.enableNetwork" size="small" />
                </div>
                <div class="w-full h-px bg-gray-800"></div>
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2 text-gray-400 text-xs">
                    <span class="text-lg">🧠</span> AI 深度分析 (打标)
                  </div>
                  <n-switch v-model:value="config.enableAI" size="small" />
                </div>
              </div>

              <n-button 
                type="primary" 
                class="w-full font-bold h-10 shadow-[0_0_15px_rgba(16,185,129,0.3)]"
                :disabled="!file || status === 'processing'"
                :loading="status === 'processing'"
                @click="startProcess"
                :color="status === 'done' ? '#a855f7' : undefined"
              >
                <template #icon>
                  <span v-if="status === 'idle'">🚀</span>
                  <span v-else-if="status === 'done'">✨</span>
                </template>
                {{ status === 'idle' ? '启动炼油厂引擎' : (status === 'processing' ? '正在精炼中...' : '处理完成 (点击重置)') }}
              </n-button>
            </div>
          </div>

          <div class="flex-1 flex flex-col bg-black rounded-xl border border-gray-800 shadow-inner overflow-hidden min-h-[200px]">
            <div class="p-2 bg-[#111] border-b border-gray-800 flex items-center gap-2">
              <div class="flex gap-1.5">
                <div class="w-2.5 h-2.5 rounded-full bg-red-500/80"></div>
                <div class="w-2.5 h-2.5 rounded-full bg-amber-500/80"></div>
                <div class="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></div>
              </div>
              <span class="text-[10px] text-gray-500 font-mono ml-auto">SYSTEM_LOGS</span>
            </div>
            <div class="flex-1 p-3 overflow-y-auto font-mono text-[10px] space-y-1 custom-scrollbar" ref="logContainer">
              <div v-if="logs.length === 0" class="text-gray-700 italic text-center mt-10">
                Waiting for data stream...
              </div>
              <div v-for="(log, idx) in logs" :key="idx" class="flex gap-2 hover:bg-[#111]">
                <span class="text-gray-600">[{{ log.time }}]</span>
                <span :class="getLogColor(log.msg)">{{ log.msg }}</span>
              </div>
            </div>
          </div>

        </div>

        <div class="w-full lg:w-2/3 flex flex-col gap-4">
          
          <div v-if="currentPhase" class="bg-[#1e1e1e] rounded-xl border border-gray-800 p-4 flex items-center gap-4 animate-in fade-in slide-in-from-top-4">
            <div class="w-12 h-12 rounded-full bg-[#111] border border-gray-700 flex items-center justify-center text-2xl shadow-inner">
              {{ phaseIcon }}
            </div>
            <div class="flex-1">
              <div class="flex justify-between items-end mb-2">
                <h3 class="text-sm font-bold text-gray-300">{{ currentPhase }}</h3>
                <span class="text-xs text-emerald-400 font-mono">{{ progress }}%</span>
              </div>
              <n-progress 
                type="line" 
                :percentage="progress" 
                :show-indicator="false" 
                processing
                color="#10b981"
                rail-color="#333"
                height="6"
              />
            </div>
          </div>

          <div class="flex-1 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden min-h-[400px]">
            <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
              <span class="font-bold text-gray-300">📊 实时数据预览 (Top 5)</span>
              <n-tag v-if="previewData.length > 0" size="small" type="success" :bordered="false" class="bg-emerald-900/30 text-emerald-400">
                已加载 {{ columns.length }} 列字段
              </n-tag>
            </div>

            <div class="flex-1 overflow-auto custom-scrollbar bg-[#161616] relative">
              <table v-if="previewData.length > 0" class="w-full text-left border-collapse text-xs">
                <thead class="bg-[#202020] sticky top-0 z-10">
                  <tr>
                    <th class="p-3 text-gray-500 font-normal border-b border-gray-700 w-12">#</th>
                    <th v-for="col in columns" :key="col" class="p-3 text-gray-400 font-normal border-b border-gray-700 whitespace-nowrap">
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody class="text-gray-300 font-mono">
                  <tr v-for="(row, idx) in previewData" :key="idx" class="hover:bg-white/5 transition-colors border-b border-gray-800 last:border-0">
                    <td class="p-3 text-gray-600">{{ idx + 1 }}</td>
                    <td v-for="col in columns" :key="col" class="p-3 whitespace-nowrap max-w-[200px] overflow-hidden text-ellipsis">
                      <span v-if="col === 'Link_Status'" 
                        :class="row[col] === 'Alive' ? 'text-emerald-400' : (row[col]?.includes('Dead') ? 'text-red-400' : 'text-amber-400')">
                        {{ row[col] }}
                      </span>
                      <span v-else-if="col === 'AI_Score'" 
                        :class="row[col] > 80 ? 'text-purple-400 font-bold' : 'text-gray-500'">
                        {{ row[col] }}
                      </span>
                      <span v-else>{{ row[col] }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>

              <div v-else class="absolute inset-0 flex flex-col items-center justify-center text-gray-700">
                <span class="text-6xl mb-4 opacity-20">📉</span>
                <p>暂无预览数据</p>
              </div>
            </div>
          </div>

          <div v-if="downloadUrl" class="bg-emerald-900/10 border border-emerald-500/30 rounded-xl p-6 text-center animate-bounce-in">
            <h3 class="text-xl font-bold text-emerald-400 mb-2">🎉 精炼完成！</h3>
            <p class="text-sm text-gray-400 mb-4">共输出有效数据 <span class="text-white font-bold">{{ finalCount }}</span> 条</p>
            <a :href="downloadUrl" download class="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-2 rounded-lg font-bold transition-all shadow-[0_0_15px_rgba(16,185,129,0.4)]">
              📥 下载清洗结果 (.csv)
            </a>
          </div>

        </div>

      </div>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
// 🔥 引入 Naive UI
import { NConfigProvider, NGlobalStyle, NButton, NTag, NSwitch, NProgress, darkTheme } from 'naive-ui'

// 🔥 主题配置 (绿色系)
const themeOverrides = {
  common: {
    primaryColor: '#10b981', // Emerald 500
    primaryColorHover: '#34d399',
    primaryColorPressed: '#059669',
  },
  Switch: {
    railColorActive: '#10b981',
  }
}

// --- 以下业务逻辑保持 100% 原样 ---

const file = ref(null)
const status = ref('idle') // idle, processing, done
const logs = ref([])
const previewData = ref([])
const columns = ref([])
const currentPhase = ref('')
const progress = ref(0)
const downloadUrl = ref('')
const finalCount = ref(0)
const logContainer = ref(null)

const config = ref({
  enableNetwork: false,
  enableAI: false
})

const phaseIcon = computed(() => {
  if (currentPhase.value.includes('清洗')) return '🧹'
  if (currentPhase.value.includes('网络') || currentPhase.value.includes('验证')) return '🌐'
  if (currentPhase.value.includes('AI') || currentPhase.value.includes('智能')) return '🧠'
  return '⚙️'
})

const handleFileSelect = (e) => {
  if (e.target.files.length > 0) file.value = e.target.files[0]
}

const handleDrop = (e) => {
  if (e.dataTransfer.files.length > 0) file.value = e.dataTransfer.files[0]
}

const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false })
  logs.value.push({ time, msg })
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

// 辅助函数：根据日志内容返回 Tailwind 颜色类
const getLogColor = (msg) => {
  if (msg.includes('✅') || msg.includes('完成')) return 'text-emerald-400'
  if (msg.includes('❌') || msg.includes('错误')) return 'text-red-400'
  if (msg.includes('⚠️') || msg.includes('跳过')) return 'text-amber-400'
  if (msg.includes('➡️') || msg.includes('启动')) return 'text-blue-400'
  return 'text-gray-400'
}

const startProcess = async () => {
  if (status.value === 'done') {
    status.value = 'idle'
    logs.value = []
    previewData.value = []
    columns.value = []
    currentPhase.value = ''
    progress.value = 0
    downloadUrl.value = ''
    file.value = null
    return
  }

  status.value = 'processing'
  logs.value = []
  downloadUrl.value = ''

  const formData = new FormData()
  formData.append('file', file.value)
  formData.append('enable_network', config.value.enableNetwork)
  formData.append('enable_ai', config.value.enableAI)

  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/refinery/process`, { 
      method: 'POST',
      body: formData
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const data = JSON.parse(line)
          handleStreamMessage(data)
        } catch (e) {
          console.error("Parse error", e)
        }
      }
    }
  } catch (e) {
    addLog(`❌ 系统错误: ${e.message}`)
    status.value = 'idle'
  }
}

const handleStreamMessage = (data) => {
  if (data.msg) addLog(data.msg)
  if (data.step === 'phase_start') {
    currentPhase.value = data.phase
    progress.value = 0
  } else if (data.progress !== undefined) {
    progress.value = data.progress
  }
  if (data.step === 'phase_preview') {
    columns.value = data.columns
    previewData.value = data.preview
    progress.value = 100
  }
  if (data.step === 'done') {
    status.value = 'done'
    downloadUrl.value = data.download_url
    finalCount.value = data.final_count
    currentPhase.value = '处理完成'
    progress.value = 100
  }
}
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
  background: #10b981;
}

/* 进场动画 */
.animate-bounce-in {
  animation: bounceIn 0.5s cubic-bezier(0.18, 0.89, 0.32, 1.28);
}

@keyframes bounceIn {
  0% { opacity: 0; transform: scale(0.9); }
  100% { opacity: 1; transform: scale(1); }
}
</style>