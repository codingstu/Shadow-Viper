<template>
    <div class="cyber-range">
        <div class="header">
            <div class="title-box">
                <span class="icon">🛡️</span>
                <div class="text-group">
                    <h1>Cyber Range <span class="badge">Security Lab v1.0</span></h1>
                    <p>交互式网络靶场：内置漏洞环境 · 实时流量分析 · 安全工具链</p>
                </div>
            </div>
            <div class="stats-row">
                <div class="stat-card">
                    <span class="label">活跃靶机</span>
                    <span class="value">{{ activeTargets }}/{{ totalTargets }}</span>
                </div>
                <div class="stat-card">
                    <span class="label">捕获请求</span>
                    <span class="value">{{ capturedRequests }}</span>
                </div>
                <button @click="checkBackend" class="scan-btn">🔄 刷新状态</button>
                <button @click="showConfigPanel = true" class="config-btn">⚙️ 配置</button>
            </div>
        </div>

        <div v-if="showConfigPanel" class="config-overlay" @click.self="showConfigPanel = false">
            <div class="config-panel">
                <div class="config-header">
                    <h3>靶场配置</h3>
                    <button @click="showConfigPanel = false" class="close-btn">×</button>
                </div>
                <div class="config-body">
                    <div class="config-group">
                        <h4>靶机端口设置</h4>
                        <div class="config-item">
                            <label>DVWA 端口:</label>
                            <input type="number" v-model="targetPorts.dvwa" min="1024" max="65535" />
                        </div>
                        <div class="config-item">
                            <label>Metasploitable2 端口:</label>
                            <input type="number" v-model="targetPorts.metasploitable" min="1024" max="65535" />
                        </div>
                        <div class="config-item">
                            <label>WebGoat 端口:</label>
                            <input type="number" v-model="targetPorts.webgoat" min="1024" max="65535" />
                        </div>
                    </div>
                    <div class="config-actions">
                        <button @click="saveConfig" class="save-btn">💾 保存配置</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="main-content">
            <div class="panel left-panel">
                <div class="panel-header">
                    <span>🎯 靶机与控制台</span>
                    <div class="panel-actions">
                        <span class="target-count">{{ targets.length }} 个靶机</span>
                    </div>
                </div>
                <div class="panel-body">
                    <div class="target-list">
                        <div class="target-item" v-for="target in targets" :key="target.id">
                            <div class="target-info">
                                <span class="target-name">{{ target.name }}</span>
                                <span class="target-status" :class="target.status">{{ target.status === 'running' ?
                        '运行中' : (target.status === 'starting' ? '启动中...' : '已停止') }}</span>
                                <span class="target-port" v-if="target.status === 'running'">
                                    <a :href="getTargetUrl(target.id)" target="_blank" class="port-link">
                                        🔗 端口: {{ getTargetPort(target.id) }} (点击访问)
                                    </a>
                                </span>
                                <span class="target-port" v-else>端口: {{ getTargetPort(target.id) }}</span>
                            </div>
                            <div class="target-actions">
                                <button class="mini-btn start" @click="startTarget(target.id)"
                                    v-if="target.status === 'stopped'" :disabled="isProcessing">启动</button>
                                <button class="mini-btn stop" @click="stopTarget(target.id)"
                                    v-else-if="target.status === 'running'" :disabled="isProcessing">停止</button>
                                <button class="mini-btn" disabled v-else>...</button>

                                <button class="mini-btn access" @click="accessTarget(target.id)"
                                    :disabled="target.status !== 'running'">访问</button>
                                <button class="mini-btn attack" @click="attackTarget(target.id)"
                                    :disabled="target.status !== 'running'">攻击</button>
                            </div>
                        </div>
                    </div>
                    <div class="console-container">
                        <div class="console-header">Web终端</div>
                        <div class="console-body" ref="consoleRef">
                            <div v-for="(log, idx) in consoleLogs" :key="idx" class="log-line">> {{ log }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="panel middle-panel">
                <div class="panel-header">
                    <span>⚔️ 攻击工具集</span>
                </div>
                <div class="panel-body">
                    <div class="tool-content">
                        <div class="tool-section">
                            <h4>端口扫描 (Nmap)</h4>
                            <div class="tool-input-group">
                                <input type="text" placeholder="目标 IP (如 127.0.0.1)" v-model="scanTarget" />
                                <button class="mini-btn" @click="runPortScan">执行扫描</button>
                            </div>
                            <div class="tool-result">
                                <div v-if="portScanResult.length > 0">
                                    <div v-for="(result, i) in portScanResult" :key="i" class="result-item">
                                        <span class="port">{{ result.port }}</span>
                                        <span class="service">{{ result.service }}</span>
                                        <span class="state" :class="result.state">{{ result.state }}</span>
                                    </div>
                                </div>
                                <div v-else class="empty-result">暂无数据</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="panel right-panel">
                <div class="panel-header">
                    <span>📡 实时流量监控</span>
                    <div class="panel-actions">
                        <span class="traffic-count">{{ trafficLogs.length }}</span>
                    </div>
                </div>
                <div class="panel-body">
                    <div class="traffic-list">
                        <div v-for="(traffic, idx) in trafficLogs" :key="idx" class="traffic-item">
                            <div class="traffic-header">
                                <span class="method">{{ traffic.method }}</span>
                                <span class="url" :title="traffic.url">{{ traffic.url }}</span>
                                <span class="status" :class="getStatusClass(traffic.status)">{{ traffic.status }}</span>
                            </div>
                            <div class="traffic-body">
                                <span class="from-to">{{ traffic.src }} ➔ {{ traffic.dst }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import axios from 'axios';

// 基础配置
const apiBaseUrl = ref(import.meta.env.VITE_API_BASE_URL); // 🔥 修改
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

        // 发送请求，带上端口参数
        const res = await axios.post(endpoint, { target_id: id, port: getTargetPort(id) });

        // 🔥 关键判断：只有后端返回 success=True 才置为 running
        if (res.data.success) {
            target.status = 'running';
            addLog(`✅ 启动成功! 访问地址: ${getTargetUrl(id)}`);
            checkBackend(); // 刷新计数
        } else {
            target.status = 'stopped';
            addLog(`❌ 启动失败: ${res.data.message}`);
            if (res.data.message.includes("Docker")) {
                addLog("💡 提示: 请确保本机已安装 Docker Desktop 并正在运行！");
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
    window.open(getTargetUrl(id), '_blank');
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

// ... 其他代码保持不变

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

// ... 其他代码保持不变

const checkBackend = async () => {
    try {
        const res = await axios.get(`${apiBaseUrl.value}/api/cyber/stats`);
        activeTargets.value = res.data.active_targets;
        capturedRequests.value = res.data.captured_requests;

        // 同步真实状态 (可选，防止页面刷新后状态丢失)
        // const tRes = await axios.get(`${apiBaseUrl.value}/api/cyber/targets`);
        // if(tRes.data.targets) { ... }
    } catch (e) {
        addLog("⚠️ 无法连接后端，请检查 main.py 是否运行");
    }
};

const getStatusClass = (s) => s < 300 ? 'success' : (s < 500 ? 'warning' : 'error');
const saveConfig = () => { showConfigPanel.value = false; addLog("配置已保存"); };

onMounted(() => {
    checkBackend();
});
</script>

<style scoped>
.cyber-range {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 40px);
    color: #e0e0e0;
    gap: 15px;
}

.header {
    background: rgba(20, 30, 40, 0.9);
    padding: 12px 20px;
    border-radius: 8px;
    border: 1px solid rgba(0, 229, 255, 0.2);
    display: flex;
    justify-content: space-between;
}

.title-box {
    display: flex;
    align-items: center;
    gap: 10px;
}

.icon {
    font-size: 28px;
}

.text-group h1 {
    margin: 0;
    color: #00e5ff;
    font-size: 20px;
}

.badge {
    font-size: 11px;
    background: #00e5ff;
    color: #000;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 5px;
}

.text-group p {
    margin: 0;
    color: #888;
    font-size: 11px;
}

.stats-row {
    display: flex;
    gap: 15px;
    align-items: center;
}

.stat-card {
    background: rgba(0, 0, 0, 0.3);
    padding: 5px 12px;
    border-radius: 6px;
    text-align: center;
}

.stat-card .label {
    font-size: 10px;
    color: #aaa;
    display: block;
}

.stat-card .value {
    font-size: 18px;
    color: #00e5ff;
    font-weight: bold;
}

.scan-btn,
.config-btn {
    padding: 8px 16px;
    border-radius: 6px;
    border: none;
    font-weight: bold;
    cursor: pointer;
    font-size: 12px;
}

.scan-btn {
    background: #00e5ff;
    color: #000;
}

.config-btn {
    background: #333;
    color: #ccc;
}

.main-content {
    display: flex;
    flex: 1;
    gap: 15px;
    min-height: 0;
}

.panel {
    background: rgba(30, 30, 40, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.left-panel {
    flex: 1.2;
}

.middle-panel {
    flex: 1;
}

.right-panel {
    flex: 1;
}

.panel-header {
    background: rgba(255, 255, 255, 0.03);
    padding: 10px 15px;
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    font-weight: bold;
    color: #00e5ff;
}

.panel-body {
    flex: 1;
    padding: 15px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 15px;
}

/* 靶机列表 */
.target-item {
    background: rgba(0, 0, 0, 0.2);
    padding: 12px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

.target-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.target-name {
    font-weight: bold;
    color: #fff;
    font-size: 13px;
}

.target-status {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
}

.target-status.running {
    color: #00ffaa;
    background: rgba(0, 255, 170, 0.1);
}

.target-status.stopped {
    color: #ff6b6b;
    background: rgba(255, 107, 107, 0.1);
}

.target-status.starting {
    color: #ffaa00;
}

.target-port {
    font-size: 11px;
    color: #888;
}

.port-link {
    color: #00e5ff;
    text-decoration: none;
}

.port-link:hover {
    text-decoration: underline;
}

.target-actions {
    display: flex;
    gap: 8px;
}

.mini-btn {
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid transparent;
    background: #333;
    color: #ccc;
    cursor: pointer;
    font-size: 11px;
    flex: 1;
}

.mini-btn.start {
    background: rgba(0, 229, 255, 0.2);
    color: #00e5ff;
    border-color: rgba(0, 229, 255, 0.3);
}

.mini-btn.stop {
    background: rgba(255, 107, 107, 0.2);
    color: #ff6b6b;
    border-color: rgba(255, 107, 107, 0.3);
}

.mini-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* 终端 */
.console-container {
    background: #000;
    border-radius: 6px;
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 150px;
    font-family: monospace;
    font-size: 11px;
    border: 1px solid #333;
}

.console-header {
    background: #1a1a1a;
    padding: 4px 8px;
    color: #666;
    border-bottom: 1px solid #333;
}

.console-body {
    padding: 8px;
    overflow-y: auto;
    color: #00ffaa;
    flex: 1;
}

.log-line {
    margin-bottom: 2px;
    word-break: break-all;
}

/* 工具与流量 */
.tool-input-group {
    display: flex;
    gap: 5px;
    margin: 10px 0;
}

.tool-input-group input {
    flex: 1;
    background: #222;
    border: 1px solid #444;
    color: #fff;
    padding: 6px;
    border-radius: 4px;
}

.result-item {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 11px;
}

.state.open {
    color: #00ffaa;
}

.state.closed {
    color: #ff6b6b;
}

.traffic-item {
    background: rgba(0, 0, 0, 0.2);
    padding: 8px;
    border-radius: 4px;
    margin-bottom: 8px;
    font-size: 11px;
}

.traffic-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
}

.method {
    font-weight: bold;
    color: #fff;
    background: #444;
    padding: 1px 4px;
    border-radius: 3px;
}

.status.success {
    color: #00ffaa;
}

.status.error {
    color: #ff6b6b;
}

.traffic-body {
    color: #666;
    font-size: 10px;
}

/* 配置面板 */
.config-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.8);
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: center;
}

.config-panel {
    background: #1e1e24;
    padding: 20px;
    border-radius: 12px;
    width: 400px;
    border: 1px solid #333;
}

.config-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 20px;
    color: #00e5ff;
}

.config-item {
    margin-bottom: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.config-item input {
    background: #111;
    border: 1px solid #444;
    color: #fff;
    padding: 5px;
    border-radius: 4px;
    width: 80px;
}

.close-btn {
    background: none;
    border: none;
    color: #fff;
    font-size: 20px;
    cursor: pointer;
}
</style>