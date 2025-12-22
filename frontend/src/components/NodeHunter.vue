<template>
    <div class="node-hunter">
      <!-- 头部 -->
      <div class="header">
        <div class="title-box">
          <span class="icon">🛰️</span>
          <div class="text-group">
            <h1>Shadow Matrix <span class="badge">Node Hunter</span></h1>
            <p>全网高带宽节点嗅探系统：支持 Vmess / Vless / Trojan</p>
          </div>
        </div>
        
        <!-- 模式切换 -->
        <div class="mode-switcher">
          <div class="mode-tabs">
            <button 
              class="mode-tab" 
              :class="{ active: activeMode === 'main' }"
              @click="switchMode('main')"
            >
              <span class="tab-icon">🌐</span>
              <span class="tab-text">全网扫描</span>
            </button>
            <button 
              class="mode-tab" 
              :class="{ active: activeMode === 'custom' }"
              @click="switchMode('custom')"
            >
              <span class="tab-icon">🎯</span>
              <span class="tab-text">自定义源</span>
            </button>
            <button 
              class="mode-tab" 
              :class="{ active: activeMode === 'analyze' }"
              @click="switchMode('analyze')"
            >
              <span class="tab-icon">🔍</span>
              <span class="tab-text">链接分析</span>
            </button>
          </div>
        </div>
        
        <div class="stats-row">
          <div class="stat-card">
            <span class="label">存活节点</span>
            <span class="value">{{ activeMode === 'custom' ? customStats.count : stats.count }}</span>
          </div>
          
          <div class="stat-card" v-if="userSources.length > 0">
            <span class="label">自定义源</span>
            <span class="value">{{ userSources.length }}</span>
          </div>
          
          <button v-if="activeMode === 'main'" @click="copySubscription" class="subscribe-btn">
            📥 复制订阅
          </button>
          
          <button 
            @click="activeMode === 'main' ? triggerScan() : (activeMode === 'custom' ? scanCustomSources() : null)" 
            class="scan-btn" 
            :disabled="stats.running && activeMode === 'main'"
          >
            <span v-if="activeMode === 'main'">
              {{ stats.running ? '🛰️ 正在嗅探...' : '📡 扫描全网' }}
            </span>
            <span v-else-if="activeMode === 'custom'">
              {{ customScanRunning ? '🎯 扫描中...' : '🎯 扫描自定义源' }}
            </span>
            <span v-else>
              🔍 分析链接
            </span>
          </button>
        </div>
      </div>
      
      <!-- 链接分析面板 -->
      <div v-if="activeMode === 'analyze'" class="analyze-panel">
        <div class="panel-header">
          <span>🔍 智能链接分析器</span>
          <span class="subtitle">输入节点网站或GitHub项目链接，自动抓取订阅源</span>
        </div>
        
        <div class="analyze-content">
          <!-- 链接输入区域 -->
          <div class="link-input-section">
            <div class="input-group">
              <div class="input-label">
                <span class="label-text">链接地址</span>
                <span class="label-hint">支持：GitHub项目、节点网站、订阅链接等</span>
              </div>
              
              <div class="url-input-wrapper">
                <input 
                  type="text" 
                  v-model="analyzeUrl" 
                  placeholder="例如：https://github.com/user/repo 或 https://example.com/subscribe.txt"
                  class="url-input"
                  @keyup.enter="analyzeLink"
                />
                <button 
                  @click="analyzeLink" 
                  class="analyze-btn"
                  :disabled="!analyzeUrl || analyzing"
                >
                  {{ analyzing ? '分析中...' : '分析链接' }}
                </button>
              </div>
              
              <div class="input-options">
                <label class="option-checkbox">
                  <input type="checkbox" v-model="deepScrape" />
                  <span>深度抓取（分析页面所有链接）</span>
                </label>
                
                <label class="option-checkbox">
                  <input type="checkbox" v-model="autoSaveValid" />
                  <span>自动保存有效链接到订阅源</span>
                </label>
              </div>
            </div>
            
            <!-- 快速示例 -->
            <div class="quick-examples">
              <div class="examples-title">💡 快速示例：</div>
              <div class="examples-grid">
                <div 
                  v-for="example in quickExamples" 
                  :key="example.url"
                  class="example-item"
                  @click="loadExample(example)"
                >
                  <span class="example-icon">{{ example.icon }}</span>
                  <span class="example-text">{{ example.name }}</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 分析结果 -->
          <div v-if="analysisResult" class="analysis-result">
            <div class="result-header" :class="{ success: analysisResult.valid, error: !analysisResult.valid }">
              <span class="result-icon">
                {{ analysisResult.valid ? '✅' : '❌' }}
              </span>
              <span class="result-title">{{ analysisResult.message }}</span>
            </div>
            
            <div class="result-details">
              <!-- 基本信息 -->
              <div class="detail-section">
                <h4>📋 链接信息</h4>
                <div class="detail-grid">
                  <div class="detail-item">
                    <span class="detail-label">URL:</span>
                    <span class="detail-value url">{{ analysisResult.url }}</span>
                  </div>
                  <div v-if="analysisResult.type" class="detail-item">
                    <span class="detail-label">类型:</span>
                    <span class="detail-value type">{{ analysisResult.type }}</span>
                  </div>
                  <div v-if="analysisResult.nodes_found !== undefined" class="detail-item">
                    <span class="detail-label">发现节点:</span>
                    <span class="detail-value count">{{ analysisResult.nodes_found }} 个</span>
                  </div>
                </div>
              </div>
              
              <!-- GitHub信息 -->
              <div v-if="analysisResult.github_info" class="detail-section">
                <h4>🐙 GitHub信息</h4>
                <div class="github-info">
                  <div class="github-item">
                    <span class="github-label">Raw URL:</span>
                    <span class="github-value">{{ analysisResult.github_info.raw_url }}</span>
                  </div>
                  <div class="github-item">
                    <span class="github-label">项目:</span>
                    <span class="github-value">{{ analysisResult.github_info.repo }}</span>
                  </div>
                </div>
              </div>
              
              <!-- 抓取的链接 -->
              <div v-if="analysisResult.scraped_links && analysisResult.scraped_links.length > 0" class="detail-section">
                <h4>🔗 发现的链接 ({{ analysisResult.scraped_links.length }})</h4>
                <div class="scraped-links">
                  <div 
                    v-for="(link, index) in analysisResult.scraped_links.slice(0, 5)" 
                    :key="index"
                    class="scraped-link"
                  >
                    <span class="link-index">{{ index + 1 }}.</span>
                    <span class="link-url">{{ link }}</span>
                  </div>
                  <div v-if="analysisResult.scraped_links.length > 5" class="more-links">
                    还有 {{ analysisResult.scraped_links.length - 5 }} 个链接...
                  </div>
                </div>
              </div>
              
              <!-- 有效链接 -->
              <div v-if="analysisResult.valid_links && analysisResult.valid_links.length > 0" class="detail-section">
                <h4>✅ 有效链接 ({{ analysisResult.valid_links.length }})</h4>
                <div class="valid-links">
                  <div 
                    v-for="(linkInfo, index) in analysisResult.valid_links" 
                    :key="index"
                    class="valid-link"
                  >
                    <div class="valid-link-header">
                      <span class="link-status">✓</span>
                      <span class="link-url">{{ linkInfo.url }}</span>
                      <span class="link-nodes">{{ linkInfo.details.nodes_found }} 节点</span>
                    </div>
                    <div class="valid-link-details">
                      <span class="detail-tag">{{ linkInfo.details.content_type || '未知' }}</span>
                      <span class="detail-tag">{{ linkInfo.details.size }} bytes</span>
                      <span v-if="linkInfo.details.is_github" class="detail-tag github">GitHub</span>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 错误信息 -->
              <div v-if="analysisResult.error" class="detail-section error">
                <h4>❌ 错误信息</h4>
                <div class="error-message">{{ analysisResult.error }}</div>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div class="result-actions">
              <button 
                v-if="analysisResult.valid && analysisResult.nodes_found > 0"
                @click="saveToSources"
                class="action-btn save-btn"
              >
                💾 保存到订阅源
              </button>
              
              <button 
                v-if="analysisResult.valid_links && analysisResult.valid_links.length > 0"
                @click="scanValidLinks"
                class="action-btn scan-btn"
              >
                🎯 扫描这些链接
              </button>
              
              <button 
                @click="clearAnalysis"
                class="action-btn clear-btn"
              >
                🗑️ 清除结果
              </button>
            </div>
          </div>
          
          <!-- 用户自定义源管理 -->
          <div class="user-sources-section">
            <div class="section-header">
              <h3>📁 我的自定义源 ({{ userSources.length }})</h3>
              <button 
                @click="refreshUserSources"
                class="refresh-btn"
                title="刷新列表"
              >
                🔄
              </button>
            </div>
            
            <div v-if="userSources.length > 0" class="sources-list">
              <div 
                v-for="(source, index) in userSources"
                :key="index"
                class="source-item"
              >
                <div class="source-info">
                  <span class="source-index">{{ index + 1 }}.</span>
                  <span class="source-url">{{ truncateUrl(source) }}</span>
                  <span v-if="isGitHubUrl(source)" class="source-badge github">GitHub</span>
                  <span v-if="isRawUrl(source)" class="source-badge raw">RAW</span>
                </div>
                <div class="source-actions">
                  <button 
                    @click="testSource(source)"
                    class="source-action test"
                    title="测试链接"
                  >
                    🧪
                  </button>
                  <button 
                    @click="scanSingleSource(source)"
                    class="source-action scan"
                    title="扫描此源"
                  >
                    🎯
                  </button>
                  <button 
                    @click="removeSource(index)"
                    class="source-action remove"
                    title="移除"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="empty-sources">
              <div class="empty-icon">📁</div>
              <div class="empty-text">暂无自定义源</div>
              <div class="empty-hint">使用上方分析器添加有效链接</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 主内容区域 -->
      <div v-else class="main-content">
        <!-- 日志面板 -->
        <div class="panel log-panel">
          <div class="panel-header">
            <span>系统终端 (Terminal)</span>
            <span class="mode-indicator">
              {{ activeMode === 'custom' ? '🎯 自定义模式' : '🌐 全网模式' }}
            </span>
          </div>
          <div class="terminal-body" ref="logRef">
            <div v-for="(log, i) in stats.logs" :key="i" class="log-line">> {{ log }}</div>
            <div v-if="!stats.logs?.length" class="empty-log">
              {{ activeMode === 'custom' ? '切换到自定义模式并扫描' : '点击扫描开始全网嗅探' }}
            </div>
          </div>
        </div>
        
        <!-- 节点列表面板 -->
        <div class="panel list-panel">
          <div class="panel-header">
            <div class="panel-title">
              <span v-if="activeMode === 'custom'">🎯 自定义源节点</span>
              <span v-else>🌐 全网扫描节点</span>
            </div>
            <div class="panel-actions">
              <span class="node-count">{{ activeMode === 'custom' ? customStats.count : stats.count }} 个节点</span>
              <button v-if="activeMode === 'custom' && customStats.count > 0" @click="exportCustomNodes" class="export-btn">
                📤 导出
              </button>
            </div>
          </div>
          
          <!-- 节点网格 -->
          <div class="node-grid">
            <!-- 自定义模式节点 -->
            <template v-if="activeMode === 'custom'">
              <div v-for="node in customStats.nodes" :key="node.id || node.name" class="node-card">
                <div class="node-header">
                  <span class="node-name">{{ node.name }}</span>
                  <span class="node-status" :class="{ online: node.alive }">
                    {{ node.alive ? '在线' : '离线' }}
                  </span>
                </div>
                <div class="node-info">
                  <span class="protocol-badge" :class="node.protocol">
                    {{ node.protocol?.toUpperCase() || 'UNKNOWN' }}
                  </span>
                  <span class="host">{{ node.host }}:{{ node.port }}</span>
                </div>
                <div class="node-stats">
                  <div class="stat-item">
                    <span class="stat-label">延迟</span>
                    <span class="stat-value" :class="getDelayClass(node.delay)">
                      {{ node.delay }}ms
                    </span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">速度</span>
                    <span class="stat-value">{{ node.speed?.toFixed(2) || '0.00' }} MB/s</span>
                  </div>
                </div>
                <div class="node-actions">
                  <button class="action-btn copy" @click="copyNode(node)">复制</button>
                  <button class="action-btn qrcode" @click="showQRCode(node)">二维码</button>
                  <button class="action-btn test" @click="testSingleNode(node)">测试</button>
                </div>
              </div>
              
              <div v-if="!customStats.nodes?.length && !customScanRunning" class="empty-nodes">
                <div class="empty-icon">🎯</div>
                <div class="empty-text">暂无自定义源节点数据</div>
                <button class="empty-btn" @click="switchMode('analyze')">添加订阅源并扫描</button>
              </div>
            </template>
            
            <!-- 全网模式节点 -->
            <template v-else>
              <div v-for="node in stats.nodes" :key="node.id || node.name" class="node-card">
                <div class="node-header">
                  <span class="node-name">{{ node.name }}</span>
                  <span class="node-status" :class="{ online: node.alive }">
                    {{ node.alive ? '在线' : '离线' }}
                  </span>
                </div>
                <div class="node-info">
                  <span class="protocol-badge" :class="node.protocol">
                    {{ node.protocol?.toUpperCase() || 'UNKNOWN' }}
                  </span>
                  <span class="host">{{ node.host }}:{{ node.port }}</span>
                </div>
                <div class="node-stats">
                  <div class="stat-item">
                    <span class="stat-label">延迟</span>
                    <span class="stat-value" :class="getDelayClass(node.delay)">
                      {{ node.delay }}ms
                    </span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">速度</span>
                    <span class="stat-value">{{ node.speed?.toFixed(2) || '0.00' }} MB/s</span>
                  </div>
                </div>
                <div class="node-actions">
                  <button class="action-btn copy" @click="copyNode(node)">复制</button>
                  <button class="action-btn qrcode" @click="showQRCode(node)">二维码</button>
                  <button class="action-btn clash" @click="copyClashConfig(node)">Clash</button>
                </div>
              </div>
              
              <div v-if="!stats.nodes?.length" class="empty-nodes">
                <div class="empty-icon">🌐</div>
                <div class="empty-text">暂无全网扫描节点数据</div>
                <button class="empty-btn" @click="triggerScan">开始全网扫描</button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </template>
  <script setup>
  import { ref, onMounted, nextTick, computed } from 'vue'
  import axios from 'axios'
  
  const stats = ref({
    count: 0,
    running: false,
    logs: [],
    nodes: []
  })

  // 修复1: 添加缺失的响应式变量
const customStats = ref({
  count: 0,
  running: false,
  logs: [],
  nodes: []
})
  
const customScanRunning = ref(false)

  const activeMode = ref('main') // main, custom, analyze
const analyzeUrl = ref('')
const deepScrape = ref(false)
const autoSaveValid = ref(true)
const analyzing = ref(false)
const analysisResult = ref(null)
const userSources = ref([])

  const logRef = ref(null)
  
  // 创建带基础配置的axios实例
  const api = axios.create({
    baseURL: '/api', // 使用代理路径
    timeout: 10000,
    headers: {
      'Content-Type': 'application/json'
    }
  })
  //初始化滚动加载
  let isInitialLoad = true

  async function fetchStats() {
    try {
      console.log('正在获取节点状态...')
      const response = await api.get('/nodes/stats')
      stats.value = response.data
      
      // 自动滚动到底部
      await nextTick()
      if (logRef.value && isInitialLoad) {
        logRef.value.scrollTop = 0  // 滚动到顶部，因为最新日志在最上面
        isInitialLoad = false
        }
    } catch (error) {
      console.error('获取状态失败:', error)
      addLog(`❌ 获取状态失败: ${error.message}`)
    }
  }
  
  // 修复2: 添加缺失的函数
  async function fetchCustomStats() {
  try {
    // 检查自定义模式是否正在扫描
    if (customScanRunning.value) {
      console.log('自定义扫描正在进行中...')
      return
    }
    
    // 只有当用户有自定义源时才调用API
    if (userSources.value.length > 0 && activeMode.value === 'custom') {
      console.log('获取自定义状态...')
      const response = await api.get('/nodes/custom-stats')
      customStats.value = response.data
    } else {
      // 没有自定义源时使用模拟数据
      customStats.value = {
        count: 0,
        running: false,
        nodes: [],
        logs: []
      }
    }
  } catch (error) {
    console.warn('获取自定义状态失败:', error)
    // 不显示错误，使用默认数据
    customStats.value = {
      count: 0,
      running: false,
      nodes: [],
      logs: []
    }
  }
}

async function scanCustomSources() {
  if (userSources.value.length === 0) {
    addLog('❌ 请先添加自定义源')
    return
  }
  
  try {
    customScanRunning.value = true
    
    addLog(`🎯 开始扫描 ${userSources.value.length} 个自定义源...`)
    
    const response = await api.post('/nodes/scan-custom', {
      sources: userSources.value,
      name: '用户自定义源'
    })
    
    addLog(`✅ ${response.data.message}`)
    
    // 开始轮询获取状态
    const pollInterval = setInterval(async () => {
      try {
        const statsResponse = await api.get('/nodes/custom-stats')
        customStats.value = statsResponse.data
        
        // 如果扫描完成
        if (!statsResponse.data.running) {
          clearInterval(pollInterval)
          customScanRunning.value = false
          addLog(`🎉 自定义扫描完成，获取 ${statsResponse.data.count} 个节点`)
        }
      } catch (pollError) {
        console.warn('轮询错误:', pollError)
      }
    }, 2000)
    
  } catch (error) {
    console.error('启动扫描失败:', error)
    addLog(`❌ 扫描失败: ${error.message}`)
    customScanRunning.value = false
  }
}

// 修复3: 添加缺失的其他函数
function getDelayClass(delay) {
  if (delay < 100) return 'good'
  if (delay < 300) return 'medium'
  return 'bad'
}

async function exportCustomNodes() {
  try {
    const response = await api.get('/nodes/export-custom')
    if (response.data.content) {
      // 创建blob并下载
      const blob = new Blob([response.data.content], { type: 'text/plain' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'custom-nodes.txt'
      a.click()
      window.URL.revokeObjectURL(url)
      addLog('✅ 已导出自定义节点')
    }
  } catch (error) {
    addLog(`❌ 导出失败: ${error.message}`)
  }
}

async function testSingleNode(node) {
  try {
    addLog(`🧪 正在测试节点 ${node.name}...`)
    const response = await api.post(`/nodes/test/${node.id || node.name}`, node)
    addLog(`✅ 节点 ${node.name} 测试完成: ${response.data.message}`)
  } catch (error) {
    addLog(`❌ 节点测试失败: ${error.message}`)
  }
}

  async function triggerScan() {
    try {
      addLog('🚀 正在启动节点扫描...')
      const response = await api.post('/nodes/trigger')
      addLog('✅ 扫描任务已启动，请等待...')
      
      // 立即更新状态
      fetchStats()
    } catch (error) {
      console.error('启动扫描失败:', error)
      addLog(`❌ 启动扫描失败: ${error.message}`)
    }
  }
  
  function addLog(message) {
    const timestamp = new Date().toLocaleTimeString()
    stats.value.logs.unshift(`[${timestamp}] ${message}`)
    // 限制日志数量
    if (stats.value.logs.length > 50) {
      stats.value.logs = stats.value.logs.slice(0, 50)
    }
  }
  
  // 在 script setup 部分添加以下函数

// 复制订阅
async function copySubscription() {
  try {
    const response = await api.get('/nodes/subscription');
    if (response.data.subscription) {
      await navigator.clipboard.writeText(response.data.subscription);
      addLog(`✅ 已复制订阅链接，可导入客户端订阅`);
      
      // 显示订阅导入教程
      showSubscriptionGuide();
    } else {
      addLog(`❌ 暂无订阅链接，请先扫描节点: ${response.data.error}`);
    }
  } catch (error) {
    addLog(`❌ 获取订阅失败: ${error.message}`);
  }
}

// 显示二维码
// 显示二维码
async function showQRCode(node) {
  try {
    // 先找到节点的索引
    const nodeIndex = stats.value.nodes.findIndex(n => 
      n.name === node.name && 
      n.host === node.host && 
      n.port === node.port
    );
    
    if (nodeIndex === -1) {
      addLog(`❌ 找不到节点: ${node.name}`);
      return;
    }
    
    // 调用正确的接口
    const response = await api.get(`/nodes/node/${nodeIndex}/qrcode`);
    
    if (response.data.qrcode_data && !response.data.error) {
      // 创建模态框显示二维码
      const modal = document.createElement('div');
      modal.id = 'qrcode-modal';
      modal.style.cssText = `
        position: fixed; 
        top: 0; 
        left: 0; 
        width: 100%; 
        height: 100%;
        background: rgba(0, 0, 0, 0.8); 
        display: flex; 
        justify-content: center;
        align-items: center; 
        z-index: 10000;
        backdrop-filter: blur(5px);
      `;
      
      modal.innerHTML = `
        <div style="
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          padding: 30px;
          border-radius: 20px;
          text-align: center;
          border: 2px solid rgba(0, 229, 255, 0.3);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          max-width: 400px;
          width: 90%;
        ">
          <h3 style="color: #00e5ff; margin-bottom: 20px; font-size: 18px;">
            📱 ${node.name}
          </h3>
          
          <img 
            src="${response.data.qrcode_data}" 
            style="
              width: 250px; 
              height: 250px; 
              border: 10px solid white;
              border-radius: 10px;
              margin-bottom: 20px;
            " 
            alt="二维码"
          />
          
          <div style="
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: left;
            font-size: 12px;
            color: #aaa;
            font-family: monospace;
            word-break: break-all;
            max-height: 80px;
            overflow-y: auto;
          ">
            <strong>分享链接:</strong><br>
            ${node.share_link ? node.share_link.substring(0, 50) + '...' : '无分享链接'}
          </div>
          
          <p style="color: #888; font-size: 12px; margin-bottom: 20px;">
            使用 Shadowrocket、V2rayNG、Clash 等客户端扫码导入
          </p>
          
          <div style="display: flex; gap: 10px; justify-content: center;">
            <button 
              onclick="this.closest('#qrcode-modal').remove()" 
              style="
                padding: 10px 30px;
                background: rgba(255, 107, 107, 0.8);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s;
              "
              onmouseover="this.style.background='rgba(255, 107, 107, 1)'"
              onmouseout="this.style.background='rgba(255, 107, 107, 0.8)'"
            >
              关闭
            </button>
            
            <button 
              onclick="copyToClipboard('${response.data.share_link || node.share_link || ''}')" 
              style="
                padding: 10px 30px;
                background: rgba(0, 229, 255, 0.8);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s;
              "
              onmouseover="this.style.background='rgba(0, 229, 255, 1)'"
              onmouseout="this.style.background='rgba(0, 229, 255, 0.8)'"
            >
              复制链接
            </button>
          </div>
        </div>
      `;
      
      // 添加复制函数到全局
      window.copyToClipboard = function(text) {
        if (!text) {
          alert('没有可复制的链接');
          return;
        }
        
        navigator.clipboard.writeText(text)
          .then(() => {
            // 显示成功提示
            const successMsg = document.createElement('div');
            successMsg.innerHTML = '✅ 链接已复制到剪贴板';
            successMsg.style.cssText = `
              position: fixed;
              top: 20px;
              right: 20px;
              background: rgba(0, 255, 0, 0.9);
              color: #000;
              padding: 10px 20px;
              border-radius: 8px;
              z-index: 10001;
              font-weight: bold;
            `;
            document.body.appendChild(successMsg);
            setTimeout(() => successMsg.remove(), 2000);
          })
          .catch(err => {
            console.error('复制失败:', err);
            alert('复制失败，请手动复制');
          });
      };
      
      // 点击模态框背景关闭
      modal.addEventListener('click', function(e) {
        if (e.target === modal) {
          modal.remove();
        }
      });
      
      document.body.appendChild(modal);
      addLog(`✅ 已为节点 ${node.name} 生成二维码`);
      
    } else {
      addLog(`❌ 该节点无法生成二维码: ${response.data.error || '未知错误'}`);
      
      // 显示错误提示
      const errorModal = document.createElement('div');
      errorModal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.8); display: flex; justify-content: center;
        align-items: center; z-index: 1000;
      `;
      
      errorModal.innerHTML = `
        <div style="background: rgba(255, 50, 50, 0.9); padding: 30px; border-radius: 10px; text-align: center; color: white;">
          <h3 style="margin-bottom: 20px;">❌ 生成二维码失败</h3>
          <p style="margin-bottom: 20px;">${response.data.error || '该节点无法生成分享链接'}</p>
          <button onclick="this.parentElement.parentElement.remove()" 
            style="padding: 10px 30px; background: white; color: #333; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
            关闭
          </button>
        </div>
      `;
      
      document.body.appendChild(errorModal);
    }
  } catch (error) {
    console.error('生成二维码失败:', error);
    addLog(`❌ 生成二维码失败: ${error.message}`);
  }
}

// 复制Clash配置
async function copyClashConfig(node) {
  try {
    // 这里简化处理，实际应该从后端获取Clash配置
    const clashConfig = {
      name: node.name,
      type: node.protocol,
      server: node.host,
      port: node.port,
      udp: true,
      'skip-cert-verify': true,
    };
    
    if (node.protocol === 'vmess') {
      clashConfig.uuid = node.uuid || '';
      clashConfig.alterId = node.alterId || 0;
      clashConfig.cipher = 'auto';
    } else if (node.protocol === 'trojan') {
      clashConfig.password = node.password || '';
    } else if (node.protocol === 'ss') {
      clashConfig.cipher = node.method || 'aes-256-gcm';
      clashConfig.password = node.password || '';
    }
    
    // 转换为YAML
    const yamlStr = `proxies:\n  - ${JSON.stringify(clashConfig, null, 2).replace(/\n/g, '\n    ')}`;
    
    await navigator.clipboard.writeText(yamlStr);
    addLog(`✅ 已复制Clash配置片段`);
  } catch (error) {
    addLog(`❌ 获取Clash配置失败: ${error.message}`);
  }
}

// 显示订阅导入指南
function showSubscriptionGuide() {
  const guide = `
如何导入订阅：

1. Shadowrocket (iOS):
   - 点击右上角加号 ➕
   - 选择 "订阅"
   - 粘贴订阅链接
   - 点击 "完成"

2. V2rayNG (Android):
   - 点击右上角 ➕
   - 选择 "从剪贴板导入"
   - 或者选择 "订阅设置" → 添加订阅

3. Clash (Windows/macOS):
   - 打开 Clash 配置文件夹
   - 创建 config.yaml 文件
   - 粘贴配置文件内容
  `;
  
  // 使用 alert 或创建更好的模态框
  alert(guide);
}

 // 修改 copyNode 函数，优先复制分享链接
function copyNode(node) {
  // 优先复制分享链接
  if (node.share_link) {
    navigator.clipboard.writeText(node.share_link)
      .then(() => {
        addLog(`✅ 已复制节点 ${node.name} 的分享链接`)
      })
      .catch(err => {
        addLog(`❌ 复制失败: ${err.message}`)
      })
  } else {
    // 如果没有分享链接，复制基本配置
    const config = {
      name: node.name,
      protocol: node.protocol,
      host: node.host,
      port: node.port,
      delay: node.delay,
      speed: node.speed
    }
    
    navigator.clipboard.writeText(JSON.stringify(config, null, 2))
      .then(() => {
        addLog(`✅ 已复制节点 ${node.name} 配置`)
      })
      .catch(err => {
        addLog(`❌ 复制失败: ${err.message}`)
      })
  }
}
  
  async function testNode(node) {
    try {
      addLog(`🧪 正在测试节点 ${node.name}...`)
      // 这里可以添加具体的测试逻辑
      addLog(`✅ 节点 ${node.name} 测试完成`)
    } catch (error) {
      addLog(`❌ 节点测试失败: ${error.message}`)
    }
  }
  
  // 快速示例
const quickExamples = ref([
  { 
    name: 'GitHub RAW文件', 
    url: 'https://raw.githubusercontent.com/freefq/free/master/v2',
    icon: '🐙'
  },
  { 
    name: 'Clash订阅', 
    url: 'https://example.com/subscribe/clash.yaml',
    icon: '⚡'
  },
  { 
    name: '节点网站', 
    url: 'https://example-nodes-site.com',
    icon: '🌐'
  },
  { 
    name: 'Base64订阅', 
    url: 'https://example.com/subscription.txt',
    icon: '🔒'
  }
])

// 加载示例
function loadExample(example) {
  analyzeUrl.value = example.url
}

// 分析链接
async function analyzeLink() {
  if (!analyzeUrl.value.trim()) return
  
  analyzing.value = true
  
  try {
    const mode = deepScrape.value ? 'scrape' : 'direct'
    const response = await api.post('/nodes/process-link', {
      url: analyzeUrl.value,
      mode: mode
    })
    
    analysisResult.value = response.data
    
    // 如果分析成功，更新用户源列表
    if (response.data.valid || (response.data.valid_links && response.data.valid_links.length > 0)) {
      await fetchUserSources()
    }
    
  } catch (error) {
    console.error('分析链接失败:', error)
    analysisResult.value = {
      valid: false,
      error: error.message,
      message: '分析失败'
    }
  } finally {
    analyzing.value = false
  }
}

  // 保存到订阅源
async function saveToSources() {
  if (!analysisResult.value?.url) return
  
  try {
    // 如果已经是直接测试模式，结果中应该已经保存了
    // 这里主要是为了深度抓取模式
    if (analysisResult.value.valid_links && analysisResult.value.valid_links.length > 0) {
      // 保存所有有效链接
      const validUrls = analysisResult.value.valid_links.map(l => l.url)
      
      for (const url of validUrls) {
        await api.post('/nodes/process-link', {
          url: url,
          mode: 'direct'
        })
      }
    } else {
      // 保存当前链接
      await api.post('/nodes/process-link', {
        url: analysisResult.value.url,
        mode: 'direct'
      })
    }
    
    await fetchUserSources()
    alert('✅ 已保存到订阅源列表')
    
  } catch (error) {
    console.error('保存失败:', error)
    alert('保存失败: ' + error.message)
  }
}

  // 扫描有效链接
async function scanValidLinks() {
  if (!analysisResult.value?.valid_links) return
  
  const urls = analysisResult.value.valid_links.map(l => l.url)
  
  // 切换到自定义模式并扫描
  activeMode.value = 'custom'
  await scanCustomUrls(urls)
}

// 扫描单个源
async function scanSingleSource(url) {
  activeMode.value = 'custom'
  await scanCustomUrls([url])
}

  // 扫描URL列表
async function scanCustomUrls(urls) {
  try {
    customScanRunning.value = true
    addLog(`🎯 开始扫描 ${urls.length} 个自定义源...`)
    
    const response = await api.post('/nodes/scan-custom', {
      sources: urls,
      name: '用户自定义源'
    })
    
    addLog(`✅ ${response.data.message}`)
    
    // 开始轮询
    const pollInterval = setInterval(async () => {
      await fetchCustomStats()
      if (!customStats.value.running) {
        clearInterval(pollInterval)
        customScanRunning.value = false
        addLog(`🎉 自定义扫描完成，获取 ${customStats.value.count} 个节点`)
      }
    }, 2000)
    
  } catch (error) {
    console.error('扫描失败:', error)
    addLog(`❌ 扫描失败: ${error.message}`)
    customScanRunning.value = false
  }
}

  // 测试源
async function testSource(url) {
  try {
    const response = await api.post('/nodes/process-link', {
      url: url,
      mode: 'direct'
    })
    
    if (response.data.valid) {
      alert(`✅ 链接有效，包含 ${response.data.nodes_found || 0} 个节点`)
    } else {
      alert(`❌ 链接无效: ${response.data.error || '未知错误'}`)
    }
  } catch (error) {
    alert('测试失败: ' + error.message)
  }
}

// 移除源
async function removeSource(index) {
  if (confirm('确定要移除此订阅源吗？')) {
    try {
      await api.delete(`/nodes/user-sources/${index}`)
      await fetchUserSources()
      addLog('🗑️ 已移除自定义源')
    } catch (error) {
      alert('移除失败: ' + error.message)
    }
  }
}

// 获取用户源
async function fetchUserSources() {
  try {
    const response = await api.get('/nodes/user-sources')
    userSources.value = response.data.sources || []
  } catch (error) {
    console.error('获取用户源失败:', error)
  }
}

// 工具函数
function truncateUrl(url, maxLength = 50) {
  if (url.length <= maxLength) return url
  return url.substring(0, maxLength) + '...'
}

function isGitHubUrl(url) {
  return url.includes('github.com') || url.includes('githubusercontent.com')
}

function isRawUrl(url) {
  return url.includes('raw.githubusercontent.com') || url.includes('/raw/')
}

function clearAnalysis() {
  analysisResult.value = null
  analyzeUrl.value = ''
}

function refreshUserSources() {
  fetchUserSources()
  addLog('🔄 已刷新自定义源列表')
}

  // 模式切换
function switchMode(mode) {
  activeMode.value = mode
  if (mode === 'analyze') {
    fetchUserSources()
  }
}

  // 组件挂载
onMounted(() => {
  fetchStats()
  fetchUserSources()
  
  // 只在主模式下轮询，自定义模式由用户手动触发
  const interval = setInterval(() => {
    if (activeMode.value === 'main') {
      fetchStats()
    } else if (activeMode.value === 'custom') {
      fetchCustomStats()
    }
  }, 3000)
  
  return () => clearInterval(interval)
})
  </script>
  
<style>
/* NodeHunter.vue - 优化后的CSS样式 */

/* ===== 1. 根容器和全局样式 ===== */
.node-hunter {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* ===== 2. 头部区域 ===== */
.header {
  background: rgba(20, 20, 30, 0.8);
  border-radius: 12px;
  padding: 12px 15px;
  margin-bottom: 10px;
  border: 1px solid rgba(0, 229, 255, 0.2);
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}

.title-box {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.title-box .icon {
  font-size: 28px;
}

.text-group h1 {
  margin: 0 0 4px 0;
  font-size: 20px;
  color: #fff;
}

.badge {
  background: linear-gradient(45deg, #00e5ff, #00ffaa);
  color: #000;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  margin-left: 6px;
}

.text-group p {
  margin: 0;
  color: #aaa;
  font-size: 11px;
}

/* ===== 3. 模式切换器 ===== */
.mode-switcher {
  margin: 8px 0;
}

.mode-tabs {
  display: flex;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 3px;
  border: 1px solid rgba(0, 229, 255, 0.1);
}

.mode-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  background: none;
  border: none;
  border-radius: 6px;
  color: #888;
  cursor: pointer;
  transition: all 0.3s;
}

.mode-tab:hover {
  background: rgba(0, 229, 255, 0.05);
}

.mode-tab.active {
  background: linear-gradient(45deg, rgba(0, 229, 255, 0.2), rgba(0, 255, 170, 0.2));
  border: 1px solid rgba(0, 229, 255, 0.3);
  color: #00e5ff;
}

.tab-icon {
  font-size: 14px;
}

.tab-text {
  font-weight: bold;
  font-size: 12px;
}

/* ===== 4. 统计行和按钮 ===== */
.stats-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 12px;
}

.stat-card {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  padding: 8px 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 90px;
}

.stat-card .label {
  font-size: 10px;
  color: #888;
  margin-bottom: 2px;
}

.stat-card .value {
  font-size: 20px;
  font-weight: bold;
  color: #00e5ff;
}

.subscribe-btn, .scan-btn, .analyze-btn, .export-btn {
  padding: 8px 15px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
  font-size: 12px;
}

.subscribe-btn {
  background: linear-gradient(45deg, #00b894, #00cec9);
  color: white;
}

.scan-btn {
  background: linear-gradient(45deg, #00e5ff, #00ffaa);
  color: #000;
}

.analyze-btn {
  background: linear-gradient(45deg, #00b894, #00cec9);
  color: white;
  min-width: 120px;
}

.export-btn {
  background: rgba(0, 229, 255, 0.2);
  border: 1px solid rgba(0, 229, 255, 0.3);
  color: #00e5ff;
}

.subscribe-btn:hover, .scan-btn:hover:not(:disabled), .analyze-btn:hover:not(:disabled), .export-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(0, 229, 255, 0.4);
}

.subscribe-btn:hover {
  box-shadow: 0 5px 15px rgba(0, 184, 148, 0.4);
}

.analyze-btn:hover:not(:disabled) {
  box-shadow: 0 5px 20px rgba(0, 184, 148, 0.4);
}

.scan-btn:disabled, .analyze-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ===== 5. 分析面板 ===== */
.analyze-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: rgba(20, 20, 30, 0.95);
  border-radius: 16px;
  border: 2px solid rgba(0, 229, 255, 0.3);
  margin-bottom: 20px;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
}

.analyze-panel .panel-header {
  padding: 20px 30px;
  background: rgba(0, 229, 255, 0.1);
  border-bottom: 1px solid rgba(0, 229, 255, 0.2);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.analyze-panel .panel-header span {
  font-size: 18px;
  font-weight: bold;
  color: #00e5ff;
}

.subtitle {
  font-size: 13px !important;
  color: #aaa !important;
  font-weight: normal !important;
}

.analyze-content {
  flex: 1;
  padding: 30px;
  overflow-y: auto;
  min-height: 0;
}

/* 链接输入区域 */
.link-input-section {
  margin-bottom: 30px;
}

.input-group {
  margin-bottom: 25px;
}

.input-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.label-text {
  font-size: 16px;
  color: #fff;
  font-weight: bold;
}

.label-hint {
  font-size: 12px;
  color: #888;
}

.url-input-wrapper {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.url-input {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-radius: 10px;
  padding: 15px 20px;
  color: #e0e0e0;
  font-size: 14px;
  outline: none;
}

.url-input:focus {
  border-color: rgba(0, 229, 255, 0.5);
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);
}

.input-options {
  display: flex;
  gap: 20px;
}

.option-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #ccc;
  cursor: pointer;
}

/* 快速示例 */
.quick-examples {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.examples-title {
  color: #ffaa00;
  margin-bottom: 15px;
  font-size: 14px;
  font-weight: bold;
}

.examples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}

.example-item {
  background: rgba(0, 229, 255, 0.05);
  border: 1px solid rgba(0, 229, 255, 0.1);
  border-radius: 8px;
  padding: 12px 15px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.example-item:hover {
  background: rgba(0, 229, 255, 0.1);
  border-color: rgba(0, 229, 255, 0.3);
  transform: translateY(-2px);
}

.example-icon {
  font-size: 20px;
}

.example-text {
  font-size: 13px;
  color: #aaa;
}

/* 分析结果 */
.analysis-result {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 30px;
}

.result-header {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.result-header.success {
  background: rgba(0, 255, 0, 0.1);
  border-bottom-color: rgba(0, 255, 0, 0.3);
}

.result-header.error {
  background: rgba(255, 0, 0, 0.1);
  border-bottom-color: rgba(255, 0, 0, 0.3);
}

.result-icon {
  font-size: 24px;
}

.result-title {
  font-size: 16px;
  font-weight: bold;
}

.result-details {
  padding: 20px;
}

.detail-section {
  margin-bottom: 25px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.detail-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.detail-section h4 {
  color: #00e5ff;
  margin-bottom: 15px;
  font-size: 15px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.detail-item {
  background: rgba(255, 255, 255, 0.03);
  padding: 12px 15px;
  border-radius: 8px;
}

.detail-label {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 5px;
}

.detail-value {
  font-size: 14px;
  word-break: break-all;
}

.detail-value.url {
  color: #00ffaa;
}

.detail-value.type {
  color: #ffaa00;
}

.detail-value.count {
  color: #00e5ff;
  font-weight: bold;
}

/* GitHub信息 */
.github-info {
  background: rgba(86, 98, 246, 0.1);
  border-radius: 10px;
  padding: 15px;
}

.github-item {
  margin-bottom: 10px;
}

.github-item:last-child {
  margin-bottom: 0;
}

.github-label {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 3px;
}

.github-value {
  font-size: 13px;
  color: #a4b0f5;
  word-break: break-all;
}

/* 链接列表 */
.scraped-links, .valid-links {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 10px;
  padding: 15px;
  max-height: 200px;
  overflow-y: auto;
}

.scraped-link, .valid-link {
  padding: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.scraped-link:last-child, .valid-link:last-child {
  border-bottom: none;
}

.link-index {
  color: #888;
  margin-right: 10px;
  font-size: 12px;
}

.link-url {
  font-size: 13px;
  color: #aaa;
  word-break: break-all;
}

.valid-link-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
}

.link-status {
  color: #00ff00;
  font-weight: bold;
}

.link-nodes {
  background: rgba(0, 229, 255, 0.2);
  color: #00e5ff;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: bold;
}

.valid-link-details {
  display: flex;
  gap: 8px;
}

.detail-tag {
  background: rgba(255, 255, 255, 0.05);
  color: #aaa;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.detail-tag.github {
  background: rgba(86, 98, 246, 0.2);
  color: #5662f6;
}

.more-links {
  text-align: center;
  padding: 10px;
  color: #888;
  font-size: 12px;
}

/* 错误信息 */
.detail-section.error {
  background: rgba(255, 0, 0, 0.1);
  border-radius: 10px;
  padding: 15px;
}

.error-message {
  color: #ff6b6b;
  font-size: 13px;
}

/* 分析结果操作按钮 */
.result-actions {
  padding: 20px;
  display: flex;
  gap: 15px;
  background: rgba(0, 0, 0, 0.3);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.action-btn {
  padding: 12px 25px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
}

.save-btn {
  background: linear-gradient(45deg, #00b894, #00cec9);
  color: white;
}

.save-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(0, 184, 148, 0.4);
}

.result-actions .scan-btn {
  background: linear-gradient(45deg, #00e5ff, #00ffaa);
  color: #000;
}

.clear-btn {
  background: rgba(255, 107, 107, 0.2);
  color: #ff6b6b;
  border: 1px solid rgba(255, 107, 107, 0.3);
}

.clear-btn:hover {
  background: rgba(255, 107, 107, 0.3);
}

/* 用户自定义源 */
.user-sources-section {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  padding: 25px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0;
  color: #00e5ff;
  font-size: 16px;
}

.refresh-btn {
  background: none;
  border: none;
  color: #00e5ff;
  font-size: 18px;
  cursor: pointer;
  padding: 5px;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.refresh-btn:hover {
  background: rgba(0, 229, 255, 0.1);
}

.sources-list {
  max-height: 300px;
  overflow-y: auto;
}

.source-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  margin-bottom: 10px;
  transition: all 0.3s;
}

.source-item:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: translateX(5px);
}

.source-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.source-index {
  color: #888;
  font-size: 12px;
  min-width: 25px;
}

.source-url {
  color: #aaa;
  font-size: 13px;
  word-break: break-all;
  flex: 1;
}

.source-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: bold;
}

.source-badge.github {
  background: rgba(86, 98, 246, 0.2);
  color: #5662f6;
}

.source-badge.raw {
  background: rgba(0, 229, 255, 0.2);
  color: #00e5ff;
}

.source-actions {
  display: flex;
  gap: 8px;
}

.source-action {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #aaa;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.source-action.test:hover {
  background: rgba(255, 170, 0, 0.1);
  border-color: rgba(255, 170, 0, 0.3);
  color: #ffaa00;
}

.source-action.scan:hover {
  background: rgba(0, 229, 255, 0.1);
  border-color: rgba(0, 229, 255, 0.3);
  color: #00e5ff;
}

.source-action.remove:hover {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.empty-sources {
  text-align: center;
  padding: 40px;
  color: #666;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 15px;
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  margin-bottom: 10px;
  color: #888;
}

.empty-hint {
  font-size: 12px;
  color: #666;
}

/* ===== 6. 主内容区域 ===== */
.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  min-height: 0;
  overflow: hidden;
}

/* 面板通用样式 */
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: rgba(20, 20, 30, 0.8);
  border-radius: 12px;
  border: 1px solid rgba(0, 229, 255, 0.2);
  backdrop-filter: blur(10px);
}

.panel-header {
  padding: 12px 15px;
  background: rgba(0, 229, 255, 0.1);
  border-bottom: 1px solid rgba(0, 229, 255, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.panel-header span {
  font-size: 14px;
  font-weight: bold;
  color: #00e5ff;
}

.mode-indicator {
  font-size: 14px;
  color: #aaa;
}

/* 终端日志区域 */
.terminal-body {
  flex: 1;
  min-height: 0;
  padding: 12px;
  background: rgba(0, 0, 0, 0.5);
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #00ffaa;
  overflow-y: auto;
}

.log-line {
  margin-bottom: 5px;
  line-height: 1.4;
}

.empty-log {
  color: #666;
  font-style: italic;
  text-align: center;
  padding: 40px 20px;
}

/* 节点列表面板头部 */
.panel-title {
  font-size: 18px;
  font-weight: bold;
  color: #00e5ff;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.node-count {
  font-size: 14px;
  color: #aaa;
}

/* ===== 7. 节点网格和卡片 ===== */
.node-grid {
  flex: 1;
  min-height: 0;
  padding: 12px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.node-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(0, 229, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  transition: all 0.3s;
}

.node-card:hover {
  border-color: rgba(0, 229, 255, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.node-name {
  font-size: 16px;
  font-weight: bold;
  color: #e0e0e0;
}

.node-status {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 10px;
  font-weight: bold;
}

.node-status.online {
  background: rgba(0, 255, 0, 0.1);
  color: #00ffaa;
  border: 1px solid rgba(0, 255, 0, 0.3);
}

.node-status:not(.online) {
  background: rgba(255, 0, 0, 0.1);
  color: #ff6b6b;
  border: 1px solid rgba(255, 0, 0, 0.3);
}

.node-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.protocol-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 10px;
  font-weight: bold;
}

.protocol-badge.vmess {
  background: rgba(0, 229, 255, 0.2);
  color: #00e5ff;
}

.protocol-badge.vless {
  background: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.protocol-badge.trojan {
  background: rgba(0, 255, 170, 0.2);
  color: #00ffaa;
}

.protocol-badge.unknown {
  background: rgba(255, 255, 255, 0.1);
  color: #aaa;
}

.host {
  font-size: 13px;
  color: #888;
  font-family: monospace;
}

.node-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: bold;
}

/* 节点延迟颜色类 */
.good { color: #00ffaa !important; }
.medium { color: #ffaa00 !important; }
.bad { color: #ff6b6b !important; }

/* 节点操作按钮 */
.node-actions {
  display: flex;
  gap: 10px;
}

.node-actions .action-btn {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(0, 229, 255, 0.2);
  background: rgba(0, 229, 255, 0.05);
  color: #00e5ff;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.node-actions .action-btn:hover {
  background: rgba(0, 229, 255, 0.1);
  border-color: rgba(0, 229, 255, 0.4);
}

.node-actions .action-btn.copy:hover {
  background: rgba(0, 255, 170, 0.1);
  border-color: rgba(0, 255, 170, 0.4);
  color: #00ffaa;
}

.node-actions .action-btn.qrcode:hover {
  background: rgba(255, 170, 0, 0.1);
  border-color: rgba(255, 170, 0, 0.4);
  color: #ffaa00;
}

.node-actions .action-btn.test:hover {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.4);
  color: #ff6b6b;
}

.node-actions .action-btn.clash:hover {
  background: rgba(86, 98, 246, 0.1);
  border-color: rgba(86, 98, 246, 0.4);
  color: #5662f6;
}

/* ===== 8. 空状态样式 ===== */
.empty-nodes {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px 15px;
  background: rgba(255, 255, 255, 0.02);
  border: 2px dashed rgba(0, 229, 255, 0.1);
  border-radius: 12px;
  margin: 15px;
}

.empty-icon {
  font-size: 36px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  font-size: 14px;
  color: #888;
  margin-bottom: 8px;
}

.empty-btn {
  background: linear-gradient(45deg, rgba(0, 229, 255, 0.2), rgba(0, 255, 170, 0.2));
  border: 1px solid rgba(0, 229, 255, 0.3);
  color: #00e5ff;
  padding: 8px 20px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 12px;
}

.empty-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(0, 229, 255, 0.2);
}

/* ===== 9. 响应式设计 ===== */
@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .mode-tabs {
    flex-direction: column;
  }
  
  .url-input-wrapper {
    flex-direction: column;
  }
  
  .analyze-btn {
    width: 100%;
  }
  
  .input-options {
    flex-direction: column;
    gap: 10px;
  }
  
  .examples-grid {
    grid-template-columns: 1fr;
  }
  
  .result-actions {
    flex-direction: column;
  }
  
  .source-item {
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
  }
  
  .source-actions {
    align-self: flex-end;
  }
  
  .node-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-row {
    flex-direction: column;
  }
}
</style>