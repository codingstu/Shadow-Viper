<template>
    <div class="ide-container">

      <div class="sidebar-panel">
        <div class="sidebar-header">
          <h2>📦 应用库</h2>
          <span class="badge">{{ historyList.length }}</span>
        </div>
        <div class="history-list">
          <div v-for="item in historyList" :key="item.id" @click="loadApp(item.id)" class="history-item" :class="{ 'active': currentAppId === item.id }">
            <div class="item-title">{{ item.full_req }}</div>
            <div class="item-meta">
              <span>ID: {{ item.id }}</span>
              <button @click.stop="deleteApp(item.id)" class="delete-btn">×</button>
            </div>
          </div>
        </div>
      </div>

      <div class="main-editor">
        <div class="status-bar">
          <div class="traffic-lights">
            <span class="light red"></span><span class="light yellow"></span><span class="light green"></span>
          </div>

          <div class="view-toggles" v-if="generatedHtml || isStreaming">
            <button @click="viewMode = 'preview'" :class="{ active: viewMode === 'preview' }" class="toggle-btn" :disabled="isStreaming">👁️ 预览</button>
            <button @click="viewMode = 'code'" :class="{ active: viewMode === 'code' }" class="toggle-btn">💻 代码</button>
          </div>

          <span class="status-text">
            {{ isStreaming ? 'DeepSeek 正在疯狂码字...' : (currentAppId ? `App #${currentAppId} Ready` : 'Ready') }}
          </span>
          <button v-if="generatedHtml && !isStreaming" @click="refreshIframe" class="action-btn">🔄 重置</button>
        </div>

        <div class="content-viewport">
          <div v-show="viewMode === 'preview'" class="viewport-inner">
            <div v-if="!generatedHtml && !isStreaming" class="empty-state">
              <div class="empty-icon">⚛️</div>
              <p>输入需求，AI 将为你构建应用</p>
            </div>
            <iframe ref="iframeRef" v-if="generatedHtml && !isStreaming" class="app-frame" :srcdoc="generatedHtml" sandbox="allow-scripts allow-same-origin allow-modals allow-forms allow-popups"></iframe>
          </div>

          <div v-show="viewMode === 'code'" class="viewport-inner code-mode">
            <div class="code-actions" v-if="!isStreaming">
              <button @click="copyCode" class="copy-btn">📋 复制</button>
            </div>
            <textarea ref="codeTextarea" readonly class="code-viewer" :value="streamBuffer || generatedHtml"></textarea>
          </div>
        </div>

        <div class="input-area">
          <div class="input-wrapper">
            <span class="input-icon">✨</span>
            <input v-model="requirement" type="text" placeholder="例如：一个番茄钟，或者待办事项清单..." class="prompt-input" @keyup.enter="generateAppStream" :disabled="isStreaming" />
            <button @click="generateAppStream" :disabled="isStreaming || !requirement" class="generate-btn">
              {{ isStreaming ? '生成中...' : '生成' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </template>

  <script setup>
  import { ref, onMounted, nextTick, watch } from 'vue';

  const requirement = ref('');
  const generatedHtml = ref('');
  const streamBuffer = ref(''); // 🔥 用于存流式数据
  const isStreaming = ref(false);
  const historyList = ref([]);
  const currentAppId = ref(null);
  const viewMode = ref('preview');
  const codeTextarea = ref(null);

  const API_BASE = 'http://127.0.0.1:8000/api/generator';

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
  };

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
  /* 保持原有的暗黑 IDE 风格 */
  .ide-container { display: flex; height: 100%; width: 100%; background-color: #1e2024; color: #cfd0d2; font-family: 'Consolas', monospace; overflow: hidden; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.5); }
  .sidebar-panel { width: 260px; background-color: #25272e; border-right: 1px solid #111; display: flex; flex-direction: column; }
  .sidebar-header { padding: 15px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; }
  .history-list { flex: 1; overflow-y: auto; padding: 10px; }
  .history-item { padding: 12px; margin-bottom: 8px; background-color: #2d3038; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
  .history-item:hover { border-color: #555; }
  .history-item.active { background-color: rgba(59, 130, 246, 0.2); border-color: #3b82f6; }
  .item-title { font-size: 13px; color: #eee; margin-bottom: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .item-meta { display: flex; justify-content: space-between; font-size: 11px; color: #888; }
  .delete-btn { background: none; border: none; color: #666; cursor: pointer; }
  .delete-btn:hover { color: #ff4d4d; }

  .main-editor { flex: 1; display: flex; flex-direction: column; }
  .status-bar { height: 48px; background-color: #25272e; border-bottom: 1px solid #111; display: flex; align-items: center; padding: 0 20px; gap: 20px; }
  .traffic-lights { display: flex; gap: 8px; margin-right: 10px; }
  .light { width: 12px; height: 12px; border-radius: 50%; }
  .red { background: #ff5f56; } .yellow { background: #ffbd2e; } .green { background: #27c93f; }
  .view-toggles { display: flex; background: #1a1c22; border-radius: 6px; padding: 2px; }
  .toggle-btn { background: transparent; border: none; color: #888; padding: 4px 12px; font-size: 12px; cursor: pointer; border-radius: 4px; }
  .toggle-btn.active { background: #3b82f6; color: white; }
  .status-text { font-size: 13px; color: #888; flex: 1; text-align: center; }
  .action-btn { background-color: #333; color: #ccc; border: none; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }

  .content-viewport { flex: 1; position: relative; overflow: hidden; background-color: white; }
  .viewport-inner { width: 100%; height: 100%; position: relative; }
  .app-frame { width: 100%; height: 100%; border: none; }
  .empty-state { position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #1e2024; color: #666; }
  .empty-icon { font-size: 60px; margin-bottom: 20px; opacity: 0.3; }

  .code-mode { background-color: #282c34; display: flex; flex-direction: column; }
  .code-actions { padding: 8px; background: #21252b; border-bottom: 1px solid #181a1f; display: flex; justify-content: flex-end; }
  .copy-btn { background: #3b82f6; color: white; border: none; padding: 4px 10px; border-radius: 4px; font-size: 12px; cursor: pointer; }
  /* 黑客绿代码 */
  .code-viewer { flex: 1; width: 100%; background: #282c34; color: #98c379; border: none; padding: 15px; font-family: 'Consolas', monospace; font-size: 13px; line-height: 1.5; resize: none; outline: none; white-space: pre; }

  .input-area { background-color: #25272e; padding: 15px 20px; border-top: 1px solid #111; }
  .input-wrapper { position: relative; display: flex; align-items: center; }
  .input-icon { position: absolute; left: 15px; font-size: 18px; }
  .prompt-input { width: 100%; background-color: #1a1c22; border: 1px solid #333; border-radius: 8px; padding: 14px 100px 14px 45px; color: white; font-size: 14px; outline: none; transition: border-color 0.2s; }
  .prompt-input:focus { border-color: #3b82f6; }
  .generate-btn { position: absolute; right: 6px; background: linear-gradient(90deg, #3b82f6, #8b5cf6); color: white; border: none; padding: 8px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; }
  .generate-btn:disabled { opacity: 0.5; cursor: not-allowed; background: #444; }
  </style>