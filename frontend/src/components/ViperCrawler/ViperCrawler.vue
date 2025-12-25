<template>
  <div class="viper-container">
    <div class="header">
      <h1>🕷️ Viper 爬虫控制台</h1>
      <p>多引擎驱动：极速 API · 智能 HTML 解析 · 深度流媒体嗅探</p>
    </div>

    <div class="input-section">
      <div class="input-group">
        <input v-model="targetUrl" type="text" placeholder="输入网址 (支持 MissAV, Reddit, 知乎, B站等)" :disabled="isCrawling" />

        <select v-model="crawlMode" :disabled="isCrawling" class="mode-select">
          <option value="text">📄 极速文本</option>
          <option value="media">🎬 深度媒体</option>
        </select>

        <select v-model="networkType" :disabled="isCrawling" class="mode-select network-select">
          <option value="auto">🤖 自动模式</option>
          <option value="node">🛰️ Shadow Matrix</option>
          <option value="proxy">🌐 猎手 IP 池</option>
          <option value="direct">⚡️ 仅直连</option>
        </select>

        <button 
          @click="startCrawl" 
          :disabled="isCrawling || !targetUrl"
          :class="{ 'processing': isCrawling }"
        >
          <span v-if="!isCrawling">开始爬取</span>
          <span v-else>⏳ 停止 (运行中...)</span>
        </button>
      </div>
    </div>

    <div class="main-display">
      <div class="panel log-panel">
        <div class="panel-header">
          <div class="header-title-group">
            <span>系统日志</span>
            <div class="status-indicator" :class="{ 'active': isCrawling || isAnalyzing }">
              <span class="status-dot"></span>
              <span class="status-text">{{ isCrawling ? '爬取中...' : (isAnalyzing ? '分析中...' : '任务空闲') }}</span>
            </div>
          </div>
        </div>
        
        <div class="log-window" ref="logWindowRef">
          <div v-for="(log, idx) in logs" :key="idx" class="log-line" :class="log.type">
            <span class="time">[{{ log.time }}]</span>
            <span class="msg">> {{ log.text }}</span>
          </div>
          <div v-if="logs.length === 0" class="placeholder">等待指令输入...</div>
        </div>
      </div>

      <div class="panel preview-panel">
        <div class="panel-header">
          <span>{{ crawlMode === 'text' ? '文本数据 (表格视图)' : '媒体/混合数据 (流视图)' }}</span>
          <div class="header-actions">
            <span v-if="previewData.length" class="count-tag">{{ previewData.length }} 条数据</span>
            
            <button 
              v-if="previewData.length > 0 && crawlMode === 'text'" 
              @click="startBattle" 
              class="mini-btn battle-btn"
              :disabled="isAnalyzing"
            >
              {{ isAnalyzing ? '⚔️ 分析战局中...' : '⚔️ 开启赛博斗兽场' }}
            </button>

            <button v-if="previewData.length > 0" @click="clearPreview" class="mini-btn">清除</button>
          </div>
        </div>

        <div class="preview-content-area">

          <div v-if="showBattlefield" class="battlefield-container">
            <div class="battle-header">
              <div class="team-score red">{{ teamRed.name || '红方' }}: {{ teamRed.warriors.filter(w => w.hp > 0).length }}</div>
              <div class="vs-badge">VS</div>
              <div class="team-score blue">{{ teamBlue.name || '蓝方' }}: {{ teamBlue.warriors.filter(w => w.hp > 0).length }}</div>
              <button @click="closeBattle" class="close-battle-btn">✕</button>
            </div>
            <canvas ref="canvasRef" class="battle-canvas"></canvas>
            <div v-if="winner" class="winner-overlay">
              <h2>🏆 {{ winner.name }} 获胜!</h2>
              <p>MVP: {{ mvp.id }} (造成 {{ mvp.damageDealt }} 点伤害)</p>
              <button @click="resetBattle" class="restart-btn">再战一场</button>
            </div>
          </div>

          <div v-else-if="crawlMode === 'text'" class="table-container">
            <table v-if="previewData.length > 0">
              <thead>
                <tr>
                  <th class="col-type">类型</th>
                  <th class="col-content">内容</th>
                  <th class="col-remark">备注</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in previewData" :key="idx">
                  <td><span class="type-tag">{{ row['类型'] }}</span></td>
                  <td class="content-cell" :title="row['内容']">{{ row['内容'] }}</td>
                  <td class="remark-cell">{{ row['备注'] }}</td>
                </tr>
              </tbody>
            </table>

            <div v-else class="preview-placeholder">
              <div class="empty-state">
                <span class="icon">📄</span>
                <p>{{ isCrawling ? '正在解析数据...' : '暂无文本数据' }}</p>
                <p class="sub-text">数据将在此处以宽屏表格形式展示</p>
              </div>
            </div>
          </div>

          <div v-else class="media-container">
            <div v-if="mediaItems.length > 0" class="media-stream-list">
              <div v-for="(item, idx) in mediaItems" :key="idx" class="media-card" :class="item.type">
                <div v-if="item.type === 'video'" class="video-layout">
                  <div class="video-player-wrapper">
                    <video :ref="(el) => initVideoPlayer(el, item.url)" class="hls-player" controls
                      :poster="proxyUrl(item.cover)" playsinline>
                    </video>
                    <div class="format-badge">{{ item.url.includes('.m3u8') ? 'HLS' : 'MP4' }}</div>
                  </div>
                  <div class="video-meta-side">
                    <div class="cover-box" v-if="item.cover && item.cover !== 'No Cover'">
                      <img :src="proxyUrl(item.cover)" alt="封面" @click="openLink(item.cover)">
                      <span class="cover-label">封面</span>
                    </div>
                    <div class="meta-info">
                      <span class="badge video">VIDEO</span>
                      <h4 :title="item.title">{{ item.title || 'Unknown Video' }}</h4>
                      <button class="copy-btn" @click="copyToClipboard(item.url)">复制地址</button>
                    </div>
                  </div>
                </div>
                <div v-else-if="item.type === 'image'" class="image-layout">
                  <img :src="proxyUrl(item.url)" class="preview-img" @click="openLink(item.url)" loading="lazy" />
                  <span class="badge image">IMG</span>
                </div>
                <div v-else class="text-card-layout">
                  <div class="text-header">
                    <span class="badge text">{{ item.rawType }}</span>
                  </div>
                  <p class="text-content">{{ item.content }}</p>
                </div>
              </div>
            </div>
            <div v-else class="preview-placeholder">
              <div class="empty-state">
                <span class="icon">🕸️</span>
                <p>{{ isCrawling ? '正在渲染数据流...' : '暂无数据' }}</p>
                <p class="sub-text">视频/图片/文本流将在此处显示</p>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, onUnmounted } from 'vue';
import Hls from 'hls.js';
import axios from 'axios';

const targetUrl = ref('');
const crawlMode = ref('text');
const networkType = ref('auto');
const logs = ref([]);
const isCrawling = ref(false);
const logWindowRef = ref(null);
const previewData = ref([]);

const showBattlefield = ref(false);
const isAnalyzing = ref(false);
const canvasRef = ref(null);
const teamRed = ref({ name: '红方', warriors: [] });
const teamBlue = ref({ name: '蓝方', warriors: [] });
const winner = ref(null);
const mvp = ref({ id: '', damageDealt: 0 });
let animationFrameId = null;

const getCurrentTime = () => new Date().toLocaleTimeString();

const proxyUrl = (url) => {
  if (!url || url === 'No Cover') return '';
  return `${import.meta.env.VITE_API_BASE_URL}/api/proxy?url=${encodeURIComponent(url)}`;
};

const initVideoPlayer = (videoEl, originalUrl) => {
  if (!videoEl || !originalUrl || videoEl.dataset.initialized === 'true') return;
  const proxied = proxyUrl(originalUrl);
  if (originalUrl.includes('.m3u8')) {
    if (Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(proxied);
      hls.attachMedia(videoEl);
    } else if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
      videoEl.src = proxied;
    }
  } else {
    videoEl.src = proxied;
  }
  videoEl.dataset.initialized = 'true';
};

const mediaItems = computed(() => {
  if (crawlMode.value !== 'media') return [];
  return previewData.value.map(row => {
    const type = row['类型'] || '';
    if (type === '视频') return { type: 'video', url: row['内容'], cover: row['备注'], title: row['标题'] };
    if (type === '图片') return { type: 'image', url: row['内容'] };
    if (!['标题', 'Meta', 'Title', 'Video-Title', 'API-Title'].includes(type) && row['内容']?.length > 2) {
      return { type: 'text', content: row['内容'], rawType: type };
    }
    return null;
  }).filter(Boolean);
});

const startCrawl = async () => {
  let finalUrl = targetUrl.value.trim();
  if (!finalUrl) return;
  if (!finalUrl.startsWith('http')) finalUrl = 'https://' + finalUrl;

  isCrawling.value = true;
  logs.value = [];
  clearPreview();
  showBattlefield.value = false;

  logs.value.push({ time: getCurrentTime(), text: `🚀 启动 Viper 引擎 [${crawlMode.value}] [Net: ${networkType.value}]...`, type: 'info' });

  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/crawl`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        url: finalUrl, 
        mode: crawlMode.value, 
        network_type: networkType.value,
      })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n').filter(line => line.trim());

      for (const line of lines) {
        try {
          const data = JSON.parse(line);
          if (data.step === 'done') {
            previewData.value = data.data;
            logs.value.push({ time: getCurrentTime(), text: `✅ 任务完成，已渲染 ${data.data.length} 条数据`, type: 'success' });
          } else if (data.step === 'error') {
            logs.value.push({ time: getCurrentTime(), text: '❌ ' + data.message, type: 'error' });
          } else {
            logs.value.push({ time: getCurrentTime(), text: data.message, type: 'info' });
          }
          await nextTick();
          if (logWindowRef.value) logWindowRef.value.scrollTop = logWindowRef.value.scrollHeight;
        } catch (e) { }
      }
    }
  } catch (err) {
    logs.value.push({ time: getCurrentTime(), text: '系统错误: ' + err.message, type: 'error' });
  } finally {
    isCrawling.value = false;
  }
};

const startBattle = async () => {
  if (previewData.value.length === 0) return;
  
  const titleRow = previewData.value.find(row => row['类型'] === '标题' || row['类型'] === 'H1');
  const postTitle = titleRow ? titleRow['内容'] : 'Unknown Topic';

  isAnalyzing.value = true;
  logs.value.push({ time: getCurrentTime(), text: '⚔️ 正在分析评论区阵营...', type: 'info' });
  
  try {
    const payload = {
      post_title: postTitle,
      comments: JSON.parse(JSON.stringify(previewData.value))
    };

    const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL}/api/crawl/analyze_comments`, payload);
    
    teamRed.value = response.data.team_red;
    teamBlue.value = response.data.team_blue;
    
    showBattlefield.value = true;
    logs.value.push({ time: getCurrentTime(), text: `✅ 战局生成: ${teamRed.value.name} vs ${teamBlue.value.name}`, type: 'success' });
    
    await nextTick();
    setupBattle();
    
  } catch (error) {
    logs.value.push({ time: getCurrentTime(), text: '❌ 战局分析失败: ' + (error.response?.data?.detail || error.message), type: 'error' });
  } finally {
    isAnalyzing.value = false;
  }
};

const setupBattle = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  
  const container = canvas.parentElement;
  canvas.width = container.offsetWidth;
  canvas.height = container.offsetHeight;
  
  const ctx = canvas.getContext('2d');

  teamRed.value.warriors.forEach((w, i) => {
    w.x = 50 + Math.random() * 50;
    w.y = 50 + (i * 30) % (canvas.height - 100);
    w.hp = w.armor;
    w.maxHp = w.armor;
    w.damageDealt = 0;
    w.color = '#ff4444';
  });
  
  teamBlue.value.warriors.forEach((w, i) => {
    w.x = canvas.width - 100 + Math.random() * 50;
    w.y = 50 + (i * 30) % (canvas.height - 100);
    w.hp = w.armor;
    w.maxHp = w.armor;
    w.damageDealt = 0;
    w.color = '#4488ff';
  });

  winner.value = null;
  mvp.value = { id: '', damageDealt: 0 };
  
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  animateBattle();
};

const animateBattle = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  drawTeam(ctx, teamRed.value.warriors);
  drawTeam(ctx, teamBlue.value.warriors);

  if (!winner.value) {
    if (Math.random() < 0.1) {
        simulateRound();
    }
    animationFrameId = requestAnimationFrame(animateBattle);
  } else {
    const allWarriors = [...teamRed.value.warriors, ...teamBlue.value.warriors];
    mvp.value = allWarriors.reduce((max, w) => w.damageDealt > max.damageDealt ? w : max, { id: 'None', damageDealt: 0 });
  }
};

const drawTeam = (ctx, warriors) => {
  warriors.forEach(w => {
    if (w.hp > 0) {
      ctx.fillStyle = w.color;
      ctx.fillRect(w.x, w.y, 10, 10);
      
      const hpPercent = w.hp / w.maxHp;
      ctx.fillStyle = '#333';
      ctx.fillRect(w.x, w.y - 6, 10, 3);
      ctx.fillStyle = '#0f0';
      ctx.fillRect(w.x, w.y - 6, 10 * hpPercent, 3);
      
      ctx.fillStyle = '#aaa';
      ctx.font = '10px monospace';
      ctx.fillText(w.id.substring(0, 8), w.x, w.y + 20);
    }
  });
};

const simulateRound = () => {
  const attack = (attackers, defenders) => {
    attackers.forEach(att => {
      if (att.hp <= 0) return;
      
      const targets = defenders.filter(d => d.hp > 0);
      if (targets.length === 0) return;
      
      const target = targets[Math.floor(Math.random() * targets.length)];
      
      att.x += (target.x - att.x) * 0.05;
      
      const dmg = Math.max(1, Math.floor((att.attack + att.poison) * 0.1));
      target.hp -= dmg;
      att.damageDealt += dmg;
      
      if (Math.abs(target.x - att.x) < 20) {
          att.x -= (target.x - att.x) * 0.5;
      }
    });
  };

  attack(teamRed.value.warriors, teamBlue.value.warriors);
  attack(teamBlue.value.warriors, teamRed.value.warriors);

  const redAlive = teamRed.value.warriors.some(w => w.hp > 0);
  const blueAlive = teamBlue.value.warriors.some(w => w.hp > 0);

  if (!blueAlive && redAlive) winner.value = teamRed.value;
  else if (!redAlive && blueAlive) winner.value = teamBlue.value;
  else if (!redAlive && !blueAlive) winner.value = { name: '平局' };
};

const resetBattle = () => { setupBattle(); };
const closeBattle = () => { showBattlefield.value = false; if (animationFrameId) cancelAnimationFrame(animationFrameId); };
const clearPreview = () => { previewData.value = []; showBattlefield.value = false; };
const openLink = (url) => window.open(url, '_blank');
const copyToClipboard = (text) => { navigator.clipboard.writeText(text); alert('地址已复制'); };

onUnmounted(() => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
});
</script>

<style scoped>
/* 容器设置 */
.viper-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 40px);
  width: 100%;
  background: #121212;
  color: #e0e0e0;
  box-sizing: border-box;
  overflow: hidden;
}

.header h1 {
  color: #42b983;
  margin: 0;
  text-align: center;
}

.header p {
  color: #666;
  margin: 5px 0 20px 0;
  text-align: center;
}

/* 输入区 */
.input-section {
  margin-bottom: 20px;
  flex-shrink: 0;
}

.input-group {
  display: flex;
  gap: 10px;
  max-width: 900px;
  margin: 0 auto;
}

input {
  flex: 1;
  padding: 12px;
  background: #1e1e1e;
  border: 1px solid #333;
  color: #fff;
  border-radius: 6px;
}

.mode-select {
  background: #252525;
  color: #fff;
  border: 1px solid #333;
  padding: 0 15px;
  border-radius: 6px;
}

.network-select {
  background-color: #2c3e50 !important;
  color: #ecf0f1 !important;
  border-color: #34495e !important;
}

button {
  padding: 0 30px;
  background: #42b983;
  border: none;
  color: #fff;
  font-weight: bold;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.3s;
}

button:disabled {
  background: #333;
  color: #888;
  cursor: not-allowed;
}

/* 🔥 按钮运行时的状态 */
button.processing {
  background: #2c3e50;
  border: 1px solid #3e5871;
  color: #fff;
  cursor: wait;
}

/* 主显示区 */
.main-display {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.panel {
  flex: 1 1 0px;
  background: #1e1e1e;
  border-radius: 12px;
  border: 1px solid #333;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.panel-header {
  padding: 10px 15px;
  background: #252525;
  border-bottom: 1px solid #333;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #ccc;
  font-weight: bold;
  flex-shrink: 0;
}

/* 🔥 系统日志标题组样式 */
.header-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 🔥 呼吸灯样式 */
.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: normal;
  background: rgba(0,0,0,0.2);
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid #444;
  color: #666;
  transition: all 0.3s;
}

.status-dot {
  width: 8px;
  height: 8px;
  background-color: #666;
  border-radius: 50%;
  transition: all 0.3s;
}

/* 激活状态 */
.status-indicator.active {
  border-color: rgba(66, 185, 131, 0.5);
  background: rgba(66, 185, 131, 0.1);
  color: #42b983;
}

.status-indicator.active .status-dot {
  background-color: #42b983;
  box-shadow: 0 0 8px #42b983;
  animation: breathe 1.5s infinite ease-in-out;
}

/* 呼吸动画 */
@keyframes breathe {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.6; }
  100% { transform: scale(1); opacity: 1; }
}

/* 日志窗口 */
.log-window {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
  font-family: 'Consolas', monospace;
  font-size: 0.9em;
  background: #1a1a1a;
}

.log-line {
  margin-bottom: 5px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  word-break: break-all;
}

.time {
  color: #555;
  margin-right: 10px;
}

.info {
  color: #64b5f6;
}

.success {
  color: #81c784;
}

.error {
  color: #e57373;
}

.download-box {
  padding: 10px;
  background: #252525;
  text-align: center;
  border-top: 1px solid #333;
  flex-shrink: 0;
}

.download-btn {
  color: #42b983;
  text-decoration: none;
  font-weight: bold;
}

/* 预览区域 */
.preview-panel {
  display: flex;
  flex-direction: column;
}

.preview-content-area {
  flex: 1;
  background: #161616;
  position: relative;
  overflow: hidden;
}

/* 文本表格容器 */
.table-container {
  width: 100%;
  height: 100%;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9em;
  table-layout: fixed;
}

th {
  text-align: left;
  padding: 12px;
  background: #252529;
  color: #42b983;
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1px solid #444;
  white-space: nowrap;
}

.col-type {
  width: 80px;
}

.col-remark {
  width: 120px;
}

.col-content {
  width: auto;
}

td {
  padding: 10px;
  border-bottom: 1px solid #2a2a2a;
  color: #ccc;
  vertical-align: top;
  line-height: 1.5;
}

tr:hover td {
  background: #222;
  color: #fff;
}

.type-tag {
  display: inline-block;
  padding: 2px 6px;
  background: #333;
  border-radius: 4px;
  font-size: 0.8em;
  color: #aaa;
}

.content-cell {
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 300px;
}

.remark-cell {
  white-space: nowrap;
  color: #666;
  font-size: 0.85em;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 媒体流容器 */
.media-container {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 20px;
  box-sizing: border-box;
}

.media-stream-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-bottom: 40px;
}

.media-card {
  background: #252525;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #333;
}

.video-layout {
  display: flex;
  height: 280px;
}

.video-player-wrapper {
  flex: 2;
  background: #000;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hls-player {
  width: 100%;
  height: 100%;
}

.format-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  background: #42b983;
  color: #000;
  padding: 2px 5px;
  font-size: 0.7em;
  font-weight: bold;
  border-radius: 3px;
}

.video-meta-side {
  flex: 1;
  padding: 15px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid #333;
  max-width: 260px;
}

.cover-box {
  height: 140px;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
  cursor: pointer;
}

.cover-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.8;
}

.meta-info h4 {
  margin: 5px 0;
  color: #fff;
  font-size: 0.9em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.copy-btn {
  margin-top: auto;
  background: #333;
  border: 1px solid #555;
  padding: 6px;
  color: #ccc;
  cursor: pointer;
  width: 100%;
}

.image-layout {
  padding: 10px;
  display: flex;
  justify-content: center;
  background: #222;
}

.preview-img {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
}

.text-card-layout {
  padding: 15px;
  border-left: 3px solid #666;
  background: #2a2a2a;
}

.text-header {
  margin-bottom: 8px;
}

.text-content {
  color: #ddd;
  font-size: 0.9em;
  line-height: 1.6;
  margin: 0;
  white-space: pre-wrap;
}

.badge {
  font-size: 0.7em;
  padding: 2px 5px;
  border-radius: 3px;
  color: #000;
  font-weight: bold;
}

.badge.video {
  background: #ff9800;
}

.badge.image {
  background: #2196f3;
}

.badge.text {
  background: #bbb;
}

.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #555;
}

.empty-state .icon {
  font-size: 3rem;
  display: block;
  margin-bottom: 10px;
}

.sub-text {
  font-size: 0.8em;
  color: #444;
  margin-top: 5px;
}

.mini-btn {
  background: transparent;
  border: 1px solid #555;
  color: #888;
  padding: 2px 8px;
  font-size: 0.8em;
  cursor: pointer;
  margin-left: 10px;
}

.count-tag {
  font-size: 0.8em;
  color: #666;
}

.browser-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #aaa;
  font-size: 12px;
  cursor: pointer;
  margin-right: 10px;
}

.browser-toggle input {
  width: auto;
  margin: 0;
}

.battle-btn {
  background: linear-gradient(45deg, #ff5722, #ff9800);
  color: white;
  border: none;
}
.battlefield-container {
  width: 100%;
  height: 100%;
  background: #000;
  position: relative;
  display: flex;
  flex-direction: column;
}
.battle-header {
  height: 40px;
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  color: #fff;
  font-weight: bold;
}
.team-score.red { color: #ff4444; }
.team-score.blue { color: #4488ff; }
.vs-badge { font-style: italic; color: #aaa; }
.battle-canvas {
  flex: 1;
  width: 100%;
  height: 100%;
}
.close-battle-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
}
.winner-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #ffc107;
  z-index: 10;
}
.winner-overlay h2 { font-size: 32px; margin-bottom: 10px; }
.restart-btn {
  margin-top: 20px;
  padding: 10px 20px;
  background: #42b983;
  border: none;
  color: white;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}
</style>
