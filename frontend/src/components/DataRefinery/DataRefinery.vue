<template>
    <div class="refinery-container">
      <header class="header">
        <div class="header-left">
          <div class="logo-box">
            <span class="logo-icon">🏭</span>
          </div>
          <div>
            <h1 class="title">Data Refinery <span class="pro-tag">PRO</span></h1>
            <p class="subtitle">智能数据清洗与增强流水线</p>
          </div>
        </div>
        <div v-if="status === 'processing'" class="status-badge processing">
          <span class="dot"></span>
          <span>引擎运转中...</span>
        </div>
      </header>

      <div class="main-grid">

        <div class="left-col">

          <div class="card config-panel">
            <h2 class="card-title">任务配置</h2>

            <div
              class="upload-area"
              :class="{ 'has-file': file }"
              @dragover.prevent @drop.prevent="handleDrop"
              @click="$refs.fileInput.click()"
            >
              <input type="file" ref="fileInput" class="hidden" accept=".csv,.xlsx,.xls" @change="handleFileSelect">

              <div v-if="!file" class="upload-placeholder">
                <div class="upload-icon">📂</div>
                <p>拖入 CSV / Excel 文件 或 点击上传</p>
              </div>

              <div v-else class="file-info">
                <div class="file-icon">📄</div>
                <div class="file-details">
                  <p class="file-name">{{ file.name }}</p>
                  <p class="file-size">{{ (file.size / 1024).toFixed(1) }} KB</p>
                </div>
                <button @click.stop="file = null" class="remove-btn">✕</button>
              </div>
            </div>

            <div class="toggles">
              <label class="toggle-item">
                <span class="toggle-label">
                  <span class="icon">🌐</span> 网络巡检 (验证死链)
                </span>
                <input type="checkbox" v-model="config.enableNetwork">
              </label>

              <label class="toggle-item">
                <span class="toggle-label">
                  <span class="icon">🧠</span> AI 深度分析 (打标/评分)
                </span>
                <input type="checkbox" v-model="config.enableAI">
              </label>
            </div>

            <button
              @click="startProcess"
              :disabled="!file || status === 'processing'"
              class="start-btn"
              :class="status"
            >
              <span v-if="status === 'idle'">🚀 启动炼油厂引擎</span>
              <span v-else-if="status === 'processing'">⚙️ 正在精炼中...</span>
              <span v-else>✨ 处理完成 (点击重置)</span>
            </button>
          </div>

          <div class="card terminal-card">
            <div class="terminal-header">
              <span>SYSTEM_LOGS</span>
              <div class="traffic-lights">
                <span class="light red"></span>
                <span class="light yellow"></span>
                <span class="light green"></span>
              </div>
            </div>
            <div ref="logContainer" class="terminal-body">
              <div v-if="logs.length === 0" class="empty-logs">
                Waiting for data stream...
              </div>
              <div v-for="(log, idx) in logs" :key="idx" class="log-line">
                <span class="log-time">[{{ log.time }}]</span>
                <span :class="getLogClass(log.msg)">{{ log.msg }}</span>
              </div>
            </div>
          </div>

        </div>

        <div class="right-col">

          <div v-if="currentPhase" class="card progress-card">
            <div class="phase-icon">{{ phaseIcon }}</div>
            <div class="progress-info">
              <div class="progress-header">
                <h3>{{ currentPhase }}</h3>
                <span class="percent">{{ progress }}%</span>
              </div>
              <div class="progress-track">
                <div class="progress-bar" :style="{ width: progress + '%' }"></div>
              </div>
            </div>
          </div>

          <div class="card table-card">
            <div class="table-header">
              <h3>📊 实时数据预览 (Top 5)</h3>
              <span v-if="previewData.length > 0" class="badge">
                已加载 {{ columns.length }} 列字段
              </span>
            </div>

            <div class="table-container">
              <table v-if="previewData.length > 0">
                <thead>
                  <tr>
                    <th>#</th>
                    <th v-for="col in columns" :key="col">{{ col }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in previewData" :key="idx">
                    <td class="row-idx">{{ idx + 1 }}</td>
                    <td v-for="col in columns" :key="col">
                      <span v-if="col === 'Link_Status'" :class="getStatusClass(row[col])">
                        {{ row[col] }}
                      </span>
                      <span v-else-if="col === 'AI_Score'" :class="row[col] > 80 ? 'score-high' : 'score-low'">
                        {{ row[col] }}
                      </span>
                      <span v-else>{{ row[col] }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>

              <div v-else class="empty-state">
                <div class="empty-icon">📉</div>
                <p>暂无预览数据</p>
              </div>
            </div>
          </div>

          <div v-if="downloadUrl" class="card download-card">
            <h3>🎉 精炼完成！</h3>
            <p>共输出有效数据 <span>{{ finalCount }}</span> 条</p>
            <a :href="downloadUrl" download class="download-btn">
              📥 下载清洗结果 (.csv)
            </a>
          </div>

        </div>
      </div>
    </div>
  </template>

  <script setup>
  import { ref, computed, nextTick } from 'vue'

  const file = ref(null)
  const status = ref('idle') // idle, processing, done
  const logs = ref([])
  const previewData = ref([])
  const columns = ref([])
  const currentPhase = ref('')
  const progress = ref(0)
  const downloadUrl = ref('')
  const finalCount = ref(0)
  const logContainer = ref(null)

  const config = ref({
    enableNetwork: false,
    enableAI: false
  })

  const phaseIcon = computed(() => {
    if (currentPhase.value.includes('清洗')) return '🧹'
    if (currentPhase.value.includes('网络') || currentPhase.value.includes('验证')) return '🌐'
    if (currentPhase.value.includes('AI') || currentPhase.value.includes('智能')) return '🧠'
    return '⚙️'
  })

  const handleFileSelect = (e) => {
    if (e.target.files.length > 0) file.value = e.target.files[0]
  }

  const handleDrop = (e) => {
    if (e.dataTransfer.files.length > 0) file.value = e.dataTransfer.files[0]
  }

  const addLog = (msg) => {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false })
    logs.value.push({ time, msg })
    nextTick(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    })
  }

  const getLogClass = (msg) => {
    if (msg.includes('✅') || msg.includes('完成')) return 'log-success'
    if (msg.includes('❌') || msg.includes('错误')) return 'log-error'
    if (msg.includes('⚠️') || msg.includes('跳过')) return 'log-warning'
    if (msg.includes('➡️') || msg.includes('启动')) return 'log-info'
    return 'log-normal'
  }

  const getStatusClass = (status) => {
    if (status === 'Alive') return 'status-alive'
    if (status && status.includes('Dead')) return 'status-dead'
    if (status === 'Timeout') return 'status-timeout'
    return ''
  }

  const startProcess = async () => {
    if (status.value === 'done') {
      status.value = 'idle'
      logs.value = []
      previewData.value = []
      columns.value = []
      currentPhase.value = ''
      progress.value = 0
      downloadUrl.value = ''
      file.value = null
      return
    }

    status.value = 'processing'
    logs.value = []
    downloadUrl.value = ''

    const formData = new FormData()
    formData.append('file', file.value)
    formData.append('enable_network', config.value.enableNetwork)
    formData.append('enable_ai', config.value.enableAI)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/refinery/process', {
        method: 'POST',
        body: formData
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const data = JSON.parse(line)
            handleStreamMessage(data)
          } catch (e) {
            console.error("Parse error", e)
          }
        }
      }
    } catch (e) {
      addLog(`❌ 系统错误: ${e.message}`)
      status.value = 'idle'
    }
  }

  const handleStreamMessage = (data) => {
    if (data.msg) addLog(data.msg)
    if (data.step === 'phase_start') {
      currentPhase.value = data.phase
      progress.value = 0
    } else if (data.progress !== undefined) {
      progress.value = data.progress
    }
    if (data.step === 'phase_preview') {
      columns.value = data.columns
      previewData.value = data.preview
      progress.value = 100
    }
    if (data.step === 'done') {
      status.value = 'done'
      downloadUrl.value = data.download_url
      finalCount.value = data.final_count
      currentPhase.value = '处理完成'
      progress.value = 100
    }
  }
  </script>

  <style scoped>
  /* 原生 CSS 样式，无需 Tailwind */
  .refinery-container {
    padding: 20px;
    color: #e0e0e0;
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    font-family: 'Consolas', 'Monaco', monospace;
  }

  /* Header */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 25px;
    padding-bottom: 15px;
    border-bottom: 1px solid #333;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 15px;
  }

  .logo-box {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #10b981 0%, #047857 100%);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
  }

  .logo-icon {
    font-size: 24px;
  }

  .title {
    font-size: 1.5rem;
    font-weight: bold;
    margin: 0;
    color: #fff;
  }

  .pro-tag {
    color: #10b981;
    font-size: 0.8em;
  }

  .subtitle {
    font-size: 0.8rem;
    color: #888;
    margin: 0;
  }

  .status-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #10b981;
    font-size: 0.9rem;
  }

  .dot {
    width: 8px;
    height: 8px;
    background-color: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 8px #10b981;
  }

  /* Grid Layout */
  .main-grid {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 20px;
    flex: 1;
    min-height: 0;
  }

  @media (max-width: 1024px) {
    .main-grid {
      grid-template-columns: 1fr;
    }
  }

  .left-col, .right-col {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  /* Cards */
  .card {
    background: #111;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
  }

  .card-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #888;
    margin-bottom: 15px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  /* Upload Area */
  .upload-area {
    border: 2px dashed #444;
    border-radius: 8px;
    padding: 30px;
    text-align: center;
    cursor: pointer;
    background: #0f0f0f;
    transition: all 0.3s;
  }

  .upload-area:hover, .upload-area.has-file {
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.05);
  }

  .upload-placeholder {
    color: #666;
  }

  .upload-icon {
    font-size: 32px;
    margin-bottom: 10px;
  }

  .file-info {
    display: flex;
    align-items: center;
    gap: 10px;
    justify-content: center;
  }

  .file-icon {
    font-size: 24px;
  }

  .file-details {
    text-align: left;
  }

  .file-name {
    color: #fff;
    font-weight: bold;
    font-size: 0.9rem;
  }

  .file-size {
    color: #666;
    font-size: 0.8rem;
  }

  .remove-btn {
    background: none;
    border: none;
    color: #666;
    cursor: pointer;
    font-size: 1.2rem;
    margin-left: 10px;
  }

  .remove-btn:hover {
    color: #ef4444;
  }

  /* Toggles */
  .toggles {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .toggle-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #1a1a1a;
    padding: 12px;
    border-radius: 6px;
    border: 1px solid #333;
    cursor: pointer;
  }

  .toggle-item:hover {
    border-color: #555;
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.9rem;
  }

  /* Start Button */
  .start-btn {
    width: 100%;
    margin-top: 20px;
    padding: 12px;
    border-radius: 8px;
    border: none;
    font-weight: bold;
    cursor: pointer;
    background: linear-gradient(90deg, #059669, #0d9488);
    color: white;
    transition: opacity 0.3s;
  }

  .start-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .start-btn.processing {
    background: #333;
  }

  /* Terminal */
  .terminal-card {
    background: #000;
    display: flex;
    flex-direction: column;
    height: 400px;
    font-family: 'Menlo', monospace;
  }

  .terminal-header {
    display: flex;
    justify-content: space-between;
    padding-bottom: 10px;
    border-bottom: 1px solid #222;
    margin-bottom: 10px;
    font-size: 0.8rem;
    color: #555;
  }

  .traffic-lights {
    display: flex;
    gap: 6px;
  }

  .light {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }
  .red { background: #ef4444; }
  .yellow { background: #f59e0b; }
  .green { background: #10b981; }

  .terminal-body {
    flex: 1;
    overflow-y: auto;
    font-size: 0.85rem;
    line-height: 1.5;
  }

  .empty-logs {
    color: #333;
    text-align: center;
    margin-top: 50px;
    font-style: italic;
  }

  .log-time {
    color: #555;
    margin-right: 8px;
  }

  .log-success { color: #10b981; }
  .log-error { color: #ef4444; }
  .log-warning { color: #f59e0b; }
  .log-info { color: #3b82f6; }
  .log-normal { color: #ccc; }

  /* Progress Card */
  .progress-card {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .phase-icon {
    width: 50px;
    height: 50px;
    background: #222;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
  }

  .progress-info {
    flex: 1;
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .progress-track {
    height: 8px;
    background: #333;
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #10b981, #2dd4bf);
    transition: width 0.3s ease;
  }

  /* Table */
  .table-card {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 400px;
  }

  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
  }

  .badge {
    background: #222;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
    color: #888;
  }

  .table-container {
    flex: 1;
    overflow: auto;
    border: 1px solid #222;
    border-radius: 4px;
    position: relative;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }

  th {
    background: #1a1a1a;
    padding: 10px;
    text-align: left;
    position: sticky;
    top: 0;
    color: #888;
    font-size: 0.8rem;
  }

  td {
    padding: 10px;
    border-bottom: 1px solid #222;
    color: #ccc;
    white-space: nowrap;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  tr:hover {
    background: #161616;
  }

  .status-alive { color: #10b981; }
  .status-dead { color: #ef4444; }
  .status-timeout { color: #f59e0b; }
  .score-high { color: #a855f7; font-weight: bold; }
  .score-low { color: #666; }

  .empty-state {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    color: #444;
  }

  .empty-icon {
    font-size: 40px;
    margin-bottom: 10px;
  }

  /* Download */
  .download-card {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    text-align: center;
  }

  .download-btn {
    display: inline-block;
    margin-top: 15px;
    padding: 10px 30px;
    background: #059669;
    color: white;
    text-decoration: none;
    border-radius: 6px;
    font-weight: bold;
  }

  .hidden {
    display: none;
  }
  </style>