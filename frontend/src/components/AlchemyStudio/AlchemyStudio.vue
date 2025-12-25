<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-global-style />
    <div class="h-screen w-full bg-[#121212] text-gray-200 flex flex-col p-2 md:p-4 overflow-hidden font-mono">
      
      <div class="shrink-0 text-center mb-4 md:mb-6">
        <h1 class="text-2xl md:text-3xl font-bold text-primary bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-cyan-500">
          🌌 Chaos Humanizer <span class="text-xs bg-purple-600/30 text-purple-300 px-2 py-0.5 rounded ml-2 align-middle border border-purple-500/30">Ultra</span>
        </h1>
        <p class="text-xs md:text-sm text-gray-500 mt-2">
          多维语言熵增系统：思维链可视化 · 自动回译 · 深度去重
        </p>
      </div>

      <div class="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
        
        <div class="flex-1 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden min-h-[300px]">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <div class="flex items-center gap-2">
              <span class="font-bold text-gray-300">📄 原始文本</span>
              <transition name="pop">
                <n-tag v-if="inputAiScore !== null" round size="small" :bordered="false"
                  :class="inputAiScore > 50 ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'">
                  🤖 {{ inputAiScore }}% AI
                </n-tag>
              </transition>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-gray-500">{{ sourceText.length }} chars</span>
              <n-button text class="text-gray-400 hover:text-red-400" @click="clearAll">
                <template #icon>✕</template>
              </n-button>
            </div>
          </div>
          
          <div class="flex-1 relative bg-[#161616]">
            <textarea 
              v-model="sourceText" 
              placeholder="在此粘贴论文... 系统将自动检测 AI 浓度并清洗" 
              class="w-full h-full bg-transparent p-4 resize-none outline-none text-gray-300 text-sm leading-relaxed font-serif placeholder-gray-700 custom-scrollbar"
              spellcheck="false"
            ></textarea>
          </div>
        </div>

        <div class="shrink-0 w-full lg:w-72 flex flex-col gap-4">
          
          <div class="flex justify-center py-4 bg-[#1e1e1e] rounded-xl border border-gray-800 lg:py-8">
            <button 
              @click="startPipeline" 
              :disabled="isLoading || !sourceText"
              class="relative w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_20px_rgba(6,182,212,0.5)] transition-all hover:scale-105 hover:shadow-[0_0_40px_rgba(6,182,212,0.8)] disabled:opacity-50 disabled:cursor-not-allowed group flex items-center justify-center overflow-hidden"
            >
              <div v-if="isLoading" class="absolute inset-0 border-4 border-t-transparent border-white rounded-full animate-spin"></div>
              <div class="z-10 flex flex-col items-center text-white">
                <span class="text-2xl mb-1 group-hover:animate-bounce">{{ isLoading ? '⚛️' : '🚀' }}</span>
                <span class="text-[10px] font-bold uppercase">{{ isLoading ? 'Running' : 'Start' }}</span>
              </div>
            </button>
          </div>

          <div class="flex-1 flex flex-col bg-black rounded-xl border border-gray-800 shadow-inner overflow-hidden min-h-[200px]">
            <div class="p-2 bg-[#111] border-b border-gray-800 flex items-center gap-2">
              <div class="flex gap-1.5">
                <div class="w-2.5 h-2.5 rounded-full bg-red-500/80"></div>
                <div class="w-2.5 h-2.5 rounded-full bg-amber-500/80"></div>
                <div class="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></div>
              </div>
              <span class="text-[10px] text-gray-500 font-mono ml-auto">Kernel Log</span>
            </div>
            <div class="flex-1 p-3 overflow-y-auto font-mono text-[10px] space-y-1 custom-scrollbar text-cyan-400" ref="logContainer">
              <div v-for="(log, idx) in logs" :key="idx" class="break-all">
                <span class="text-blue-600 mr-1">></span>{{ log }}
              </div>
              <div v-if="isLoading" class="animate-pulse">_</div>
            </div>
          </div>

          <div v-if="pipelinePath.length > 0" class="bg-[#1e1e1e] p-3 rounded-xl border border-gray-800 flex flex-col items-center gap-2">
            <span class="text-[10px] text-gray-500 uppercase tracking-widest">Process Chain</span>
            <div class="flex items-center gap-1 w-full justify-center overflow-hidden">
              <div class="w-6 h-6 rounded-full bg-gray-800 border border-gray-600 flex items-center justify-center text-[8px] text-gray-400 shrink-0">
                {{ originLang || '?' }}
              </div>
              <div class="w-4 h-0.5 bg-gray-700"></div>
              
              <div v-for="(lang, idx) in pipelinePath" :key="idx" class="flex items-center">
                <div 
                  class="w-6 h-6 rounded-full border flex items-center justify-center text-[8px] transition-all duration-500 shrink-0"
                  :class="currentLang === lang ? 'bg-cyan-500/20 border-cyan-400 text-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.5)] scale-110' 
                         : (isStepDone(lang) ? 'bg-transparent border-blue-600 text-blue-600' : 'bg-gray-800 border-gray-700 text-gray-600')"
                >
                  {{ lang }}
                </div>
                <div v-if="idx < pipelinePath.length - 1" class="w-2 h-0.5 bg-gray-700 mx-0.5"></div>
              </div>
              
              <div class="w-4 h-0.5 bg-gray-700"></div>
              <div class="w-6 h-6 rounded-full bg-gray-800 border border-gray-600 flex items-center justify-center text-[8px] text-gray-400 shrink-0"
                :class="{ 'border-emerald-500 text-emerald-500': currentLang === 'FINAL' }">
                END
              </div>
            </div>
          </div>

        </div>

        <div class="flex-1 flex flex-col bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-xl overflow-hidden min-h-[300px]">
          <div class="p-3 bg-[#252525] border-b border-gray-700 flex justify-between items-center shrink-0">
            <div class="flex items-center gap-2">
              <span class="font-bold text-gray-300">
                {{ isLoading ? '⚗️ 正在熔炼...' : '✨ 最终产物' }}
              </span>
              <transition name="pop">
                <n-tag v-if="finalAiScore !== null" round size="small" :bordered="false"
                  :class="finalAiScore < 30 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'">
                  😊 {{ finalAiScore }}% AI
                </n-tag>
              </transition>
            </div>
            
            <div class="flex items-center gap-2">
              <div v-if="resultText && !isLoading" class="flex bg-black rounded p-0.5 border border-gray-700">
                <button 
                  @click="viewMode = 'text'"
                  class="px-2 py-0.5 text-xs rounded transition-colors"
                  :class="viewMode === 'text' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'"
                >纯文本</button>
                <button 
                  @click="viewMode = 'diff'"
                  class="px-2 py-0.5 text-xs rounded transition-colors"
                  :class="viewMode === 'diff' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'"
                >差异</button>
              </div>
              <n-button v-if="resultText && !isLoading" size="tiny" secondary type="primary" @click="copyResult">
                📋
              </n-button>
            </div>
          </div>

          <div class="flex-1 relative bg-[#161616] overflow-hidden">
            <div v-if="isLoading" class="absolute inset-0 z-10 bg-black/80 flex flex-col items-center justify-center font-mono">
              <div class="text-8xl font-black text-white/5 select-none absolute">{{ currentLang || 'INIT' }}</div>
              <div class="z-20 text-cyan-400 text-xs px-8 text-center leading-relaxed max-w-md opacity-80 break-words">
                {{ intermediateContent || '正在初始化神经链路...' }}
              </div>
              <div class="absolute bottom-0 w-full h-0.5 bg-gradient-to-r from-transparent via-cyan-500 to-transparent animate-scan"></div>
            </div>

            <div v-else class="w-full h-full">
              <textarea 
                v-if="viewMode === 'text'" 
                readonly 
                v-model="resultText" 
                placeholder="等待熔炼结果..."
                class="w-full h-full bg-transparent p-4 resize-none outline-none text-gray-300 text-sm leading-relaxed font-serif custom-scrollbar"
              ></textarea>
              
              <div 
                v-else 
                class="w-full h-full p-4 overflow-y-auto text-sm leading-loose font-serif text-gray-400 whitespace-pre-wrap custom-scrollbar" 
                v-html="diffHtml"
              ></div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue';
// 🔥 引入 Naive UI
import { NConfigProvider, NGlobalStyle, NButton, NTag, darkTheme } from 'naive-ui';

// 🔥 主题配置 (紫色/青色系)
const themeOverrides = {
  common: {
    primaryColor: '#00e5ff',
    primaryColorHover: '#33ebff',
    primaryColorPressed: '#00b8cc',
  },
};

// --- 以下业务逻辑保持 100% 原样 ---

const sourceText = ref('');
const resultText = ref('');
const isLoading = ref(false);
const viewMode = ref('text');
const logs = ref([]);
const logContainer = ref(null);

const pipelinePath = ref([]);
const currentLang = ref('');
const originLang = ref('');
const intermediateContent = ref('');
const processedSteps = ref([]);

// 🔥 AI 分数
const inputAiScore = ref(null);
const finalAiScore = ref(null);

// Diff 算法
const diffWords = (text1, text2) => {
  if (!text1 || !text2) return '';
  const isChinese = (str) => /[\u4e00-\u9fa5]/.test(str);
  let words1 = isChinese(text1) ? text1.split('') : text1.split(/([^\S\r\n]+|[().,;!?])/).filter(Boolean);
  let words2 = isChinese(text2) ? text2.split('') : text2.split(/([^\S\r\n]+|[().,;!?])/).filter(Boolean);

  const n = words1.length, m = words2.length;
  const dp = Array(n + 1).fill(0).map(() => Array(m + 1).fill(0));

  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (words1[i - 1] === words2[j - 1]) dp[i][j] = dp[i - 1][j - 1] + 1;
      else dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  let i = n, j = m;
  let html = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && words1[i - 1] === words2[j - 1]) {
      html.unshift(`<span class="text-gray-300">${words1[i - 1]}</span>`); i--; j--; // 普通文本
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      html.unshift(`<span class="bg-emerald-500/20 text-emerald-400 font-bold px-0.5 rounded">${words2[j - 1]}</span>`); j--; // 新增
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      html.unshift(`<span class="bg-red-500/20 text-red-400 line-through px-0.5 rounded">${words1[i - 1]}</span>`); i--; // 删除
    }
  }
  return html.join('');
};

const diffHtml = computed(() => diffWords(sourceText.value, resultText.value));
const isStepDone = (lang) => processedSteps.value.includes(lang);

const addLog = (msg) => {
  logs.value.push(msg);
  nextTick(() => {
    if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight;
  });
};

const clearAll = () => {
  sourceText.value = '';
  resultText.value = '';
  inputAiScore.value = null;
  finalAiScore.value = null;
  pipelinePath.value = [];
  logs.value = [];
}

const startPipeline = async () => {
  if (!sourceText.value.trim()) return;

  isLoading.value = true;
  resultText.value = '';
  pipelinePath.value = [];
  processedSteps.value = [];
  intermediateContent.value = '';
  currentLang.value = '';
  originLang.value = '';
  viewMode.value = 'text';
  logs.value = [];

  // 重置分数
  inputAiScore.value = null;
  finalAiScore.value = null;

  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/alchemy/de_ai`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: sourceText.value })
    });

    if (!response.ok) throw new Error("后端连接异常");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);

          if (data.step === 'thought') addLog(data.msg);
          else if (data.step === 'detected') {
            originLang.value = data.lang;
            // 🔥 更新输入分数
            inputAiScore.value = data.score;
            addLog(data.msg);
          }
          else if (data.step === 'path_created') {
            pipelinePath.value = data.path;
            addLog(`路径规划: ${data.desc}`);
          }
          else if (data.step === 'process') {
            currentLang.value = data.lang;
          }
          else if (data.step === 'update_view') {
            intermediateContent.value = data.content;
            if (data.lang && !processedSteps.value.includes(data.lang)) {
              const idx = pipelinePath.value.indexOf(data.lang);
              if (idx > 0) processedSteps.value.push(pipelinePath.value[idx - 1]);
            }
          }
          else if (data.step === 'done') {
            resultText.value = data.result;
            // 🔥 更新输出分数
            finalAiScore.value = data.final_score;
            processedSteps.value = [...pipelinePath.value];
            addLog(`✅ 熔炼完成 | AI 率降至 ${data.final_score}%`);
          }
          else if (data.step === 'error') {
            addLog(`❌ 错误: ${data.msg}`);
            resultText.value = "错误: " + data.msg;
          }
        } catch (e) { }
      }
    }
  } catch (e) {
    addLog(`❌ 系统错误: ${e.message}`);
  } finally {
    isLoading.value = false;
  }
};

const copyResult = () => {
  navigator.clipboard.writeText(resultText.value);
  alert("已复制");
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
  background: #42b983;
}

/* 徽章弹出动画 */
.pop-enter-active, .pop-leave-active {
  transition: all 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
}
.pop-enter-from, .pop-leave-to {
  transform: scale(0.5);
  opacity: 0;
}

/* 扫描线动画 */
@keyframes scan {
  0% { transform: translateY(0); }
  100% { transform: translateY(-300px); }
}
.animate-scan {
  animation: scan 1.5s linear infinite;
}
</style>