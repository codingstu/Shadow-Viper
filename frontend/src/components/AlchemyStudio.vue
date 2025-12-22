<template>
  <div class="alchemy-container">
    <div class="header">
      <div class="title-box">
        <span class="icon">🌌</span>
        <div class="text-group">
          <h1>Chaos Humanizer <span class="badge">Ultra</span></h1>
          <p>多维语言熵增系统：思维链可视化 · 自动回译 · 深度去重</p>
        </div>
      </div>
    </div>

    <div class="workspace">

      <div class="panel input-panel">
        <div class="panel-header">
          <div class="ph-left">
            <span class="panel-title">📄 原始文本</span>
            <div class="ai-score-badge high" v-if="inputAiScore !== null">
              <span class="score-icon">🤖</span>
              <span class="score-val">{{ inputAiScore }}% AI</span>
            </div>
          </div>
          <div class="actions">
            <span class="char-count">{{ sourceText.length }} chars</span>
            <button @click="clearAll" class="icon-btn">✕</button>
          </div>
        </div>
        <div class="editor-anchor">
          <textarea v-model="sourceText" placeholder="在此粘贴论文... 系统将自动检测 AI 浓度并清洗" class="magic-textarea source"
            spellcheck="false"></textarea>
        </div>
      </div>

      <div class="control-center">
        <button @click="startPipeline" class="transmute-btn" :disabled="isLoading || !sourceText"
          :class="{ 'processing': isLoading }">
          <div class="btn-content">
            <span v-if="!isLoading" class="btn-icon">⚛️</span>
            <span v-else class="spinner"></span>
            <span class="btn-text">{{ isLoading ? '运行中' : '启动熵增' }}</span>
          </div>
        </button>

        <div class="neural-terminal">
          <div class="terminal-header">
            <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
            <span class="term-title">Kernel Log</span>
          </div>
          <div class="terminal-body" ref="logContainer">
            <div v-for="(log, idx) in logs" :key="idx" class="term-line">
              <span class="term-arrow">></span> {{ log }}
            </div>
            <div class="typing-cursor" v-if="isLoading">_</div>
          </div>
        </div>

        <div class="process-viz" v-if="pipelinePath.length > 0">
          <div class="path-steps">
            <div class="viz-step start">{{ originLang || '?' }}</div>
            <div class="viz-line"></div>
            <div v-for="(lang, idx) in pipelinePath" :key="idx" class="viz-step mid"
              :class="{ 'active': currentLang === lang, 'done': isStepDone(lang) }">
              {{ lang }}
            </div>
            <div class="viz-line"></div>
            <div class="viz-step end" :class="{ 'active': currentLang === 'FINAL' }">
              {{ originLang || 'END' }}
            </div>
          </div>
        </div>
      </div>

      <div class="panel output-panel">
        <div class="panel-header">
          <div class="ph-left">
            <span class="panel-title">
              {{ isLoading ? '⚗️ 重构中...' : '✨ 最终产物' }}
            </span>
            <div class="ai-score-badge low" v-if="finalAiScore !== null">
              <span class="score-icon">😊</span>
              <span class="score-val">{{ finalAiScore }}% AI</span>
            </div>
          </div>
          <div class="actions">
            <div class="view-toggle" v-if="resultText && !isLoading">
              <button :class="{ active: viewMode === 'text' }" @click="viewMode = 'text'">纯文本</button>
              <button :class="{ active: viewMode === 'diff' }" @click="viewMode = 'diff'">差异对比</button>
            </div>
            <button @click="copyResult" class="icon-btn copy" v-if="resultText && !isLoading">📋</button>
          </div>
        </div>

        <div class="editor-anchor output-bg">
          <div v-if="isLoading" class="intermediate-view">
            <div class="lang-badge">{{ currentLang || 'INIT' }}</div>
            <div class="matrix-text">{{ intermediateContent || '正在初始化...' }}</div>
            <div class="scan-line"></div>
          </div>

          <div v-else class="final-view">
            <textarea v-if="viewMode === 'text'" readonly v-model="resultText" placeholder="等待熔炼结果..."
              class="magic-textarea result"></textarea>
            <div v-else class="diff-view-container" v-html="diffHtml"></div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue';

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

// 🔥 新增：AI 分数
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
      html.unshift(`<span class="diff-same">${words1[i - 1]}</span>`); i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      html.unshift(`<span class="diff-ins">${words2[j - 1]}</span>`); j--;
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      html.unshift(`<span class="diff-del">${words1[i - 1]}</span>`); i--;
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
    const response = await fetch('http://127.0.0.1:8000/api/alchemy/de_ai', {
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
/* 全局样式 */
.alchemy-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  color: #e0e0e0;
  gap: 20px;
  font-family: 'Inter', sans-serif;
  overflow: hidden;
}

.header {
  padding: 0 10px;
  flex-shrink: 0;
}

.title-box {
  display: flex;
  align-items: center;
  gap: 15px;
}

.icon {
  font-size: 32px;
  filter: drop-shadow(0 0 10px rgba(0, 229, 255, 0.6));
}

.text-group h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  background: linear-gradient(to right, #00e5ff, #2979ff);
  -webkit-background-clip: text;
  color: transparent;
}

.badge {
  font-size: 10px;
  vertical-align: super;
  background: #2979ff;
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
}

.text-group p {
  margin: 4px 0 0;
  color: #888;
  font-size: 12px;
}

.workspace {
  display: flex;
  flex: 1;
  gap: 20px;
  padding-bottom: 20px;
  min-height: 0;
  overflow: hidden;
}

/* 面板 */
.panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(30, 30, 30, 0.6);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
  min-width: 0;
}

.panel-header {
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.ph-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #ccc;
}

/* 🔥 AI 分数徽章 */
.ai-score-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  border: 1px solid transparent;
  animation: popIn 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
}

.ai-score-badge.high {
  background: rgba(255, 82, 82, 0.1);
  color: #ff5252;
  border-color: rgba(255, 82, 82, 0.3);
}

.ai-score-badge.low {
  background: rgba(105, 240, 174, 0.1);
  color: #69f0ae;
  border-color: rgba(105, 240, 174, 0.3);
}

@keyframes popIn {
  0% {
    transform: scale(0.5);
    opacity: 0;
  }

  100% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 编辑锚点 */
.editor-anchor {
  flex: 1;
  position: relative;
  width: 100%;
  height: 100%;
}

.magic-textarea {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100% !important;
  height: 100% !important;
  background: transparent;
  border: none;
  padding: 20px;
  color: #e0e0e0;
  font-size: 15px;
  line-height: 1.8;
  resize: none;
  outline: none;
  font-family: 'Georgia', serif;
  overflow-y: auto !important;
  box-sizing: border-box;
}

/* 中控 */
.control-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  width: 240px;
  padding-top: 20px;
  flex-shrink: 0;
}

.transmute-btn {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #2979ff, #00e5ff);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 0 20px rgba(41, 121, 255, 0.5);
  transition: all 0.3s;
  flex-shrink: 0;
}

.transmute-btn:hover:not(:disabled) {
  transform: scale(1.1);
  box-shadow: 0 0 40px rgba(0, 229, 255, 0.8);
}

.btn-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.btn-icon {
  font-size: 24px;
}

.btn-text {
  font-size: 9px;
  font-weight: bold;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid #fff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.neural-terminal {
  width: 100%;
  flex: 1;
  background: #000;
  border-radius: 8px;
  border: 1px solid #333;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: 'Consolas', monospace;
  font-size: 11px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
  min-height: 0;
}

.terminal-header {
  background: #222;
  padding: 5px 10px;
  display: flex;
  gap: 5px;
  align-items: center;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.red {
  background: #ff5f56;
}

.yellow {
  background: #ffbd2e;
}

.green {
  background: #27c93f;
}

.term-title {
  color: #666;
  margin-left: auto;
  font-size: 9px;
}

.terminal-body {
  flex: 1;
  padding: 10px;
  overflow-y: auto;
  color: #00e5ff;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.term-arrow {
  color: #2979ff;
  margin-right: 5px;
}

.typing-cursor {
  animation: blink 1s infinite;
  display: inline-block;
}

.process-viz {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  gap: 8px;
  flex-shrink: 0;
  margin-bottom: 10px;
}

.path-steps {
  display: flex;
  align-items: center;
  gap: 4px;
}

.viz-step {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #222;
  border-radius: 50%;
  border: 1px solid #444;
  color: #666;
  font-size: 10px;
  font-weight: bold;
  transition: all 0.5s;
}

.viz-line {
  width: 10px;
  height: 2px;
  background: #333;
}

.viz-step.active {
  border-color: #00e5ff;
  color: #fff;
  background: rgba(0, 229, 255, 0.2);
  box-shadow: 0 0 10px #00e5ff;
  transform: scale(1.1);
}

.viz-step.done {
  border-color: #2979ff;
  color: #2979ff;
  background: transparent;
}

/* 视图 */
.intermediate-view {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: rgba(0, 0, 0, 0.3);
  color: #00e5ff;
  font-family: monospace;
  overflow: hidden;
}

.lang-badge {
  font-size: 80px;
  opacity: 0.1;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-weight: 900;
  z-index: 0;
}

.matrix-text {
  z-index: 2;
  text-align: center;
  max-width: 90%;
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.5;
  opacity: 0.8;
}

.scan-line {
  height: 2px;
  width: 100%;
  background: linear-gradient(90deg, transparent, #00e5ff, transparent);
  position: absolute;
  bottom: 0;
  animation: scan 1.2s infinite linear;
}

.final-view {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
}

.diff-view-container {
  width: 100%;
  height: 100%;
  padding: 20px;
  overflow-y: auto;
  font-size: 15px;
  line-height: 2;
  font-family: 'Georgia', serif;
  color: #888;
  white-space: pre-wrap;
  box-sizing: border-box;
}

:deep(.diff-del) {
  background: rgba(244, 67, 54, 0.2);
  color: #ff8a80;
  text-decoration: line-through;
  padding: 0 2px;
  border-radius: 3px;
}

:deep(.diff-ins) {
  background: rgba(0, 230, 118, 0.2);
  color: #69f0ae;
  font-weight: bold;
  padding: 0 2px;
  border-radius: 3px;
}

:deep(.diff-same) {
  color: #ccc;
}

.view-toggle button {
  background: transparent;
  border: 1px solid #444;
  color: #888;
  margin-left: 5px;
  cursor: pointer;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
}

.view-toggle button.active {
  background: #2979ff;
  color: white;
  border-color: #2979ff;
}

.icon-btn {
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  font-size: 16px;
  margin-left: 10px;
}

/* 滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

@keyframes scan {
  0% {
    transform: translateY(0);
  }

  100% {
    transform: translateY(-300px);
  }
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>