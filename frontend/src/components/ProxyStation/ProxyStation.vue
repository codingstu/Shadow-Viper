<template>
  <div class="proxy-station">
    <div class="header-section">
      <div class="title-group">
        <h1>🌐 猎手 IP 池 <span class="version">v1.3 HTTPS版</span></h1>
        <p>基于付费通道的全球免费代理采集与清洗系统</p>
      </div>
      <div class="status-cards">
        <div class="card">
          <div class="card-label">存活数量</div>
          <div class="card-value highlight">{{ stats.count }}</div>
        </div>
        <div class="card">
          <div class="card-label">引擎状态</div>
          <div class="card-value" :class="stats.running ? 'busy' : 'idle'">
            {{ stats.running ? '🔥 正在清洗中' : '💤 等待指令' }}
          </div>
        </div>
      </div>
    </div>

    <div class="workspace">
      <div class="left-pane">
        <div class="control-box">
          <button
            @click="triggerTask"
            :disabled="stats.running"
            class="main-btn"
            :class="{ 'btn-loading': stats.running }"
          >
            <span v-if="!stats.running">🚀 启动 IP 狩猎</span>
            <span v-else>⏳ 正在扫描全球节点...</span>
          </button>

          <div class="sub-controls">
            <button @click="fetchData" class="sec-btn">🔄 刷新</button>
            <button @click="cleanPool" class="danger-btn">🗑️ 清空</button>
          </div>
        </div>

        <div class="log-container">
          <div class="panel-title">运行终端</div>
          <div class="log-window">
            <div v-for="(log, i) in stats.logs" :key="i" class="log-item">
              {{ log }}
            </div>
            <div v-if="stats.logs.length === 0" class="log-empty">
              > 系统就绪，等待启动...
            </div>
          </div>
        </div>
      </div>

      <div class="right-pane">
        <div class="panel-title">
          <span>🏆 优质代理排行榜 (Top 100)</span>
          <span class="api-hint">API: /api/proxy_pool/pop</span>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th width="140">IP 地址</th>
                <th width="80">端口</th>
                <th width="80">协议</th>
                <th width="100">响应速度</th>
                <th>最后验证</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in proxyList" :key="p.ip + p.port">
                <td class="font-mono ip-txt">{{ p.ip }}</td>
                <td class="font-mono">{{ p.port }}</td>
                <td><span class="tag-proto">{{ p.protocol.toUpperCase() }}</span></td>
                <td>
                  <div class="speed-indicator" :class="getSpeedLevel(p.speed)">
                    <div class="dot"></div>
                    {{ p.speed }} ms
                  </div>
                </td>
                <td class="time-txt">{{ formatTime(p.last_check) }}</td>
              </tr>
              <tr v-if="proxyList.length === 0">
                <td colspan="5" class="empty-state">
                  <div class="empty-icon">🕸️</div>
                  <div>暂无有效代理</div>
                  <div class="sub-text">请点击左侧按钮开始抓取</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const stats = ref({ count: 0, running: false, logs: [] });
const proxyList = ref([]);
let timer = null;

const getSpeedLevel = (ms) => {
  if (ms < 500) return 'fast';
  if (ms < 1500) return 'medium';
  return 'slow';
};

const formatTime = (timeStr) => {
  return timeStr.split(' ')[1];
};

const fetchData = async () => {
  try {
    const resStats = await fetch('http://127.0.0.1:8000/api/proxy_pool/stats');
    stats.value = await resStats.json();

    const resList = await fetch('http://127.0.0.1:8000/api/proxy_pool/list');
    proxyList.value = await resList.json();
  } catch (e) {
    console.error("API Error", e);
  }
};

const triggerTask = async () => {
  if (stats.value.running) return;
  try {
    await fetch('http://127.0.0.1:8000/api/proxy_pool/trigger', { method: 'POST' });
    fetchData();
  } catch (e) { alert("连接后端失败"); }
};

// 🔥 清空池子
const cleanPool = async () => {
  if (!confirm("确定要清空所有代理吗？")) return;
  try {
    await fetch('http://127.0.0.1:8000/api/proxy_pool/clean', { method: 'DELETE' });
    fetchData();
  } catch (e) { alert("清空失败"); }
};

onMounted(() => {
  fetchData();
  timer = setInterval(fetchData, 2000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.proxy-station {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 40px);
  color: #eee;
  gap: 20px;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.title-group h1 { margin: 0; font-size: 24px; color: #42b983; display: flex; align-items: center; gap: 10px; }
.version { font-size: 12px; background: rgba(66, 185, 131, 0.2); padding: 2px 6px; border-radius: 4px; }
.title-group p { margin: 5px 0 0; color: #888; font-size: 13px; }

.status-cards { display: flex; gap: 15px; }
.card {
  background: #1e1e1e;
  padding: 10px 20px;
  border-radius: 8px;
  border: 1px solid #333;
  text-align: center;
  min-width: 100px;
}
.card-label { font-size: 12px; color: #666; margin-bottom: 5px; }
.card-value { font-size: 20px; font-weight: bold; font-family: 'Consolas', monospace; }
.highlight { color: #42b983; }
.busy { color: #ff9800; animation: pulse 1.5s infinite; }
.idle { color: #666; }

.workspace {
  display: flex;
  flex: 1;
  gap: 20px;
  min-height: 0;
}

.left-pane { flex: 1; display: flex; flex-direction: column; gap: 15px; min-width: 300px; max-width: 400px; }
.right-pane { flex: 2; display: flex; flex-direction: column; background: #1e1e1e; border-radius: 12px; border: 1px solid #333; overflow: hidden; }

/* 按钮组 */
.control-box { display: flex; flex-direction: column; gap: 10px; }
.sub-controls { display: flex; gap: 10px; }

button {
  border: none; border-radius: 6px; padding: 12px; cursor: pointer;
  font-weight: bold; transition: all 0.2s; color: white;
}
.main-btn { width: 100%; background: linear-gradient(135deg, #42b983 0%, #35495e 100%); box-shadow: 0 4px 15px rgba(66, 185, 131, 0.3); }
.main-btn:hover { transform: translateY(-2px); }
.main-btn:disabled { opacity: 0.7; cursor: wait; }

.sec-btn { flex: 1; background: #2c3e50; border: 1px solid #3e5871; }
.sec-btn:hover { background: #34495e; }

.danger-btn { flex: 1; background: #c62828; border: 1px solid #b71c1c; }
.danger-btn:hover { background: #d32f2f; }

.log-container {
  flex: 1;
  background: #000;
  border-radius: 8px;
  border: 1px solid #333;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-title {
  padding: 10px 15px; background: #252525; border-bottom: 1px solid #333;
  font-size: 13px; font-weight: bold; color: #ccc;
  display: flex; justify-content: space-between;
}
.log-window {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.log-item { border-bottom: 1px solid #111; padding-bottom: 2px; margin-bottom: 2px; color: #aaa; }
.log-item:first-child { color: #fff; font-weight: bold; }
.log-empty { color: #444; font-style: italic; }

.api-hint { font-size: 12px; color: #555; font-weight: normal; font-family: monospace; }
.table-container { flex: 1; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; }
thead { position: sticky; top: 0; background: #252525; z-index: 10; }
th { text-align: left; padding: 12px 15px; color: #888; font-size: 12px; font-weight: 600; }
td { padding: 10px 15px; border-bottom: 1px solid #2a2a2a; color: #ddd; font-size: 13px; }
tr:hover { background: rgba(255,255,255,0.02); }

.font-mono { font-family: 'Consolas', monospace; }
.ip-txt { color: #81c784; font-weight: bold; }
.tag-proto { background: #333; padding: 2px 6px; border-radius: 4px; font-size: 11px; color: #aaa; }
.time-txt { color: #666; font-size: 12px; }

.speed-indicator { display: flex; align-items: center; gap: 6px; font-weight: bold; font-size: 12px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.fast { color: #4caf50; } .fast .dot { background: #4caf50; box-shadow: 0 0 5px #4caf50; }
.medium { color: #ff9800; } .medium .dot { background: #ff9800; }
.slow { color: #f44336; } .slow .dot { background: #f44336; }

.empty-state { text-align: center; padding: 60px 0; color: #555; }
.empty-icon { font-size: 48px; margin-bottom: 10px; opacity: 0.3; }
.sub-text { font-size: 12px; margin-top: 5px; }

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}
</style>