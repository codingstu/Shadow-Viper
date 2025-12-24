<template>
    <div class="eagle-layout">
        <div class="control-deck glass-panel">
            <div class="module-title">
                <span class="icon">🦅</span>
                <div class="text">
                    <h2>Eagle Eye <span class="tag">Pro Audit</span></h2>
                    <p>全球资产隐匿审计系统 | 智能代理链路由</p>
                </div>
            </div>

            <div class="identity-panel">
                <div class="id-row">
                    <span class="label">VIRTUAL IDENTITY:</span>
                    <span class="val mac">{{ status.identity?.mac || 'Initializing...' }}</span>
                </div>
                <div class="id-row">
                    <span class="label">PROXY CHAIN:</span>
                    <div class="chain-display">
                        <span v-for="(node, i) in status.active_chain" :key="i" class="chain-node">
                            {{ node }} <span v-if="i < status.active_chain.length - 1">→</span>
                        </span>
                        <span v-if="!status.active_chain?.length" class="unsafe">NO PROXY DETECTED</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="workspace">
            <div class="left-col">
                <div class="input-deck glass-panel">
                    <div class="panel-head">
                        <span>TARGET INPUT</span>
                        <div class="mode-switch">
                            <button :class="{ active: scanMode === 'active' }"
                                @click="scanMode = 'active'">🔫 实战探测</button>
                            <button :class="{ active: scanMode === 'shodan' }"
                                @click="scanMode = 'shodan'">🔍 Shodan</button>
                        </div>
                    </div>
                    <div class="input-wrapper">
                        <textarea v-model="targetInput" placeholder="[实战模式] 输入 IP: 192.168.1.0/24
[Shodan模式] 输入关键词 (无需IP):
- webcam
- Hikvision
- port:554 has_screenshot:true
- country:CN" :disabled="status.running"></textarea>
                    </div>
                    <div class="action-bar">
                        <button v-if="!status.running" class="scan-btn" :class="scanMode" @click="startScan"
                            :disabled="!targetInput">
                            {{ scanMode === 'shodan' ? 'SHODAN SEARCH' : 'START AUDIT' }}
                        </button>

                        <button v-else class="stop-btn" @click="stopScan">
                            🛑 STOP TASK
                        </button>
                    </div>
                </div>

                <div class="log-panel glass-panel">
                    <div class="panel-head">
                        AUDIT PROCESS LOGS
                        <span class="live-dot" v-if="status.running"></span>
                    </div>
                    <div class="log-container" ref="logRef">
                        <div v-for="(log, i) in status.logs" :key="i" class="log-line">{{ log }}</div>
                    </div>
                </div>
            </div>

            <div class="right-col glass-panel">
                <div class="panel-head">
                    ASSETS DISCOVERED ({{ status.results.length }})
                </div>
                <div class="asset-list">
                    <div v-for="(item, i) in status.results" :key="i" class="asset-card" :class="item.risk">
                        <div class="card-row top">
                            <span class="ip">{{ item.ip }}:{{ item.port }}</span>
                            <span class="time">{{ item.timestamp }}</span>
                        </div>
                        <div class="card-row mid">
                            <span class="brand-tag">📷 {{ item.brand }}</span>
                            <span class="proxy-tag">via {{ item.proxy }}</span>
                        </div>
                        <div class="card-row btm">
                            <span class="status-text" :class="item.status === 'OPEN' ? 'safe' : 'danger'">
                                {{ item.status }}
                            </span>
                            <button class="crack-btn" @click="crack(item.ip)" :disabled="item.status === 'OPEN'">
                                🔨 CRACK
                            </button>
                        </div>
                    </div>
                    <div v-if="status.results.length === 0" class="empty-state">
                        <div class="empty-icon">📡</div>
                        <p>等待任务指令...</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import axios from 'axios';

const targetInput = ref('127.0.0.1\n192.168.1.0/24');
const scanMode = ref('active'); // 默认模式
const status = ref({ running: false, logs: [], results: [] });
const logRef = ref(null);
let timer = null;

const api = axios.create({ baseURL: 'http://127.0.0.1:8000/api/eagle-eye' });

const startScan = async () => {
    if (!targetInput.value) return;
    try {
        await api.post('/scan', {
            target: targetInput.value,
            mode: scanMode.value
        });
    } catch (e) {
        alert("启动失败: " + e.message);
    }
};

const stopScan = async () => {
    try {
        await api.post('/stop');
    } catch (e) {
        alert("停止指令发送失败");
    }
};

const crack = async (ip) => {
    await api.post('/crack', null, { params: { ip } });
    alert("已加入爆破队列");
};

const fetchStatus = async () => {
    try {
        const res = await api.get('/status');
        status.value = res.data;
        nextTick(() => { if (logRef.value && status.value.running) logRef.value.scrollTop = 0; });
    } catch (e) { }
};

onMounted(() => {
    fetchStatus();
    timer = setInterval(fetchStatus, 1000);
});

onUnmounted(() => clearInterval(timer));
</script>

<style scoped>
/* 全局布局与配色优化 */
.eagle-layout {
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 15px;
    font-family: 'Consolas', 'Monaco', monospace;
    color: #e0f0ff;
}

/* 玻璃态面板 */
.glass-panel {
    background: rgba(30, 40, 50, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(100, 200, 255, 0.1);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.panel-head {
    background: rgba(0, 0, 0, 0.3);
    padding: 10px 15px;
    font-size: 12px;
    font-weight: bold;
    color: #7af;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* 顶部控制台 */
.control-deck {
    padding: 15px;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
}

.module-title {
    display: flex;
    gap: 12px;
    align-items: center;
}

.module-title .icon {
    font-size: 32px;
}

.module-title h2 {
    margin: 0;
    color: #00e5ff;
    font-size: 20px;
    letter-spacing: 1px;
}

.tag {
    font-size: 10px;
    background: #00e5ff;
    color: #000;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 8px;
}

.module-title p {
    margin: 0;
    color: #8ab;
    font-size: 12px;
}

.identity-panel {
    text-align: right;
    font-size: 11px;
}

.id-row {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}

.label {
    color: #689;
}

.val {
    font-weight: bold;
    color: #fff;
}

.mac {
    font-family: monospace;
    letter-spacing: 1px;
    color: #fba;
}

.chain-display {
    display: flex;
    gap: 5px;
    color: #4f8;
}

.chain-node {
    background: rgba(0, 255, 100, 0.1);
    padding: 1px 6px;
    border-radius: 3px;
    border: 1px solid rgba(0, 255, 100, 0.3);
}

.unsafe {
    color: #f55;
    animation: blink 2s infinite;
}

/* 主工作区 */
.workspace {
    display: flex;
    flex: 1;
    gap: 15px;
    min-height: 0;
}

.left-col {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 15px;
    min-width: 0;
}

.right-col {
    flex: 1.2;
    min-width: 0;
}

/* 输入区优化 */
.input-wrapper {
    flex: 1;
    padding: 10px;
    display: flex;
}

textarea {
    flex: 1;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #fff;
    padding: 10px;
    border-radius: 4px;
    resize: none;
    font-family: inherit;
    font-size: 13px;
    height: 120px;
}

textarea:focus {
    outline: none;
    border-color: #00e5ff;
    background: rgba(0, 0, 0, 0.4);
}

.action-bar {
    padding: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}

/* 按钮样式 */
.scan-btn {
    background: linear-gradient(135deg, #00e5ff, #0099cc);
    color: #000;
    border: none;
    padding: 8px 30px;
    border-radius: 4px;
    font-weight: bold;
    cursor: pointer;
    transition: .2s;
    width: 100%;
}

.scan-btn:hover {
    box-shadow: 0 0 15px rgba(0, 229, 255, 0.4);
    transform: translateY(-1px);
}

.scan-btn.shodan {
    background: linear-gradient(135deg, #ff5722, #bf360c);
    box-shadow: 0 0 10px rgba(255, 87, 34, 0.4);
    color: #fff;
}

/* 停止按钮样式 */
.stop-btn {
    background: linear-gradient(135deg, #ff4444, #cc0000);
    color: #fff;
    border: none;
    padding: 8px 30px;
    border-radius: 4px;
    font-weight: bold;
    cursor: pointer;
    transition: .2s;
    width: 100%;
    animation: pulse 2s infinite;
}

.stop-btn:hover {
    box-shadow: 0 0 15px rgba(255, 68, 68, 0.6);
}

/* 日志面板 */
.log-panel {
    flex: 1;
    min-height: 0;
}

.log-container {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
    font-size: 11px;
    line-height: 1.6;
}

.log-line {
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    padding-bottom: 2px;
    margin-bottom: 2px;
    color: #8c9;
}

.live-dot {
    width: 8px;
    height: 8px;
    background: #4f8;
    border-radius: 50%;
    animation: blink 1s infinite;
    margin-left: 10px;
}

/* 资产列表 */
.asset-list {
    flex: 1;
    overflow-y: auto;
    padding: 15px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 15px;
    align-content: start;
}

.asset-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 12px;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: .2s;
}

.asset-card:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: #00e5ff;
}

.asset-card.HIGH {
    border-left: 3px solid #f90;
}

.card-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
}

.top {
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    padding-bottom: 5px;
    margin-bottom: 2px;
}

.ip {
    font-size: 13px;
    font-weight: bold;
    color: #fff;
}

.time {
    color: #678;
    font-size: 10px;
}

.brand-tag {
    color: #00e5ff;
    font-weight: bold;
}

.proxy-tag {
    font-size: 9px;
    background: #234;
    padding: 1px 4px;
    border-radius: 2px;
    color: #89a;
}

.status-text {
    font-weight: bold;
}

.status-text.safe {
    color: #4f8;
}

.status-text.danger {
    color: #f55;
}

.crack-btn {
    background: transparent;
    border: 1px solid #f55;
    color: #f55;
    padding: 3px 10px;
    border-radius: 3px;
    cursor: pointer;
    font-size: 10px;
    transition: .2s;
}

.crack-btn:hover:not(:disabled) {
    background: #f55;
    color: #fff;
}

.crack-btn:disabled {
    border-color: #456;
    color: #456;
    cursor: not-allowed;
}

.empty-state {
    grid-column: 1/-1;
    text-align: center;
    color: #567;
    margin-top: 50px;
}

.empty-icon {
    font-size: 40px;
    margin-bottom: 10px;
    opacity: 0.5;
}

@keyframes blink {
    50% {
        opacity: 0.3;
    }
}

@keyframes pulse {
    0% {
        opacity: 1;
    }

    50% {
        opacity: 0.8;
    }

    100% {
        opacity: 1;
    }
}

.mode-switch {
    display: flex;
    gap: 5px;
}

.mode-switch button {
    background: transparent;
    border: 1px solid #444;
    color: #666;
    padding: 2px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
}

.mode-switch button.active {
    background: #00e5ff;
    color: #000;
    border-color: #00e5ff;
    font-weight: bold;
}
</style>