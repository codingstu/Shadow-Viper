<template>
  <div class="sync-button-container">
    <!-- 同步到 Supabase 按钮 -->
    <button
      @click="handleSync"
      :class="['sync-btn', { 'is-syncing': isSyncing, 'is-success': lastSyncSuccess }]"
      :disabled="isSyncing"
      :title="isSyncing ? '正在同步...' : '点击同步数据到 Supabase'"
    >
      <span class="sync-icon" v-if="isSyncing">⏳</span>
      <span class="sync-icon" v-else-if="lastSyncSuccess">✅</span>
      <span class="sync-icon" v-else>📤</span>
      {{ buttonText }}
    </button>

    <!-- 同步状态提示 -->
    <div v-if="lastSyncStatus" :class="['sync-status', lastSyncSuccess ? 'success' : 'error']">
      {{ lastSyncStatus }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const isSyncing = ref(false)
const lastSyncSuccess = ref(false)
const lastSyncStatus = ref('')
const syncCount = ref(0)

const buttonText = computed(() => {
  if (isSyncing.value) return '正在同步...'
  if (lastSyncSuccess.value) return '✅ 已同步'
  return '📤 同步到 Supabase'
})

const handleSync = async () => {
  if (isSyncing.value) return

  isSyncing.value = true
  lastSyncStatus.value = '正在同步数据...'
  lastSyncSuccess.value = false

  try {
    const response = await fetch('/api/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()

    if (data.success) {
      lastSyncSuccess.value = true
      syncCount.value++
      lastSyncStatus.value = `✅ 数据同步成功！(${new Date().toLocaleTimeString()})`
      
      // 3 秒后清除成功状态
      setTimeout(() => {
        lastSyncStatus.value = ''
        lastSyncSuccess.value = false
      }, 3000)
    } else {
      lastSyncSuccess.value = false
      lastSyncStatus.value = `❌ 同步失败: ${data.message}`
    }
  } catch (error) {
    lastSyncSuccess.value = false
    lastSyncStatus.value = `❌ 请求失败: ${error.message}`
  } finally {
    isSyncing.value = false
  }
}
</script>

<style scoped>
.sync-button-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.sync-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.sync-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4);
}

.sync-btn:active:not(:disabled) {
  transform: translateY(0);
}

.sync-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.sync-btn.is-syncing {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  animation: pulse 1.5s ease-in-out infinite;
}

.sync-btn.is-success {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.sync-icon {
  font-size: 16px;
  display: inline-block;
}

.sync-status {
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 4px;
  white-space: nowrap;
  min-height: 24px;
  display: flex;
  align-items: center;
}

.sync-status.success {
  background-color: rgba(76, 175, 80, 0.1);
  color: #4caf50;
}

.sync-status.error {
  background-color: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}
</style>
