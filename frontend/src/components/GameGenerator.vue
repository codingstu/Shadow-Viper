<template>
    <div class="ide-container game-theme">
      
      <div class="sidebar-panel">
        <div class="sidebar-header">
          <h2>🎮 游戏库</h2>
          <span class="badge">{{ gameHistory.length }}</span>
        </div>
        <div class="history-list">
          <div v-for="item in gameHistory" :key="item.id" @click="loadGame(item.id)" class="history-item" :class="{ 'active': currentAppId === item.id }">
            <div class="item-title">{{ item.full_req.replace('[GAME] ', '') }}</div> 
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
            <button @click="viewMode = 'preview'" :class="{ active: viewMode === 'preview' }" class="toggle-btn" :disabled="isStreaming">🕹️ 试玩</button>
            <button @click="viewMode = 'code'" :class="{ active: viewMode === 'code' }" class="toggle-btn">👾 源码</button>
          </div>
          <span class="status-text">{{ isStreaming ? 'Building Game Engine...' : 'Ready to Play' }}</span>
          <button v-if="generatedHtml && !isStreaming" @click="refreshIframe" class="action-btn">🔄 重开一局</button>
        </div>
  
        <div class="content-viewport">
          <div v-show="viewMode === 'preview'" class="viewport-inner game-viewport">
            <div v-if="!generatedHtml && !isStreaming" class="empty-state">
              <div class="empty-icon">👾</div>
              <p>想玩什么？DeepSeek 现场给你做</p>
            </div>
            <iframe ref="iframeRef" v-if="generatedHtml && !isStreaming" class="app-frame" :srcdoc="generatedHtml" sandbox="allow-scripts allow-same-origin allow-modals allow-forms allow-popups allow-pointer-lock"></iframe>
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
            <span class="input-icon">🎮</span>
            <input v-model="requirement" type="text" placeholder="例如：一个躲避陨石的飞机游戏，按空格发射子弹..." class="prompt-input" @keyup.enter="generateGameStream" :disabled="isStreaming" />
            <button @click="generateGameStream" :disabled="isStreaming || !requirement" class="generate-btn">
              {{ isStreaming ? '编译中...' : 'Start' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref, onMounted, nextTick, watch, computed } from 'vue';
  
  const requirement = ref('');
  const generatedHtml = ref('');
  const streamBuffer = ref('');
  const isStreaming = ref(false);
  const historyList = ref([]);
  const currentAppId = ref(null);
  const viewMode = ref('preview');
  const codeTextarea = ref(null);
  
  // 游戏列表只显示 [GAME] 开头的
  const gameHistory = computed(() => historyList.value.filter(item => item.full_req.startsWith('[GAME]')));
  
  // 🔥🔥🔥 核心修复：这里必须是纯 URL，不能带 []() 🔥🔥🔥
  const API_BASE = 'http://127.0.0.1:8000/api/game'; 
  const HISTORY_API = 'http://127.0.0.1:8000/api/generator/history';
  const LOAD_API = 'http://127.0.0.1:8000/api/generator/load';
  const DELETE_API = 'http://127.0.0.1:8000/api/generator/delete';
  
  onMounted(() => fetchHistory());
  
  watch(streamBuffer, () => {
    if (codeTextarea.value) codeTextarea.value.scrollTop = codeTextarea.value.scrollHeight;
  });
  
  const fetchHistory = async () => {
    try {
      const res = await fetch(HISTORY_API);
      historyList.value = await res.json();
    } catch (e) { console.error(e); }
  };
  
  const generateGameStream = async () => {
    if (!requirement.value.trim()) return;
    isStreaming.value = true;
    streamBuffer.value = '';
    generatedHtml.value = '';
    currentAppId.value = null;
    viewMode.value = 'code';
    
    try {
      const response = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requirement: requirement.value })
      });
  
      if (!response.ok) throw new Error(response.statusText);
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
            if (data.type === 'chunk') streamBuffer.value += data.content;
            else if (data.type === 'done') {
              generatedHtml.value = data.html;
              currentAppId.value = data.id;
              streamBuffer.value = '';
              viewMode.value = 'preview';
              await fetchHistory();
            }
          } catch (e) {}
        }
      }
    } catch (e) { alert(e.message); } 
    finally { isStreaming.value = false; requirement.value = ''; }
  };
  
  const loadGame = async (id) => {
    if (currentAppId.value === id) return;
    isStreaming.value = true;
    viewMode.value = 'preview';
    try {
      const res = await fetch(`${LOAD_API}/${id}`);
      const data = await res.json();
      generatedHtml.value = data.html;
      currentAppId.value = id;
    } finally { isStreaming.value = false; }
  };
  
  const deleteApp = async (id) => {
    if (!confirm('Del?')) return;
    await fetch(`${DELETE_API}/${id}`, { method: 'DELETE' });
    await fetchHistory();
    if (currentAppId.value === id) { generatedHtml.value = ''; currentAppId.value = null; }
  };
  
  const refreshIframe = () => {
    const html = generatedHtml.value;
    generatedHtml.value = '';
    nextTick(() => generatedHtml.value = html);
  };
  const copyCode = () => navigator.clipboard.writeText(generatedHtml.value);
  </script>
  
  <style scoped>
  /* 游戏主题样式 */
  .ide-container { display: flex; height: 100%; width: 100%; background-color: #1e1e24; color: #d0cfd2; font-family: 'Consolas', monospace; overflow: hidden; border-radius: 8px; }
  .sidebar-panel { width: 260px; background-color: #25252e; border-right: 1px solid #000; display: flex; flex-direction: column; }
  .sidebar-header { padding: 15px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; }
  .sidebar-header h2 { color: #a78bfa; margin: 0; font-size: 16px; }
  .badge { background-color: #8b5cf6; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
  
  .history-list { flex: 1; overflow-y: auto; padding: 10px; }
  .history-item { padding: 12px; margin-bottom: 8px; background-color: #2d2d38; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
  .history-item:hover { border-color: #666; }
  .history-item.active { background-color: rgba(139, 92, 246, 0.2); border-color: #8b5cf6; }
  .item-title { font-size: 13px; color: #eee; margin-bottom: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .item-meta { display: flex; justify-content: space-between; font-size: 11px; color: #888; }
  .delete-btn { background: none; border: none; color: #666; cursor: pointer; }
  .delete-btn:hover { color: #ff4d4d; }
  
  .main-editor { flex: 1; display: flex; flex-direction: column; }
  .status-bar { height: 48px; background-color: #25252e; border-bottom: 1px solid #000; display: flex; align-items: center; padding: 0 20px; gap: 20px; }
  .traffic-lights { display: flex; gap: 8px; margin-right: 10px; }
  .light { width: 12px; height: 12px; border-radius: 50%; }
  .red { background: #ff5f56; } .yellow { background: #ffbd2e; } .green { background: #27c93f; }
  .view-toggles { display: flex; background: #1a1a22; border-radius: 6px; padding: 2px; }
  .toggle-btn { background: transparent; border: none; color: #888; padding: 4px 12px; font-size: 12px; cursor: pointer; border-radius: 4px; }
  .toggle-btn.active { background: #8b5cf6; color: white; }
  .status-text { font-size: 13px; color: #888; flex: 1; text-align: center; }
  .action-btn { background-color: #333; color: #ccc; border: none; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
  
  .content-viewport { flex: 1; position: relative; overflow: hidden; background-color: #000; }
  .viewport-inner { width: 100%; height: 100%; position: relative; }
  .app-frame { width: 100%; height: 100%; border: none; }
  .empty-state { position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #1e1e24; color: #666; }
  .empty-icon { font-size: 60px; margin-bottom: 20px; opacity: 0.3; }
  
  .code-mode { background-color: #282c34; display: flex; flex-direction: column; }
  .code-actions { padding: 8px; background: #21252b; border-bottom: 1px solid #181a1f; display: flex; justify-content: flex-end; }
  .copy-btn { background: #8b5cf6; color: white; border: none; padding: 4px 10px; border-radius: 4px; font-size: 12px; cursor: pointer; }
  .code-viewer { flex: 1; width: 100%; background: #282c34; color: #d19a66; border: none; padding: 15px; font-family: 'Consolas', monospace; font-size: 13px; line-height: 1.5; resize: none; outline: none; white-space: pre; }
  
  .input-area { background-color: #25252e; padding: 15px 20px; border-top: 1px solid #000; }
  .input-wrapper { position: relative; display: flex; align-items: center; }
  .input-icon { position: absolute; left: 15px; font-size: 18px; }
  .prompt-input { width: 100%; background-color: #1a1a22; border: 1px solid #333; border-radius: 8px; padding: 14px 100px 14px 45px; color: white; font-size: 14px; outline: none; transition: border-color 0.2s; }
  .prompt-input:focus { border-color: #8b5cf6; }
  .generate-btn { position: absolute; right: 6px; background: linear-gradient(90deg, #8b5cf6, #d946ef); color: white; border: none; padding: 8px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; }
  .generate-btn:disabled { opacity: 0.5; cursor: not-allowed; background: #444; }
  </style>