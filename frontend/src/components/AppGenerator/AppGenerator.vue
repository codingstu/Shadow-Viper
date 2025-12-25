<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-global-style />
    <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
      
      <div class="shrink-0 mb-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(147,51,234,0.4)]">
              <span class="text-xl">⚡</span>
            </div>
            <div>
              <h1 class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-blue-400">
                App Generator <span class="text-xs bg-purple-900/30 text-purple-300 px-2 py-0.5 rounded ml-1 border border-purple-500/30 align-middle">DeepSeek Engine</span>
              </h1>
            </div>
          </div>
          
          <div class="flex items-center gap-2 bg-[#1e1e1e] px-3 py-1.5 rounded-full border border-gray-800">
            <span class="relative flex h-2.5 w-2.5">
              <span v-if="isStreaming" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5" :class="isStreaming ? 'bg-green-500' : 'bg-gray-500'"></span>
            </span>
            <span class="text-xs font-mono" :class="isStreaming ? 'text-green-400' : 'text-gray-500'">
              {{ isStreaming ? 'GENERATING...' : 'READY' }}
            </span>
          </div>
        </div>
      </div>

      <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
        
        <div class="w-full lg:w-64 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden shrink-0 lg:h-full h-auto max-h-[200px] lg:max-h-none">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <span class="font-bold text-gray-300 text-sm">📦 APP LIBRARY</span>
            <n-tag size="small" :bordered="false" class="bg-gray-800 text-purple-400">{{ historyList.length }}</n-tag>
          </div>
          
          <div class="flex-1 overflow-y-auto p-2 custom-scrollbar space-y-2">
            <div 
              v-for="item in historyList" 
              :key="item.id" 
              @click="loadApp(item.id)" 
              class="p-3 rounded-lg cursor-pointer border transition-all duration-200 group relative"
              :class="currentAppId === item.id 
                ? 'bg-purple-900/20 border-purple-500/50 shadow-[0_0_10px_rgba(168,85,247,0.2)]' 
                : 'bg-[#252525] border-transparent hover:border-gray-600 hover:bg-[#2a2a2a]'"
            >
              <div class="text-xs text-gray-300 font-bold mb-1 line-clamp-2 leading-relaxed">{{ item.full_req }}</div>
              <div class="flex justify-between items-center mt-2">
                <span class="text-[10px] text-gray-600 font-mono">ID: {{ item.id }}</span>
                <button 
                  @click.stop="deleteApp(item.id)" 
                  class="text-gray-600 hover:text-red-400 transition-colors px-1.5 py-0.5 rounded hover:bg-red-900/20 text-xs opacity-0 group-hover:opacity-100"
                >
                  ✕
                </button>
              </div>
            </div>

            <div v-if="historyList.length === 0" class="text-center py-8 text-gray-600 text-xs">
              暂无历史记录
            </div>
          </div>
        </div>

        <div class="flex-1 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden">
          
          <div class="p-2 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0 h-12">
            <div class="flex bg-black rounded p-0.5 border border-gray-700">
              <button 
                @click="viewMode = 'preview'" 
                :disabled="isStreaming"
                class="px-3 py-1 text-xs rounded transition-all flex items-center gap-1"
                :class="viewMode === 'preview' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300 disabled:opacity-50'"
              >
                👁️ 预览
              </button>
              <button 
                @click="viewMode = 'code'" 
                class="px-3 py-1 text-xs rounded transition-all flex items-center gap-1"
                :class="viewMode === 'code' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'"
              >
                💻 代码
              </button>
            </div>

            <div class="flex gap-2" v-if="!isStreaming">
               <n-button 
                v-if="viewMode === 'code' && (streamBuffer || generatedHtml)" 
                size="tiny" secondary type="info" 
                @click="copyCode"
              >
                📋 复制代码
              </n-button>
              <n-button 
                v-if="generatedHtml" 
                size="tiny" secondary 
                @click="refreshIframe"
              >
                🔄 重置
              </n-button>
            </div>
          </div>

          <div class="flex-1 relative bg-white overflow-hidden">
            <div v-show="viewMode === 'preview'" class="w-full h-full relative">
              <div v-if="!generatedHtml && !isStreaming" class="absolute inset-0 flex flex-col items-center justify-center bg-[#1a1a1a] text-gray-500">
                <span class="text-6xl mb-4 opacity-20 filter grayscale">⚛️</span>
                <p class="text-sm font-mono">输入需求，AI 将为你构建应用</p>
              </div>
              <iframe 
                ref="iframeRef" 
                v-if="generatedHtml && !isStreaming" 
                class="w-full h-full border-none" 
                :srcdoc="generatedHtml" 
                sandbox="allow-scripts allow-same-origin allow-modals allow-forms allow-popups"
              ></iframe>
            </div>

            <div v-show="viewMode === 'code'" class="w-full h-full bg-[#0d1117] flex flex-col">
              <textarea 
                ref="codeTextarea" 
                readonly 
                class="w-full h-full bg-transparent text-green-400 p-4 font-mono text-xs leading-relaxed resize-none outline-none custom-scrollbar selection:bg-green-900"
                :value="streamBuffer || generatedHtml"
              ></textarea>
            </div>
          </div>

          <div class="p-4 bg-[#252525] border-t border-gray-700 shrink-0">
            <div class="relative">
              <div class="absolute left-3 top-1/2 -translate-y-1/2 text-lg">✨</div>
              <n-input
                v-model:value="requirement"
                type="text"
                placeholder="例如：一个番茄钟，或者待办事项清单..."
                class="!bg-[#1a1a1a] !border-gray-600 !text-gray-200 !pl-10 !pr-24 !h-12 !text-sm !rounded-lg"
                @keyup.enter="generateAppStream"
                :disabled="isStreaming"
              />
              <div class="absolute right-1 top-1/2 -translate-y-1/2">
                <n-button 
                  type="primary" 
                  class="font-bold shadow-[0_0_10px_rgba(147,51,234,0.4)]"
                  :loading="isStreaming"
                  :disabled="isStreaming || !requirement"
                  @click="generateAppStream"
                >
                  {{ isStreaming ? '生成中' : '生成' }}
                </n-button>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
// 🔥 引入 Naive UI
import { NConfigProvider, NGlobalStyle, NButton, NInput, NTag, darkTheme } from 'naive-ui';

// 🔥 主题配置 (紫/蓝系)
const themeOverrides = {
  common: {
    primaryColor: '#9333ea', // Purple 600
    primaryColorHover: '#a855f7',
    primaryColorPressed: '#7e22ce',
  },
  Input: {
    borderFocus: '1px solid #9333ea',
    boxShadowFocus: '0 0 0 2px rgba(147, 51, 234, 0.2)',
  }
};

// --- 以下业务逻辑保持 100% 原样 ---

const requirement = ref('');
const generatedHtml = ref('');
const streamBuffer = ref(''); // 🔥 用于存流式数据
const isStreaming = ref(false);
const historyList = ref([]);
const currentAppId = ref(null);
const viewMode = ref('preview');
const codeTextarea = ref(null);

const API_BASE = `${import.meta.env.VITE_API_BASE_URL}/api/generator`;
  
onMounted(() => fetchHistory());

// 自动滚动代码到底部，像黑客终端一样
watch(streamBuffer, () => {
  if (codeTextarea.value) {
    codeTextarea.value.scrollTop = codeTextarea.value.scrollHeight;
  }
});

const fetchHistory = async () => {
  try {
    const res = await fetch(`${API_BASE}/history`);
    historyList.value = await res.json();
  } catch (e) { console.error(e); }
};

// 🔥🔥🔥 核心修复：流式读取器 🔥🔥🔥
const generateAppStream = async () => {
  if (!requirement.value.trim()) return;

  isStreaming.value = true;
  streamBuffer.value = ''; // 清空缓冲区
  generatedHtml.value = '';
  currentAppId.value = null;
  viewMode.value = 'code'; // 强制切换到代码视图看直播

  try {
    const response = await fetch(`${API_BASE}/generate_app`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement: requirement.value })
    });

    if (!response.ok) throw new Error(response.statusText);

    // 获取流式读取器
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);

          if (data.type === 'chunk') {
            // 收到代码片段 -> 追加显示
            streamBuffer.value += data.content;
          } else if (data.type === 'done') {
            // 完成 -> 保存并切换预览
            generatedHtml.value = data.html;
            currentAppId.value = data.id;
            streamBuffer.value = ''; // 清空流缓冲，显示最终代码
            viewMode.value = 'preview'; // 自动切回预览，见证奇迹
            await fetchHistory();
          } else if (data.type === 'error') {
            alert('Error: ' + data.message);
          }
        } catch (e) {
          // 忽略非 JSON 行
        }
      }
    }
  } catch (e) {
    alert('Stream Error: ' + e.message);
  } finally {
    isStreaming.value = false;
    requirement.value = ''; // 清空输入框
  }
};

const loadApp = async (id) => {
  if (currentAppId.value === id) return;
  isStreaming.value = true; // 借用 loading 状态
  viewMode.value = 'preview';
  try {
    const res = await fetch(`${API_BASE}/load/${id}`);
    const data = await res.json();
    generatedHtml.value = data.html;
    currentAppId.value = id;
  } finally {
    isStreaming.value = false;
  }
};

const deleteApp = async (id) => {
  if (!confirm('确定删除?')) return;
  await fetch(`${API_BASE}/delete/${id}`, { method: 'DELETE' });
  await fetchHistory();
  if (currentAppId.value === id) { generatedHtml.value = ''; currentAppId.value = null; }
  }

const refreshIframe = () => {
  const html = generatedHtml.value;
  generatedHtml.value = '';
  nextTick(() => generatedHtml.value = html);
};

const copyCode = () => {
  navigator.clipboard.writeText(generatedHtml.value);
  alert('已复制');
};
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
  background: #9333ea;
}
</style>