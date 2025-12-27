<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">

      <div class="header bg-[#1e1e20]/90 backdrop-blur-md border border-white/10 rounded-full p-2 mb-4 shadow-2xl flex justify-center items-center gap-4 mx-auto w-fit">
      <div class="flex items-center gap-3 pl-2">
        <div class="p-1.5 bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 rounded-full border border-violet-500/30">
          <span class="text-lg">🎮</span>
        </div>
        <div class="flex flex-col leading-none">
          <h1 class="text-sm font-bold text-white m-0">Game Generator</h1>
          <span class="text-[10px] text-violet-400 font-mono scale-90 origin-left">3D Engine</span>
        </div>
      </div>

      <div class="w-px h-6 bg-white/10 hidden sm:block"></div>

      <div class="flex items-center gap-1.5 pr-3">
        <span class="relative flex h-1.5 w-1.5">
          <span v-if="isStreaming" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-fuchsia-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-1.5 w-1.5" :class="isStreaming ? 'bg-fuchsia-500' : 'bg-gray-500'"></span>
        </span>
        <span class="text-[9px] font-mono" :class="isStreaming ? 'text-fuchsia-400' : 'text-gray-500'">
          {{ isStreaming ? 'COMPILING' : 'READY' }}
        </span>
      </div>
    </div>
      <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">

        <!-- 左侧游戏库保持不变 -->
        <div
          class="w-full lg:w-64 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden shrink-0 lg:h-full h-auto max-h-[200px] lg:max-h-none">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <span class="font-bold text-gray-300 text-sm">🕹️ GAME LIBRARY</span>
            <n-tag size="small" :bordered="false" class="bg-gray-800 text-violet-400">{{ gameHistory.length }}</n-tag>
          </div>

          <div class="flex-1 overflow-y-auto p-2 custom-scrollbar space-y-2">
            <div v-for="item in gameHistory" :key="item.id" @click="loadGame(item.id)"
              class="p-3 rounded-lg cursor-pointer border transition-all duration-200 group relative" :class="currentAppId === item.id
    ? 'bg-violet-900/20 border-violet-500/50 shadow-[0_0_10px_rgba(139,92,246,0.2)]'
    : 'bg-[#252525] border-transparent hover:border-gray-600 hover:bg-[#2a2a2a]'">
              <div class="flex items-start gap-2">
                <div class="text-xs px-1.5 py-0.5 rounded border mt-0.5" :class="item.game_type === '3d'
    ? 'bg-blue-900/20 text-blue-400 border-blue-500/30'
    : 'bg-violet-900/20 text-violet-400 border-violet-500/30'">
                  {{ item.game_type === '3d' ? '3D' : '2D' }}
                </div>
                <div class="text-xs text-gray-300 font-bold mb-1 line-clamp-2 leading-relaxed flex-1">
                  {{ item.full_req.replace('[GAME] ', '') }}
                </div>
              </div>
              <div class="flex justify-between items-center mt-2">
                <span class="text-[10px] text-gray-600 font-mono">ID: {{ item.id }}</span>
                <button @click.stop="deleteApp(item.id)"
                  class="text-gray-600 hover:text-red-400 transition-colors px-1.5 py-0.5 rounded hover:bg-red-900/20 text-xs opacity-0 group-hover:opacity-100">
                  ✕
                </button>
              </div>
            </div>

            <div v-if="gameHistory.length === 0" class="text-center py-8 text-gray-600 text-xs">
              暂无游戏记录
            </div>
          </div>
        </div>

        <div class="flex-1 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden">

          <!-- 顶部控制栏 - 增加游戏类型选择器 -->
          <div class="p-2 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0 h-12">
            <div class="flex items-center gap-3">
              <div class="flex bg-black rounded p-0.5 border border-gray-700">
                <button @click="viewMode = 'preview'" :disabled="isStreaming"
                  class="px-3 py-1 text-xs rounded transition-all flex items-center gap-1"
                  :class="viewMode === 'preview' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300 disabled:opacity-50'">
                  🕹️ 试玩
                </button>
                <button @click="viewMode = 'code'"
                  class="px-3 py-1 text-xs rounded transition-all flex items-center gap-1"
                  :class="viewMode === 'code' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'">
                  👾 源码
                </button>
              </div>

              <div class="flex items-center gap-1">
                <n-select v-model:value="gameType" :options="gameTypeOptions" size="tiny" style="width: 100px"
                  :disabled="isStreaming" />
              </div>
            </div>

            <div class="flex gap-2" v-if="!isStreaming">
              <n-button v-if="viewMode === 'code' && (streamBuffer || generatedHtml)" size="tiny" secondary type="info"
                @click="copyCode">
                📋 复制代码
              </n-button>
              <n-button v-if="generatedHtml" size="tiny" secondary @click="refreshIframe">
                🔄 重开一局
              </n-button>
            </div>
          </div>

          <!-- 游戏预览/代码区域 -->
          <div class="flex-1 relative bg-black overflow-hidden">
            <div v-show="viewMode === 'preview'" class="w-full h-full relative">
              <div v-if="!generatedHtml && !isStreaming"
                class="absolute inset-0 flex flex-col items-center justify-center bg-[#151515] text-gray-600">
                <span class="text-6xl mb-4 opacity-20 animate-pulse">{{ gameType === '3d' ? '🌌' : '👾' }}</span>
                <p class="text-sm font-mono">想玩什么？DeepSeek 现场给你做</p>
                <p class="text-xs text-gray-500 mt-2">当前引擎：{{ gameType === '3d' ? 'Three.js (3D)' : 'Phaser (2D)' }}</p>
              </div>

              <!-- iframe - 修复沙箱配置 -->
              <iframe ref="iframeRef" v-if="generatedHtml && !isStreaming" class="w-full h-full border-none"
                :srcdoc="iframeHtml" sandbox="allow-scripts allow-modals allow-forms allow-popups allow-pointer-lock"
                @load="onIframeLoad" @error="onIframeError"></iframe>

              <!-- 错误提示 -->
              <div v-if="iframeError && generatedHtml"
                class="absolute inset-0 flex flex-col items-center justify-center bg-red-900/10 backdrop-blur-sm">
                <div class="bg-[#1a1a1a] p-6 rounded-xl border border-red-500/50 max-w-md shadow-2xl">
                  <div class="flex items-center gap-3 mb-3">
                    <div class="text-red-400 text-xl">⚠️</div>
                    <div>
                      <div class="text-red-400 text-lg font-bold">游戏加载失败</div>
                      <div class="text-gray-400 text-sm">{{ iframeError }}</div>
                    </div>
                  </div>
                  <div class="flex gap-3">
                    <button @click="refreshIframe"
                      class="px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded text-sm transition-colors flex-1">
                      重新加载
                    </button>
                    <button @click="viewMode = 'code'"
                      class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors flex-1">
                      查看源码
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-show="viewMode === 'code'" class="w-full h-full bg-[#0d1117] flex flex-col">
              <textarea ref="codeTextarea" readonly
                class="w-full h-full bg-transparent text-yellow-500/90 p-4 font-mono text-xs leading-relaxed resize-none outline-none custom-scrollbar selection:bg-yellow-900/30"
                :value="streamBuffer || generatedHtml"></textarea>
            </div>
          </div>

          <!-- 输入区域 - 增加提示 -->
          <div class="p-4 bg-[#252525] border-t border-gray-700 shrink-0">
            <div class="relative">
              <div class="absolute left-3 top-1/2 -translate-y-1/2 text-lg">{{ gameType === '3d' ? '🌌' : '🎮' }}</div>
              <n-input v-model:value="requirement" type="text" :placeholder="gameType === '3d'
    ? '例如：第一人称射击游戏，用WASD移动，鼠标瞄准射击...'
    : '例如：一个躲避陨石的飞机游戏，按空格发射子弹...'"
                class="!bg-[#1a1a1a] !border-gray-600 !text-gray-200 !pl-10 !pr-24 !h-12 !text-sm !rounded-lg"
                @keyup.enter="generateGameStream" :disabled="isStreaming" />
              <div class="absolute right-1 top-1/2 -translate-y-1/2">
                <n-button type="primary" class="font-bold shadow-[0_0_10px_rgba(139,92,246,0.4)]" :loading="isStreaming"
                  :disabled="isStreaming || !requirement" @click="generateGameStream">
                  {{ isStreaming ? '编译中' : 'Start' }}
                </n-button>
              </div>
            </div>
            <div class="mt-2 text-xs text-gray-500 flex justify-between">
              <span>当前引擎：<span :class="gameType === '3d' ? 'text-blue-400' : 'text-violet-400'">{{ gameType === '3d' ?
    'Three.js (3D)' : 'Phaser (2D)' }}</span></span>
              <span class="text-gray-600">建议{{ gameType === '3d' ? '3D' : '2D' }}游戏描述</span>
            </div>
          </div>

        </div>

      </div>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue';
import { NConfigProvider, NGlobalStyle, NButton, NInput, NTag, NSelect, darkTheme } from 'naive-ui';

// 🔥 主题配置保持不变
const themeOverrides = {
  common: {
    primaryColor: '#8b5cf6',
    primaryColorHover: '#a78bfa',
    primaryColorPressed: '#7c3aed',
  },
  Input: {
    borderFocus: '1px solid #8b5cf6',
    boxShadowFocus: '0 0 0 2px rgba(139, 92, 246, 0.2)',
  }
};

// --- 业务逻辑 ---
const requirement = ref('');
const gameType = ref('2d'); // 默认2D
const gameTypeOptions = [
  { label: '2D游戏 (Phaser)', value: '2d' },
  { label: '3D游戏 (Three.js)', value: '3d' }
];

const generatedHtml = ref('');
const streamBuffer = ref('');
const isStreaming = ref(false);
const historyList = ref([]);
const currentAppId = ref(null);
const viewMode = ref('preview');
const codeTextarea = ref(null);
const iframeRef = ref(null);
const iframeError = ref(null);

// 游戏列表
const gameHistory = computed(() => historyList.value.filter(item => item.full_req.startsWith('[GAME]')));

// 在 GameGenerator.vue 的 script 部分
const iframeHtml = computed(() => {
  if (!generatedHtml.value) return '';

  let html = generatedHtml.value;

  // 如果是3D游戏，进行额外验证
  if (gameType.value === '3d') {
    // 检查常见的语法错误
    const syntaxChecks = [
      {
        pattern: /\bnegative\s+\d+/,
        fix: (match) => match.replace('negative', '-'),
        message: '修复 "negative" 语法错误'
      },
      {
        pattern: /new THREE\.Vector3\([^)]*negative/,
        fix: (match) => match.replace('negative', '-'),
        message: '修复 Vector3 参数中的语法错误'
      },
      {
        pattern: /;[ \t]*\n[ \t]*\)/,
        fix: (match) => match.replace(';', ''),
        message: '修复行尾多余的分号'
      }
    ];

    syntaxChecks.forEach(check => {
      if (check.pattern.test(html)) {
        console.warn(check.message, check.pattern.exec(html));
        html = html.replace(check.pattern, check.fix);
      }
    });

    // 如果代码不完整，包装成完整HTML
    if (!html.includes('<!DOCTYPE') && !html.includes('<html')) {
      html = createSafeThreeJsWrapper(html);
    }
  }

  return html;
});


// 🔥 API地址
const API_BASE = `${import.meta.env.VITE_API_BASE_URL}/api/game`;
const HISTORY_API = `${import.meta.env.VITE_API_BASE_URL}/api/generator/history`;
const LOAD_API = `${import.meta.env.VITE_API_BASE_URL}/api/generator/load`;
const DELETE_API = `${import.meta.env.VITE_API_BASE_URL}/api/generator/delete`;

onMounted(() => fetchHistory());

watch(streamBuffer, () => {
  if (codeTextarea.value) codeTextarea.value.scrollTop = codeTextarea.value.scrollHeight;
});

const fetchHistory = async () => {
  try {
    const res = await fetch(HISTORY_API);
    historyList.value = await res.json();
  } catch (e) {
    console.error('获取历史记录失败:', e);
  }
};

const generateGameStream = async () => {
  if (!requirement.value.trim()) return;
  isStreaming.value = true;
  streamBuffer.value = '';
  generatedHtml.value = '';
  currentAppId.value = null;
  iframeError.value = null;
  viewMode.value = 'code';

  try {
    const response = await fetch(`${API_BASE}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requirement: requirement.value,
        game_type: gameType.value
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP错误: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);
          if (data.type === 'chunk') {
            streamBuffer.value += data.content;
          } else if (data.type === 'done') {
            generatedHtml.value = data.html;
            currentAppId.value = data.id;
            streamBuffer.value = '';
            viewMode.value = 'preview';
            await fetchHistory();
          } else if (data.type === 'error') {
            iframeError.value = data.message || '未知错误';
          }
        } catch (e) {
          console.warn('解析流数据失败:', e, line);
        }
      }
    }
  } catch (e) {
    iframeError.value = e.message;
    console.error('生成游戏失败:', e);
  }
  finally {
    isStreaming.value = false;
    requirement.value = '';
  }
};

const loadGame = async (id) => {
  if (currentAppId.value === id) return;
  isStreaming.value = true;
  viewMode.value = 'preview';
  iframeError.value = null;

  try {
    const res = await fetch(`${LOAD_API}/${id}`);
    if (!res.ok) {
      throw new Error(`加载失败: ${res.status}`);
    }
    const data = await res.json();
    generatedHtml.value = data.html;
    currentAppId.value = id;
    // 设置游戏类型（如果有）
    if (data.game_type) {
      gameType.value = data.game_type;
    }
  } catch (e) {
    iframeError.value = e.message;
    console.error('加载游戏失败:', e);
  } finally {
    isStreaming.value = false;
  }
};

const deleteApp = async (id) => {
  if (!confirm('确定删除这个游戏吗？')) return;
  try {
    await fetch(`${DELETE_API}/${id}`, { method: 'DELETE' });
    await fetchHistory();
    if (currentAppId.value === id) {
      generatedHtml.value = '';
      currentAppId.value = null;
      iframeError.value = null;
    }
  } catch (e) {
    console.error('删除游戏失败:', e);
    alert('删除失败: ' + e.message);
  }
};

const refreshIframe = () => {
  iframeError.value = null;
  const html = generatedHtml.value;
  generatedHtml.value = '';
  nextTick(() => {
    generatedHtml.value = html;
    // 强制iframe重新加载
    if (iframeRef.value) {
      iframeRef.value.src = 'about:blank';
      setTimeout(() => {
        iframeRef.value.srcdoc = iframeHtml.value;
      }, 10);
    }
  });
};

const onIframeLoad = () => {
  iframeError.value = null;
  console.log('iframe加载完成');

  // 检查iframe内部是否有错误
  setTimeout(() => {
    try {
      const iframe = iframeRef.value;
      if (iframe && iframe.contentDocument) {
        const errorDiv = iframe.contentDocument.getElementById('error-message');
        if (errorDiv && errorDiv.style.display !== 'none') {
          iframeError.value = '游戏代码执行错误';
        }
      }
    } catch (e) {
      // 跨域错误，忽略
    }
  }, 100);
};

const onIframeError = (event) => {
  iframeError.value = 'iframe加载失败，可能是脚本错误';
  console.error('iframe错误:', event);
};

const copyCode = () => {
  const codeToCopy = streamBuffer.value || generatedHtml.value;
  if (codeToCopy) {
    navigator.clipboard.writeText(codeToCopy)
      .then(() => alert('代码已复制到剪贴板'))
      .catch(err => console.error('复制失败:', err));
  }
};
</script>

<style scoped>
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
  background: #8b5cf6;
}

/* 修复iframe中的样式冲突 */
:deep() iframe {
  isolation: isolate;
}
</style>